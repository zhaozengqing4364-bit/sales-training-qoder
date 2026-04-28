"""
SQLAlchemy Models - All 9 entities
Generated from data-model.md

兼容性说明：
- 使用 String(36) 存储 UUID 以兼容 SQLite 和 PostgreSQL
- 在应用层使用 uuid.UUID 类型进行转换
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _jsonb_compatible_type():
    return JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


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


class ReportGenerationStatus(str, enum.Enum):
    """Status of report generation for a session."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InterruptionType(str, enum.Enum):
    FORBIDDEN_WORD = "forbidden_word"
    MISSING_POINT = "missing_point"
    VAGUE_RESPONSE = "vague_response"


class ManagerInterventionDueState(str, enum.Enum):
    PENDING = "pending"
    DUE = "due"
    RESOLVED = "resolved"


class ManagerInterventionReminderStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    SENT = "sent"


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wechat_user_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100))
    email = Column(String(255), unique=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(20), default="user", nullable=False)  # user, admin, support
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin', 'support')", name="ck_user_role"),
    )

    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="user")
    leaderboard_entries = relationship("LeaderboardEntry", back_populates="user")
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    training_preferences = relationship(
        "UserTrainingPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    presentation_progress = relationship(
        "UserPresentationProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    achievements = relationship(
        "UserAchievement",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    goals = relationship(
        "UserGoal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    highlight_reviews = relationship(
        "HighlightReview",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserTrainingPreference(Base):
    __tablename__ = "user_training_preferences"

    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    voice_mode = Column(String(32), nullable=True)
    agent_id = Column(String(36), nullable=True)
    persona_id = Column(String(36), nullable=True)
    presentation_id = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "voice_mode IS NULL OR voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_user_training_preferences_voice_mode",
        ),
    )

    user = relationship("User", back_populates="training_preferences")


class UserPresentationProgress(Base):
    """Per-user durable progress marker for resuming long PPT practice."""

    __tablename__ = "user_presentation_progress"

    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    presentation_id = Column(
        String(36),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_page_number = Column(Integer, nullable=False)
    last_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_practice_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "last_page_number >= 1",
            name="ck_user_presentation_progress_page_positive",
        ),
        Index(
            "idx_user_presentation_progress_user_updated",
            "user_id",
            "updated_at",
        ),
    )

    user = relationship("User", back_populates="presentation_progress")
    presentation = relationship("Presentation", back_populates="user_progress")


class Achievement(Base):
    """Configurable achievement rule definition for retention loops."""

    __tablename__ = "achievements"

    achievement_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    icon_key = Column(String(60), nullable=False, default="trophy")
    condition_json = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user_achievements = relationship(
        "UserAchievement",
        back_populates="achievement",
        cascade="all, delete-orphan",
    )


class UserAchievement(Base):
    """Idempotent achievement unlock for a user."""

    __tablename__ = "user_achievements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id = Column(
        String(36),
        ForeignKey("achievements.achievement_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_json = Column(JSON, nullable=False, default=dict)
    unlocked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "achievement_id",
            name="uq_user_achievements_user_achievement",
        ),
        Index("idx_user_achievements_user_unlocked", "user_id", "unlocked_at"),
    )

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


class Notification(Base):
    """In-app notification with read/unread, expiry, and evidence metadata."""

    __tablename__ = "notifications"

    notification_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(30), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    action_label = Column(String(80), nullable=True)
    action_path = Column(String(500), nullable=True)
    source = Column(String(160), nullable=True, index=True)
    evidence_json = Column(JSON, nullable=False, default=dict)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('system', 'tip', 'reminder', 'achievement', 'ai_coach')",
            name="ck_notification_type",
        ),
        Index(
            "idx_notifications_user_read_created", "user_id", "is_read", "created_at"
        ),
    )

    user = relationship("User", back_populates="notifications")


class UserGoal(Base):
    """User-configurable practice goal."""

    __tablename__ = "user_goals"

    goal_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type = Column(String(40), nullable=False)
    period = Column(String(20), nullable=False, default="weekly")
    target_count = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "goal_type IN ('weekly_sessions', 'monthly_presentations')",
            name="ck_user_goal_type",
        ),
        CheckConstraint(
            "period IN ('weekly', 'monthly')",
            name="ck_user_goal_period",
        ),
        CheckConstraint("target_count > 0", name="ck_user_goal_target_positive"),
        Index("idx_user_goals_user_active", "user_id", "is_active"),
    )

    user = relationship("User", back_populates="goals")


