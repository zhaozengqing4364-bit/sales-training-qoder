"""
Pydantic Schemas for ConversationMessage and ReplayData

Request/Response schemas for Conversation Replay APIs.
Uses Pydantic v2 with ConfigDict(from_attributes=True).

References:
- Requirements: R9, R10 (Conversation storage and replay)
- Design: Section 11-12, 18 (Message Storage, Replay Service, Data Models)
- API Contract: docs/api-contract/replay.md
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ========== Type Aliases for API ==========
MessageRoleType = str  # "user" | "assistant"
HighlightTypeType = str  # "good" | "bad" | "neutral"
SalesStageType = str  # "opening" | "discovery" | "presentation" | "objection" | "closing"
TimelineMarkerTypeType = str  # "stage_change" | "highlight" | "fuzzy_word"


# ========== Nested Schemas ==========

class FuzzyDetectionSchema(BaseModel):
    """Fuzzy word detection result - R6"""
    category: str = Field(..., description="Category: uncertain|filler|vague")
    matched: list[str] = Field(..., description="Matched fuzzy words")
    suggestion: str = Field(..., description="Improvement suggestion")
    severity: str = Field(..., description="Severity: high|medium|low")


class ScoreDimensionSchema(BaseModel):
    """Score dimension with trend - R8"""
    name: str = Field(..., description="Dimension name")
    score: int = Field(..., ge=0, le=100, description="Score 0-100")
    trend: str = Field(default="stable", description="Trend: up|down|stable")
    delta: int = Field(default=0, description="Score change from previous")


class ScoreSnapshotSchema(BaseModel):
    """Score snapshot at a specific turn - R8"""
    overall: int = Field(..., ge=0, le=100, description="Overall score 0-100")
    dimensions: list[ScoreDimensionSchema] = Field(
        default_factory=list,
        description="Dimension scores"
    )


class TimelineMarkerSchema(BaseModel):
    """Timeline marker for replay visualization - R10"""
    timestamp_ms: int = Field(..., ge=0, description="Timestamp in milliseconds")
    type: TimelineMarkerTypeType = Field(
        ...,
        description="Marker type: stage_change|highlight|fuzzy_word"
    )
    label: str = Field(..., description="Display label")
    message_id: str = Field(..., description="Associated message ID")
    highlight_type: HighlightTypeType | None = Field(
        None,
        description="Highlight type: good|bad|neutral"
    )


class StageSummarySchema(BaseModel):
    """Summary for a sales stage - R10"""
    stage: SalesStageType = Field(..., description="Stage ID")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    score: int = Field(..., ge=0, le=100, description="Average score for this stage")


class VoicePolicySnapshotReferenceSchema(BaseModel):
    """Voice policy baseline reference captured at session creation time."""

    voice_mode: str | None = Field(None, description="Resolved voice mode")
    runtime_profile_id: str | None = Field(None, description="Resolved runtime profile ID")
    instruction_contract_hash: str | None = Field(
        None,
        description="Hash of compiled instruction contract captured at session start",
    )
    network_access_mode: str | None = Field(
        None,
        description="Tool network access mode resolved at session start",
    )
    tool_policy: dict[str, Any] = Field(default_factory=dict, description="Resolved tool policy")
    knowledge_base_ids: list[str] = Field(default_factory=list, description="Bound knowledge base IDs")
    source: dict[str, str] = Field(default_factory=dict, description="Policy resolution source map")
    resolved_at: str | None = Field(None, description="ISO8601 policy resolution timestamp")
    agent_persona_override_config: dict[str, Any] | None = Field(
        None,
        description="Agent-persona association override config snapshot",
    )


# ========== ConversationMessage Schemas ==========

class ConversationMessageBase(BaseModel):
    """Base ConversationMessage fields"""
    turn_number: int = Field(..., ge=1, description="Turn number in conversation")
    role: MessageRoleType = Field(..., description="Role: user|assistant")
    content: str = Field(..., description="Message text content")


class ConversationMessageResponse(ConversationMessageBase):
    """Full ConversationMessage response - R9, R10"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Message UUID")
    session_id: str = Field(..., description="Session UUID")
    audio_url: str | None = Field(None, description="Audio file URL")
    timestamp: datetime = Field(..., description="Message timestamp")
    duration_ms: int | None = Field(None, description="Audio duration in milliseconds")

    # Analysis data
    fuzzy_words: list[FuzzyDetectionSchema] | None = Field(
        None,
        description="Detected fuzzy words"
    )
    transcript_metadata: dict[str, Any] | None = Field(
        None,
        description="Transcript normalization metadata"
    )
    sales_stage: SalesStageType | None = Field(
        None,
        description="Sales stage at this turn"
    )
    score_snapshot: ScoreSnapshotSchema | None = Field(
        None,
        description="Score snapshot at this turn"
    )
    ai_feedback: str | None = Field(None, description="AI feedback for this turn")

    # Highlight markers
    is_highlight: bool = Field(default=False, description="Whether this is a key moment")
    highlight_type: HighlightTypeType | None = Field(
        None,
        description="Highlight type: good|bad|neutral"
    )
    highlight_reason: str | None = Field(None, description="Reason for highlight")


