from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.conversation.session_evidence import SessionEvidenceService


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": not evaluable,
        "overall_result": "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "main_capability_not_passed",
            "issue_text": "证据不足，当前无法评估。",
            "recovery_rule": "请先完成至少一轮有效互动后再结束。",
        },
        "next_goal": {
            "goal_type": "main_capability_focus",
            "goal_text": "先完成一轮有效互动再评估。",
            "rule": "补齐用户表达和AI回应后再结束。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


class TestSessionEvidenceService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return SessionEvidenceService(mock_db)

    @pytest.fixture
    def sample_session_id(self) -> str:
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_projection_normalizes_legacy_scores_and_logs_projection_completeness(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=81.0,
            accuracy_score=84.0,
            completeness_score=78.0,
            total_duration_seconds=135,
            start_time=datetime.now(UTC) - timedelta(seconds=135),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=_make_effectiveness_snapshot(
                evaluable=True,
                reason=None,
            ),
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="您好，我想先了解下贵司目前怎么做客户回访。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1500,
                fuzzy_words=None,
                transcript_metadata={"source": "legacy"},
                sales_stage="opening",
                score_snapshot={"overall": 72, "dimension_scores": {"沟通技巧": 70}},
                ai_feedback="先确认客户背景",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
            SimpleNamespace(
                id="msg-2",
                session_id=sample_session_id,
                turn_number=2,
                role="assistant",
                content="目前主要靠人工跟进，信息容易丢失。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={"overall_score": 86, "dimension_scores": {"沟通技巧": 84}},
                ai_feedback="继续追问影响范围",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        with patch("common.conversation.session_evidence.logger") as logger:
            result = await service.get_projection(
                session_id=sample_session_id,
                require_completed=True,
            )

        assert result.is_success
        projection = result.value
        assert projection.session_id == sample_session_id
        assert projection.overall_score == pytest.approx(81.0)
        assert projection.messages[0]["score_snapshot"]["overall_score"] == 72.0
        assert "overall" not in projection.messages[0]["score_snapshot"]
        assert projection.stage_summary == [
            {"stage": "opening", "duration_ms": 1500, "score": 72},
            {"stage": "discovery", "duration_ms": 1800, "score": 86},
        ]
        assert projection.evaluable is True
        assert projection.not_evaluable_reason is None
        assert projection.evidence_completeness["message_count"] == 2
        assert projection.evidence_completeness["legacy_score_key_used"] is True
        assert projection.evidence_completeness["complete"] is True

        logger.info.assert_called_once()
        call = logger.info.call_args
        assert call.args[0] == "practice_session_evidence_projection_built"
        assert call.kwargs["session_id"] == sample_session_id
        assert call.kwargs["message_count"] == 2
        assert call.kwargs["legacy_score_key_used"] is True
        assert call.kwargs["projection_complete"] is True

    @pytest.mark.asyncio
    async def test_get_projection_falls_back_to_latest_message_scores_when_session_scores_missing(
        self,
        service: SessionEvidenceService,
        mock_db: AsyncMock,
        sample_session_id: str,
    ) -> None:
        session = SimpleNamespace(
            session_id=sample_session_id,
            status="completed",
            logic_score=None,
            accuracy_score=None,
            completeness_score=None,
            total_duration_seconds=96,
            start_time=datetime.now(UTC) - timedelta(seconds=96),
            end_time=datetime.now(UTC),
            effectiveness_snapshot=None,
            voice_policy_snapshot=None,
        )
        messages = [
            SimpleNamespace(
                id="msg-1",
                session_id=sample_session_id,
                turn_number=1,
                role="user",
                content="我们预算其实卡得比较紧。",
                audio_url=None,
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                fuzzy_words=None,
                transcript_metadata=None,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 89,
                    "dimension_scores": {
                        "professional": 88,
                        "communication": 82,
                        "discovery": 76,
                    },
                },
                ai_feedback="继续确认预算审批链路",
                is_highlight=False,
                highlight_type=None,
                highlight_reason=None,
            ),
        ]

        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = messages
        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        result = await service.get_projection(
            session_id=sample_session_id,
            require_completed=True,
        )

        assert result.is_success
        projection = result.value
        assert projection.logic_score == pytest.approx(88.0)
        assert projection.accuracy_score == pytest.approx(82.0)
        assert projection.completeness_score == pytest.approx(76.0)
        assert projection.overall_score == pytest.approx(82.0)
        assert projection.evaluable is True
        assert projection.not_evaluable_reason is None
        assert projection.evidence_completeness["session_scores"] is False
        assert projection.evidence_completeness["message_scores"] == 1