class BusinessRuleConfig(Base):
    """Versioned business-rule configuration for governed runtime rules."""

    __tablename__ = "business_rule_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    domain = Column(String(80), nullable=False, index=True)
    key = Column(String(160), nullable=False, index=True)
    schema_version = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False)
    value_json = Column("value", _jsonb_compatible_type(), nullable=False, default=dict)
    default_value_json = Column(
        "default_value",
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
    )
    type = Column(String(40), nullable=False, default="rule_json")
    range_or_allowlist_json = Column(
        "range_or_allowlist",
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
    )
    read_path = Column(String(255), nullable=False)
    admin_entry = Column(String(255), nullable=False)
    permission = Column(String(80), nullable=False, default="admin")
    audit_policy = Column(Text, nullable=False)
    fallback_policy = Column(Text, nullable=False)
    rollback_policy = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    validation_errors_json = Column(
        "validation_errors",
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
    )
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived', 'disabled')",
            name="ck_business_rule_config_status",
        ),
        UniqueConstraint("key", "version", name="uq_business_rule_config_key_version"),
        Index(
            "idx_business_rule_configs_key_status_version",
            "key",
            "status",
            "version",
        ),
        Index("idx_business_rule_configs_domain_status", "domain", "status"),
    )

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])


class BusinessRuleConfigAuditLog(Base):
    """Audit trail for business-rule draft, publish, rollback, and disable actions."""

    __tablename__ = "business_rule_config_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(
        String(36),
        ForeignKey("business_rule_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    domain = Column(String(80), nullable=False, index=True)
    config_key = Column(String(160), nullable=False, index=True)
    action = Column(String(40), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    before_version = Column(Integer, nullable=True)
    after_version = Column(Integer, nullable=True)
    before_snapshot_json = Column(
        "before_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    after_snapshot_json = Column(
        "after_snapshot",
        _jsonb_compatible_type(),
        nullable=True,
    )
    reason = Column(Text, nullable=False, default="not-provided")
    trace_id = Column(String(120), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('seed_default', 'create_draft', 'update_draft', 'validate', "
            "'preview', 'publish', 'rollback', 'disable', 'delete_draft')",
            name="ck_business_rule_audit_action",
        ),
        Index(
            "idx_business_rule_audit_key_created",
            "config_key",
            "created_at",
        ),
    )

    config = relationship("BusinessRuleConfig")
    actor = relationship("User", foreign_keys=[actor_id])


class PasswordResetToken(Base):
    """Durable password-reset lifecycle row.

    Formal auth-recovery work should extend this model + its Alembic history
    (`026_password_reset_tokens`, `027_reset_lifecycle_delivery`, and
    `028_reset_single_active_token`) instead of reintroducing
    `used_at` is reserved for successful consumption, while `invalidated_at`
    records superseded/expired tokens that must still remain auditable.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True, index=True)
    invalidation_reason = Column(String(32), nullable=True)
    delivery_status = Column(String(20), nullable=False, default="pending", index=True)
    delivery_attempted_at = Column(DateTime(timezone=True), nullable=True)
    delivery_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')",
            name="ck_password_reset_tokens_delivery_status",
        ),
        CheckConstraint(
            "invalidation_reason IS NULL OR invalidation_reason IN ('superseded', 'expired')",
            name="ck_password_reset_tokens_invalidation_reason",
        ),
        Index("idx_password_reset_tokens_user_created", "user_id", "created_at"),
        Index(
            "uq_password_reset_tokens_single_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("used_at IS NULL AND invalidated_at IS NULL"),
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    user = relationship("User", back_populates="password_reset_tokens")


class Scenario(Base):
    __tablename__ = "scenarios"

    scenario_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scenario_type = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String)
    persona_prompt = Column(String)  # For sales bot
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('presentation', 'sales')", name="ck_scenario_type"
        ),
    )

    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="scenario")


class Presentation(Base):
    __tablename__ = "presentations"

    presentation_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title = Column(String(200), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer)
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    version_number = Column(Integer, default=1)
    status = Column(String(20), default="processing", index=True)
    uploaded_by_admin_id = Column(String(36), ForeignKey("users.user_id"))
    total_pages = Column(Integer)
    ocr_progress = Column(Float, default=0)

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')", name="ck_presentation_status"
        ),
    )

    # Relationships
    pages = relationship(
        "Page", back_populates="presentation", cascade="all, delete-orphan"
    )
    # Note: RequiredTalkingPoint is accessed through Page, not directly
    forbidden_words = relationship(
        "ForbiddenWord",
        foreign_keys="ForbiddenWord.presentation_id",
        cascade="all, delete-orphan",
    )
    practice_sessions = relationship("PracticeSession", back_populates="presentation")
    user_progress = relationship(
        "UserPresentationProgress",
        back_populates="presentation",
        cascade="all, delete-orphan",
    )


class Page(Base):
    __tablename__ = "pages"

    page_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    presentation_id = Column(
        String(36), ForeignKey("presentations.presentation_id"), nullable=False
    )
    page_number = Column(Integer, nullable=False)
    ocr_extracted_text = Column(String)
    image_url = Column(String(500))
    extraction_confidence = Column(Float)
    needs_manual_review = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint(
            "presentation_id", "page_number", name="uq_page_presentation_number"
        ),
        Index("idx_pages_presentation", "presentation_id"),
    )

    # Relationships
    presentation = relationship("Presentation", back_populates="pages")
    required_talking_points = relationship(
        "RequiredTalkingPoint", cascade="all, delete-orphan"
    )
    forbidden_words = relationship("ForbiddenWord", cascade="all, delete-orphan")


class RequiredTalkingPoint(Base):
    __tablename__ = "required_talking_points"

    point_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(
        String(36), ForeignKey("pages.page_id"), nullable=False, index=True
    )
    description = Column(String, nullable=False)
    created_by = Column(String(10), nullable=False)
    is_ai_generated = Column(Boolean, default=False)
    confirmed_by_admin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

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
            name="ck_forbidden_word_mutually_exclusive",
        ),
    )


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    scenario_id = Column(
        String(36), ForeignKey("scenarios.scenario_id"), nullable=False
    )
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))

    # Agent Platform fields (R12: Session Management Enhancement)
    # Nullable for backward compatibility with existing sessions
    # SET NULL on delete to preserve session history when Agent/Persona is deleted
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    persona_id = Column(
        String(36),
        ForeignKey("personas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    voice_mode = Column(String(32), nullable=False, default="legacy", index=True)
    voice_runtime_profile_id = Column(
        String(36),
        ForeignKey("voice_runtime_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    voice_policy_snapshot = Column(JSON, nullable=True)
    effectiveness_snapshot = Column(JSON, nullable=True)

    start_time = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    end_time = Column(DateTime(timezone=True))
    status = Column(String(20), default="preparing", index=True)
    current_page = Column(Integer)
    logic_score = Column(Float)
    accuracy_score = Column(Float)
    completeness_score = Column(Float)
    audio_url = Column(String(500))
    archived = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    archived_at = Column(DateTime(timezone=True), nullable=True)
    transcript_url = Column(String(500))
    total_duration_seconds = Column(Integer)
    llm_tokens_used = Column(Integer, default=0)
    interruption_count = Column(Integer, default=0)

    # Report generation status (Story 3.1)
    report_status = Column(String(20), default="pending", index=True)
    report_generated_at = Column(DateTime(timezone=True))
    report_error = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('preparing', 'in_progress', 'paused', 'completed', 'scoring')",
            name="ck_session_status",
        ),
        CheckConstraint(
            "voice_mode IN ('legacy', 'stepfun_realtime')", name="ck_session_voice_mode"
        ),
        CheckConstraint("logic_score BETWEEN 0 AND 100", name="ck_logic_score"),
        CheckConstraint("accuracy_score BETWEEN 0 AND 100", name="ck_accuracy_score"),
        CheckConstraint(
            "completeness_score BETWEEN 0 AND 100", name="ck_completeness_score"
        ),
        CheckConstraint(
            "report_status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_report_status",
        ),
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_status", "status"),
        Index("idx_sessions_start", "start_time"),
        Index("idx_sessions_agent", "agent_id"),
        Index("idx_sessions_persona", "persona_id"),
        Index("idx_sessions_report_status", "report_status"),
    )

    # Relationships
    user = relationship("User", back_populates="practice_sessions")
    scenario = relationship("Scenario", back_populates="practice_sessions")
    presentation = relationship("Presentation", back_populates="practice_sessions")
    interruption_events = relationship(
        "InterruptionEvent", cascade="all, delete-orphan"
    )
    # Agent Platform relationships
    agent = relationship("Agent", back_populates="sessions")
    persona = relationship("Persona", back_populates="sessions")
    # Conversation messages (R9: Conversation Message Storage)
    messages = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )
    # Audio segments for browser-direct OSS upload audit trail
    audio_segments = relationship(
        "SessionAudioSegment", back_populates="session", cascade="all, delete-orphan"
    )
    highlight_reviews = relationship(
        "HighlightReview",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ConversationMessage(Base):
    """Conversation message persisted for replay and report pages."""

    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_number = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # user|assistant
    content = Column(Text, nullable=False)
    audio_url = Column(String(500), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    fuzzy_words = Column(JSON, nullable=True)
    transcript_metadata = Column(JSON, nullable=True)
    sales_stage = Column(String(50), nullable=True)
    score_snapshot = Column(JSON, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    is_highlight = Column(Boolean, default=False, nullable=False)
    highlight_type = Column(String(20), nullable=True)
    highlight_reason = Column(String(200), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_conversation_message_role",
        ),
        CheckConstraint(
            "highlight_type IS NULL OR highlight_type IN ('good', 'bad', 'neutral')",
            name="ck_conversation_message_highlight_type",
        ),
        CheckConstraint(
            "sales_stage IS NULL OR sales_stage IN ('opening', 'discovery', 'presentation', 'objection', 'closing')",
            name="ck_conversation_message_sales_stage",
        ),
        Index("ix_conversation_messages_session_turn", "session_id", "turn_number"),
        Index("idx_conversation_messages_session", "session_id"),
        Index("idx_conversation_messages_timestamp", "timestamp"),
        Index("idx_conversation_messages_is_highlight", "is_highlight"),
    )

    session = relationship("PracticeSession", back_populates="messages")
    highlight_review_items = relationship(
        "HighlightReviewItem",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class HighlightReview(Base):
    """Durable learner-selected highlight review list for a practice session."""

    __tablename__ = "highlight_reviews"

    review_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_version = Column(String(40), nullable=False, default="highlight_review_v1")
    title = Column(String(160), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            name="uq_highlight_reviews_user_session",
        ),
        Index("idx_highlight_reviews_user_updated", "user_id", "updated_at"),
        Index("idx_highlight_reviews_session", "session_id"),
    )

    user = relationship("User", back_populates="highlight_reviews")
    session = relationship("PracticeSession", back_populates="highlight_reviews")
    items = relationship(
        "HighlightReviewItem",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="HighlightReviewItem.sort_order",
    )
    shares = relationship(
        "HighlightReviewShare",
        back_populates="review",
        cascade="all, delete-orphan",
    )


class HighlightReviewItem(Base):
    """Snapshot of one highlighted turn selected for later review."""

    __tablename__ = "highlight_review_items"

    item_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(
        String(36),
        ForeignKey("highlight_reviews.review_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id = Column(
        String(36),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_number = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)
    content_excerpt = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    stage_name = Column(String(80), nullable=True)
    issue_label = Column(String(80), nullable=True)
    suggested_response = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    source_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_highlight_review_item_role",
        ),
        UniqueConstraint(
            "review_id",
            "message_id",
            name="uq_highlight_review_items_review_message",
        ),
        Index("idx_highlight_review_items_review", "review_id"),
        Index("idx_highlight_review_items_message", "message_id"),
    )

    review = relationship("HighlightReview", back_populates="items")
    message = relationship(
        "ConversationMessage", back_populates="highlight_review_items"
    )


class HighlightReviewShare(Base):
    """Consent-gated, revocable share token for internal WeCom pilots."""

    __tablename__ = "highlight_review_shares"

    share_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(
        String(36),
        ForeignKey("highlight_reviews.review_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    channel = Column(String(20), nullable=False, default="wecom")
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    consent_granted = Column(Boolean, nullable=False, default=False)
    consent_text = Column(Text, nullable=True)
    policy_version = Column(String(80), nullable=False)
    policy_snapshot = Column(JSON, nullable=False, default=dict)
    ttl_days = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revoked_by_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    revoked_reason = Column(String(200), nullable=True)
    desensitization_version = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "channel IN ('wecom')",
            name="ck_highlight_review_share_channel",
        ),
        CheckConstraint("ttl_days BETWEEN 1 AND 90", name="ck_highlight_share_ttl"),
        Index("idx_highlight_review_shares_review", "review_id"),
        Index("idx_highlight_review_shares_user", "user_id"),
    )

    review = relationship("HighlightReview", back_populates="shares")
    access_logs = relationship(
        "HighlightReviewShareAccessLog",
        back_populates="share",
        cascade="all, delete-orphan",
    )


class HighlightReviewShareAccessLog(Base):
    """Append-only audit log for share create/access/revoke events."""

    __tablename__ = "highlight_review_share_access_logs"

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    share_id = Column(
        String(36),
        ForeignKey("highlight_review_shares.share_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(20), nullable=False)
    actor_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    viewer_label = Column(String(120), nullable=True)
    client_fingerprint = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="success")
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'accessed', 'revoked', 'denied')",
            name="ck_highlight_share_access_event_type",
        ),
        CheckConstraint(
            "status IN ('success', 'failed', 'blocked')",
            name="ck_highlight_share_access_status",
        ),
        Index("idx_highlight_share_access_logs_share", "share_id", "created_at"),
        Index("idx_highlight_share_access_logs_actor", "actor_user_id", "created_at"),
    )

    share = relationship("HighlightReviewShare", back_populates="access_logs")


class InterruptionEvent(Base):
    __tablename__ = "interruption_events"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    interruption_type = Column(String(30), nullable=False)
    trigger_content = Column(String)
    ai_response = Column(String, nullable=False)
    user_response_after = Column(String)
    detection_latency_ms = Column(Integer)
    was_effective = Column(Boolean)

    __table_args__ = (
        CheckConstraint(
            "interruption_type IN ('forbidden_word', 'missing_point', 'vague_response')",
            name="ck_interruption_type",
        ),
        Index("idx_interruptions_session", "session_id"),
    )

    # Relationships
    session = relationship("PracticeSession", back_populates="interruption_events")


class ManagerIntervention(Base):
    __tablename__ = "manager_interventions"

    intervention_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    manager_user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    issue_family = Column(String(64), nullable=False, index=True)
    note = Column(Text)
    due_state = Column(String(20), nullable=False, default="pending", index=True)
    reminder_status = Column(String(20), nullable=False, default="not_sent")
    reminder_sent_at = Column(DateTime(timezone=True))
    resolving_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "due_state IN ('pending', 'due', 'resolved')",
            name="ck_manager_intervention_due_state",
        ),
        CheckConstraint(
            "reminder_status IN ('not_sent', 'sent')",
            name="ck_manager_intervention_reminder_status",
        ),
        CheckConstraint(
            "(resolving_session_id IS NULL AND due_state IN ('pending', 'due')) OR "
            "(resolving_session_id IS NOT NULL AND due_state = 'resolved')",
            name="ck_manager_intervention_resolution_state",
        ),
        Index("idx_manager_interventions_user_created", "user_id", "created_at"),
        Index(
            "idx_manager_interventions_manager_created", "manager_user_id", "created_at"
        ),
    )


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    entry_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    scenario_type = Column(String(20), nullable=False, index=True)
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))
    average_score = Column(Float, nullable=False)
    total_sessions = Column(Integer, default=1)
    rank = Column(Integer, index=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('presentation', 'sales')",
            name="ck_leaderboard_scenario_type",
        ),
        CheckConstraint("average_score BETWEEN 0 AND 100", name="ck_leaderboard_score"),
        UniqueConstraint(
            "user_id",
            "scenario_type",
            "presentation_id",
            name="uq_leaderboard_user_scenario",
        ),
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
    status = Column(
        String(20), nullable=False, default="success"
    )  # success, failed, warning
    details = Column(String, nullable=True)  # JSON string for additional details
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'warning')", name="ck_system_log_status"
        ),
        Index("idx_system_logs_created_at", "created_at"),
        Index("idx_system_logs_user_id", "user_id"),
        Index("idx_system_logs_action", "action"),
    )

    # Relationships
    user = relationship("User", backref="system_logs")


class PromptTemplate(Base):
    """Prompt template for AI interactions."""

    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    prompt_type = Column(String(50), nullable=False)
    category = Column(String(100), nullable=False, default="common")
    template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("idx_prompt_templates_type", "prompt_type"),
        Index("idx_prompt_templates_active", "is_active"),
    )


class ScenarioPrompt(Base):
    """Link between scenarios and prompt templates."""

    __tablename__ = "scenario_prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_type = Column(String(50), nullable=False)
    scenario_id = Column(String(255), nullable=True)
    prompt_type = Column(String(50), nullable=False)
    template_id = Column(String(36), ForeignKey("prompt_templates.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    template = relationship("PromptTemplate")

    __table_args__ = (
        Index("idx_scenario_prompts_type", "scenario_type", "prompt_type"),
    )


class StagedEvaluationResult(Base):
    """Staged evaluation result for a practice session.
    Matches actual DB schema.
    """

    __tablename__ = "staged_evaluation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False)
    stage_number = Column(Integer, nullable=False)
    start_turn = Column(Integer, nullable=False, default=0)
    end_turn = Column(Integer, nullable=False, default=0)
    scores = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    strengths = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    weaknesses = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    suggestions = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    summary = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("idx_staged_eval_session", "session_id"),
        Index("idx_staged_eval_stage", "session_id", "stage_number", unique=True),
        {"extend_existing": True},
    )


class ComprehensiveReport(Base):
    """Comprehensive evaluation report for a practice session.
    Matches actual DB schema.
    """

    __tablename__ = "comprehensive_reports"

    session_id = Column(String(36), primary_key=True)
    overall_score = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    dimension_scores = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    key_strengths = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    key_improvements = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    recommendations = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    detailed_feedback = Column(Text, nullable=True)
    stage_summaries = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = {"extend_existing": True}


class ScoringRuleset(Base):
    """Versioned scoring ruleset managed through the admin control plane."""

    __tablename__ = "scoring_rulesets"

    ruleset_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_type = Column(String(20), nullable=False, index=True)
    version = Column(String(80), nullable=False)
    display_name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    definition_json = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    published_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('sales', 'presentation')",
            name="ck_scoring_ruleset_scenario_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_scoring_ruleset_status",
        ),
        UniqueConstraint(
            "scenario_type",
            "version",
            name="uq_scoring_ruleset_scenario_version",
        ),
        Index("idx_scoring_rulesets_scenario_active", "scenario_type", "is_active"),
    )


class VerificationCheckType(str, enum.Enum):
    """Types of verification checks for release gates"""

    MIGRATION = "migration"  # Database migration check
    UNIT_TESTS = "unit_tests"  # Unit test execution
    COVERAGE = "coverage"  # Code coverage gate
    INTEGRATION_TESTS = "integration_tests"  # Integration test gate
    CONTRACT = "contract"  # API contract test
    PERFORMANCE = "performance"  # Performance benchmark
    HEALTH = "health"  # Health checks
    SECURITY = "security"  # Security checks
    DOCUMENTATION = "documentation"  # Documentation checks
    MANUAL = "manual"  # Manual checklist item


class VerificationStatus(str, enum.Enum):
    """Status of a verification check"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReleaseVerificationRecord(Base):
    """
    ReleaseVerificationRecord - Records release gate verification results

    Tracks verification checks for release candidates to ensure
    quality gates are passed before deployment.

    References:
    - Requirements: FR40 - Release gate check results recording and tracking
    - NFR19: Contract test pass rate 100% required for release
    """

    __tablename__ = "release_verification_records"

    record_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_version = Column(String(50), nullable=False, index=True)
    release_candidate_id = Column(String(100), nullable=False, index=True)

    # Check details
    check_type = Column(String(20), nullable=False)
    check_name = Column(String(200), nullable=False)
    check_description = Column(Text, nullable=True)

    # Result
    status = Column(String(20), nullable=False, default="pending")
    passed = Column(Boolean, nullable=False, default=False)
    details = Column(JSON, nullable=True)  # Additional check-specific data
    error_message = Column(Text, nullable=True)

    # Audit trail
    executed_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Traceability
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint(
            "check_type IN ("
            "'migration', "
            "'unit_tests', "
            "'coverage', "
            "'integration_tests', "
            "'contract', "
            "'performance', "
            "'health', "
            "'security', "
            "'documentation', "
            "'manual'"
            ")",
            name="ck_verification_check_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'skipped')",
            name="ck_verification_status",
        ),
        Index("idx_verification_release_version", "release_version"),
        Index("idx_verification_candidate", "release_candidate_id"),
        Index("idx_verification_status", "status"),
        Index("idx_verification_type", "check_type"),
    )

    # Relationships
    executor = relationship("User", foreign_keys=[executed_by])


class ReleaseVerificationSummary(Base):
    """
    ReleaseVerificationSummary - Overall verification summary for a release candidate

    Aggregates all verification checks for a release candidate to provide
    a go/no-go decision summary.
    """

    __tablename__ = "release_verification_summaries"

    summary_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_version = Column(String(50), nullable=False, unique=True, index=True)
    release_candidate_id = Column(String(100), nullable=False, unique=True)

    # Summary counts
    total_checks = Column(Integer, nullable=False, default=0)
    passed_checks = Column(Integer, nullable=False, default=0)
    failed_checks = Column(Integer, nullable=False, default=0)
    skipped_checks = Column(Integer, nullable=False, default=0)
    pending_checks = Column(Integer, nullable=False, default=0)

    # Overall decision
    overall_status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, passed, failed
    go_no_go_decision = Column(String(10), nullable=True)  # go, no_go, conditional
    decision_reason = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    finalized_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "overall_status IN ('pending', 'passed', 'failed')",
            name="ck_verification_summary_status",
        ),
        CheckConstraint(
            "go_no_go_decision IS NULL OR go_no_go_decision IN ('go', 'no_go', 'conditional')",
            name="ck_go_no_go_decision",
        ),
        Index("idx_verification_summary_version", "release_version"),
    )

    # Relationships
    finalizer = relationship("User", foreign_keys=[finalized_by])


