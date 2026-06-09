from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sales_trainer.rules import DEFAULT_SHORT_ANSWER_PASS_THRESHOLD

SalesTrainerUnitType = Literal["quiz", "audio_scoring"]
SalesTrainerStatus = Literal["draft", "published", "archived"]
SalesTrainerMaterialType = Literal["ppt_deck", "script", "example_audio", "attachment"]
SalesTrainerPathModuleType = Literal[
    "audio_scoring",
    "article_exam",
    "audio_scoring_group",
    "realtime_placeholder",
]
QuizAttemptStatus = Literal["submitted", "scored", "failed"]
AudioSubmissionStatus = Literal[
    "uploaded",
    "transcribing",
    "transcribed",
    "transcription_failed",
    "scoring",
    "scored",
    "scoring_failed",
]
QuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "short_answer"
]
SalesTrainerQuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "short_answer"
]


class SalesTrainerPathConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    path_key: str = Field("default", min_length=1, max_length=80)
    module_key: str | None = Field(None, min_length=1, max_length=80)
    module_type: SalesTrainerPathModuleType | None = None
    path_title: str | None = Field(None, max_length=120)
    goal_title: str | None = Field(None, max_length=200)
    level_title: str | None = Field(None, max_length=120)
    level_description: str | None = Field(None, max_length=1000)
    order_index: int = Field(1, ge=1)
    target_unit_id: str | None = Field(None, min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    exam_paper_id: str | None = Field(None, min_length=1, max_length=36)
    material_id: str | None = Field(None, min_length=1, max_length=36)
    material_version_id: str | None = Field(None, min_length=1, max_length=36)
    scoring_prompt_id: str | None = Field(None, min_length=1, max_length=36)
    disabled_reason: str | None = Field(None, max_length=300)
    unlock_after_unit_ids: list[str] = Field(default_factory=list)
    completion_rule: Literal["passed", "scored", "submitted"] = "passed"
    primary_action_label: str | None = Field(None, max_length=40)
    retry_action_label: str | None = Field(None, max_length=40)
    review_action_label: str | None = Field(None, max_length=40)
    guidance_templates: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_guidance_templates(self) -> SalesTrainerPathConfig:
        allowed_keys = {
            "locked",
            "not_started",
            "not_passed",
            "not_scored",
            "audio_improvement",
            "start_level_title",
            "retry_level_title",
            "path_completed_title",
            "start_level_reason",
            "retry_level_reason",
            "path_completed_reason",
        }
        invalid_keys = sorted(set(self.guidance_templates) - allowed_keys)
        if invalid_keys:
            raise ValueError("guidance_templates contains unsupported keys")
        for value in self.guidance_templates.values():
            if not isinstance(value, str) or len(value) > 300:
                raise ValueError("guidance_templates values must be strings <= 300 chars")
        return self


class SalesTrainerTaskBriefConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    title: str | None = Field(None, max_length=200)
    purpose: str | None = Field(None, max_length=1000)
    scenario: str | None = Field(None, max_length=1000)
    instructions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    upload_guidance: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_list_values(self) -> SalesTrainerTaskBriefConfig:
        for values in (
            self.instructions,
            self.success_criteria,
            self.common_mistakes,
        ):
            if len(values) > 20:
                raise ValueError("task brief list values must contain <= 20 items")
            for value in values:
                if not isinstance(value, str) or not value.strip() or len(value) > 500:
                    raise ValueError("task brief list items must be non-empty strings <= 500 chars")
        return self


class SalesTrainerMaterialBindingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str = Field(..., min_length=1, max_length=36)
    required: bool = True
    confirmation_required: bool = True
    version_policy: Literal["current_published", "locked_version"] = "current_published"
    locked_version_id: str | None = Field(None, min_length=1, max_length=36)
    display_order: int = Field(1, ge=1)
    learner_note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def validate_version_policy(self) -> SalesTrainerMaterialBindingConfig:
        if self.version_policy == "locked_version" and not self.locked_version_id:
            raise ValueError("locked_version_id is required when version_policy=locked_version")
        return self


class SalesTrainerUnitMaterialsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    require_latest_confirmation: bool = True
    bindings: list[SalesTrainerMaterialBindingConfig] = Field(default_factory=list)


class SalesTrainerLearnerRubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    weight: float | None = Field(None, ge=0, le=100)
    excellent: str | None = Field(None, max_length=500)
    passable: str | None = Field(None, max_length=500)
    needs_work: str | None = Field(None, max_length=500)


class SalesTrainerLearnerRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_to_learner: bool = True
    pass_threshold: float | None = Field(None, ge=0, le=100)
    criteria: list[SalesTrainerLearnerRubricCriterion] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rubric(self) -> SalesTrainerLearnerRubric:
        if len(self.criteria) > 20:
            raise ValueError("learner_rubric.criteria must contain <= 20 items")
        if len(self.common_mistakes) > 20:
            raise ValueError("learner_rubric.common_mistakes must contain <= 20 items")
        for value in self.common_mistakes:
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError("learner_rubric.common_mistakes items must be non-empty strings <= 500 chars")
        return self


class ShortAnswerAiScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model_config_id: str | None = Field(None, min_length=1, max_length=36)
    system_prompt: str | None = Field(None, max_length=4000)
    prompt_template: str | None = Field(None, max_length=8000)
    pass_threshold: float = Field(DEFAULT_SHORT_ANSWER_PASS_THRESHOLD, ge=0, le=100)
    temperature: float | None = Field(None, ge=0, le=2)
    timeout: float | None = Field(None, gt=0, le=120)
    max_retries: int | None = Field(None, ge=0, le=5)
    max_tokens: int | None = Field(None, ge=1, le=4000)

    @model_validator(mode="after")
    def validate_prompt_template(self) -> ShortAnswerAiScoringConfig:
        if self.prompt_template is None:
            return self
        required_variables = ("{stem}", "{reference_answer}", "{answer}")
        missing = [
            variable
            for variable in required_variables
            if variable not in self.prompt_template
        ]
        if missing:
            raise ValueError(
                "prompt_template must include {stem}, {reference_answer}, and {answer}"
            )
        return self


class UnitQuestionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=36)
    order_index: int = Field(1, ge=1)
    points: int = Field(10, gt=0, le=100)


class SalesTrainerUnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    unit_type: SalesTrainerUnitType
    config: dict[str, Any] = Field(default_factory=dict)
    questions: list[UnitQuestionBinding] = Field(default_factory=list)


class SalesTrainerUnitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    config: dict[str, Any] | None = None
    questions: list[UnitQuestionBinding] | None = None


class SalesTrainerUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_id: str
    name: str
    description: str | None = None
    unit_type: SalesTrainerUnitType
    config: dict[str, Any]
    status: SalesTrainerStatus
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object
    questions: list[dict[str, Any]] = Field(default_factory=list)


class SalesTrainerUnitListResponse(BaseModel):
    items: list[SalesTrainerUnitResponse]
    total: int


class SalesTrainerPathLevelResponse(BaseModel):
    unit_id: str
    name: str
    description: str | None = None
    unit_type: SalesTrainerUnitType
    module_key: str | None = None
    module_type: SalesTrainerPathModuleType | None = None
    order_index: int
    level_title: str
    level_description: str | None = None
    locked: bool
    lock_reason: str | None = None
    status: Literal["locked", "available", "in_progress", "completed"]
    completion_rule: Literal["passed", "scored", "submitted"]
    primary_action_label: str
    retry_action_label: str
    review_action_label: str
    target_path: str
    latest_result: dict[str, Any] | None = None


class SalesTrainerGoalEvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: Literal["quiz_attempt", "audio_submission"]
    unit_id: str
    unit_type: SalesTrainerUnitType
    level_title: str
    status: str
    passed: bool | None = None
    score: float | None = None
    max_score: float | None = None
    submitted_at: object | None = None
    result_path: str | None = None


