"""
Pydantic Schemas for API validation
Generated from data-model.md and contracts/openapi.yaml
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class InterruptionType(StrEnum):
    FORBIDDEN_WORD = "forbidden_word"
    MISSING_POINT = "missing_point"
    VAGUE_RESPONSE = "vague_response"


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


# ========== Voice Policy Snapshot Schemas ==========
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


# ========== Session Report Schema ==========
class SessionReport(BaseModel):
    session_id: UUID
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
    retry_entry: dict[str, Any] | None = None


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