class UploadStatus(str, enum.Enum):
    """Upload status for audio segments."""

    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


class SessionAudioSegment(Base):
    """Audio segment metadata for browser-direct OSS uploads.

    Each row represents one audio chunk uploaded during a training session.
    The actual audio bytes live in Alibaba Cloud OSS; this table only stores
    metadata and upload status.
    """

    __tablename__ = "session_audio_segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_sequence = Column(Integer, nullable=False)
    object_key = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False, default="audio/webm")
    size_bytes = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    upload_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "upload_status IN ('pending', 'uploaded', 'failed')",
            name="ck_audio_segment_upload_status",
        ),
        UniqueConstraint(
            "session_id",
            "segment_sequence",
            name="uq_audio_segment_session_sequence",
        ),
        Index("idx_audio_segments_session", "session_id"),
    )

    # Relationships
    session = relationship("PracticeSession", back_populates="audio_segments")


class KnowledgeConfigVersion(Base):
    """Versioned control-plane snapshot for the knowledge answering engine."""

    __tablename__ = "knowledge_config_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version_name = Column(String(120), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    notes = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_knowledge_config_version_status",
        ),
        Index("idx_knowledge_config_versions_status", "status"),
    )


class KnowledgeQueryProfile(Base):
    """Configures query rewrite behavior for one knowledge intent/profile."""

    __tablename__ = "knowledge_query_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rewrite_strategy = Column(String(50), nullable=False)
    max_rewrite_queries = Column(Integer, nullable=False, default=1)
    stop_after_first_success = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_query_profile_version_key",
        ),
        Index("idx_knowledge_query_profiles_profile_key", "profile_key"),
    )


