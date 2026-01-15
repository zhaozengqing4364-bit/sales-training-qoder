"""
SQLAlchemy Models - All 9 entities
Generated from data-model.md

兼容性说明：
- 使用 String(36) 存储 UUID 以兼容 SQLite 和 PostgreSQL
- 在应用层使用 uuid.UUID 类型进行转换
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class ScenarioType(str, enum.Enum):
    PRESENTATION = "presentation"
    SALES = "sales"


class PresentationStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(str, enum.Enum):
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    SCORING = "scoring"


class InterruptionType(str, enum.Enum):
    FORBIDDEN_WORD = "forbidden_word"
    MISSING_POINT = "missing_point"
    VAGUE_RESPONSE = "vague_response"


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wechat_user_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100))
    email = Column(String(255), unique=True)
    role = Column(String(20), default="user", nullable=False)  # user, admin
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="ck_user_role"),
    )

    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="user")
    leaderboard_entries = relationship("LeaderboardEntry", back_populates="user")


class Scenario(Base):
    __tablename__ = "scenarios"

    scenario_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String)
    persona_prompt = Column(String)  # For sales bot
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("scenario_type IN ('presentation', 'sales')", name="ck_scenario_type"),
    )

    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="scenario")


class Presentation(Base):
    __tablename__ = "presentations"

    presentation_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer)
    upload_date = Column(DateTime, default=datetime.utcnow)
    version_number = Column(Integer, default=1)
    status = Column(String(20), default="processing", index=True)
    uploaded_by_admin_id = Column(String(36), ForeignKey("users.user_id"))
    total_pages = Column(Integer)
    ocr_progress = Column(Float, default=0)

    __table_args__ = (
        CheckConstraint("status IN ('processing', 'ready', 'failed')", name="ck_presentation_status"),
    )

    # Relationships
    pages = relationship("Page", back_populates="presentation", cascade="all, delete-orphan")
    # Note: RequiredTalkingPoint is accessed through Page, not directly
    forbidden_words = relationship("ForbiddenWord", foreign_keys="ForbiddenWord.presentation_id", cascade="all, delete-orphan")
    practice_sessions = relationship("PracticeSession", back_populates="presentation")


class Page(Base):
    __tablename__ = "pages"

    page_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    ocr_extracted_text = Column(String)
    image_url = Column(String(500))
    extraction_confidence = Column(Float)
    needs_manual_review = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("presentation_id", "page_number", name="uq_page_presentation_number"),
        Index("idx_pages_presentation", "presentation_id"),
    )

    # Relationships
    presentation = relationship("Presentation", back_populates="pages")
    required_talking_points = relationship("RequiredTalkingPoint", cascade="all, delete-orphan")
    forbidden_words = relationship("ForbiddenWord", cascade="all, delete-orphan")


class RequiredTalkingPoint(Base):
    __tablename__ = "required_talking_points"

    point_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey("pages.page_id"), nullable=False, index=True)
    description = Column(String, nullable=False)
    created_by = Column(String(10), nullable=False)
    is_ai_generated = Column(Boolean, default=False)
    confirmed_by_admin = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("created_by IN ('admin', 'ai')", name="ck_point_created_by"),
        Index("idx_talking_points_page", "page_id"),
    )

    # Relationships
    page = relationship("Page", back_populates="required_talking_points")


class ForbiddenWord(Base):
    __tablename__ = "forbidden_words"

    word_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))
    page_id = Column(String(36), ForeignKey("pages.page_id"))
    phrase = Column(String(500), nullable=False)
    suggested_alternative = Column(String)
    is_regex = Column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(
            "(presentation_id IS NOT NULL AND page_id IS NULL) OR "
            "(presentation_id IS NULL AND page_id IS NOT NULL)",
            name="ck_forbidden_word_mutually_exclusive"
        ),
    )


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.scenario_id"), nullable=False)
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))

    # Agent Platform fields (R12: Session Management Enhancement)
    # Nullable for backward compatibility with existing sessions
    # SET NULL on delete to preserve session history when Agent/Persona is deleted
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    persona_id = Column(String(36), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True)

    start_time = Column(DateTime, default=datetime.utcnow, index=True)
    end_time = Column(DateTime)
    status = Column(String(20), default="preparing", index=True)
    current_page = Column(Integer)
    logic_score = Column(Float)
    accuracy_score = Column(Float)
    completeness_score = Column(Float)
    audio_url = Column(String(500))
    transcript_url = Column(String(500))
    total_duration_seconds = Column(Integer)
    llm_tokens_used = Column(Integer, default=0)
    interruption_count = Column(Integer, default=0)

    __table_args__ = (
        CheckConstraint("status IN ('preparing', 'in_progress', 'paused', 'completed', 'scoring')", name="ck_session_status"),
        CheckConstraint("logic_score BETWEEN 0 AND 100", name="ck_logic_score"),
        CheckConstraint("accuracy_score BETWEEN 0 AND 100", name="ck_accuracy_score"),
        CheckConstraint("completeness_score BETWEEN 0 AND 100", name="ck_completeness_score"),
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_status", "status"),
        Index("idx_sessions_start", "start_time"),
        Index("idx_sessions_agent", "agent_id"),
        Index("idx_sessions_persona", "persona_id"),
    )

    # Relationships
    user = relationship("User", back_populates="practice_sessions")
    scenario = relationship("Scenario", back_populates="practice_sessions")
    presentation = relationship("Presentation", back_populates="practice_sessions")
    interruption_events = relationship("InterruptionEvent", cascade="all, delete-orphan")
    # Agent Platform relationships
    agent = relationship("Agent", back_populates="sessions")
    persona = relationship("Persona", back_populates="sessions")
    # Conversation messages (R9: Conversation Message Storage)
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


class InterruptionEvent(Base):
    __tablename__ = "interruption_events"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    interruption_type = Column(String(30), nullable=False)
    trigger_content = Column(String)
    ai_response = Column(String, nullable=False)
    user_response_after = Column(String)
    detection_latency_ms = Column(Integer)
    was_effective = Column(Boolean)

    __table_args__ = (
        CheckConstraint("interruption_type IN ('forbidden_word', 'missing_point', 'vague_response')", name="ck_interruption_type"),
        Index("idx_interruptions_session", "session_id"),
    )

    # Relationships
    session = relationship("PracticeSession", back_populates="interruption_events")


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    entry_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    scenario_type = Column(String(20), nullable=False, index=True)
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))
    average_score = Column(Float, nullable=False)
    total_sessions = Column(Integer, default=1)
    rank = Column(Integer, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("scenario_type IN ('presentation', 'sales')", name="ck_leaderboard_scenario_type"),
        CheckConstraint("average_score BETWEEN 0 AND 100", name="ck_leaderboard_score"),
        UniqueConstraint("user_id", "scenario_type", "presentation_id", name="uq_leaderboard_user_scenario"),
        Index("idx_leaderboard_scenario", "scenario_type"),
        Index("idx_leaderboard_rank", "rank"),
    )

    # Relationships
    user = relationship("User", back_populates="leaderboard_entries")


class SystemLogStatus(str, enum.Enum):
    """System log status types"""
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"


class SystemLog(Base):
    """
    SystemLog - Audit log for system activities

    Tracks user actions and system events for audit purposes.

    References:
    - Requirements: 7.1, 7.2, 7.3
    - Design: Section "System Logs API"
    """
    __tablename__ = "system_logs"

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(100), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    user_identifier = Column(String(255), nullable=False)  # email or "system"
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), nullable=False, default="success")  # success, failed, warning
    details = Column(String, nullable=True)  # JSON string for additional details
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'warning')",
            name="ck_system_log_status"
        ),
        Index("idx_system_logs_created_at", "created_at"),
        Index("idx_system_logs_user_id", "user_id"),
        Index("idx_system_logs_action", "action"),
    )

    # Relationships
    user = relationship("User", backref="system_logs")
