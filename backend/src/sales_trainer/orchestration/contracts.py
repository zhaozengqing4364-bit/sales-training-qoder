"""Strict domain contracts for newcomer-training path orchestration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ActivityType = Literal[
    "lesson",
    "quiz",
    "audio_assessment",
    "realtime_roleplay",
    "ai_coach",
    "assignment",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LessonConfig(StrictModel):
    learning_content_id: str = Field(min_length=1, max_length=36)
    completion_mode: Literal["all_chapters", "learner_confirmed"] = "all_chapters"


class QuizConfig(StrictModel):
    exam_paper_id: str = Field(min_length=1, max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class AudioAssessmentConfig(StrictModel):
    scoring_rubric_id: str = Field(min_length=1, max_length=36)
    material_id: str | None = Field(default=None, min_length=1, max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class RealtimeRoleplayConfig(StrictModel):
    practice_template_id: str = Field(min_length=1, max_length=36)
    runtime_profile_id: str = Field(min_length=1, max_length=120)
    completion_mode: Literal["session_completed", "scored"] = "session_completed"


class AiCoachActivityConfig(StrictModel):
    coach_profile_id: str = Field(min_length=1, max_length=120)
    completion_mode: Literal["session_completed", "goal_reached"] = "session_completed"


class AssignmentConfig(StrictModel):
    submission_type: Literal["text", "file", "text_or_file"]
    review_mode: Literal["automatic_complete", "manual_review"]
    max_file_size_bytes: int = Field(
        default=10_485_760,
        ge=1,
        le=52_428_800,
    )


class ActivityBase(StrictModel):
    activity_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    prerequisites: list[str] = Field(default_factory=list, max_length=50)


class LessonActivity(ActivityBase):
    type: Literal["lesson"]
    config: LessonConfig


class QuizActivity(ActivityBase):
    type: Literal["quiz"]
    config: QuizConfig


class AudioAssessmentActivity(ActivityBase):
    type: Literal["audio_assessment"]
    config: AudioAssessmentConfig


class RealtimeRoleplayActivity(ActivityBase):
    type: Literal["realtime_roleplay"]
    config: RealtimeRoleplayConfig


class AiCoachActivity(ActivityBase):
    type: Literal["ai_coach"]
    config: AiCoachActivityConfig


class AssignmentActivity(ActivityBase):
    type: Literal["assignment"]
    config: AssignmentConfig


ActivityConfig = Annotated[
    LessonActivity
    | QuizActivity
    | AudioAssessmentActivity
    | RealtimeRoleplayActivity
    | AiCoachActivity
    | AssignmentActivity,
    Field(discriminator="type"),
]


class CompletionPolicy(StrictModel):
    mode: Literal["all_required", "at_least_count"]
    activity_ids: list[str] = Field(default_factory=list, max_length=200)
    count: int | None = Field(default=None, ge=1, le=200)


class AudienceRule(StrictModel):
    learner_levels: list[str] = Field(default_factory=list, max_length=50)
    roles: list[str] = Field(default_factory=list, max_length=50)
    departments: list[str] = Field(default_factory=list, max_length=100)


class ModuleConfig(StrictModel):
    module_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    estimated_minutes: int | None = Field(default=None, ge=1, le=10_080)
    audience_rule: AudienceRule = Field(default_factory=AudienceRule)
    prerequisites: list[str] = Field(default_factory=list, max_length=50)
    completion_policy: CompletionPolicy
    activities: list[ActivityConfig] = Field(default_factory=list, max_length=200)


class PhaseConfig(StrictModel):
    phase_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    order_index: int = Field(ge=1)
    required: bool = True
    modules: list[ModuleConfig] = Field(default_factory=list, max_length=100)


class TrainingPathPayload(StrictModel):
    schema_version: Literal["newcomer_training_orchestration_v1"] = (
        "newcomer_training_orchestration_v1"
    )
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    phases: list[PhaseConfig] = Field(default_factory=list, max_length=50)


class PathIssueResponse(StrictModel):
    code: str
    message: str
    object_id: str
    field_path: str
    severity: str = "error"


class PathValidationResponse(StrictModel):
    can_publish: bool
    issues: list[PathIssueResponse] = Field(default_factory=list)


class TrainingPathConfigResponse(StrictModel):
    active_revision_id: str | None
    active_revision_no: int | None
    working_revision_id: str | None
    payload: TrainingPathPayload
    validation: PathValidationResponse | None = None


class JourneyNextAction(StrictModel):
    activity_id: str
    activity_type: ActivityType
    action_key: str
    label: str


class JourneyActivityProgress(StrictModel):
    activity_id: str
    activity_type: ActivityType
    title: str
    description: str | None = None
    required: bool
    estimated_minutes: int | None = None
    status: str
    completed: bool
    passed: bool | None = None
    score: float | None = None
    max_score: float | None = None
    locked: bool = False
    lock_reason: str | None = None
    action_key: str | None = None
    is_primary_next_action: bool = False


class JourneyModuleProgress(StrictModel):
    module_id: str
    title: str
    description: str | None = None
    required: bool
    estimated_minutes: int | None = None
    status: str
    completed: bool
    completed_count: int
    total_required: int
    percent: float
    locked: bool = False
    lock_reason: str | None = None
    activities: list[JourneyActivityProgress] = Field(default_factory=list)


class JourneyPhaseProgress(StrictModel):
    phase_id: str
    title: str
    description: str | None = None
    required: bool
    status: str
    completed: bool
    completed_count: int
    total_required: int
    percent: float
    locked: bool = False
    lock_reason: str | None = None
    modules: list[JourneyModuleProgress] = Field(default_factory=list)


class JourneyProgressSummary(StrictModel):
    completed: bool
    completed_count: int
    total_required: int
    percent: float


class JourneyResponse(StrictModel):
    enrollment_id: str
    path_revision_id: str
    path_title: str
    phases: list[JourneyPhaseProgress] = Field(default_factory=list)
    progress: JourneyProgressSummary
    primary_next_action: JourneyNextAction | None = None


class ModuleDetailResponse(StrictModel):
    enrollment_id: str
    path_revision_id: str
    phase_id: str
    module: JourneyModuleProgress


class LessonRunnerDescriptor(StrictModel):
    type: Literal["lesson"] = "lesson"
    learning_content_id: str
    completion_mode: Literal["all_chapters", "learner_confirmed"]


class QuizRunnerDescriptor(StrictModel):
    type: Literal["quiz"] = "quiz"
    exam_paper_id: str
    pass_score: float
    max_attempts: int | None = None


class AudioRunnerDescriptor(StrictModel):
    type: Literal["audio_assessment"] = "audio_assessment"
    material_id: str | None = None
    material_version_id: str | None = None
    material_title: str | None = None
    pass_score: float
    max_attempts: int | None = None


class RealtimeRunnerDescriptor(StrictModel):
    type: Literal["realtime_roleplay"] = "realtime_roleplay"


class AiCoachRunnerDescriptor(StrictModel):
    type: Literal["ai_coach"] = "ai_coach"


class AssignmentRunnerDescriptor(StrictModel):
    type: Literal["assignment"] = "assignment"
    submission_type: Literal["text", "file", "text_or_file"]
    review_mode: Literal["automatic_complete", "manual_review"]
    max_file_size_bytes: int


ActivityRunnerDescriptor = Annotated[
    LessonRunnerDescriptor
    | QuizRunnerDescriptor
    | AudioRunnerDescriptor
    | RealtimeRunnerDescriptor
    | AiCoachRunnerDescriptor
    | AssignmentRunnerDescriptor,
    Field(discriminator="type"),
]


class ActivityDetailResponse(StrictModel):
    enrollment_id: str
    path_revision_id: str
    phase_id: str
    module_id: str
    activity: JourneyActivityProgress
    runner: ActivityRunnerDescriptor