class SalesTrainerGoalWeakPoint(BaseModel):
    unit_id: str
    level_title: str
    issue_type: Literal[
        "not_started",
        "not_passed",
        "not_scored",
        "locked",
        "audio_improvement",
    ]
    issue_text: str
    evidence_id: str | None = None
    score: float | None = None
    max_score: float | None = None


class SalesTrainerGoalNextRecommendation(BaseModel):
    title: str
    reason: str
    action_label: str
    target_path: str
    unit_id: str | None = None
    level_title: str | None = None
    recommendation_kind: Literal["start_level", "retry_level", "review_result", "path_completed"]


class SalesTrainerGoalContextResponse(BaseModel):
    goal_title: str | None = None
    score_basis: Literal["sales_trainer_path_projection_v1"] = (
        "sales_trainer_path_projection_v1"
    )
    evidence_items: list[SalesTrainerGoalEvidenceItem] = Field(default_factory=list)
    weak_points: list[SalesTrainerGoalWeakPoint] = Field(default_factory=list)
    next_recommendation: SalesTrainerGoalNextRecommendation | None = None


class SalesTrainerPathResponse(BaseModel):
    path_key: str
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    title: str
    goal_title: str | None = None
    total_levels: int
    completed_levels: int
    current_level_id: str | None = None
    next_level_id: str | None = None
    levels: list[SalesTrainerPathLevelResponse]
    goal_context: SalesTrainerGoalContextResponse


class SalesTrainerPathListResponse(BaseModel):
    items: list[SalesTrainerPathResponse]
    total: int


class NewcomerPathModuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str = Field(..., min_length=1, max_length=80)
    module_type: Literal[
        "audio_scoring",
        "article_exam",
        "audio_scoring_group",
        "realtime_placeholder",
    ] = "audio_scoring"
    enabled: bool = True
    order_index: int = Field(1, ge=1)
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    target_unit_id: str | None = Field(None, min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    exam_paper_id: str | None = Field(None, min_length=1, max_length=36)
    material_id: str | None = Field(None, min_length=1, max_length=36)
    material_version_id: str | None = Field(None, min_length=1, max_length=36)
    scoring_prompt_id: str | None = Field(None, min_length=1, max_length=36)
    disabled_reason: str | None = Field(None, max_length=300)
    unlock_after_unit_ids: list[str] = Field(default_factory=list)
    completion_rule: Literal["passed", "scored", "submitted"] = "passed"
    primary_action_label: str | None = Field(None, max_length=40)
    retry_action_label: str | None = Field(None, max_length=40)
    review_action_label: str | None = Field(None, max_length=40)
    guidance_templates: dict[str, str] = Field(default_factory=dict)


class NewcomerPathConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_key: str = Field("newcomer_training_path_v1", min_length=1, max_length=80)
    title: str = Field("新人训练路径", min_length=1, max_length=120)
    goal_title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=1000)
    enabled: bool = True
    modules: list[NewcomerPathModuleConfig] = Field(default_factory=list)


class NewcomerPathConfigSaveRequest(NewcomerPathConfigPayload):
    reason: str | None = Field(None, max_length=500)


class NewcomerPathConfigActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)
    revision_id: str | None = Field(None, min_length=1, max_length=36)


class NewcomerPathRevisionSummary(BaseModel):
    revision_id: str
    revision_no: int
    status: Literal["working", "published", "archived"]
    change_class: Literal[
        "non_semantic",
        "semantic",
        "binding",
        "scoring_high_risk",
    ]
    title: str
    module_count: int
    is_active: bool
    is_working: bool
    source_revision_id: str | None = None
    payload_hash: str
    reason: str | None = None
    trace_id: str | None = None
    created_by: str | None = None
    published_by: str | None = None
    created_at: object
    published_at: object | None = None


class NewcomerPathConfigResponse(BaseModel):
    source: Literal["active_revision", "unit_backfill"]
    path: NewcomerPathConfigPayload
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    working_revision_id: str | None = None
    working_revision_no: int | None = None
    has_unpublished_revision: bool = False


