"""
Unit tests for Realtime Scoring Service

Requirements: Story 2.6 - Real-time scoring updates and improvement suggestions
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from evaluation.services.realtime_scoring import (
    RealtimeScoringService,
    IncrementalScoreState,
    ScoreUpdateEvent,
)
from evaluation.services.ai_scoring import AIScoringService
from common.error_handling.result import Result


@pytest.fixture
def mock_ai_scoring():
    """Create mock AI scoring service."""
    service = Mock(spec=AIScoringService)
    service.evaluate_conversation = AsyncMock()
    return service


@pytest.fixture
def scoring_service(mock_ai_scoring):
    """Create scoring service with mock AI."""
    return RealtimeScoringService(ai_scoring_service=mock_ai_scoring)


class TestIncrementalScoreState:
    """Test incremental score state management."""

    def test_initial_state(self):
        """Test initial state creation."""
        state = IncrementalScoreState(session_id="test-session")

        assert state.session_id == "test-session"
        assert state.current_overall == 0.0
        assert state.turn_scores == []
        assert state.dimension_history == {}

    def test_first_turn_update(self):
        """Test first turn score update."""
        state = IncrementalScoreState(session_id="test-session")

        result = state.update_with_new_scores(
            turn_number=1,
            dimension_scores={"专业度": 80, "沟通技巧": 75},
            overall_score=77.5,
        )

        assert result["overall"] == 77.5
        assert result["turn_count"] == 1
        assert state.current_overall == 77.5

    def test_incremental_update_with_history(self):
        """Test incremental update with historical weighting."""
        state = IncrementalScoreState(session_id="test-session")

        # First turn
        state.update_with_new_scores(
            turn_number=1,
            dimension_scores={"专业度": 80},
            overall_score=80.0,
        )

        # Second turn with different score
        result = state.update_with_new_scores(
            turn_number=2,
            dimension_scores={"专业度": 90},
            overall_score=90.0,
        )

        # Should be weighted: 80 * 0.7 + 90 * 0.3 = 83
        assert result["overall"] == 83.0
        assert state.current_overall == 83.0

    def test_score_trend_improving(self):
        """Test trend detection for improving scores."""
        state = IncrementalScoreState(session_id="test-session")

        # Add improving scores
        for i, score in enumerate([70, 75, 80, 85]):
            state.update_with_new_scores(
                turn_number=i + 1,
                dimension_scores={"专业度": score},
                overall_score=float(score),
            )

        trend = state.get_score_trend()

        assert trend["direction"] == "improving"
        assert trend["change_rate"] > 0

    def test_score_trend_declining(self):
        """Test trend detection for declining scores."""
        state = IncrementalScoreState(session_id="test-session")

        # Add declining scores
        for i, score in enumerate([85, 80, 75, 70]):
            state.update_with_new_scores(
                turn_number=i + 1,
                dimension_scores={"专业度": score},
                overall_score=float(score),
            )

        trend = state.get_score_trend()

        assert trend["direction"] == "declining"
        assert trend["change_rate"] < 0

    def test_score_trend_stable(self):
        """Test trend detection for stable scores."""
        state = IncrementalScoreState(session_id="test-session")

        # Add stable scores
        for i, score in enumerate([75, 76, 75, 76]):
            state.update_with_new_scores(
                turn_number=i + 1,
                dimension_scores={"专业度": score},
                overall_score=float(score),
            )

        trend = state.get_score_trend()

        assert trend["direction"] == "stable"


class TestRealtimeScoringService:
    """Test realtime scoring service."""

    @pytest.mark.asyncio
    async def test_evaluate_turn_triggers_update(self, scoring_service, mock_ai_scoring):
        """Test that evaluate_turn triggers score update at right turns."""
        mock_ai_scoring.evaluate_conversation.return_value = Result.ok({
            "overall": 80,
            "dimensions": [
                {"name": "专业度", "score": 80, "weight": 0.25},
                {"name": "沟通技巧", "score": 80, "weight": 0.25},
            ],
        })

        result = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=5,  # Should trigger (>= MIN_TURNS_BEFORE_SCORE)
            conversation_history=[{"role": "user", "content": "test"}],
            stage_name="开场",
            trace_id="test-trace",
        )

        assert result.is_success
        assert result.value is not None
        assert isinstance(result.value, ScoreUpdateEvent)
        assert result.value.overall_score == 80

    @pytest.mark.asyncio
    async def test_evaluate_turn_no_trigger_early_turns(self, scoring_service, mock_ai_scoring):
        """Test that early turns don't trigger score update."""
        result = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=1,  # Too early
            conversation_history=[{"role": "user", "content": "test"}],
            stage_name="开场",
        )

        assert result.is_success
        assert result.value is None  # No update triggered
        mock_ai_scoring.evaluate_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_turn_interval_respected(self, scoring_service, mock_ai_scoring):
        """Test that score update interval is respected."""
        mock_ai_scoring.evaluate_conversation.return_value = Result.ok({
            "overall": 80,
            "dimensions": [{"name": "专业度", "score": 80, "weight": 0.25}],
        })

        # Turn 5 should trigger (first after MIN_TURNS_BEFORE_SCORE)
        result1 = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=5,
            conversation_history=[],
            stage_name="开场",
        )
        assert result1.value is not None

        # Turn 6 should NOT trigger (interval = 3)
        result2 = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=6,
            conversation_history=[],
            stage_name="开场",
        )
        assert result2.value is None

        # Turn 8 should trigger again
        result3 = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=8,
            conversation_history=[],
            stage_name="开场",
        )
        assert result3.value is not None

    @pytest.mark.asyncio
    async def test_evaluate_turn_handles_failure(self, scoring_service, mock_ai_scoring):
        """Test that scoring failure is handled gracefully."""
        mock_ai_scoring.evaluate_conversation.return_value = Result.fail("[AI_ERROR]")

        result = await scoring_service.evaluate_turn(
            session_id="test-session",
            turn_number=5,
            conversation_history=[],
            stage_name="开场",
        )

        assert not result.is_success
        assert "[AI_ERROR]" in result.fallback

    @pytest.mark.asyncio
    async def test_suggestion_generation(self, scoring_service):
        """Test improvement suggestion generation."""
        suggestions = await scoring_service._generate_suggestions(
            dimension_scores={"专业度": 60, "沟通技巧": 85},
            stage_name="开场",
            score_trend={"direction": "stable", "change_rate": 0},
        )

        assert len(suggestions) > 0
        # Should have suggestion for low-scoring dimension
        assert any("专业度" in s for s in suggestions)

    def test_should_trigger_score_update(self, scoring_service):
        """Test trigger condition logic."""
        # Too early
        assert not scoring_service._should_trigger_score_update(1)
        assert not scoring_service._should_trigger_score_update(2)

        # First trigger at turn 5 (MIN_TURNS_BEFORE_SCORE + 0)
        assert scoring_service._should_trigger_score_update(5)

        # Interval = 3, so next at turn 8
        assert not scoring_service._should_trigger_score_update(6)
        assert not scoring_service._should_trigger_score_update(7)
        assert scoring_service._should_trigger_score_update(8)

    def test_clear_session_state(self, scoring_service):
        """Test session state cleanup."""
        # Create state
        state = scoring_service._get_or_create_state("test-session")
        assert "test-session" in scoring_service._score_states

        # Clear state
        scoring_service.clear_session_state("test-session")
        assert "test-session" not in scoring_service._score_states

    def test_get_session_summary(self, scoring_service):
        """Test session summary retrieval."""
        # No state yet
        summary = scoring_service.get_session_summary("test-session")
        assert summary is None

        # Create state with scores
        state = scoring_service._get_or_create_state("test-session")
        state.update_with_new_scores(
            turn_number=1,
            dimension_scores={"专业度": 80},
            overall_score=80.0,
        )

        summary = scoring_service.get_session_summary("test-session")
        assert summary is not None
        assert summary["session_id"] == "test-session"
        assert summary["final_score"] == 80.0
        assert summary["total_turns"] == 1


