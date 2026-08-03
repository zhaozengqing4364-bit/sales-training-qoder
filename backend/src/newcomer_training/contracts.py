"""Stable, provider-neutral contracts for path and activity orchestration."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivityType(StrEnum):
    LESSON = "lesson"
    QUIZ = "quiz"
    AUDIO_ASSESSMENT = "audio_assessment"
    AI_COACH = "ai_coach"
    ASSIGNMENT = "assignment"


class AIDependency(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class StageCompletionRule(StrEnum):
    ALL_REQUIRED = "all_required"
    ALL_ACTIVITIES = "all_activities"


class StageVisibility(StrEnum):
    LEARNER = "learner"
    ASSIGNED_ONLY = "assigned_only"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: int = Field(default=0, ge=0, le=100)
    retry_interval_seconds: int = Field(default=0, ge=0, le=604_800)

    @model_validator(mode="after")
    def require_interval_for_retries(self) -> RetryPolicy:
        if self.max_attempts > 1 and self.retry_interval_seconds < 1:
            raise ValueError("retry_interval_seconds is required when retries are enabled")
        return self


class LessonActivityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Working path revisions deliberately allow an unbound resource.  The
    # validation/publish gates below the draft boundary turn an empty value
    # into a user-actionable blocker.  This keeps "save draft" distinct from
    # "ready to publish" and lets an editor preserve work while a resource is
    # being created in-flow.
    learning_unit_revision_id: str = Field(default="", max_length=160)
    required_checkpoint_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)

    @model_validator(mode="after")
    def checkpoint_ids_are_unique(self) -> LessonActivityConfig:
        if len(set(self.required_checkpoint_ids)) != len(
            self.required_checkpoint_ids
        ):
            raise ValueError("required_checkpoint_ids must be unique")
        return self


class QuizActivityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quiz_revision_id: str = Field(default="", max_length=160)


class AudioAssessmentActivityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audio_material_revision_id: str = Field(default="", max_length=160)
    scoring_scheme_revision_id: str = Field(default="", max_length=160)
    allowed_recording_modes: tuple[Literal["browser", "file"], ...] = (
        "browser",
        "file",
    )
    max_duration_seconds: int = Field(default=1_800, ge=1, le=1_800)
    max_size_bytes: int = Field(default=100 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    baseline_only: bool = False


class AICoachActivityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    coach_profile_revision_id: str = Field(default="", max_length=160)


class AssignmentActivityConfig(BaseModel):
    """The launch assignment is the fixed three-segment async recording flow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_revision_id: str = Field(default="", max_length=160)
    scoring_scheme_revision_id: str = Field(
        default="",
        max_length=160,
    )
    allowed_recording_modes: tuple[Literal["browser", "file"], ...] = (
        "browser",
        "file",
    )
    max_duration_seconds: int = Field(default=1_800, ge=1, le=1_800)
    max_size_bytes: int = Field(default=100 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    segment_ids: tuple[
        Literal["discovery"], Literal["objection"], Literal["commitment"]
    ] = ("discovery", "objection", "commitment")


class ActivityDefinition(BaseModel):
    """Common immutable activity definition inherited by the closed union."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    activity_id: str = Field(min_length=1, max_length=160)
    type: ActivityType
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1_000)
    why_it_matters: str = Field(min_length=1, max_length=1_000)
    steps: tuple[str, ...] = Field(min_length=1, max_length=50)
    success_criteria: tuple[str, ...] = Field(min_length=1, max_length=50)
    competency_keys: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    estimated_minutes: int = Field(ge=1, le=1_440)
    required: bool = True
    prerequisite_activity_ids: tuple[str, ...] = Field(
        default_factory=tuple, max_length=100
    )
    ai_dependency: AIDependency = AIDependency.NONE
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)

    @model_validator(mode="after")
    def prerequisites_are_unique_and_not_self(self) -> ActivityDefinition:
        prerequisites = self.prerequisite_activity_ids
        if len(set(prerequisites)) != len(prerequisites):
            raise ValueError("prerequisite_activity_ids must be unique")
        if self.activity_id in prerequisites:
            raise ValueError("an activity cannot depend on itself")
        if len(set(self.competency_keys)) != len(self.competency_keys):
            raise ValueError("competency_keys must be unique")
        return self


class LessonActivityDefinition(ActivityDefinition):
    type: Literal[ActivityType.LESSON]
    config: LessonActivityConfig


class QuizActivityDefinition(ActivityDefinition):
    type: Literal[ActivityType.QUIZ]
    config: QuizActivityConfig


class AudioAssessmentActivityDefinition(ActivityDefinition):
    type: Literal[ActivityType.AUDIO_ASSESSMENT]
    config: AudioAssessmentActivityConfig


class AICoachActivityDefinition(ActivityDefinition):
    type: Literal[ActivityType.AI_COACH]
    config: AICoachActivityConfig


class AssignmentActivityDefinition(ActivityDefinition):
    type: Literal[ActivityType.ASSIGNMENT]
    config: AssignmentActivityConfig


ActivityDefinitionValue = Annotated[
    LessonActivityDefinition | QuizActivityDefinition | AudioAssessmentActivityDefinition | AICoachActivityDefinition | AssignmentActivityDefinition,
    Field(discriminator="type"),
]


class StageDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_id: str = Field(min_length=1, max_length=160)
    sequence: int = Field(ge=1, le=10_000)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1_000)
    entry_conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    completion_rule: StageCompletionRule = StageCompletionRule.ALL_REQUIRED
    visibility: StageVisibility = StageVisibility.LEARNER
    activities: tuple[ActivityDefinitionValue, ...] = Field(
        min_length=1, max_length=500
    )


class PathRevisionDraft(BaseModel):
    """A revision payload before persistence adds stable path/revision identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["newcomer_training_path_v2"] = (
        "newcomer_training_path_v2"
    )
    title: str = Field(min_length=1, max_length=200)
    revision_label: str = Field(min_length=1, max_length=120)
    stages: tuple[StageDefinition, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_graph(self) -> PathRevisionDraft:
        stage_ids: set[str] = set()
        stage_sequences: set[int] = set()
        seen_activities: set[str] = set()
        for stage in sorted(self.stages, key=lambda item: item.sequence):
            if stage.stage_id in stage_ids:
                raise ValueError("stage_id must be unique")
            if stage.sequence in stage_sequences:
                raise ValueError("stage sequence must be unique")
            stage_ids.add(stage.stage_id)
            stage_sequences.add(stage.sequence)
            for activity in stage.activities:
                if activity.activity_id in seen_activities:
                    raise ValueError("activity_id must be unique across the revision")
                missing = set(activity.prerequisite_activity_ids) - seen_activities
                if missing:
                    raise ValueError(
                        "activity prerequisites must reference earlier activities"
                    )
                seen_activities.add(activity.activity_id)
        return self


__all__ = [
    "ActivityDefinition",
    "ActivityDefinitionValue",
    "ActivityType",
    "AICoachActivityConfig",
    "AssignmentActivityConfig",
    "AudioAssessmentActivityConfig",
    "LessonActivityConfig",
    "PathRevisionDraft",
    "QuizActivityConfig",
    "RetryPolicy",
    "StageDefinition",
]