class NewcomerPathRevisionListResponse(BaseModel):
    items: list[NewcomerPathRevisionSummary]
    total: int


class QuizAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=36)
    answer_payload: Any


class QuizAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(..., min_length=1, max_length=36)
    answers: list[QuizAnswerSubmit] = Field(..., min_length=1)


class QuizAnswerResponse(BaseModel):
    answer_id: str
    question_id: str
    question_type: QuestionType
    answer_payload: Any
    question_title: str | None = None
    question_stem: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: Any = None
    reference_answer: str | None = None
    explanation: str | None = None
    scoring_feedback: str | None = None
    scoring_reason: str | None = None
    normalized_score: float | None = None
    attempt_context: dict[str, Any] | None = None
    is_correct: bool | None = None
    score: float | None = None
    created_at: object


class QuizAttemptResponse(BaseModel):
    attempt_id: str
    unit_id: str
    user_id: str
    user_name: str | None = None
    user_email: str | None = None
    user_department: str | None = None
    total_score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    status: QuizAttemptStatus
    submitted_at: object
    answers: list[QuizAnswerResponse] = Field(default_factory=list)


class QuizAttemptListResponse(BaseModel):
    items: list[QuizAttemptResponse]
    total: int


class ExamPaperQuestionBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=36)
    order_index: int = Field(1, ge=1)
    points: int = Field(10, gt=0, le=100)


class ExamPaperCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_key: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    module_key: str = Field("business_skills", min_length=1, max_length=80)
    pass_threshold: float | None = Field(None, ge=0)
    questions: list[ExamPaperQuestionBinding] = Field(..., min_length=1)


class ExamPaperUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_key: str | None = Field(None, min_length=1, max_length=120)
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    module_key: str | None = Field(None, min_length=1, max_length=80)
    pass_threshold: float | None = Field(None, ge=0)
    questions: list[ExamPaperQuestionBinding] | None = Field(None, min_length=1)


class ExamPaperQuestionResponse(BaseModel):
    question_id: str
    order_index: int
    points: int
    question_type: QuestionType | None = None
    title: str | None = None
    stem: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)


class ExamPaperResponse(BaseModel):
    paper_id: str
    paper_key: str
    title: str
    description: str | None = None
    module_key: str
    unit_id: str
    pass_threshold: float | None = None
    status: SalesTrainerStatus
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object
    questions: list[ExamPaperQuestionResponse] = Field(default_factory=list)
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    working_revision_id: str | None = None
    working_revision_no: int | None = None
    has_unpublished_revision: bool = False


class ExamPaperListResponse(BaseModel):
    items: list[ExamPaperResponse]
    total: int


class ExamPaperRevisionResponse(BaseModel):
    revision_id: str
    revision_no: int
    status: Literal["working", "published", "archived"]
    change_class: Literal[
        "non_semantic",
        "semantic",
        "binding",
        "scoring_high_risk",
    ]
    title: str | None = None
    question_count: int
    is_active: bool
    is_working: bool
    source_revision_id: str | None = None
    payload_hash: str
    reason: str | None = None
    trace_id: str | None = None
    created_by: str | None = None
    published_by: str | None = None
    created_at: object
    published_at: object | None = None


class ExamPaperRevisionListResponse(BaseModel):
    items: list[ExamPaperRevisionResponse]
    total: int


class PaperAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(..., min_length=1, max_length=36)
    answers: list[QuizAnswerSubmit] = Field(..., min_length=1)


class PaperRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_revision_id: str = Field(..., min_length=1, max_length=36)
    reason: str = Field(..., min_length=1, max_length=1000)


class PaperAttemptResponse(QuizAttemptResponse):
    paper_id: str
    paper_title: str
    paper_revision_id: str | None = None
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    legacy_snapshot_only: bool = True


class NewcomerArticleBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str = Field(..., min_length=1, max_length=80)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    path_key: str | None = Field(None, min_length=1, max_length=80)
    active_revision_id: str | None = Field(None, min_length=1, max_length=36)
    active_revision_no: int | None = Field(None, ge=1)
    working_revision_id: str | None = Field(None, min_length=1, max_length=36)
    working_revision_no: int | None = Field(None, ge=1)
    has_unpublished_revision: bool = False
    impact_scope: Literal["future_learners_only"] | None = None


class NewcomerArticleBindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_content_id: str = Field(..., min_length=1, max_length=36)
    path_key: str = Field("newcomer_training_path_v1", min_length=1, max_length=80)
    reason: str | None = Field(None, max_length=500)


class NewcomerArticleChapterResponse(BaseModel):
    chapter_id: str
    title: str
    content: str
    order_index: int


class NewcomerArticleResponse(BaseModel):
    module_key: str
    learning_content_id: str
    title: str
    summary: str | None = None
    owner: str | None = None
    source: str | None = None
    chapters: list[NewcomerArticleChapterResponse] = Field(default_factory=list)


class AudioUploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(..., min_length=1, max_length=100)


class AudioUploadUrlResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_at: str
    content_type: str
    storage_backend: str


class AudioSubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str | None = Field(None, min_length=1, max_length=36)
    purpose: str = Field("general_audio_scoring", min_length=1, max_length=50)
    original_filename: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(..., min_length=1, max_length=100)
    size_bytes: int = Field(..., ge=1)
    storage_key: str = Field(..., min_length=1)
    file_hash: str | None = Field(None, max_length=128)
    duration_seconds: float | None = Field(None, ge=0)
    source_page: str | None = Field(None, min_length=1, max_length=100)
    confirmed_material_version_id: str | None = Field(None, min_length=1, max_length=36)
    auto_process: bool = True


class SalesTrainerMaterialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=200)
    material_type: SalesTrainerMaterialType = "ppt_deck"
    description: str | None = Field(None, max_length=4000)
    purpose: str = Field("ppt_pitch", min_length=1, max_length=50)


class SalesTrainerMaterialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_key: str | None = Field(None, min_length=1, max_length=120)
    name: str | None = Field(None, min_length=1, max_length=200)
    material_type: SalesTrainerMaterialType | None = None
    description: str | None = Field(None, max_length=4000)
    purpose: str | None = Field(None, min_length=1, max_length=50)


class SalesTrainerMaterialVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_label: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=200)
    file_name: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(..., min_length=1, max_length=120)
    file_size_bytes: int = Field(..., ge=1)
    storage_key: str = Field(..., min_length=1)
    file_hash: str | None = Field(None, max_length=128)
    release_notes: str | None = Field(None, max_length=4000)


class SalesTrainerMaterialVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_id: str
    material_id: str
    version_label: str
    title: str
    file_name: str
    content_type: str
    file_size_bytes: int
    storage_key: str
    file_hash: str | None = None
    release_notes: str | None = None
    status: SalesTrainerStatus
    published_at: object | None = None
    published_by: str | None = None
    created_by: str | None = None
    created_at: object
    updated_at: object


class SalesTrainerMaterialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_id: str
    material_key: str
    name: str
    material_type: SalesTrainerMaterialType
    description: str | None = None
    purpose: str
    status: SalesTrainerStatus
    current_version_id: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object
    current_version: SalesTrainerMaterialVersionResponse | None = None
    versions: list[SalesTrainerMaterialVersionResponse] = Field(default_factory=list)


class SalesTrainerMaterialListResponse(BaseModel):
    items: list[SalesTrainerMaterialResponse]
    total: int


class SalesTrainerUnitMaterialBriefItem(BaseModel):
    material_id: str
    material_key: str
    name: str
    material_type: SalesTrainerMaterialType
    description: str | None = None
    purpose: str
    required: bool
    confirmation_required: bool
    learner_note: str | None = None
    display_order: int
    current_version: SalesTrainerMaterialVersionResponse


class SalesTrainerUnitBriefResponse(BaseModel):
    unit: SalesTrainerUnitResponse
    task_brief: dict[str, Any]
    materials: list[SalesTrainerUnitMaterialBriefItem]
    score_scheme: dict[str, Any] | None = None