class KnowledgeIntentRule(Base):
    """Maps user-query patterns to knowledge query profiles."""

    __tablename__ = "knowledge_intent_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent_key = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    match_type = Column(String(50), nullable=False)
    pattern = Column(Text, nullable=False)
    profile_key = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_knowledge_intent_rules_priority", "priority"),
        Index("idx_knowledge_intent_rules_intent_key", "intent_key"),
    )


class KnowledgeEntityAlias(Base):
    """Deterministic alias mapping used before retrieval planning."""

    __tablename__ = "knowledge_entity_aliases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_entity = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_knowledge_entity_alias_confidence",
        ),
        UniqueConstraint(
            "config_version_id", "alias", name="uq_knowledge_entity_alias_version_alias"
        ),
        Index("idx_knowledge_entity_aliases_canonical_entity", "canonical_entity"),
    )


class KnowledgeRankingProfile(Base):
    """Business-owned reranking weights for retrieved candidates."""

    __tablename__ = "knowledge_ranking_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    title_exact_boost = Column(Float, nullable=False, default=0.0)
    entity_match_boost = Column(Float, nullable=False, default=0.0)
    doc_type_weights_json = Column(JSON, nullable=False, default=dict)
    section_weights_json = Column(JSON, nullable=False, default=dict)
    min_pass_score = Column(Float, nullable=False, default=0.0)
    min_pass_score_keyword = Column(Float, nullable=False, default=0.0)
    # Unified scoring weights (elevated from hardcoded values in _rerank_results)
    base_weight = Column(Float, nullable=False, default=0.50)
    coverage_weight = Column(Float, nullable=False, default=0.20)
    phrase_bonus = Column(Float, nullable=False, default=0.15)
    title_bonus_max = Column(Float, nullable=False, default=0.10)
    ratio_bonus_max = Column(Float, nullable=False, default=0.05)
    cross_encoder_weight = Column(Float, nullable=False, default=0.0)
    diversity_penalty = Column(Float, nullable=False, default=0.12)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_ranking_profile_version_key",
        ),
        Index("idx_knowledge_ranking_profiles_profile_key", "profile_key"),
    )


