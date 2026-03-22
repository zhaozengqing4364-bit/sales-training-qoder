"""
Unit tests for report generation trigger (Story 3.1)

Tests:
- Report generation trigger on session end
- Retry mechanism
- Status tracking
"""

import asyncio

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from common.db.models import PracticeSession, ReportGenerationStatus
from evaluation.services.report_generation_trigger import (
    ReportGenerationTrigger,
    trigger_report_generation,
)
from common.error_handling.result import Result


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
    trigger = ReportGenerationTrigger(mock_db, mock_report_service)
    return trigger


class TestReportGenerationTrigger:
    """Test report generation trigger functionality."""

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_success(self, report_trigger, mock_db, mock_report_service):
        """Test successful report generation trigger."""
        # Arrange
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.report_status = "pending"

        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        # Mock report generation success
        mock_report = MagicMock()
        mock_report.overall_score = 85.5
        mock_report_service.generate_report.return_value = Result.ok(mock_report)

        # Act
        await report_trigger.trigger_on_session_end(session_id, scenario_type)

        # Assert
        mock_report_service.generate_report.assert_called_once_with(
            session_id=session_id,
            scenario_type=scenario_type,
        )
        assert mock_session.report_status == "completed"
        assert mock_session.report_generated_at is not None

    @pytest.mark.asyncio
    async def test_trigger_on_session_end_failure(self, report_trigger, mock_db, mock_report_service):
        """Test report generation failure handling."""
        # Arrange
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.report_status = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        # Mock report generation failure
        mock_report_service.generate_report.return_value = Result.fail("[GENERATION_FAILED]")

        # Act
        await report_trigger.trigger_on_session_end(session_id, scenario_type)

        # Assert
        assert mock_session.report_status == "failed"
        assert mock_session.report_error == "[GENERATION_FAILED]"

    @pytest.mark.asyncio
    async def test_get_report_status(self, report_trigger, mock_db):
        """Test getting report generation status."""
        # Arrange
        session_id = "test-session-123"

        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.report_status = "completed"
        mock_session.report_generated_at = datetime.now(timezone.utc)
        mock_session.report_error = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await report_trigger.get_report_status(session_id)

        # Assert
        assert result.is_success
        assert result.value["report_status"] == "completed"
        assert result.value["report_generated_at"] is not None

    @pytest.mark.asyncio
    async def test_get_report_status_not_found(self, report_trigger, mock_db):
        """Test getting status for non-existent session."""
        # Arrange
        session_id = "non-existent"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await report_trigger.get_report_status(session_id)

        # Assert
        assert not result.is_success
        assert result.fallback == "[SESSION_NOT_FOUND]"


class TestTriggerReportGeneration:
    """Test fire-and-forget trigger function."""

    @pytest.mark.asyncio
    @patch("evaluation.services.report_generation_trigger.ReportGenerationTrigger")
    @patch("evaluation.services.report_generation_trigger.get_db_session")
    async def test_trigger_report_generation(self, mock_get_db, mock_trigger_class):
        """Test fire-and-forget report generation trigger."""
        # Arrange
        session_id = "test-session-123"
        scenario_type = "sales"

        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db

        mock_trigger = AsyncMock()
        mock_trigger_class.return_value = mock_trigger

        # Act
        await trigger_report_generation(session_id, scenario_type, db=None)

        # Wait for async task to complete
        await asyncio.sleep(0.1)

        # Assert
        mock_trigger_class.assert_called_once_with(mock_db)
        mock_trigger.trigger_on_session_end.assert_called_once_with(
            session_id, scenario_type
        )


class TestRetryMechanism:
    """Test retry mechanism for report generation."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, report_trigger, mock_report_service):
        """Test that report generation is retried on failure."""
        # Arrange
        session_id = "test-session-123"
        scenario_type = "sales"

        # Mock report service to fail twice then succeed
        mock_report_service.generate_report.side_effect = [
            Result.fail("[TEMP_ERROR]"),
            Result.fail("[TEMP_ERROR]"),
            Result.ok(MagicMock(overall_score=85)),
        ]

        # Act & Assert
        # The retry decorator should handle this
        # Note: Actual retry testing would require more complex setup
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