class SalesTrainerTrainingRecordResponse(BaseModel):
    record_id: str
    record_type: Literal["audio_submission", "quiz_attempt"]
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    legacy_snapshot_only: bool = True
    unit_id: str
    unit_name: str | None = None
    unit_type: SalesTrainerUnitType
    user_id: str
    user_name: str | None = None
    user_email: str | None = None
    user_department: str | None = None
    status: str
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    submitted_at: object | None = None
    material_snapshot: dict[str, Any] | None = None
    score_scheme_snapshot: dict[str, Any] | None = None
    task_brief_snapshot: dict[str, Any] | None = None
    audio_submission: dict[str, Any] | None = None
    quiz_attempt: dict[str, Any] | None = None
    operation_logs: list[dict[str, Any]] = Field(default_factory=list)


class SalesTrainerTrainingRecordListResponse(BaseModel):
    items: list[SalesTrainerTrainingRecordResponse]
    total: int


class AudioScorePromptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    purpose: str = Field("general_audio_scoring", min_length=1, max_length=50)
    system_prompt: str = Field(..., min_length=1)
    scoring_template: str = Field(..., min_length=1)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    learner_rubric: SalesTrainerLearnerRubric | dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_template_variables(self) -> AudioScorePromptCreate:
        if "{transcript}" not in self.scoring_template:
            raise ValueError("scoring_template must include {transcript}")
        if isinstance(self.learner_rubric, dict):
            SalesTrainerLearnerRubric.model_validate(self.learner_rubric)
        return self


class AudioScorePromptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    purpose: str | None = Field(None, min_length=1, max_length=50)
    system_prompt: str | None = Field(None, min_length=1)
    scoring_template: str | None = Field(None, min_length=1)
    output_schema: dict[str, Any] | None = None
    learner_rubric: SalesTrainerLearnerRubric | dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_template_variables(self) -> AudioScorePromptUpdate:
        if self.scoring_template is not None and "{transcript}" not in self.scoring_template:
            raise ValueError("scoring_template must include {transcript}")
        if isinstance(self.learner_rubric, dict):
            SalesTrainerLearnerRubric.model_validate(self.learner_rubric)
        return self


class AudioScorePromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    name: str
    purpose: str
    system_prompt: str
    scoring_template: str
    output_schema: dict[str, Any]
    learner_rubric: dict[str, Any]
    version: int
    status: SalesTrainerStatus
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object


class AudioTranscriptResponse(BaseModel):
    transcript_id: str
    provider: str
    transcript_text: str
    raw_payload: dict[str, Any] | None = None
    started_at: object | None = None
    completed_at: object | None = None
    created_at: object


class AudioScoreResultResponse(BaseModel):
    score_id: str
    submission_id: str
    prompt_id: str
    prompt_version: int
    prompt_hash: str
    deucate_model: str | None = None
    transcript_snapshot: str | None = None
    total_score: float | None = None
    passed: bool | None = None
    summary: str | None = None
    strengths: list[Any]
    improvements: list[Any]
    dimension_scores: dict[str, Any]
    raw_response: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    legacy_snapshot_only: bool = False
    created_at: object


class SalesTrainerQuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(..., min_length=1, max_length=20)
    label: str = Field(..., min_length=1, max_length=500)


class SalesTrainerQuestionCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    order_index: int = Field(1, ge=1)


class SalesTrainerQuestionCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=160)
    parent_id: str | None = Field(None, min_length=1, max_length=36)
    description: str | None = Field(None, max_length=2000)
    order_index: int | None = Field(None, ge=1)


class SalesTrainerQuestionCategoryResponse(BaseModel):
    category_id: str
    parent_id: str | None = None
    name: str
    description: str | None = None
    usage_scope: str
    order_index: int
    created_at: object
    updated_at: object


class SalesTrainerQuestionCategoryListResponse(BaseModel):
    items: list[SalesTrainerQuestionCategoryResponse]
    total: int


class SalesTrainerQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)
    stem: str = Field(..., min_length=1)
    category_id: str = Field(..., min_length=1, max_length=36)
    question_type: SalesTrainerQuestionType
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    tags: list[str] = Field(default_factory=list)
    department: str | None = Field(None, min_length=1, max_length=120)
    safety_flagged: bool = False
    options: list[SalesTrainerQuestionOption] = Field(default_factory=list)
    correct_answer: str | None = Field(None, min_length=1, max_length=20)
    correct_answers: list[str] = Field(default_factory=list)
    correct_bool: bool | None = None
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_dimensions: list[str] = Field(default_factory=list)
    explanation: str | None = Field(None, max_length=4000)
    ai_scoring: ShortAnswerAiScoringConfig | None = None


class SalesTrainerQuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    stem: str | None = Field(None, min_length=1)
    category_id: str | None = Field(None, min_length=1, max_length=36)
    question_type: SalesTrainerQuestionType | None = None
    difficulty: Literal["easy", "medium", "hard"] | None = None
    tags: list[str] | None = None
    department: str | None = Field(None, min_length=1, max_length=120)
    safety_flagged: bool | None = None
    options: list[SalesTrainerQuestionOption] | None = None
    correct_answer: str | None = Field(None, min_length=1, max_length=20)
    correct_answers: list[str] | None = None
    correct_bool: bool | None = None
    reference_answer: str | None = Field(None, max_length=8000)
    scoring_dimensions: list[str] | None = None
    explanation: str | None = Field(None, max_length=4000)
    ai_scoring: ShortAnswerAiScoringConfig | None = None


class SalesTrainerQuestionResponse(BaseModel):
    question_id: str
    title: str
    stem: str
    reference_answer: str | None = None
    category_id: str
    question_type: SalesTrainerQuestionType
    difficulty: Literal["easy", "medium", "hard"]
    status: SalesTrainerStatus
    tags: list[str]
    scoring_dimensions: list[str]
    scoring_criteria: dict[str, Any]
    safety_flagged: bool
    department: str | None = None
    usage_scope: str
    version: int
    content_hash: str | None = None
    published_at: object | None = None
    created_at: object
    updated_at: object
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: str | None = None
    correct_answers: list[str] = Field(default_factory=list)
    correct_bool: bool | None = None
    explanation: str | None = None
    ai_scoring: dict[str, Any] | None = None


class SalesTrainerQuestionListResponse(BaseModel):
    items: list[SalesTrainerQuestionResponse]
    total: int


class SalesTrainerSettingsResponse(BaseModel):
    storage_backend: str
    direct_upload_supported: bool
    cos_configured: bool
    cos_public_read: bool
    oss_configured: bool
    asr_mode: str
    asr_model: str
    dashscope_configured: bool
    deucate_configured: bool
    deucate_model: str | None = None
    max_file_size_mb: int
    allowed_mime_types: list[str]
    file_url_expires_seconds: int


class AudioSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: str
    unit_id: str | None = None
    user_id: str
    user_name: str | None = None
    user_email: str | None = None
    user_department: str | None = None
    purpose: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    file_hash: str | None = None
    duration_seconds: float | None = None
    source_page: str | None = None
    confirmed_material_version_id: str | None = None
    confirmed_material_at: object | None = None
    material_snapshot: dict[str, Any] | None = None
    score_scheme_snapshot: dict[str, Any] | None = None
    task_brief_snapshot: dict[str, Any] | None = None
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    legacy_snapshot_only: bool = False
    status: AudioSubmissionStatus
    error_code: str | None = None
    error_message: str | None = None
    created_at: object
    updated_at: object
    transcript: AudioTranscriptResponse | None = None
    score_result: AudioScoreResultResponse | None = None


class AudioSubmissionListResponse(BaseModel):
    items: list[AudioSubmissionResponse]
    total: int


class AudioScoreResultListResponse(BaseModel):
    items: list[AudioScoreResultResponse]
    total: int


class OperationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: str
    actor_id: str | None = None
    actor_role: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any]
    created_at: object


class OperationLogListResponse(BaseModel):
    items: list[OperationLogResponse]
    total: int
