from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sales_trainer.rules import DEFAULT_SHORT_ANSWER_PASS_THRESHOLD

SalesTrainerUnitType = Literal["quiz", "audio_scoring"]
SalesTrainerStatus = Literal["draft", "published", "archived"]
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
    path_title: str | None = Field(None, max_length=120)
    goal_title: str | None = Field(None, max_length=200)
    level_title: str | None = Field(None, max_length=120)
    level_description: str | None = Field(None, max_length=1000)
    order_index: int = Field(1, ge=1)
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
    auto_process: bool = True


class AudioScorePromptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    purpose: str = Field("general_audio_scoring", min_length=1, max_length=50)
    system_prompt: str = Field(..., min_length=1)
    scoring_template: str = Field(..., min_length=1)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_template_variables(self) -> AudioScorePromptCreate:
        if "{transcript}" not in self.scoring_template:
            raise ValueError("scoring_template must include {transcript}")
        return self


class AudioScorePromptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=200)
    purpose: str | None = Field(None, min_length=1, max_length=50)
    system_prompt: str | None = Field(None, min_length=1)
    scoring_template: str | None = Field(None, min_length=1)
    output_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_template_variables(self) -> AudioScorePromptUpdate:
        if self.scoring_template is not None and "{transcript}" not in self.scoring_template:
            raise ValueError("scoring_template must include {transcript}")
        return self


class AudioScorePromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    name: str
    purpose: str
    system_prompt: str
    scoring_template: str
    output_schema: dict[str, Any]
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