class TestScoreUpdateEvent:
    """Test score update event formatting."""

    def test_to_websocket_event(self):
        """Test conversion to WebSocket event format."""
        event = ScoreUpdateEvent(
            session_id="test-session",
            timestamp="2024-01-01T00:00:00Z",
            turn_count=5,
            overall_score=85.0,
            dimension_scores={"专业度": 85, "沟通技巧": 80},
            suggestions=["建议1", "建议2"],
            stage_name="需求挖掘",
            trace_id="test-trace",
        )

        ws_event = event.to_websocket_event()

        assert ws_event["type"] == "score_update"
        assert ws_event["timestamp"] == "2024-01-01T00:00:00Z"
        assert ws_event["trace_id"] == "test-trace"
        assert ws_event["data"]["session_id"] == "test-session"
        assert ws_event["data"]["overall_score"] == 85.0
        assert ws_event["data"]["stage_name"] == "需求挖掘"


class TestTrackDFIntegration:
    """Test Track D - Track F integration for report generation."""

    @pytest.mark.asyncio
    async def test_save_scoring_context_success(self):
        """Test saving scoring context to database."""
        from unittest.mock import AsyncMock, MagicMock

        # Setup service with state
        service = RealtimeScoringService()
        state = IncrementalScoreState(session_id="test-session")
        state.turn_scores = [
            {"turn": 5, "timestamp": "2024-01-01T00:00:00Z", "dimensions": {"专业度": 80}, "overall": 82.0},
            {"turn": 8, "timestamp": "2024-01-01T00:00:10Z", "dimensions": {"专业度": 85}, "overall": 85.0},
        ]
        state.current_overall = 85.0
        state.dimension_history = {"专业度": [80.0, 85.0]}
        service._score_states["test-session"] = state

        # Mock database session
        mock_db = AsyncMock()
        mock_session = MagicMock()
        mock_session.voice_policy_snapshot = {}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        # Execute
        result = await service.save_scoring_context("test-session", mock_db)

        # Assert
        assert result.is_success
        assert result.value["session_id"] == "test-session"
        assert result.value["final_score"] == 85.0
        assert result.value["total_turns"] == 2
        assert "scoring_history" in result.value
        assert "stored_at" in result.value
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_save_scoring_context_no_state(self):
        """Test saving when no scoring state exists."""
        service = RealtimeScoringService()

        result = await service.save_scoring_context("non-existent-session")

        assert not result.is_success
        assert "[SCORING_CONTEXT_NOT_FOUND]" in result.fallback

    @pytest.mark.asyncio
    async def test_save_scoring_context_no_db_session(self):
        """Test saving without database session (in-memory only)."""
        service = RealtimeScoringService()
        state = IncrementalScoreState(session_id="test-session")
        state.turn_scores = [{"turn": 5, "overall": 82.0}]
        state.current_overall = 82.0
        service._score_states["test-session"] = state

        # No db_session provided
        result = await service.save_scoring_context("test-session", None)

        # Should still succeed (in-memory only)
        assert result.is_success
        assert result.value["final_score"] == 82.0

    @pytest.mark.asyncio
    async def test_get_scoring_context_from_db_success(self):
        """Test retrieving scoring context from database."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_session = MagicMock()
        mock_session.voice_policy_snapshot = {
            "realtime_scores": {
                "session_id": "test-session",
                "final_score": 88.5,
                "dimension_scores": {"专业度": 90.0},
                "total_turns": 10,
                "trend": {"direction": "improving"},
            }
        }
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        result = await RealtimeScoringService.get_scoring_context_from_db(
            "test-session", mock_db
        )

        assert result.is_success
        assert result.value["final_score"] == 88.5
        assert result.value["trend"]["direction"] == "improving"

    @pytest.mark.asyncio
    async def test_get_scoring_context_from_db_not_found(self):
        """Test retrieving when session not found."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await RealtimeScoringService.get_scoring_context_from_db(
            "non-existent", mock_db
        )

        assert not result.is_success
        assert "[SESSION_NOT_FOUND]" in result.fallback

    @pytest.mark.asyncio
    async def test_get_scoring_context_from_db_no_data(self):
        """Test retrieving when session exists but no scoring data."""
        from unittest.mock import AsyncMock, MagicMock

        mock_db = AsyncMock()
        mock_session = MagicMock()
        mock_session.voice_policy_snapshot = {}  # No realtime_scores
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        result = await RealtimeScoringService.get_scoring_context_from_db(
            "test-session", mock_db
        )

        assert not result.is_success
        assert "[SCORING_CONTEXT_NOT_FOUND]" in result.fallback