class KnowledgeChunkingPreset(Base):
    """Named chunking configuration that belongs to a config version."""

    __tablename__ = "knowledge_chunking_presets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    chunking_strategy = Column(String(50), nullable=False, default="element_boundary")
    chunk_size = Column(Integer, nullable=False, default=500)
    chunk_overlap = Column(Integer, nullable=False, default=50)
    is_default = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id", "profile_key", name="uq_chunking_preset_version_key"
        ),
        Index("idx_knowledge_chunking_presets_profile_key", "profile_key"),
    )


class KnowledgeAnswerabilityProfile(Base):
    """Thresholds for deciding whether evidence is sufficient to answer."""

    __tablename__ = "knowledge_answerability_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    required_slots_json = Column(JSON, nullable=False, default=list)
    optional_slots_json = Column(JSON, nullable=False, default=list)
    sufficient_threshold = Column(Float, nullable=False, default=1.0)
    partial_threshold = Column(Float, nullable=False, default=0.0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_answerability_profile_version_key",
        ),
        Index("idx_knowledge_answerability_profiles_profile_key", "profile_key"),
    )


class KnowledgeAnswerRun(Base):
    """Top-level audit row for one knowledge-answering attempt."""

    __tablename__ = "knowledge_answer_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entrypoint = Column(String(100), nullable=False)
    query_text = Column(Text, nullable=False)
    answerability = Column(String(20), nullable=False, default="insufficient")
    final_status = Column(String(20), nullable=False, default="completed")
    blocked_reason = Column(String(100), nullable=True)
    citations_json = Column(JSON, nullable=False, default=list)
    retrieval_summary_json = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "answerability IN ('sufficient', 'partial', 'insufficient', 'blocked')",
            name="ck_knowledge_answer_run_answerability",
        ),
        CheckConstraint(
            "final_status IN ('completed', 'blocked', 'failed')",
            name="ck_knowledge_answer_run_final_status",
        ),
        Index("idx_knowledge_answer_runs_session_created", "session_id", "created_at"),
    )


class KnowledgeAnswerRunStep(Base):
    """Step-level payload audit for one knowledge-answer run."""

    __tablename__ = "knowledge_answer_run_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_run_id = Column(
        String(36),
        ForeignKey("knowledge_answer_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    input_payload = Column(JSON, nullable=False, default=dict)
    output_payload = Column(JSON, nullable=False, default=dict)
    duration_ms = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed', 'skipped')",
            name="ck_knowledge_answer_run_step_status",
        ),
        UniqueConstraint(
            "answer_run_id", "step_order", name="uq_knowledge_answer_run_steps_order"
        ),
        Index("idx_knowledge_answer_run_steps_run", "answer_run_id"),
    )
