"""
Unit Tests for ReplayService

Tests for get_messages(), get_replay_data(), get_highlights(), and timeline generation.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.conversation.replay import ReplayService, STAGE_NAMES
from common.db.models import SessionStatus


class TestReplayService:
    """Tests for ReplayService"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession"""
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create ReplayService with mock db"""
        return ReplayService(mock_db)

    @pytest.fixture
    def sample_session_id(self):
        """Sample session ID"""
        return str(uuid.uuid4())

    @pytest.fixture
    def mock_completed_session(self, sample_session_id):
        """Create a mock completed session"""
        session = MagicMock()
        session.session_id = sample_session_id
        session.status = SessionStatus.COMPLETED.value
        session.agent_id = None
        session.persona_id = None
        return session

    @pytest.fixture
    def mock_in_progress_session(self, sample_session_id):
        """Create a mock in-progress session"""
        session = MagicMock()
        session.session_id = sample_session_id
        session.status = SessionStatus.IN_PROGRESS.value
        return session

    @pytest.fixture
    def mock_messages(self, sample_session_id):
        """Create mock conversation messages"""
        messages = []
        for i in range(3):
            msg = MagicMock()
            msg.id = str(uuid.uuid4())
            msg.session_id = sample_session_id
            msg.turn_number = i + 1
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i + 1}"
            msg.audio_url = f"https://storage.example.com/audio/msg-{i + 1}.mp3"
            msg.timestamp = datetime.utcnow()
            msg.duration_ms = 3000 + i * 500
            msg.fuzzy_words = None
            msg.sales_stage = "opening" if i == 0 else "discovery"
            msg.score_snapshot = {"overall": 70 + i * 5, "dimensions": []}
            msg.ai_feedback = None
            msg.is_highlight = False
            msg.highlight_type = None
            msg.highlight_reason = None
            messages.append(msg)
        return messages

    # ========== _check_session_completed tests ==========

    @pytest.mark.asyncio
    async def test_check_session_completed_success(self, service, mock_db, mock_completed_session):
        """Test checking a completed session succeeds"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_completed_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        assert result.value.status == SessionStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_check_session_completed_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test checking an in-progress session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    @pytest.mark.asyncio
    async def test_check_session_completed_not_found(self, service, mock_db, sample_session_id):
        """Test checking a non-existent session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await service._check_session_completed(sample_session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_FOUND]" in result.fallback

    # ========== get_messages tests ==========

    @pytest.mark.asyncio
    async def test_get_messages_success(self, service, mock_db, mock_completed_session, mock_messages):
        """Test getting messages for a completed session"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages

        mock_db.execute.side_effect = [mock_session_result, mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        messages, total = result.value
        assert len(messages) == 3
        assert total == 3

    @pytest.mark.asyncio
    async def test_get_messages_session_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test getting messages for an incomplete session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_messages(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    @pytest.mark.asyncio
    async def test_get_messages_pagination(self, service, mock_db, mock_completed_session, mock_messages):
        """Test pagination for messages"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages[:1]

        mock_db.execute.side_effect = [mock_session_result, mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages(
            mock_completed_session.session_id,
            page=2,
            page_size=10
        )

        # Assert
        assert result.is_success
        messages, total = result.value
        assert total == 100

    # ========== get_replay_data tests ==========

    @pytest.mark.asyncio
    async def test_get_replay_data_success(self, service, mock_db, mock_completed_session, mock_messages):
        """Test getting replay data for a completed session"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages

        mock_db.execute.side_effect = [mock_session_result, mock_messages_result]

        # Act
        result = await service.get_replay_data(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        data = result.value
        assert data["session_id"] == mock_completed_session.session_id
        assert len(data["messages"]) == 3
        assert "timeline_markers" in data
        assert "stage_summary" in data
        assert "total_duration_ms" in data

    @pytest.mark.asyncio
    async def test_get_replay_data_session_not_completed(self, service, mock_db, mock_in_progress_session):
        """Test getting replay data for an incomplete session fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_in_progress_session
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_replay_data(mock_in_progress_session.session_id)

        # Assert
        assert not result.is_success
        assert "[SESSION_NOT_COMPLETED]" in result.fallback

    # ========== get_highlights tests ==========

    @pytest.mark.asyncio
    async def test_get_highlights_success(self, service, mock_db, mock_completed_session):
        """Test getting highlights for a completed session"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        # Create highlighted messages
        highlight_msg = MagicMock()
        highlight_msg.id = str(uuid.uuid4())
        highlight_msg.turn_number = 2
        highlight_msg.role = "user"
        highlight_msg.content = "我们的产品大概能帮您节省30%"
        highlight_msg.timestamp = datetime.utcnow()
        highlight_msg.is_highlight = True
        highlight_msg.highlight_type = "bad"
        highlight_msg.highlight_reason = "模糊词使用"
        highlight_msg.ai_feedback = "建议使用具体数据"
        highlight_msg.fuzzy_words = [{"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}]

        mock_highlights_result = MagicMock()
        mock_highlights_result.scalars.return_value.all.return_value = [highlight_msg]

        mock_db.execute.side_effect = [mock_session_result, mock_highlights_result]

        # Act
        result = await service.get_highlights(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        highlights = result.value
        assert len(highlights) == 1
        assert highlights[0]["highlight_type"] == "bad"
        assert highlights[0]["highlight_reason"] == "模糊词使用"

    @pytest.mark.asyncio
    async def test_get_highlights_empty(self, service, mock_db, mock_completed_session):
        """Test getting highlights when none exist"""
        # Arrange
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = mock_completed_session

        mock_highlights_result = MagicMock()
        mock_highlights_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_session_result, mock_highlights_result]

        # Act
        result = await service.get_highlights(mock_completed_session.session_id)

        # Assert
        assert result.is_success
        assert len(result.value) == 0

    # ========== _generate_timeline_markers tests ==========

    def test_generate_timeline_markers_stage_changes(self, service, mock_messages):
        """Test timeline markers include stage changes"""
        # Act
        markers = service._generate_timeline_markers(mock_messages)

        # Assert
        stage_markers = [m for m in markers if m["type"] == "stage_change"]
        assert len(stage_markers) >= 1  # At least opening stage

    def test_generate_timeline_markers_fuzzy_words(self, service, sample_session_id):
        """Test timeline markers include high severity fuzzy words"""
        # Arrange
        msg = MagicMock()
        msg.id = str(uuid.uuid4())
        msg.sales_stage = "presentation"
        msg.duration_ms = 3000
        msg.is_highlight = False
        msg.fuzzy_words = [
            {"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}
        ]

        # Act
        markers = service._generate_timeline_markers([msg])

        # Assert
        fuzzy_markers = [m for m in markers if m["type"] == "fuzzy_word"]
        assert len(fuzzy_markers) == 1
        assert "大概" in fuzzy_markers[0]["label"]
        assert fuzzy_markers[0]["highlight_type"] == "bad"

    def test_generate_timeline_markers_highlights(self, service, sample_session_id):
        """Test timeline markers include highlights"""
        # Arrange
        msg = MagicMock()
        msg.id = str(uuid.uuid4())
        msg.sales_stage = "presentation"
        msg.duration_ms = 3000
        msg.is_highlight = True
        msg.highlight_type = "good"
        msg.highlight_reason = "优秀案例引用"
        msg.fuzzy_words = None

        # Act
        markers = service._generate_timeline_markers([msg])

        # Assert
        highlight_markers = [m for m in markers if m["type"] == "highlight"]
        assert len(highlight_markers) == 1
        assert highlight_markers[0]["label"] == "优秀案例引用"
        assert highlight_markers[0]["highlight_type"] == "good"

    def test_generate_timeline_markers_cumulative_time(self, service, mock_messages):
        """Test timeline markers have cumulative timestamps"""
        # Act
        markers = service._generate_timeline_markers(mock_messages)

        # Assert
        # Timestamps should be cumulative
        if len(markers) > 1:
            for i in range(1, len(markers)):
                assert markers[i]["timestamp_ms"] >= markers[i - 1]["timestamp_ms"]

    # ========== _generate_stage_summary tests ==========

    def test_generate_stage_summary(self, service, mock_messages):
        """Test stage summary generation"""
        # Act
        summary = service._generate_stage_summary(mock_messages)

        # Assert
        assert isinstance(summary, list)
        for item in summary:
            assert "stage" in item
            assert "duration_ms" in item
            assert "score" in item

    def test_generate_stage_summary_with_scores(self, service, sample_session_id):
        """Test stage summary includes average scores"""
        # Arrange
        messages = []
        for i in range(3):
            msg = MagicMock()
            msg.sales_stage = "presentation"
            msg.duration_ms = 1000
            msg.score_snapshot = {"overall": 70 + i * 10}  # 70, 80, 90
            messages.append(msg)

        # Act
        summary = service._generate_stage_summary(messages)

        # Assert
        presentation_summary = next((s for s in summary if s["stage"] == "presentation"), None)
        assert presentation_summary is not None
        assert presentation_summary["score"] == 80  # Average of 70, 80, 90

    # ========== _calculate_total_duration tests ==========

    def test_calculate_total_duration(self, service, mock_messages):
        """Test total duration calculation"""
        # Act
        total = service._calculate_total_duration(mock_messages)

        # Assert
        expected = sum(msg.duration_ms for msg in mock_messages)
        assert total == expected

    def test_calculate_total_duration_with_none(self, service):
        """Test total duration handles None values"""
        # Arrange
        msg1 = MagicMock()
        msg1.duration_ms = 1000
        msg2 = MagicMock()
        msg2.duration_ms = None
        msg3 = MagicMock()
        msg3.duration_ms = 2000

        # Act
        total = service._calculate_total_duration([msg1, msg2, msg3])

        # Assert
        assert total == 3000

    # ========== _message_to_dict tests ==========

    def test_message_to_dict(self, service, mock_messages):
        """Test message to dict conversion"""
        # Act
        result = service._message_to_dict(mock_messages[0])

        # Assert
        assert "id" in result
        assert "session_id" in result
        assert "turn_number" in result
        assert "role" in result
        assert "content" in result
        assert "audio_url" in result
        assert "timestamp" in result
        assert "duration_ms" in result
        assert "fuzzy_words" in result
        assert "sales_stage" in result
        assert "score_snapshot" in result
        assert "is_highlight" in result

    # ========== _generate_suggested_response tests ==========

    def test_generate_suggested_response_bad_highlight(self, service):
        """Test suggested response for bad highlight"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "bad"
        msg.fuzzy_words = [
            {"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}
        ]

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is not None
        assert "请给出具体数据" in result

    def test_generate_suggested_response_good_highlight(self, service):
        """Test suggested response for good highlight returns None"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "good"
        msg.fuzzy_words = None

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is None

    def test_generate_suggested_response_neutral_highlight(self, service):
        """Test suggested response for neutral highlight returns None"""
        # Arrange
        msg = MagicMock()
        msg.highlight_type = "neutral"
        msg.fuzzy_words = None

        # Act
        result = service._generate_suggested_response(msg)

        # Assert
        assert result is None
