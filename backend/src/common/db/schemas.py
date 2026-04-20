"""
Pydantic Schemas for API validation
Generated from data-model.md and contracts/openapi.yaml
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from training_runtime.models import TrainingRuntimeDescriptor, TrainingRuntimeSubject


class ScenarioType(StrEnum):
    PRESENTATION = "presentation"
    SALES = "sales"


class PresentationStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionStatus(StrEnum):
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    SCORING = "scoring"


class SessionLifecycleAction(StrEnum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    END = "end"


class ManagerInterventionDueState(StrEnum):
    PENDING = "pending"
    DUE = "due"
    RESOLVED = "resolved"


class ManagerInterventionReminderStatus(StrEnum):
    NOT_SENT = "not_sent"
    SENT = "sent"


class InterruptionType(StrEnum):
    FORBIDDEN_WORD = "forbidden_word"
    MISSING_POINT = "missing_point"
    VAGUE_RESPONSE = "vague_response"


# ========== Shared Asset Governance Schemas ==========
class AssetGovernanceAnomaly(BaseModel):
    kind: str
    severity: str
    summary: str
    detected_at: datetime | None = None
    session_id: str | None = None
    source: str | None = None


class AssetGovernanceImpactSummary(BaseModel):
    impact_level: str
    recent_session_count: int = 0
    active_session_count: int = 0
    impacted_user_count: int = 0
    last_session_at: datetime | None = None


class AssetGovernanceRecentChangeSummary(BaseModel):
    last_changed_at: datetime | None = None
    latest_change_type: str
    latest_change_label: str
    change_count_7d: int = 0
    sessions_since_change: int = 0


class AssetGovernanceHealthSummary(BaseModel):
    status: str
    anomaly_count: int = 0
    blocking_count: int = 0
    warning_count: int = 0
    sample_anomalies: list[AssetGovernanceAnomaly] = Field(default_factory=list)


class AssetGovernanceSummary(BaseModel):
    impact_summary: AssetGovernanceImpactSummary
    recent_change_summary: AssetGovernanceRecentChangeSummary
    health_summary: AssetGovernanceHealthSummary


class LinkedAssetChangeReference(BaseModel):
    asset_type: str
    asset_label: str
    asset_id: str
    asset_name: str
    admin_path: str
    latest_change_label: str
    latest_change_type: str
    last_changed_at: datetime | None = None
    change_count_7d: int = 0
    sessions_since_change: int = 0
    impact_level: str = "low"
    health_status: str = "healthy"


# ========== User Schemas ==========
class UserBase(BaseModel):
    name: str = Field(..., max_length=100)
    department: str | None = Field(None, max_length=100)
    email: EmailStr | None = None


class UserCreate(UserBase):
    wechat_user_id: str = Field(..., max_length=128)


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    wechat_user_id: str
    created_at: datetime
    last_login: datetime | None = None
    is_active: bool = True


class UserTrainingPreferencesResponse(BaseModel):
    voice_mode: str | None = None
    agent_id: str | None = None
    persona_id: str | None = None
    presentation_id: str | None = None
    updated_at: datetime | None = None


class UserTrainingPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_mode: Literal["legacy", "stepfun_realtime"] | None = None
    agent_id: str | None = Field(None, max_length=36)
    persona_id: str | None = Field(None, max_length=36)
    presentation_id: str | None = Field(None, max_length=36)
    updated_at: datetime | None = None


# ========== Auth Schemas ==========
class WechatLoginRequest(BaseModel):
    code: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ========== Scenario Schemas ==========
class ScenarioBase(BaseModel):
    scenario_type: ScenarioType = ScenarioType.SALES
    name: str = Field(..., max_length=100)
    description: str | None = None
    persona_prompt: str | None = None  # For sales bot


class ScenarioResponse(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)
    scenario_id: UUID
    is_active: bool = True
    created_at: datetime


# ========== Presentation Schemas ==========
class PresentationBase(BaseModel):
    title: str = Field(..., max_length=200)


class PresentationCreate(PresentationBase):
    pass  # file is handled separately as multipart


class PresentationResponse(PresentationBase):
    model_config = ConfigDict(from_attributes=True)
    presentation_id: UUID
    status: PresentationStatus
    upload_date: datetime
    version_number: int
    total_pages: int | None = None
    ocr_progress: float = 0.0
    governance_summary: AssetGovernanceSummary | None = None


class PresentationDetail(PresentationResponse):
    model_config = ConfigDict(from_attributes=True)
    file_url: str
    pages: list["PageResponse"] = []


# ========== Page Schemas ==========
class PageBase(BaseModel):
    page_number: int
    ocr_extracted_text: str | None = None
    image_url: str | None = None


class PageResponse(PageBase):
    model_config = ConfigDict(from_attributes=True)
    page_id: UUID
    presentation_id: UUID
    extraction_confidence: float | None = None
    needs_manual_review: bool = False
    talking_points: list["RequiredTalkingPointResponse"] = []


# ========== Required Talking Point Schemas ==========
class RequiredTalkingPointBase(BaseModel):
    description: str


class RequiredTalkingPointCreate(RequiredTalkingPointBase):
    pass


class RequiredTalkingPointResponse(RequiredTalkingPointBase):
    model_config = ConfigDict(from_attributes=True)
    point_id: UUID
    page_id: UUID
    is_ai_generated: bool = False
    confirmed_by_admin: bool = True
    created_at: datetime


# ========== Forbidden Word Schemas ==========
class ForbiddenWordBase(BaseModel):
    phrase: str = Field(..., max_length=500)
    suggested_alternative: str | None = None
    page_id: UUID | None = None  # If None, applies to entire presentation


class ForbiddenWordCreate(ForbiddenWordBase):
    pass


class ForbiddenWordResponse(ForbiddenWordBase):
    model_config = ConfigDict(from_attributes=True)
    word_id: UUID
    presentation_id: UUID | None = None
    is_regex: bool = False


# ========== Practice Session Schemas ==========
class SessionBase(BaseModel):
    scenario_type: ScenarioType = ScenarioType.SALES
    presentation_id: UUID | None = None  # Required for presentation scenario
    sales_persona: str | None = Field(
        default=None,
        description="Deprecated legacy field. Use agent_id + persona_id instead.",
        deprecated=True,
    )
    scenario_id: UUID | None = None  # Optional scenario ID


class SessionCreate(SessionBase):
    # Agent Platform fields (R12: Session Management Enhancement)
    agent_id: UUID | None = None  # Optional Agent ID for enhanced sessions
    persona_id: UUID | None = None  # Optional Persona ID for enhanced sessions
    voice_mode: Literal["legacy", "stepfun_realtime"] | None = Field(
        None, description="Voice mode override: legacy | stepfun_realtime"
    )
    runtime_profile_id: UUID | None = Field(
        None, description="Optional runtime profile override"
    )
    focus_intent: dict[str, Any] | None = Field(
        default=None,
        description="Optional retry focus intent carried forward from a prior report, including sales issue/goal or presentation page focus.",
    )


class SessionUpdate(BaseModel):
    status: SessionStatus | None = None
    current_page: int | None = None


class SessionLifecycleRequest(BaseModel):
    action: SessionLifecycleAction


class SessionLifecycleResponse(BaseModel):
    session_id: UUID
    previous_status: SessionStatus
    status: SessionStatus
    ai_state: Literal["listening", "idle"]
    changed: bool
    scenario_type: ScenarioType
    runtime_subject: TrainingRuntimeSubject = (
        TrainingRuntimeSubject.TRAINING_SCENARIO_RUNTIME
    )
    start_time: datetime
    end_time: datetime | None = None
    total_duration_seconds: int | None = None


class SessionResponse(BaseModel):
    """Response for practice session."""

    model_config = ConfigDict(from_attributes=True)
    session_id: UUID
    user_id: UUID
    scenario_id: UUID
    scenario_type: ScenarioType = ScenarioType.SALES
    presentation_id: UUID | None = None
    agent_id: UUID | None = None
    persona_id: UUID | None = None
    voice_mode: str | None = None
    runtime_subject: TrainingRuntimeSubject = (
        TrainingRuntimeSubject.TRAINING_SCENARIO_RUNTIME
    )
    runtime_descriptor: TrainingRuntimeDescriptor | None = None
    runtime_profile_id: UUID | None = None
    voice_policy_snapshot: dict[str, Any] | None = None
    voice_policy_snapshot_ref: "VoicePolicySnapshotReference | None" = None
    effectiveness_snapshot: dict[str, Any] | None = None
    status: SessionStatus
    start_time: datetime
    end_time: datetime | None = None
    current_page: int | None = None


class SessionDetail(SessionResponse):
    model_config = ConfigDict(from_attributes=True)
    presentation: PresentationResponse | None = None
    interruption_count: int = 0
    total_duration_seconds: int | None = None
    interruption_events: list["InterruptionEventResponse"] = []


class PresentationReviewDimensionScore(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    description: str = ""


class PresentationReviewPageIssueCluster(BaseModel):
    issue_type: Literal[
        "off_page",
        "missing_point",
        "overlong_explanation",
        "forbidden_word",
        "weak_qa_handling",
    ]
    summary: str
    evidence: list[str] = Field(default_factory=list)
    turn_numbers: list[int] = Field(default_factory=list)
    linked_points: list[str] = Field(default_factory=list)
    linked_phrases: list[str] = Field(default_factory=list)
    related_page_numbers: list[int] = Field(default_factory=list)


class PresentationReviewPageSummary(BaseModel):
    page_number: int
    stage_number: int
    start_turn: int
    end_turn: int
    average_score: float = Field(..., ge=0, le=100)
    key_points: list[str] = Field(default_factory=list)
    matched_required_points: list[str] = Field(default_factory=list)
    missing_required_points: list[str] = Field(default_factory=list)
    issue_clusters: list[PresentationReviewPageIssueCluster] = Field(default_factory=list)
    summary: str


class PresentationRequiredTalkingPointCoverage(BaseModel):
    status: Literal["complete", "degraded"]
    total: int = 0
    covered: int = 0
    missing: int = 0
    coverage_ratio: float = Field(..., ge=0, le=1)


class PresentationReviewDiagnostics(BaseModel):
    has_page_metadata: bool
    pages_with_messages: int = 0
    total_pages: int = 0
    page_coverage_ratio: float = Field(..., ge=0, le=1)
    required_points_total: int = 0
    required_points_covered: int = 0
    required_points_missing: int = 0
    required_coverage_ratio: float = Field(..., ge=0, le=1)
    degraded_reasons: list[str] = Field(default_factory=list)
    page_issue_cluster_count: int = 0
    page_issue_types: list[str] = Field(default_factory=list)


class PresentationReview(BaseModel):
    overall_score: float = Field(..., ge=0, le=100)
    dimension_scores: list[PresentationReviewDimensionScore] = Field(default_factory=list)
    page_summaries: list[PresentationReviewPageSummary] = Field(default_factory=list)
    required_talking_points: PresentationRequiredTalkingPointCoverage
    issue_counts: dict[str, int] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    detailed_feedback: str
    has_page_metadata: bool
    coverage_status: Literal["complete", "degraded"]
    diagnostics: PresentationReviewDiagnostics


# ========== Voice Policy Snapshot Schemas ==========
class VoicePolicyRuntimeBinding(BaseModel):
    """Compact industry-pack binding summary persisted into report/replay evidence."""

    industry_pack_strategy: str
    customer_pressure_source: str
    sales_focus: str = ""
    value_axes: list[str] = Field(default_factory=list)
    objection_axes: list[str] = Field(default_factory=list)
    question_strategy: str = ""
    revisit_on_evasion: bool = False
    require_evidence: bool = False
    expected_customer_questions: list[str] = Field(default_factory=list)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    runtime_impacts: list[str] = Field(default_factory=list)


class VoicePolicySnapshotReference(BaseModel):
    """Immutable voice policy baseline reference stored at session creation time."""

    voice_mode: str | None = None
    runtime_profile_id: str | None = None
    instruction_contract_hash: str | None = None
    network_access_mode: str | None = None
    tool_policy: dict[str, Any] = Field(default_factory=dict)
    knowledge_base_ids: list[str] = Field(default_factory=list)
    source: dict[str, str] = Field(default_factory=dict)
    resolved_at: str | None = None
    runtime_binding: VoicePolicyRuntimeBinding | None = None
    agent_persona_override_config: dict[str, Any] | None = None


# ========== Interruption Event Schemas ==========
class InterruptionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: UUID
    session_id: UUID
    timestamp: datetime
    interruption_type: InterruptionType
    trigger_content: str | None = None
    ai_response: str
    detection_latency_ms: int | None = None


# ========== Audio Audit Schemas ==========
class AudioAuditSegmentSchema(BaseModel):
    """Single audio segment metadata for the learner-facing audit trail."""
    segment_sequence: int = Field(..., description="Zero-based segment index within the session")
    created_at: datetime | None = Field(None, description="Segment registration timestamp")
    duration_ms: int | None = Field(None, description="Segment duration in milliseconds")
    size_bytes: int | None = Field(None, description="Segment upload size in bytes")
    upload_status: str = Field(..., description="Upload status: pending | uploaded | failed")
    playback_path: str | None = Field(None, description="Stable handoff path for signed-URL redirect")
    error_message: str | None = Field(None, description="Compact error token when upload_status is 'failed'")


class AudioAuditSummarySchema(BaseModel):
    """Aggregated audio recording status for a session."""
    recording_status: str = Field(..., description="Raw recording status from runtime metrics")
    total_segments: int = Field(0, description="Total segments registered")
    uploaded_segments: int = Field(0, description="Segments successfully uploaded")
    failed_segments: int = Field(0, description="Segments that failed to upload")
    total_bytes: int = Field(0, description="Total uploaded bytes across all segments")
    latest_segment_sequence: int | None = Field(None, description="Highest segment sequence seen")
    storage_prefix: str | None = Field(None, description="OSS storage prefix for this session's audio")
    last_uploaded_at: str | None = Field(None, description="ISO-8601 timestamp of last upload")
    learner_status: Literal["available", "partial", "missing"] = Field(
        "missing",
        description="Derived learner-facing status: available if all uploaded, partial if some, missing if none",
    )
    degraded_reasons: list[str] = Field(
        default_factory=list,
        description="List of degradation reasons: 'upload_failed' if any segments failed, 'segments_pending' if any are still pending",
    )


class AudioAuditPayloadSchema(BaseModel):
    """Full audio audit payload included in report and replay responses."""
    summary: AudioAuditSummarySchema
    segments: list[AudioAuditSegmentSchema] = Field(default_factory=list)


# ========== Session Report Schema ==========
class SessionReport(BaseModel):
    session_id: UUID
    scenario_type: ScenarioType = ScenarioType.SALES
    logic_score: float = Field(..., ge=0, le=100)
    accuracy_score: float = Field(..., ge=0, le=100)
    completeness_score: float = Field(..., ge=0, le=100)
    overall_score: float = Field(..., ge=0, le=100)
    suggestions: list[str]
    audio_url: str | None = None
    transcript_url: str | None = None
    voice_policy_snapshot_ref: VoicePolicySnapshotReference | None = None
    effectiveness_snapshot: dict[str, Any] | None = None
    pass_flags: dict[str, bool] | None = None
    main_capability_passed: bool | None = None
    overall_result: Literal["pass", "strong_pass", "fail"] | None = None
    main_issue: dict[str, Any] | None = None
    next_goal: dict[str, Any] | None = None
    stage_summary: list[dict[str, Any]] = Field(default_factory=list)
    evaluable: bool | None = None
    not_evaluable_reason: str | None = None
    evidence_completeness: dict[str, Any] | None = None
    canonical_evaluation_kernel: dict[str, Any] | None = None
    compatibility_readers: dict[str, Any] | None = None
    presentation_review: PresentationReview | None = None
    retry_entry: dict[str, Any] | None = None
    audio_audit: "AudioAuditPayloadSchema | None" = None
    conclusion_evidence: dict[str, Any] | None = None
    evidence_degradation: dict[str, Any] | None = None


# ========== Manager Intervention Schemas ==========
class ManagerInterventionBase(BaseModel):
    user_id: UUID
    issue_family: str = Field(..., min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("issue_family")
    @classmethod
    def validate_issue_family(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("issue_family cannot be empty")
        return cleaned

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ManagerInterventionCreate(ManagerInterventionBase):
    due_state: ManagerInterventionDueState = ManagerInterventionDueState.PENDING
    reminder_status: ManagerInterventionReminderStatus = (
        ManagerInterventionReminderStatus.NOT_SENT
    )
    resolving_session_id: UUID | None = None


class ManagerInterventionUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    due_state: ManagerInterventionDueState | None = None
    reminder_status: ManagerInterventionReminderStatus | None = None
    resolving_session_id: UUID | None = None

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ManagerInterventionReminderRequest(BaseModel):
    user_id: UUID
    intervention_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ManagerInterventionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    intervention_id: UUID
    manager_user_id: UUID
    user_id: UUID
    issue_family: str
    note: str | None = None
    due_state: ManagerInterventionDueState
    reminder_status: ManagerInterventionReminderStatus
    reminder_sent_at: datetime | None = None
    resolving_session_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ManagerInterventionListResponse(BaseModel):
    items: list[ManagerInterventionResponse] = Field(default_factory=list)
    total: int = 0


# ========== Enhanced Session Report Schema (R12) ==========
class DimensionScore(BaseModel):
    """Score for a single dimension"""

    name: str
    score: float = Field(..., ge=0, le=100)
    weight: float = Field(default=1.0, ge=0, le=1)


class SessionHighlight(BaseModel):
    """Highlight moment from session"""

    message_id: str
    turn_number: int
    highlight_type: str  # good|bad|neutral
    reason: str
    content: str


class EnhancedSessionReport(BaseModel):
    """Enhanced session report with dimension scores - R12.3"""

    session_id: UUID
    overall_score: float = Field(..., ge=0, le=100)
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    highlights: list[SessionHighlight] = Field(default_factory=list)
    total_turns: int = 0
    duration_seconds: int | None = None
    agent_name: str | None = None
    persona_name: str | None = None
    voice_policy_snapshot_ref: VoicePolicySnapshotReference | None = None


# ========== Session Stats Schema (R12.4) ==========
class SessionStats(BaseModel):
    """User session statistics"""

    total_sessions: int = 0
    weekly_sessions: int = 0
    average_score: float = 0.0
    completed_sessions: int = 0
    total_practice_minutes: int = 0


# ========== Practice History Schema ==========
class PracticeHistoryResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# ========== Leaderboard Schemas ==========
class LeaderboardEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rank: int
    user: UserResponse
    average_score: float
    total_sessions: int


# ========== Analytics Dashboard Schema ==========
class AnalyticsDashboard(BaseModel):
    total_sessions: int
    completion_rate: float
    average_score: float
    most_common_gaps: list[str]
    score_distribution: dict


# ========== WebSocket Messages ==========
class AudioChunkMessage(BaseModel):
    audio: str  # base64 encoded
    sequence: int
    sample_rate: int = 16000


class UserSpeakingMessage(BaseModel):
    speaking: bool


class PageChangeMessage(BaseModel):
    page_number: int


class PauseMessage(BaseModel):
    pass


class ResumeMessage(BaseModel):
    pass


# Update forward references
PageResponse.model_rebuild()
PresentationDetail.model_rebuild()
SessionResponse.model_rebuild()
SessionDetail.model_rebuild()
