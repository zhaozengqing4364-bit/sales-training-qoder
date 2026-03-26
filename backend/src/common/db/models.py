"""
SQLAlchemy Models - All 9 entities
Generated from data-model.md

兼容性说明：
- 使用 String(36) 存储 UUID 以兼容 SQLite 和 PostgreSQL
- 在应用层使用 uuid.UUID 类型进行转换
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

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
    role = Column(String(20), default="user", nullable=False)  # user, admin, support
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin', 'support')", name="ck_user_role"),
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    voice_mode = Column(String(32), nullable=False, default="legacy", index=True)
    voice_runtime_profile_id = Column(String(36), ForeignKey("voice_runtime_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    voice_policy_snapshot = Column(JSON, nullable=True)
    effectiveness_snapshot = Column(JSON, nullable=True)

    start_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    end_time = Column(DateTime(timezone=True))
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

    # Report generation status (Story 3.1)
    report_status = Column(String(20), default="pending", index=True)
    report_generated_at = Column(DateTime(timezone=True))
    report_error = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('preparing', 'in_progress', 'paused', 'completed', 'scoring')", name="ck_session_status"),
        CheckConstraint("voice_mode IN ('legacy', 'stepfun_realtime')", name="ck_session_voice_mode"),
        CheckConstraint("logic_score BETWEEN 0 AND 100", name="ck_logic_score"),
        CheckConstraint("accuracy_score BETWEEN 0 AND 100", name="ck_accuracy_score"),
        CheckConstraint("completeness_score BETWEEN 0 AND 100", name="ck_completeness_score"),
        CheckConstraint("report_status IN ('pending', 'processing', 'completed', 'failed')", name="ck_report_status"),
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
    interruption_events = relationship("InterruptionEvent", cascade="all, delete-orphan")
    # Agent Platform relationships
    agent = relationship("Agent", back_populates="sessions")
    persona = relationship("Persona", back_populates="sessions")
    # Conversation messages (R9: Conversation Message Storage)
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


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
        default=lambda: datetime.now(timezone.utc),
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


class InterruptionEvent(Base):
    __tablename__ = "interruption_events"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("practice_sessions.session_id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
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


class ManagerIntervention(Base):
    __tablename__ = "manager_interventions"

    intervention_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    manager_user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
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
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
        Index("idx_manager_interventions_manager_created", "manager_user_id", "created_at"),
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
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    scores = Column(JSON, nullable=True, default=dict)
    strengths = Column(JSON, nullable=True, default=list)
    suggestions = Column(JSON, nullable=True, default=list)
    summary = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = {"extend_existing": True}


class ComprehensiveReport(Base):
    """Comprehensive evaluation report for a practice session.
    Matches actual DB schema.
    """
    __tablename__ = "comprehensive_reports"

    session_id = Column(String(36), primary_key=True)
    overall_score = Column(Float, nullable=True, default=0.0)
    dimension_scores = Column(JSON, nullable=True, default=list)
    key_strengths = Column(JSON, nullable=True, default=list)
    key_improvements = Column(JSON, nullable=True, default=list)
    recommendations = Column(JSON, nullable=True, default=list)
    detailed_feedback = Column(Text, nullable=True, default="")
    stage_summaries = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = {"extend_existing": True}


class VerificationCheckType(str, enum.Enum):
    """Types of verification checks for release gates"""
    MIGRATION = "migration"           # Database migration check
    UNIT_TESTS = "unit_tests"         # Unit test execution
    COVERAGE = "coverage"             # Code coverage gate
    INTEGRATION_TESTS = "integration_tests"  # Integration test gate
    CONTRACT = "contract"             # API contract test
    PERFORMANCE = "performance"       # Performance benchmark
    HEALTH = "health"                 # Health checks
    SECURITY = "security"             # Security checks
    DOCUMENTATION = "documentation"   # Documentation checks
    MANUAL = "manual"                 # Manual checklist item


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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
            name="ck_verification_check_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'skipped')",
            name="ck_verification_status"
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
    overall_status = Column(String(20), nullable=False, default="pending")  # pending, passed, failed
    go_no_go_decision = Column(String(10), nullable=True)  # go, no_go, conditional
    decision_reason = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    finalized_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "overall_status IN ('pending', 'passed', 'failed')",
            name="ck_verification_summary_status"
        ),
        CheckConstraint(
            "go_no_go_decision IS NULL OR go_no_go_decision IN ('go', 'no_go', 'conditional')",
            name="ck_go_no_go_decision"
        ),
        Index("idx_verification_summary_version", "release_version"),
    )

    # Relationships
    finalizer = relationship("User", foreign_keys=[finalized_by])
