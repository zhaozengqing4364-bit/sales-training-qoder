"""
Unit Tests for MessageStorageService

Tests for save_message(), update_analysis(), and mark_highlight() operations.

References:
- Requirements: R9 (Conversation message storage)
- Design: Section 11 (Message Storage Service)
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.conversation.storage import MessageStorageService


class TestMessageStorageService:
    """Tests for MessageStorageService"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.rollback = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create MessageStorageService with mock db"""
        return MessageStorageService(mock_db)

    @pytest.fixture
    def sample_session_id(self):
        """Sample session ID"""
        return str(uuid.uuid4())

    @pytest.fixture
    def sample_message_id(self):
        """Sample message ID"""
        return str(uuid.uuid4())

    # ========== save_message tests ==========

    @pytest.mark.asyncio
    async def test_save_message_basic(self, service, mock_db, sample_session_id):
        """Test saving a basic message without analysis data"""
        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=1,
            role="user",
            content="Hello, I want to learn about your product"
        )

        # Assert
        assert result.is_success
        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    @pytest.mark.asyncio
    async def test_save_message_with_audio(self, service, mock_db, sample_session_id):
        """Test saving a message with audio data"""
        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=1,
            role="user",
            content="Hello",
            audio_url="https://storage.example.com/audio/msg-001.mp3",
            duration_ms=3500
        )

        # Assert
        assert result.is_success
        message = result.value
        assert message.audio_url == "https://storage.example.com/audio/msg-001.mp3"
        assert message.duration_ms == 3500

    @pytest.mark.asyncio
    async def test_save_message_with_analysis_data(self, service, mock_db, sample_session_id):
        """Test saving a message with analysis data"""
        # Arrange
        analysis_data = {
            "fuzzy_words": [
                {"category": "uncertain", "matched": ["大概"], "suggestion": "请给出具体数据", "severity": "high"}
            ],
            "sales_stage": "presentation",
            "score_snapshot": {"overall": 72, "dimensions": []},
            "ai_feedback": "Good response"
        }

        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=2,
            role="user",
            content="我们的产品大概能帮您节省30%的成本",
            analysis_data=analysis_data
        )

        # Assert
        assert result.is_success
        message = result.value
        assert message.fuzzy_words == analysis_data["fuzzy_words"]
        assert message.sales_stage == "presentation"
        assert message.score_snapshot == analysis_data["score_snapshot"]
        assert message.ai_feedback == "Good response"

    @pytest.mark.asyncio
    async def test_save_message_assistant_role(self, service, mock_db, sample_session_id):
        """Test saving an assistant message"""
        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=1,
            role="assistant",
            content="你好，我是XX公司的采购负责人"
        )

        # Assert
        assert result.is_success
        assert result.value.role == "assistant"

    @pytest.mark.asyncio
    async def test_save_message_invalid_role(self, service, mock_db, sample_session_id):
        """Test saving a message with invalid role fails"""
        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=1,
            role="invalid_role",
            content="Hello"
        )

        # Assert
        assert not result.is_success
        assert "[INVALID_ROLE]" in result.fallback

    @pytest.mark.asyncio
    async def test_save_message_db_error(self, service, mock_db, sample_session_id):
        """Test handling database error during save"""
        # Arrange
        mock_db.commit.side_effect = Exception("Database error")

        # Act
        result = await service.save_message(
            session_id=sample_session_id,
            turn_number=1,
            role="user",
            content="Hello"
        )

        # Assert
        assert not result.is_success
        assert "[MESSAGE_SAVE_FAILED]" in result.fallback
        assert mock_db.rollback.called

    # ========== update_analysis tests ==========

    @pytest.mark.asyncio
    async def test_update_analysis_fuzzy_words(self, service, mock_db, sample_message_id):
        """Test updating fuzzy words analysis"""
        # Arrange
        mock_message = MagicMock()
        mock_message.id = sample_message_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        fuzzy_words = [
            {"category": "uncertain", "matched": ["可能"], "suggestion": "请确认", "severity": "medium"}
        ]

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            fuzzy_words=fuzzy_words
        )

        # Assert
        assert result.is_success
        assert mock_message.fuzzy_words == fuzzy_words
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_update_analysis_sales_stage(self, service, mock_db, sample_message_id):
        """Test updating sales stage"""
        # Arrange
        mock_message = MagicMock()
        mock_message.id = sample_message_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            sales_stage="discovery"
        )

        # Assert
        assert result.is_success
        assert mock_message.sales_stage == "discovery"

    @pytest.mark.asyncio
    async def test_update_analysis_invalid_stage(self, service, mock_db, sample_message_id):
        """Test updating with invalid sales stage fails"""
        # Arrange
        mock_message = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            sales_stage="invalid_stage"
        )

        # Assert
        assert not result.is_success
        assert "[INVALID_SALES_STAGE]" in result.fallback

    @pytest.mark.asyncio
    async def test_update_analysis_score_snapshot(self, service, mock_db, sample_message_id):
        """Test updating score snapshot"""
        # Arrange
        mock_message = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        score_snapshot = {
            "overall": 75,
            "dimensions": [
                {"name": "专业度", "score": 80, "trend": "up", "delta": 5}
            ]
        }

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            score_snapshot=score_snapshot
        )

        # Assert
        assert result.is_success
        assert mock_message.score_snapshot == score_snapshot

    @pytest.mark.asyncio
    async def test_update_analysis_message_not_found(self, service, mock_db, sample_message_id):
        """Test updating non-existent message fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            sales_stage="opening"
        )

        # Assert
        assert not result.is_success
        assert "[MESSAGE_NOT_FOUND]" in result.fallback

    @pytest.mark.asyncio
    async def test_update_analysis_multiple_fields(self, service, mock_db, sample_message_id):
        """Test updating multiple analysis fields at once"""
        # Arrange
        mock_message = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.update_analysis(
            message_id=sample_message_id,
            fuzzy_words=[{"category": "filler", "matched": ["嗯"], "suggestion": "减少填充词", "severity": "low"}],
            sales_stage="presentation",
            score_snapshot={"overall": 70, "dimensions": []},
            ai_feedback="注意减少模糊表达"
        )

        # Assert
        assert result.is_success
        assert mock_message.fuzzy_words is not None
        assert mock_message.sales_stage == "presentation"
        assert mock_message.score_snapshot is not None
        assert mock_message.ai_feedback == "注意减少模糊表达"

    # ========== mark_highlight tests ==========

    @pytest.mark.asyncio
    async def test_mark_highlight_good(self, service, mock_db, sample_message_id):
        """Test marking a message as a good highlight"""
        # Arrange
        mock_message = MagicMock()
        mock_message.id = sample_message_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="good",
            highlight_reason="优秀案例引用"
        )

        # Assert
        assert result.is_success
        assert mock_message.is_highlight is True
        assert mock_message.highlight_type == "good"
        assert mock_message.highlight_reason == "优秀案例引用"

    @pytest.mark.asyncio
    async def test_mark_highlight_bad(self, service, mock_db, sample_message_id):
        """Test marking a message as a bad highlight"""
        # Arrange
        mock_message = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="bad",
            highlight_reason="模糊词使用"
        )

        # Assert
        assert result.is_success
        assert mock_message.highlight_type == "bad"

    @pytest.mark.asyncio
    async def test_mark_highlight_neutral(self, service, mock_db, sample_message_id):
        """Test marking a message as a neutral highlight"""
        # Arrange
        mock_message = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="neutral",
            highlight_reason="阶段转换点"
        )

        # Assert
        assert result.is_success
        assert mock_message.highlight_type == "neutral"

    @pytest.mark.asyncio
    async def test_mark_highlight_invalid_type(self, service, mock_db, sample_message_id):
        """Test marking with invalid highlight type fails"""
        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="invalid",
            highlight_reason="Some reason"
        )

        # Assert
        assert not result.is_success
        assert "[INVALID_HIGHLIGHT_TYPE]" in result.fallback

    @pytest.mark.asyncio
    async def test_mark_highlight_reason_too_long(self, service, mock_db, sample_message_id):
        """Test marking with too long reason fails"""
        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="good",
            highlight_reason="x" * 201  # 201 characters
        )

        # Assert
        assert not result.is_success
        assert "[HIGHLIGHT_REASON_TOO_LONG]" in result.fallback

    @pytest.mark.asyncio
    async def test_mark_highlight_message_not_found(self, service, mock_db, sample_message_id):
        """Test marking non-existent message fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.mark_highlight(
            message_id=sample_message_id,
            highlight_type="good",
            highlight_reason="Great response"
        )

        # Assert
        assert not result.is_success
        assert "[MESSAGE_NOT_FOUND]" in result.fallback

    # ========== get_message_by_id tests ==========

    @pytest.mark.asyncio
    async def test_get_message_by_id_success(self, service, mock_db, sample_message_id):
        """Test getting a message by ID"""
        # Arrange
        mock_message = MagicMock()
        mock_message.id = sample_message_id
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_message_by_id(sample_message_id)

        # Assert
        assert result.is_success
        assert result.value.id == sample_message_id

    @pytest.mark.asyncio
    async def test_get_message_by_id_not_found(self, service, mock_db, sample_message_id):
        """Test getting non-existent message fails"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await service.get_message_by_id(sample_message_id)

        # Assert
        assert not result.is_success
        assert "[MESSAGE_NOT_FOUND]" in result.fallback

    # ========== get_messages_by_session tests ==========

    @pytest.mark.asyncio
    async def test_get_messages_by_session_success(self, service, mock_db, sample_session_id):
        """Test getting messages for a session"""
        # Arrange
        mock_messages = [MagicMock(), MagicMock()]
        
        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2
        
        # Mock messages query
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages
        
        mock_db.execute.side_effect = [mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages_by_session(
            session_id=sample_session_id,
            page=1,
            page_size=50
        )

        # Assert
        assert result.is_success
        messages, total = result.value
        assert len(messages) == 2
        assert total == 2

    @pytest.mark.asyncio
    async def test_get_messages_by_session_pagination(self, service, mock_db, sample_session_id):
        """Test pagination for session messages"""
        # Arrange
        mock_messages = [MagicMock()]
        
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100
        
        mock_messages_result = MagicMock()
        mock_messages_result.scalars.return_value.all.return_value = mock_messages
        
        mock_db.execute.side_effect = [mock_count_result, mock_messages_result]

        # Act
        result = await service.get_messages_by_session(
            session_id=sample_session_id,
            page=2,
            page_size=10
        )

        # Assert
        assert result.is_success
        messages, total = result.value
        assert total == 100
