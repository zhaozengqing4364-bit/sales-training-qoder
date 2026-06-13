from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachInteractionInternalV1,
    AiCoachInteractionPublicV1,
    AiCoachNextActionV1,
    AiCoachScoreResultV1,
)

AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION: Literal["ai_coach_chat_response_v1"] = (
    "ai_coach_chat_response_v1"
)

AiCoachUiEventTypeV1: TypeAlias = Literal[
    "assistant_text",
    "quiz_card",
    "quiz_result",
    "explanation_card",
    "summary_card",
    "followup_prompt",
]
AiCoachUiEventStatusV1: TypeAlias = Literal["pending", "submitted", "scored", "failed"]
AiCoachChatResumeStrategyV1: TypeAlias = Literal[
    "latest_active_or_new",
    "latest_in_progress",
    "new",
]
AiCoachChatCommandV1: TypeAlias = Literal[
    "continue",
    "explain",
    "switch_scenario",
    "summarize",
    "end",
    "retry",
]
AiCoachChatSessionPhaseV1: TypeAlias = Literal[
    "starting",
    "answering",
    "reviewing",
    "choosing",
    "summarizing",
    "completed",
]
AiCoachChatStreamEventTypeV1: TypeAlias = Literal[
    "status",
    "session_snapshot",
    "error",
]
AiCoachChatStreamPhaseV1: TypeAlias = Literal[
    "resolving_session",
    "creating_session",
    "session_ready",
    "saving_user_message",
    "scoring_answer",
    "answer_scored",
    "deciding_next_action",
    "generating_first_card",
    "generating_next_card",
    "completed",
    "failed",
]


class AiCoachQuizCardPayloadInternalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction: AiCoachInteractionInternalV1
    explanation: str | None = Field(None, max_length=2000)


class AiCoachQuizCardPayloadPublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction: AiCoachInteractionPublicV1
    explanation: str | None = Field(None, max_length=2000)


class AiCoachExplanationCardPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    body: str = Field(..., min_length=1, max_length=4000)


class AiCoachSummaryCardPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    items: list[str] = Field(default_factory=list, min_length=1, max_length=8)
    score_percent: float | None = Field(None, ge=0, le=100)
    mastered: bool | None = None
    strengths: list[str] = Field(default_factory=list, max_length=5)
    weaknesses: list[str] = Field(default_factory=list, max_length=5)
    next_steps: list[str] = Field(default_factory=list, max_length=5)


class AiCoachFollowupPromptPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompts: list[str] = Field(default_factory=list, min_length=1, max_length=4)


class AiCoachAssistantTextPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=4000)


class AiCoachQuizResultPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_result: AiCoachScoreResultV1


class AiCoachCoachStatePublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_phase: AiCoachChatSessionPhaseV1
    active_event_id: str | None = Field(None, max_length=36)
    auto_step_count: int = Field(..., ge=0)
    answered_card_count: int = Field(..., ge=0)
    correct_streak: int = Field(..., ge=0)
    incorrect_streak: int = Field(..., ge=0)
    current_focus: str | None = Field(None, max_length=120)
    difficulty: Literal["warmup", "normal", "challenge"]
    last_action: AiCoachNextActionV1 | None = None
    can_auto_advance: bool
    stopped_reason: str | None = Field(None, max_length=200)


AiCoachUiEventInternalPayloadV1: TypeAlias = (
    AiCoachQuizCardPayloadInternalV1
    | AiCoachExplanationCardPayloadV1
    | AiCoachSummaryCardPayloadV1
    | AiCoachFollowupPromptPayloadV1
    | AiCoachAssistantTextPayloadV1
    | AiCoachQuizResultPayloadV1
)
AiCoachUiEventPublicPayloadV1: TypeAlias = (
    AiCoachQuizCardPayloadPublicV1
    | AiCoachExplanationCardPayloadV1
    | AiCoachSummaryCardPayloadV1
    | AiCoachFollowupPromptPayloadV1
    | AiCoachAssistantTextPayloadV1
    | AiCoachQuizResultPayloadV1
)


class AiCoachChatUiEventInternalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: AiCoachUiEventTypeV1
    payload: AiCoachUiEventInternalPayloadV1

    @model_validator(mode="after")
    def validate_payload_matches_type(self) -> AiCoachChatUiEventInternalV1:
        match self.type:
            case "quiz_card":
                if isinstance(self.payload, AiCoachQuizCardPayloadInternalV1):
                    return self
            case "explanation_card":
                if isinstance(self.payload, AiCoachExplanationCardPayloadV1):
                    return self
            case "summary_card":
                if isinstance(self.payload, AiCoachSummaryCardPayloadV1):
                    return self
            case "followup_prompt":
                if isinstance(self.payload, AiCoachFollowupPromptPayloadV1):
                    return self
            case "assistant_text":
                if isinstance(self.payload, AiCoachAssistantTextPayloadV1):
                    return self
            case "quiz_result":
                if isinstance(self.payload, AiCoachQuizResultPayloadV1):
                    return self
        raise ValueError(f"payload does not match ui event type {self.type}")


class AiCoachChatResponseInternalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai_coach_chat_response_v1"] = (
        AI_COACH_CHAT_RESPONSE_SCHEMA_VERSION
    )
    assistant_text: str = Field(..., min_length=1, max_length=4000)
    ui_events: list[AiCoachChatUiEventInternalV1] = Field(
        default_factory=list,
        max_length=8,
    )


class AiCoachChatSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str = Field(..., min_length=1, max_length=80)
    resume_strategy: AiCoachChatResumeStrategyV1 | None = None


class AiCoachChatMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(None, min_length=1, max_length=2000)
    command: AiCoachChatCommandV1 | None = None
    event_id: str | None = Field(None, min_length=1, max_length=36)

    @model_validator(mode="after")
    def validate_content_or_command(self) -> AiCoachChatMessageCreate:
        if self.command is None and not (self.content or "").strip():
            raise ValueError("content or command is required")
        return self


class AiCoachChatEventAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_payload: AiCoachAnswerPayloadV1


class AiCoachChatMessagePublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(..., min_length=1, max_length=36)
    role: Literal["user", "assistant"]
    content: str
    order_index: int = Field(..., ge=1)
    created_at: datetime


class AiCoachUiEventPublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, max_length=36)
    message_id: str = Field(..., min_length=1, max_length=36)
    type: AiCoachUiEventTypeV1
    status: AiCoachUiEventStatusV1
    payload: AiCoachUiEventPublicPayloadV1
    answer_payload: AiCoachAnswerPayloadV1 | None = None
    score_result: AiCoachScoreResultV1 | None = None
    order_index: int = Field(..., ge=1)
    created_at: datetime


class AiCoachChatSessionPublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=36)
    module_key: str = Field(..., min_length=1, max_length=80)
    status: Literal["in_progress", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    messages: list[AiCoachChatMessagePublicV1] = Field(default_factory=list)
    ui_events: list[AiCoachUiEventPublicV1] = Field(default_factory=list)
    coach_state: AiCoachCoachStatePublicV1 | None = None


class AiCoachChatStreamStatusEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["status"] = "status"
    phase: AiCoachChatStreamPhaseV1
    message: str = Field(..., min_length=1, max_length=300)
    session_id: str | None = Field(None, max_length=36)


class AiCoachChatStreamSessionSnapshotEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["session_snapshot"] = "session_snapshot"
    phase: AiCoachChatStreamPhaseV1 = "session_ready"
    session: AiCoachChatSessionPublicV1


class AiCoachChatStreamErrorEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    phase: Literal["failed"] = "failed"
    error_code: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=300)
    recoverable: bool = True


AiCoachChatStreamEventV1: TypeAlias = (
    AiCoachChatStreamStatusEventV1
    | AiCoachChatStreamSessionSnapshotEventV1
    | AiCoachChatStreamErrorEventV1
)