class ConversationMessageDetailResponse(ConversationMessageResponse):
    """Detailed ConversationMessage response with suggested response - R10.3"""
    suggested_response: str | None = Field(
        None,
        description="Suggested better response for highlights"
    )


class ConversationMessageListResponse(BaseModel):
    """Paginated ConversationMessage list response - R10.1"""
    messages: list[ConversationMessageResponse]
    total: int = Field(..., description="Total number of messages")


# ========== Highlight Schemas ==========

class HighlightResponse(BaseModel):
    """Highlight message response - R10.3"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Message UUID")
    turn_number: int = Field(..., ge=1, description="Turn number")
    role: MessageRoleType = Field(..., description="Role: user|assistant")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    highlight_type: HighlightTypeType = Field(
        ...,
        description="Highlight type: good|bad|neutral"
    )
    highlight_reason: str | None = Field(None, description="Reason for highlight")
    ai_feedback: str | None = Field(None, description="AI feedback")
    suggested_response: str | None = Field(
        None,
        description="Suggested better response"
    )


class HighlightsResponse(BaseModel):
    """Highlights list response - R10.3"""
    highlights: list[HighlightResponse]
    total_good: int = Field(default=0, ge=0, description="Count of good highlights")
    total_bad: int = Field(default=0, ge=0, description="Count of bad highlights")


# ========== ReplayData Schemas ==========

class ReplayDataResponse(BaseModel):
    """Complete replay data response - R10.2"""
    session_id: str = Field(..., description="Session UUID")
    agent_name: str | None = Field(None, description="Agent name")
    persona_name: str | None = Field(None, description="Persona name")
    voice_policy_snapshot_ref: VoicePolicySnapshotReferenceSchema | None = Field(
        None,
        description="Session voice policy baseline reference",
    )
    total_duration_ms: int = Field(..., ge=0, description="Total duration in milliseconds")
    messages: list[ConversationMessageResponse] = Field(
        ...,
        description="All conversation messages"
    )
    timeline_markers: list[TimelineMarkerSchema] = Field(
        default_factory=list,
        description="Timeline markers for visualization"
    )
    stage_summary: list[StageSummarySchema] = Field(
        default_factory=list,
        description="Summary by sales stage"
    )


# ========== Request Schemas ==========

class SaveMessageRequest(BaseModel):
    """Request schema for saving a message (internal use)"""
    session_id: str = Field(..., description="Session UUID")
    turn_number: int = Field(..., ge=1, description="Turn number")
    role: MessageRoleType = Field(..., description="Role: user|assistant")
    content: str = Field(..., description="Message content")
    audio_url: str | None = Field(None, description="Audio file URL")
    duration_ms: int | None = Field(None, ge=0, description="Audio duration")


class UpdateAnalysisRequest(BaseModel):
    """Request schema for updating message analysis (internal use)"""
    fuzzy_words: list[FuzzyDetectionSchema] | None = None
    sales_stage: SalesStageType | None = None
    score_snapshot: ScoreSnapshotSchema | None = None
    ai_feedback: str | None = None


class MarkHighlightRequest(BaseModel):
    """Request schema for marking a message as highlight (internal use)"""
    highlight_type: HighlightTypeType = Field(
        ...,
        description="Highlight type: good|bad|neutral"
    )
    highlight_reason: str = Field(..., max_length=200, description="Reason for highlight")


# ========== API Response Wrappers ==========
# Following Result[T] pattern from common/error_handling/result.py

class ConversationMessagesSuccessResponse(BaseModel):
    """Success response wrapper for message list"""
    success: bool = True
    data: ConversationMessageListResponse
    trace_id: str | None = None


class ConversationMessageSuccessResponse(BaseModel):
    """Success response wrapper for single message"""
    success: bool = True
    data: ConversationMessageDetailResponse
    trace_id: str | None = None


class ReplayDataSuccessResponse(BaseModel):
    """Success response wrapper for replay data"""
    success: bool = True
    data: ReplayDataResponse
    trace_id: str | None = None


class HighlightsSuccessResponse(BaseModel):
    """Success response wrapper for highlights"""
    success: bool = True
    data: HighlightsResponse
    trace_id: str | None = None


class ConversationErrorResponse(BaseModel):
    """Error response wrapper for conversation operations"""
    success: bool = False
    error: str = Field(..., description="Error code like [SESSION_NOT_FOUND]")
    error_code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    trace_id: str | None = None
