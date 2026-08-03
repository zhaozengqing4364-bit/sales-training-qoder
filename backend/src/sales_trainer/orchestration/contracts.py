"""Strict domain contracts for newcomer-training path orchestration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    learning_content_id: str = Field(max_length=36)
    completion_mode: Literal["all_chapters", "learner_confirmed"] = "all_chapters"


class QuizConfig(StrictModel):
    exam_paper_id: str = Field(max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)


class AudioAssessmentConfig(StrictModel):
    scoring_rubric_id: str = Field(max_length=36)
    material_id: str | None = Field(default=None, max_length=36)
    pass_score: float = Field(ge=0, le=100)
    max_attempts: int | None = Field(default=None, ge=1, le=100)
    example_transcript: str | None = Field(default=None, max_length=8000)

    @field_validator("material_id")
    @classmethod
    def normalize_material_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("example_transcript")
    @classmethod
    def normalize_example_transcript(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class RealtimeRoleplayConfig(StrictModel):
    practice_template_id: str = Field(max_length=36)
    runtime_profile_id: str = Field(max_length=120)
    completion_mode: Literal["session_completed", "scored"] = "session_completed"
    practice_template_revision_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )
    practice_template_version: int | None = Field(default=None, ge=1)
    practice_template_content_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )
    runtime_profile_snapshot_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )
    governed_assets_snapshot_hash: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )
    runner_snapshot: dict[str, object] | None = None


class AiCoachActivityConfig(StrictModel):
    coach_profile_id: str = Field(max_length=120)
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
    objective: str | None = Field(default=None, max_length=240)
    why_it_matters: str | None = Field(default=None, max_length=500)
    steps: list[Annotated[str, Field(min_length=1, max_length=240)]] = Field(
        default_factory=list,
        max_length=10,
    )
    success_criteria: list[Annotated[str, Field(min_length=1, max_length=240)]] = Field(
        default_factory=list, max_length=10
    )
    primary_action_label: str | None = Field(default=None, max_length=40)


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
    outcome: str | None = Field(default=None, max_length=240)
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
    outcome: str | None = Field(default=None, max_length=240)
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
    objective: str | None = None
    why_it_matters: str | None = None
    steps: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    primary_action_label: str | None = None
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
    outcome: str | None = None
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
    outcome: str | None = None
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


class JourneyListCurrentPhase(StrictModel):
    phase_id: str
    title: str
    status: str


class JourneyListSummary(StrictModel):
    path_revision_id: str
    path_title: str
    current_phase: JourneyListCurrentPhase | None = None
    progress: JourneyProgressSummary
    primary_next_action: JourneyNextAction | None = None
    risk_labels: list[str] = Field(default_factory=list, max_length=2)


class AdminJourneyListItem(StrictModel):
    learner_id: str
    learner_name: str
    team: dict[str, str] | None = None
    summary: JourneyListSummary


class AdminJourneyListResponse(StrictModel):
    items: list[AdminJourneyListItem] = Field(default_factory=list)
    total: int = 0


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


class AudioScoringFocus(StrictModel):
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    weight: float | None = Field(default=None, ge=0, le=100)


class AudioRunnerDescriptor(StrictModel):
    type: Literal["audio_assessment"] = "audio_assessment"
    material_id: str | None = None
    material_version_id: str | None = None
    material_title: str | None = None
    material_version_label: str | None = None
    material_file_name: str | None = None
    material_content_type: str | None = None
    scoring_rubric_revision_id: str | None = None
    scoring_rubric_revision_no: int | None = None
    scoring_rubric_title: str | None = None
    scoring_focuses: list[AudioScoringFocus] = Field(default_factory=list)
    example_transcript: str | None = None
    pass_score: float
    max_attempts: int | None = None


class RealtimeScoringFocus(StrictModel):
    label: str
    description: str | None = None
    weight: float | None = None


class RealtimeRunnerDescriptor(StrictModel):
    type: Literal["realtime_roleplay"] = "realtime_roleplay"
    configuration_ready: bool
    configuration_message: str | None = None
    template_title: str | None = None
    template_description: str | None = None
    template_version: int | None = None
    scenario: str | None = None
    counterpart_role: str | None = None
    counterpart_style: str | None = None
    goals: list[str] = Field(default_factory=list)
    scoring_title: str | None = None
    scoring_description: str | None = None
    scoring_version: str | None = None
    scoring_focuses: list[RealtimeScoringFocus] = Field(default_factory=list)
    passing_score: float | None = None


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
