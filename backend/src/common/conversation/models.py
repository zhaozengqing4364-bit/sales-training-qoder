"""
Conversation SQLAlchemy Models

Models for ConversationMessage entity.
Uses String(36) for UUID storage to maintain compatibility with SQLite and PostgreSQL.

References:
- Requirements: R9 (Conversation message storage)
- Design: Section 18 (Data Models)
- API Contract: docs/api-contract/replay.md
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from common.db.models import Base


class MessageRole(str, enum.Enum):
    """Message sender role"""
    USER = "user"
    ASSISTANT = "assistant"


class HighlightType(str, enum.Enum):
    """Highlight classification for key moments"""
    GOOD = "good"
    BAD = "bad"
    NEUTRAL = "neutral"


class ConversationMessage(Base):
    """
    ConversationMessage - Single message in a practice conversation

    A ConversationMessage represents one turn in a practice session,
    containing the text content, optional audio, and analysis data
    from capability modules (fuzzy words, sales stage, scoring).

    Requirements: R9, R10
    Design: Section 18
    API Contract: docs/api-contract/replay.md
    """
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False
    )

    # Message content
    turn_number = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # user|assistant
    content = Column(Text, nullable=False)

    # Audio data
    audio_url = Column(String(500), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Analysis data (JSON fields for capability module results)
    fuzzy_words = Column(JSON, nullable=True)  # [{category, matched, suggestion, severity}]
    sales_stage = Column(String(50), nullable=True)  # opening|discovery|presentation|objection|closing
    score_snapshot = Column(JSON, nullable=True)  # {overall, dimensions: [{name, score, trend, delta}]}
    ai_feedback = Column(Text, nullable=True)

    # Highlight markers for key moments
    is_highlight = Column(Boolean, default=False)
    highlight_type = Column(String(20), nullable=True)  # good|bad|neutral
    highlight_reason = Column(String(200), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_conversation_message_role"
        ),
        CheckConstraint(
            "highlight_type IS NULL OR highlight_type IN ('good', 'bad', 'neutral')",
            name="ck_conversation_message_highlight_type"
        ),
        CheckConstraint(
            "sales_stage IS NULL OR sales_stage IN ('opening', 'discovery', 'presentation', 'objection', 'closing')",
            name="ck_conversation_message_sales_stage"
        ),
        # Composite index for efficient session message retrieval
        Index("ix_conversation_messages_session_turn", "session_id", "turn_number"),
        Index("idx_conversation_messages_session", "session_id"),
        Index("idx_conversation_messages_timestamp", "timestamp"),
        Index("idx_conversation_messages_is_highlight", "is_highlight"),
    )

    # Relationships
    # Note: The back_populates="messages" requires PracticeSession to have a 'messages' relationship
    # This will be added when PracticeSession is extended in Task 1.1
    session = relationship("PracticeSession", back_populates="messages")
