from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum_practice.schema_types import ExaminerAgentStatus, LearnerLevel


def _default_allowed_levels() -> list[LearnerLevel]:
    return ["conservative", "beginner", "intermediate", "advanced"]


class ExaminerLearnerLevelStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_level: LearnerLevel = "conservative"
    allowed_levels: list[LearnerLevel] = Field(
        default_factory=_default_allowed_levels,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_default_is_allowed(self) -> ExaminerLearnerLevelStrategy:
        if self.default_level not in self.allowed_levels:
            raise ValueError("default_level must be included in allowed_levels")
        return self


class ExaminerTimeoutConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_seconds: int = Field(..., ge=1, le=1500)


class ExaminerAgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    question_source_ids: list[str] = Field(default_factory=list)
    learner_level_strategy: ExaminerLearnerLevelStrategy = Field(
        default_factory=ExaminerLearnerLevelStrategy
    )
    scoring_policy_id: str = Field(..., min_length=1, max_length=36)
    timeout_config: ExaminerTimeoutConfig
    safety_config: dict[str, object] = Field(default_factory=dict)
    prompt_config: dict[str, object] = Field(default_factory=dict)
    simulation_config: dict[str, object] = Field(default_factory=dict)


class ExaminerAgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    question_source_ids: list[str] | None = None
    learner_level_strategy: ExaminerLearnerLevelStrategy | None = None
    scoring_policy_id: str | None = Field(None, min_length=1, max_length=36)
    timeout_config: ExaminerTimeoutConfig | None = None
    safety_config: dict[str, object] | None = None
    prompt_config: dict[str, object] | None = None
    simulation_config: dict[str, object] | None = None


class ExaminerAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    examiner_agent_id: str
    name: str
    description: str | None = None
    question_source_ids: list[str]
    learner_level_strategy: dict[str, object]
    scoring_policy_id: str
    timeout_config: dict[str, object]
    safety_config: dict[str, object]
    prompt_config: dict[str, object]
    simulation_config: dict[str, object]
    status: ExaminerAgentStatus
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object


class ExaminerAgentListResponse(BaseModel):
    items: list[ExaminerAgentResponse]
    total: int


class ExaminerAgentSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_level: LearnerLevel | None = None
    sample_answer: str = Field(..., min_length=1, max_length=8000)
    question_id: str | None = Field(None, min_length=1, max_length=36)


class ExaminerAgentSimulationResponse(BaseModel):
    mode: Literal["dry_run"] = "dry_run"
    mutates_records: bool = False
    examiner_agent_id: str
    selected_question_id: str
    learner_level: LearnerLevel
    scoring_policy_id: str
    timeout_seconds: int
    result: dict[str, object]
