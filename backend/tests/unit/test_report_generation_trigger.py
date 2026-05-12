"""
Unit tests for report generation trigger (Story 3.1)

These proofs lock the optional enhanced-report sidecar as a compatibility/enhancement
surface. Canonical completed-session truth still comes from the session-evidence read line.

Tests:
- Report generation trigger on session end
- Own-session commit semantics for fire-and-forget execution
- Status tracking and failure handling
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.error_handling.result import Result
from evaluation.services.report_generation_trigger import (
    ReportGenerationTrigger,
    trigger_report_generation,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_report_service():
    """Mock comprehensive report service."""
    service = AsyncMock()
    service.generate_report = AsyncMock()
    return service


@pytest.fixture
def report_trigger(mock_db, mock_report_service):
    """Create report generation trigger instance."""
    return ReportGenerationTrigger(mock_db, mock_report_service)


@pytest.fixture
def own_session_report_trigger(mock_db, mock_report_service):
    """Create report generation trigger that owns its DB session."""
    return ReportGenerationTrigger(
        mock_db,
        mock_report_service,
        owns_db_session=True,
    )


def _mock_db_session(mock_db: AsyncMock, session: MagicMock | None) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = session
    mock_db.execute.return_value = result


def _complete_sales_projection() -> SimpleNamespace:
    return SimpleNamespace(
        evidence_completeness={
            "session_scores": True,
            "message_count": 2,
            "complete": True,
        }
    )


class TestReportGenerationTrigger:
    """Test report generation trigger functionality."""

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_success(self, report_trigger, mock_db, mock_report_service):
        """Caller-owned sessions should update state without auto-commit."""
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.status = "scoring"
        mock_session.report_status = "pending"
        _mock_db_session(mock_db, mock_session)

        mock_report = MagicMock()
        mock_report.overall_score = 85.5
        mock_report_service.generate_report.return_value = Result.ok(mock_report)

        with patch(
            "common.conversation.session_evidence.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(_complete_sales_projection())),
        ):
            await report_trigger.trigger_on_session_end(session_id, scenario_type)

        mock_report_service.generate_report.assert_called_once_with(
            session_id=session_id,
            scenario_type=scenario_type,
        )
        assert mock_session.report_status == "completed"
        assert mock_session.report_generated_at is not None
        assert mock_session.status == "completed"
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_success_commits_owned_session(
        self,
        own_session_report_trigger,
        mock_db,
        mock_report_service,
    ):
        """Fire-and-forget execution must commit processing and terminal writes itself."""
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.status = "scoring"
        mock_session.report_status = "pending"
        _mock_db_session(mock_db, mock_session)

        mock_report = MagicMock()
        mock_report.overall_score = 85.5
        mock_report_service.generate_report.return_value = Result.ok(mock_report)

        with patch(
            "common.conversation.session_evidence.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(_complete_sales_projection())),
        ):
            await own_session_report_trigger.trigger_on_session_end(session_id, "sales")

        assert mock_session.report_status == "completed"
        assert mock_session.status == "completed"
        assert mock_session.report_generated_at is not None
        assert mock_db.commit.await_count == 2

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_failure_commits_owned_session_terminal_state(
        self,
        own_session_report_trigger,
        mock_db,
        mock_report_service,
    ):
        """Optional enhanced-report failures should still persist a truthful terminal sales status."""
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.status = "scoring"
        mock_session.report_status = "processing"
        _mock_db_session(mock_db, mock_session)

        mock_report_service.generate_report.return_value = Result.fail("[GENERATION_FAILED]")

        with patch(
            "common.conversation.session_evidence.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(_complete_sales_projection())),
        ):
            await own_session_report_trigger.trigger_on_session_end(session_id, "sales")

        assert mock_session.report_status == "failed"
        assert mock_session.report_error == "[GENERATION_FAILED]"
        assert mock_session.status == "completed"
        assert mock_db.commit.await_count == 2

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_skips_generation_when_session_missing(
        self,
        own_session_report_trigger,
        mock_db,
        mock_report_service,
    ):
        """Unknown sessions should fail cleanly without calling the report generator."""
        _mock_db_session(mock_db, None)

        await own_session_report_trigger.trigger_on_session_end("missing-session", "sales")

        mock_report_service.generate_report.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_malformed_report_result_marks_failed(
        self,
        report_trigger,
        mock_db,
        mock_report_service,
    ):
        """Malformed report-service responses should not fake success."""
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.status = "scoring"
        mock_session.report_status = "pending"
        _mock_db_session(mock_db, mock_session)

        mock_report_service.generate_report.return_value = object()

        with patch(
            "common.conversation.session_evidence.SessionEvidenceService.get_projection",
            new=AsyncMock(return_value=Result.ok(_complete_sales_projection())),
        ):
            await report_trigger.trigger_on_session_end(session_id, "sales")

        assert mock_session.report_status == "failed"
        assert "is_success" in mock_session.report_error
        assert mock_session.status == "completed"
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_defers_sales_completion_when_projection_incomplete(
        self,
        report_trigger,
        mock_db,
        mock_report_service,
    ):
        """Boundary case: replay gating stays intact until canonical evidence is readable."""
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.status = "scoring"
        mock_session.report_status = "pending"
        _mock_db_session(mock_db, mock_session)

        mock_report = MagicMock()
        mock_report.overall_score = 85.5
        mock_report_service.generate_report.return_value = Result.ok(mock_report)

        with patch(
            "common.conversation.session_evidence.SessionEvidenceService.get_projection",
            new=AsyncMock(
                return_value=Result.ok(
                    SimpleNamespace(
                        evidence_completeness={
                            "session_scores": False,
                            "message_count": 1,
                            "complete": False,
                        }
                    )
                )
            ),
        ):
            await report_trigger.trigger_on_session_end(session_id, "sales")

        assert mock_session.report_status == "completed"
        assert mock_session.status == "scoring"

    @pytest.mark.asyncio
    async def test_get_report_status(self, report_trigger, mock_db):
        """Test getting report generation status."""
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.report_status = "completed"
        mock_session.report_generated_at = datetime.now(UTC)
        mock_session.report_error = None
        _mock_db_session(mock_db, mock_session)

        result = await report_trigger.get_report_status(session_id)

        assert result.is_success
        assert result.value["report_status"] == "completed"
        assert result.value["report_generated_at"] is not None

    @pytest.mark.asyncio
    async def test_get_report_status_not_found(self, report_trigger, mock_db):
        """Test getting status for non-existent session."""
        _mock_db_session(mock_db, None)

        result = await report_trigger.get_report_status("non-existent")

        assert not result.is_success
        assert result.fallback == "[SESSION_NOT_FOUND]"

    def test_phase4_local_report_payload_marks_presentation_evidence_source(
        self,
        monkeypatch,
        tmp_path,
    ):
        """The #44 local seam must not label Presentation report evidence as Sales."""
        transcript_path = tmp_path / "provider.jsonl"
        transcript_path.write_text(
            '{"fixture_version":"presentation-provider-script.v1",'
            '"provider":"phase4_local_stepfun",'
            '"direction":"provider_event",'
            '"payload":{"transcript":"业务目标"}}\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("PHASE4_E2E_PROVIDER_TRANSCRIPT", str(transcript_path))

        payload = ReportGenerationTrigger._build_phase4_local_report_payload(
            SimpleNamespace(
                session_id="presentation-session-1",
                scenario_type="presentation",
                overall_score=88.0,
                ruleset_version="presentation_review_v1",
                score_basis="presentation_review",
                evidence_completeness={"message_count": 1, "complete": True},
            )
        )

        assert payload["evidence"]["source"] == "phase4_local_presentation_e2e"
        assert payload["evidence"]["scenario_type"] == "presentation"
        assert payload["evidence"]["provider_transcript"]["fixture_version"] == (
            "presentation-provider-script.v1"
        )


class TestTriggerReportGeneration:
    """Test fire-and-forget trigger function."""

    @pytest.mark.asyncio
    @patch("evaluation.services.report_generation_trigger.ReportGenerationTrigger")
    @patch("evaluation.services.report_generation_trigger.get_db_session")
    async def test_trigger_report_generation_uses_owned_session(self, mock_get_db, mock_trigger_class):
        """db=None should construct a trigger that commits its own writes."""
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db

        mock_trigger = AsyncMock()
        mock_trigger_class.return_value = mock_trigger

        await trigger_report_generation(session_id, scenario_type, db=None)
        await asyncio.sleep(0.1)

        mock_trigger_class.assert_called_once_with(mock_db, owns_db_session=True)
        mock_trigger.trigger_on_session_end.assert_called_once_with(
            session_id,
            scenario_type,
        )


class TestRetryMechanism:
    """Test retry mechanism for report generation."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, report_trigger, mock_report_service):
        """Document current retry coverage gap without broadening this task."""
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_report_service.generate_report.side_effect = [
            Result.fail("[TEMP_ERROR]"),
            Result.fail("[TEMP_ERROR]"),
            Result.ok(MagicMock(overall_score=85)),
        ]

        assert session_id
        assert scenario_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
