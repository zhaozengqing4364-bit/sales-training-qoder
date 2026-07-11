"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
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
from sqlalchemy.orm import relationship

from common.db.model_registry.base import Base
from common.db.model_registry.enums import (
    TrainingTaskStatus,
)


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
    voice_mode = Column(
        String(32),
        nullable=False,
        default="stepfun_realtime",
        server_default="stepfun_realtime",
        index=True,
    )
    voice_runtime_profile_id = Column(
        String(36),
        ForeignKey("voice_runtime_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    voice_policy_snapshot = Column(JSON, nullable=True)
    effectiveness_snapshot = Column(JSON, nullable=True)
    practice_template_id = Column(
        String(36),
        ForeignKey("practice_templates.template_id", ondelete="SET NULL"),
        nullable=True,
    )
    curriculum_snapshot = Column(JSON, nullable=True)
    runtime_state = Column(JSON, nullable=True)

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
    archived = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)
    transcript_url = Column(String(500))
    total_duration_seconds = Column(Integer)
    llm_tokens_used = Column(Integer, default=0)
    interruption_count = Column(Integer, default=0)

    # Report generation status (Story 3.1)
    report_status = Column(String(20), default="pending", index=True)
    report_generated_at = Column(DateTime(timezone=True))
    report_status_updated_at = Column(DateTime(timezone=True), nullable=True)
    report_retryable = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    report_trace_id = Column(String(64), nullable=True)
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
        Index("idx_sessions_practice_template", "practice_template_id"),
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
        "HighlightReview", back_populates="session", cascade="all, delete-orphan"
    )
    evaluation_runs = relationship(
        "EvaluationRun", back_populates="session", cascade="all, delete-orphan"
    )
    report_snapshots = relationship(
        "TrainingReportSnapshot",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class TrainingTask(Base):
    """Top-level training assignment, not a runtime subject."""

    __tablename__ = "training_tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False)
    assignee_id = Column(
        String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    scenario_type = Column(String(32), nullable=False)
    goal = Column(Text, nullable=False)
    focus_intent = Column(String(120), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completion_criteria = Column(JSON, nullable=False, default=dict)
    practice_template_id = Column(
        String(36),
        ForeignKey("practice_templates.template_id", ondelete="SET NULL"),
        nullable=True,
    )
    curriculum_plan_id = Column(String(36), nullable=True)
    source = Column(
        String(50), nullable=False, default="manual", server_default="manual"
    )
    status = Column(
        String(32),
        nullable=False,
        default=TrainingTaskStatus.ASSIGNED.value,
        server_default=TrainingTaskStatus.ASSIGNED.value,
        index=True,
    )
    resulting_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    before_after_summary = Column(JSON, nullable=True)
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
            name="ck_training_tasks_scenario_type",
        ),
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed', 'expired', 'cancelled')",
            name="ck_training_tasks_status",
        ),
        Index("idx_training_tasks_assignee_status", "assignee_id", "status"),
        Index("idx_training_tasks_practice_template", "practice_template_id"),
        Index("idx_training_tasks_curriculum_plan", "curriculum_plan_id"),
        Index("idx_training_tasks_due_date", "due_date"),
        Index("idx_training_tasks_created_at", "created_at"),
    )

    assignee = relationship("User", back_populates="training_tasks")
    resulting_session = relationship("PracticeSession")
    retraining_tasks = relationship(
        "RetrainingTask",
        back_populates="training_task",
        foreign_keys="RetrainingTask.training_task_id",
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


__all__ = [
    "Scenario",
    "Presentation",
    "Page",
    "RequiredTalkingPoint",
    "ForbiddenWord",
    "PracticeSession",
    "TrainingTask",
    "ConversationMessage",
    "HighlightReview",
    "HighlightReviewItem",
    "HighlightReviewShare",
    "HighlightReviewShareAccessLog",
    "InterruptionEvent",
]
