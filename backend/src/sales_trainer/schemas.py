from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from sales_trainer.rules import DEFAULT_SHORT_ANSWER_PASS_THRESHOLD

SalesTrainerUnitType = Literal["quiz", "audio_scoring"]
SalesTrainerStatus = Literal["draft", "published", "archived"]
SalesTrainerMaterialType = Literal["ppt_deck", "script", "example_audio", "attachment"]
SalesTrainerPathModuleType = Literal[
    "audio_scoring",
    "article_exam",
    "audio_scoring_group",
    "realtime_roleplay",
    "realtime_placeholder",
]
NewcomerPathCompletionRule = Literal["passed", "scored", "submitted"]
NewcomerCanonicalCompletionRule = Literal[
    "audio_scored",
    "paper_passed",
    "all_audio_options_scored",
    "placeholder_disabled",
]
NEWCOMER_COMPLETION_RULE_COMPATIBILITY: Final[
    Mapping[NewcomerCanonicalCompletionRule, NewcomerPathCompletionRule]
] = {
    "audio_scored": "scored",
    "paper_passed": "passed",
    "all_audio_options_scored": "scored",
    "placeholder_disabled": "submitted",
}

NEWCOMER_PATH_HISTORICAL_PREREQUISITE_CONTEXT: Final = (
    "allow_historical_invalid_prerequisites"
)


def _validate_unlock_after_unit_ids(
    values: list[str],
    info: ValidationInfo,
) -> list[str]:
    if (
        isinstance(info.context, Mapping)
        and info.context.get(NEWCOMER_PATH_HISTORICAL_PREREQUISITE_CONTEXT) is True
    ):
        return values
    if any(not value.strip() for value in values):
        raise PydanticCustomError(
            "newcomer_path_prerequisite_invalid",
            "unlock_after_unit_ids cannot contain blank values",
        )
    if len(set(values)) != len(values):
        raise PydanticCustomError(
            "newcomer_path_prerequisite_invalid",
            "unlock_after_unit_ids cannot contain duplicate values",
        )
    return values


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
QuestionType = Literal["single_choice", "multiple_choice", "true_false", "short_answer"]
SalesTrainerQuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "short_answer"
]
BusinessEtiquetteQuestionDraftType = Literal[
    "single_choice", "multiple_choice", "short_answer"
]
BusinessEtiquetteQuestionDraftStatus = Literal[
    "pending_review", "approved", "rejected", "converted"
]
BusinessEtiquetteCapabilityStatus = Literal["draft", "published", "archived"]
SalesTrainerRoleplayObservationSource = Literal["heuristic", "llm_evaluator"]
SalesTrainerRoleplayObservationStatus = Literal[
    "pending",
    "completed",
    "failed",
    "ignored",
]


class SalesTrainerPathConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    path_key: str = Field("default", min_length=1, max_length=80)
    module_key: str | None = Field(None, min_length=1, max_length=80)
    scenario_key: str | None = Field(None, min_length=1, max_length=80)
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
    capability_keys: list[str] = Field(default_factory=list)
    learner_level_required: list[str] = Field(default_factory=list)
    completion_rule: NewcomerPathCompletionRule = "passed"
    primary_action_label: str | None = Field(None, max_length=40)
    retry_action_label: str | None = Field(None, max_length=40)
    review_action_label: str | None = Field(None, max_length=40)
    guidance_templates: dict[str, str] = Field(default_factory=dict)
    ai_coach: dict[str, Any] | None = None
    runtime_binding: dict[str, Any] | None = None

    @field_validator("unlock_after_unit_ids")
    @classmethod
    def validate_unlock_after_unit_ids(
        cls,
        values: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        return _validate_unlock_after_unit_ids(values, info)

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
                raise ValueError(
                    "guidance_templates values must be strings <= 300 chars"
                )
        return self

    @field_validator("learner_level_required")
    @classmethod
    def validate_learner_level_required(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values if value.strip()]
        if len(stripped) > 20:
            raise ValueError("learner_level_required must contain <= 20 items")
        if len(set(stripped)) != len(stripped):
            raise ValueError("learner_level_required cannot contain duplicates")
        for value in stripped:
            if len(value) > 80:
                raise ValueError("learner_level_required items must be <= 80 chars")
        return stripped

    @field_validator("capability_keys")
    @classmethod
    def validate_capability_keys(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values if value.strip()]
        if len(stripped) > 20:
            raise ValueError("capability_keys must contain <= 20 items")
        if len(set(stripped)) != len(stripped):
            raise ValueError("capability_keys cannot contain duplicates")
        for value in stripped:
            if len(value) > 80:
                raise ValueError("capability_keys items must be <= 80 chars")
        return stripped


class NewcomerPathDurationOptionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_key: str = Field(..., min_length=1, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=120)
    duration_minutes: int = Field(..., gt=0)
    target_unit_id: str = Field(..., min_length=1, max_length=36)
    order_index: int = Field(1, ge=1)


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
                    raise ValueError(
                        "task brief list items must be non-empty strings <= 500 chars"
                    )
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
            raise ValueError(
                "locked_version_id is required when version_policy=locked_version"
            )
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
                raise ValueError(
                    "learner_rubric.common_mistakes items must be non-empty strings <= 500 chars"
                )
        return self


class SalesTrainerAudioScoreOutputFieldSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | list[str] | None = None
    description: str | None = Field(None, max_length=1000)
    enum: list[str | int | float | bool | None] | None = None
    items: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None
    required: list[str] | None = None


class SalesTrainerAudioScoreOutputSchema(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    schema_version: str = Field("audio_score_output_v1", min_length=1, max_length=80)
    type: Literal["object"] = "object"
    properties: dict[str, SalesTrainerAudioScoreOutputFieldSchema] = Field(
        default_factory=dict
    )
    required: list[str] = Field(default_factory=list)
    additional_properties: bool | dict[str, Any] | None = Field(
        None, alias="additionalProperties"
    )

    @model_validator(mode="after")
    def validate_required_fields(self) -> SalesTrainerAudioScoreOutputSchema:
        if len(self.properties) > 100:
            raise ValueError("output_schema.properties must contain <= 100 fields")
        if len(self.required) > 100:
            raise ValueError("output_schema.required must contain <= 100 fields")
        if len(set(self.required)) != len(self.required):
            raise ValueError("output_schema.required cannot contain duplicates")
        missing = [field for field in self.required if field not in self.properties]
        if missing:
            raise ValueError(
                "output_schema.required fields must be declared in output_schema.properties"
            )
        for key in self.properties:
            if not key.strip() or len(key) > 120:
                raise ValueError(
                    "output_schema.properties keys must be non-empty strings <= 120 chars"
                )
        return self


def _coerce_legacy_learner_rubric(
    value: Any,
) -> SalesTrainerLearnerRubric | dict[str, Any]:
    if isinstance(value, SalesTrainerLearnerRubric):
        return value
    if not isinstance(value, dict):
        return {}
    try:
        return cast(
            SalesTrainerLearnerRubric,
            SalesTrainerLearnerRubric.model_validate(value),
        )
    except ValueError:
        return {}


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


class SalesTrainerAiCoachAvailabilityResponse(BaseModel):
    enabled: bool
    configured: bool
    available: bool
    coach_path: str | None = None
    disabled_reason: str | None = None
    allowed_interaction_types: list[
        Literal["single_choice", "multiple_choice", "short_answer"]
    ] = Field(default_factory=list)


class SalesTrainerPathLevelResponse(BaseModel):
    unit_id: str
    name: str
    description: str | None = None
    unit_type: SalesTrainerUnitType
    module_key: str | None = None
    module_type: SalesTrainerPathModuleType | None = None
    learning_content_id: str | None = None
    exam_paper_id: str | None = None
    order_index: int
    level_title: str
    level_description: str | None = None
    locked: bool
    lock_reason: str | None = None
    status: Literal["locked", "available", "in_progress", "completed"]
    learner_level_required: list[str] = Field(default_factory=list)
    completion_rule: NewcomerPathCompletionRule
    primary_action_label: str
    retry_action_label: str
    review_action_label: str
    target_path: str
    ai_coach_availability: SalesTrainerAiCoachAvailabilityResponse | None = None
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
    recommendation_kind: Literal[
        "start_level", "retry_level", "review_result", "path_completed"
    ]


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


class AiCoachRetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(1, ge=0, le=5)
    retry_backoff: float = Field(1.0, gt=0, le=30)


AiCoachNextActionV1 = Literal[
    "continue_drill",
    "increase_difficulty",
    "remediate",
    "switch_scenario",
    "summarize",
    "ask_user_choice",
    "end_session",
]
AiCoachSessionStartBehaviorV1 = Literal[
    "welcome_only",
    "plan_then_wait",
    "plan_and_first_card",
]
AiCoachEntryResumePolicyV1 = Literal[
    "latest_active_or_new",
    "latest_in_progress",
    "new",
]
AiCoachRemediationStrategyV1 = Literal[
    "explain_then_retry",
    "ask_user_choice",
    "simplify_then_retry",
]
AiCoachInteractionTypeV1 = Literal["single_choice", "multiple_choice", "short_answer"]
AiCoachTrainingCardTypeV1 = Literal[
    "scenario_judgment",
    "expression_rewrite",
    "role_response",
]
AiCoachUiEventTypeV1 = Literal[
    "quiz_card",
    "explanation_card",
    "summary_card",
    "followup_prompt",
]


def _default_ai_coach_next_actions() -> list[AiCoachNextActionV1]:
    return [
        "continue_drill",
        "increase_difficulty",
        "remediate",
        "switch_scenario",
        "summarize",
        "ask_user_choice",
        "end_session",
    ]


def _default_ai_coach_training_card_types() -> list[AiCoachTrainingCardTypeV1]:
    return [
        "scenario_judgment",
    ]


def _default_ai_coach_interaction_types() -> list[AiCoachInteractionTypeV1]:
    return [
        "single_choice",
        "multiple_choice",
    ]


def _default_ai_coach_ui_event_types() -> list[AiCoachUiEventTypeV1]:
    return [
        "quiz_card",
        "explanation_card",
        "summary_card",
        "followup_prompt",
    ]


def _default_business_etiquette_question_draft_types() -> list[
    BusinessEtiquetteQuestionDraftType
]:
    return [
        "single_choice",
        "multiple_choice",
        "short_answer",
    ]


# Backend-pinned contract version for the layered interaction payload.
# Admin tooling MUST NOT override this. See sales_trainer.AGENTS.md §AI Coach.
AI_COACH_INTERACTION_SCHEMA_VERSION: Literal["ai_coach_interaction_v1"] = (
    "ai_coach_interaction_v1"
)
AI_COACH_PUBLIC_INTERACTION_SCHEMA_VERSION: Literal[
    "ai_coach_interaction_public_v1"
] = "ai_coach_interaction_public_v1"


class AiCoachConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    coach_mode: Literal[
        "single_choice_drill",
        "multiple_choice_drill",
        "short_answer_drill",
        "mixed_drill",
    ] = "mixed_drill"
    allowed_interaction_types: list[AiCoachInteractionTypeV1] = Field(
        default_factory=_default_ai_coach_interaction_types
    )
    allowed_training_card_types: list[AiCoachTrainingCardTypeV1] = Field(
        default_factory=_default_ai_coach_training_card_types,
        min_length=1,
        max_length=3,
    )
    chat_enabled: bool = True
    allowed_ui_event_types: list[AiCoachUiEventTypeV1] = Field(
        default_factory=_default_ai_coach_ui_event_types
    )
    max_cards_per_message: int = Field(1, ge=1, le=5)
    streaming_enabled: bool = True
    entry_resume_policy: AiCoachEntryResumePolicyV1 = "latest_active_or_new"
    generation_timeout_seconds: int = Field(120, ge=5, le=120)
    proactive_coaching_enabled: bool = False
    session_start_behavior: AiCoachSessionStartBehaviorV1 = "welcome_only"
    auto_advance_enabled: bool = False
    max_auto_steps_per_session: int = Field(5, ge=1, le=10)
    correct_streak_to_increase_difficulty: int = Field(2, ge=1, le=10)
    incorrect_streak_to_remediate: int = Field(1, ge=1, le=10)
    incorrect_streak_to_pause: int = Field(2, ge=1, le=10)
    remediation_strategy: AiCoachRemediationStrategyV1 = "explain_then_retry"
    summary_when_mastery_reached: bool = True
    allowed_next_actions: list[AiCoachNextActionV1] = Field(
        default_factory=_default_ai_coach_next_actions
    )
    chat_welcome_message: str = Field(
        "你好，我是商务技巧 AI 教练。你可以直接说想练什么，我会把练习卡片放在对话里。",
        min_length=1,
        max_length=300,
    )
    empty_response_recovery_message: str = Field(
        "我没有拿到可操作的训练卡片。你可以继续下一题、换个场景，或先总结本轮。",
        min_length=1,
        max_length=300,
    )
    empty_response_recovery_prompts: list[str] = Field(
        default_factory=lambda: ["继续下一题", "换个场景", "总结本轮"],
        min_length=1,
        max_length=4,
    )
    generation_failure_recovery_message: str = Field(
        "我已保留当前训练局，但下一步训练生成失败。你可以让我重试、换主题，或先总结一下。",
        min_length=1,
        max_length=300,
    )
    generation_failure_recovery_prompts: list[str] = Field(
        default_factory=lambda: ["重试下一题", "换主题", "总结一下"],
        min_length=1,
        max_length=4,
    )
    prompt_template_id: str | None = Field(None, min_length=1, max_length=36)
    prompt_revision_id: str | None = Field(None, min_length=1, max_length=36)
    prompt_contract_hash: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        description=(
            "Runtime audit contract hash. Module config keeps this null; "
            "session runtime records the compiled prompt hash."
        ),
    )
    # Scoring prompt (used only when short_answer is in
    # ``allowed_interaction_types``). Kept separate from the generation
    # prompt so the two contracts can evolve independently. When
    # ``short_answer`` is enabled, both fields become required and the
    # backend validates them before allowing AI Coach to start a session.
    scoring_prompt_template_id: str | None = Field(None, min_length=1, max_length=36)
    scoring_prompt_revision_id: str | None = Field(None, min_length=1, max_length=36)
    scoring_contract_hash: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        description=(
            "Runtime audit contract hash for the scoring prompt. Module config "
            "keeps this null; session runtime records the compiled prompt hash."
        ),
    )
    min_turns: int = Field(3, ge=1, le=20)
    max_turns: int = Field(10, ge=1, le=50)
    mastery_threshold: float = Field(80.0, ge=0, le=100)
    # Backward-compatible: legacy callers may set "v1". Backend will replace
    # this with AI_COACH_INTERACTION_SCHEMA_VERSION at runtime.
    output_schema_version: str = Field(
        AI_COACH_INTERACTION_SCHEMA_VERSION, min_length=1, max_length=32
    )
    generation_model: str | None = Field(None, min_length=1, max_length=120)
    scoring_model: str | None = Field(None, min_length=1, max_length=120)
    retry_policy: AiCoachRetryPolicy = Field(default_factory=AiCoachRetryPolicy)
    failure_behavior: Literal["abort", "skip_turn", "continue_with_fallback"] = (
        "skip_turn"
    )

    @field_validator("prompt_template_id", "scoring_prompt_template_id")
    @classmethod
    def validate_prompt_template_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise ValueError("prompt template id must be a UUID") from exc

    @field_validator(
        "empty_response_recovery_prompts",
        "generation_failure_recovery_prompts",
    )
    @classmethod
    def validate_recovery_prompts(cls, value: list[str]) -> list[str]:
        prompts = [item.strip() for item in value]
        if any(not item for item in prompts):
            raise ValueError("recovery prompts must not contain empty strings")
        return prompts

    @model_validator(mode="after")
    def validate_turn_range(self) -> AiCoachConfig:
        if self.max_turns < self.min_turns:
            raise ValueError("max_turns must be greater than or equal to min_turns")
        if not self.allowed_interaction_types:
            raise ValueError("allowed_interaction_types must not be empty")
        if not self.allowed_training_card_types:
            raise ValueError("allowed_training_card_types must not be empty")
        short_answer_card_types = {"expression_rewrite", "role_response"}
        if (
            set(self.allowed_training_card_types) & short_answer_card_types
            and "short_answer" not in self.allowed_interaction_types
        ):
            raise ValueError(
                "expression_rewrite and role_response require short_answer "
                "in allowed_interaction_types"
            )
        if not self.allowed_ui_event_types:
            raise ValueError("allowed_ui_event_types must not be empty")
        if not self.allowed_next_actions:
            raise ValueError("allowed_next_actions must not be empty")
        if self.incorrect_streak_to_pause < self.incorrect_streak_to_remediate:
            raise ValueError(
                "incorrect_streak_to_pause must be greater than or equal to "
                "incorrect_streak_to_remediate"
            )
        if "short_answer" in self.allowed_interaction_types:
            if not self.scoring_prompt_template_id:
                raise ValueError(
                    "scoring_prompt_template_id is required when "
                    "'short_answer' is in allowed_interaction_types"
                )
        return self

    @model_validator(mode="before")
    @classmethod
    def _coerce_pinned_fields(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        values["output_schema_version"] = AI_COACH_INTERACTION_SCHEMA_VERSION
        values["prompt_contract_hash"] = None
        values["scoring_contract_hash"] = None
        return values

    def pinned_schema_version(self) -> str:
        """Return the backend-pinned interaction schema version.

        Admin-supplied ``output_schema_version`` is intentionally ignored here:
        the contract version is a backend constant so the runtime can rely on
        it for validation and cache keying.
        """
        return AI_COACH_INTERACTION_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# AI coach interaction v1 schemas
#
# Three-layer field model (see sales_trainer/AGENTS.md §AI Coach):
#   - AiCoachInteractionInternalV1  : server-side contract; never returned to
#                                     learners. Holds answer_key, scoring
#                                     rubric, source_evidence.
#   - AiCoachInteractionPublicV1    : learner-facing render spec. Strictly
#                                     excludes answer_key, scoring_rubric,
#                                     source_evidence, raw_model_output and
#                                     any internal prompt/snapshot.
#   - AiCoachAnswerPayloadV1 / AiCoachScoreResultV1 : wire payloads between
#                                     learner submission and scorer.
# ---------------------------------------------------------------------------


class AiCoachInteractionOptionV1(BaseModel):
    """Internal option contract. Carries the ``is_distractor`` flag
    because the scorer needs it; never returned to learners."""

    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(..., min_length=1, max_length=40)
    text: str = Field(..., min_length=1, max_length=2000)
    is_distractor: bool | None = None


class AiCoachPublicInteractionOptionV1(BaseModel):
    """Public option contract: strictly ``option_id`` + ``text`` only.

    ``is_distractor`` is intentionally absent because exposing it would
    leak the answer to the learner (they could simply pick the option
    whose flag is ``false``). The internal scorer still has access to
    the flag through ``AiCoachInteractionInternalV1``.
    """

    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(..., min_length=1, max_length=40)
    text: str = Field(..., min_length=1, max_length=2000)


class AiCoachAnswerKeyV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_ids: list[str] = Field(default_factory=list)
    reference_answer: str | None = Field(None, max_length=8000)


class AiCoachScoringPointV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=80)
    score: float = Field(..., ge=0, le=100)
    description: str | None = Field(None, max_length=1000)


class AiCoachScoringRubricV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_score: float = Field(100.0, ge=0, le=100)
    points: list[AiCoachScoringPointV1] = Field(default_factory=list)
    partial_credit_policy: Literal[
        "all_or_nothing",
        "proportional",
        "tiered",
    ] = "all_or_nothing"


class AiCoachFeedbackGuidanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct: str = Field(..., min_length=1, max_length=2000)
    incorrect: str = Field(..., min_length=1, max_length=2000)


class AiCoachStructuredFeedbackV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    did_well: list[str] = Field(default_factory=list, max_length=5)
    main_issue: str = Field(..., min_length=1, max_length=1000)
    why_inappropriate: str = Field(..., min_length=1, max_length=1500)
    suggested_response: str = Field(..., min_length=1, max_length=2000)
    next_step: str = Field(..., min_length=1, max_length=1000)


class AiCoachSourceEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str | None = Field(None, min_length=1, max_length=36)
    quote: str | None = Field(None, max_length=2000)
    reason: str = Field(..., min_length=1, max_length=2000)
    confidence: float | None = Field(None, ge=0, le=1)


class AiCoachInteractionInternalV1(BaseModel):
    """Server-side contract for an AI coach interaction turn.

    Strict ``extra="forbid"`` so any unrecognised field from the model
    surfaces as a validation error during ingestion rather than leaking
    into the stored snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai_coach_interaction_v1"] = (
        AI_COACH_INTERACTION_SCHEMA_VERSION
    )
    training_card_type: AiCoachTrainingCardTypeV1 = "scenario_judgment"
    interaction_type: Literal["single_choice", "multiple_choice", "short_answer"]
    stem: str = Field(..., min_length=5, max_length=2000)
    options: list[AiCoachInteractionOptionV1] | None = None
    answer_key: AiCoachAnswerKeyV1
    scoring_rubric: AiCoachScoringRubricV1
    feedback_guidance: AiCoachFeedbackGuidanceV1
    capability_keys: list[str] = Field(default_factory=list, max_length=10)
    source_chapter_orders: list[int] = Field(default_factory=list, max_length=20)
    source_evidence: list[AiCoachSourceEvidenceV1] | None = None

    @model_validator(mode="after")
    def validate_interaction_shape(self) -> AiCoachInteractionInternalV1:
        interaction_type = self.interaction_type
        options = self.options
        answer_key = self.answer_key
        scoring_rubric = self.scoring_rubric

        if interaction_type == "single_choice":
            if not options or len(options) < 2:
                raise ValueError(
                    "single_choice interaction must include at least 2 options"
                )
            if len(answer_key.option_ids) != 1:
                raise ValueError(
                    "single_choice answer_key must contain exactly 1 option_id"
                )
        elif interaction_type == "multiple_choice":
            if not options or len(options) < 2:
                raise ValueError(
                    "multiple_choice interaction must include at least 2 options"
                )
            if len(answer_key.option_ids) < 1:
                raise ValueError(
                    "multiple_choice answer_key must contain >=1 option_id"
                )
        elif interaction_type == "short_answer":
            if options is not None:
                raise ValueError("short_answer interaction must not include options")
            if not (
                (answer_key.reference_answer and answer_key.reference_answer.strip())
                or scoring_rubric.points
            ):
                raise ValueError(
                    "short_answer interaction must include reference_answer "
                    "or at least one scoring_rubric point"
                )

        if self.training_card_type in {"expression_rewrite", "role_response"}:
            if interaction_type != "short_answer":
                raise ValueError(
                    "expression_rewrite and role_response cards must use short_answer"
                )

        if answer_key.option_ids:
            valid_ids = {o.option_id for o in (options or [])}
            unknown = [oid for oid in answer_key.option_ids if oid not in valid_ids]
            if unknown:
                raise ValueError(
                    f"answer_key references unknown option_id(s): {unknown}"
                )

        total_points = sum(p.score for p in scoring_rubric.points)
        if total_points - scoring_rubric.max_score > 0.01:
            raise ValueError("scoring_rubric point scores must not exceed max_score")
        if any(not key.strip() or len(key) > 80 for key in self.capability_keys):
            raise ValueError("capability_keys must contain non-empty strings <= 80")
        if any(order < 1 for order in self.source_chapter_orders):
            raise ValueError("source_chapter_orders values must be >= 1")
        return self


class AiCoachInteractionPublicV1(BaseModel):
    """Learner-facing render spec for an interaction turn.

    STRICTLY EXCLUDES answer_key / scoring_rubric / source_evidence /
    raw_model_output / prompt / snapshot. Validated via ``extra="forbid"``
    so the internal model cannot accidentally leak through.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai_coach_interaction_public_v1"] = (
        AI_COACH_PUBLIC_INTERACTION_SCHEMA_VERSION
    )
    interaction_id: str = Field(..., min_length=1, max_length=64)
    session_id: str = Field(..., min_length=1, max_length=36)
    turn_number: int = Field(..., ge=1)
    training_card_type: AiCoachTrainingCardTypeV1 = "scenario_judgment"
    interaction_type: Literal["single_choice", "multiple_choice", "short_answer"]
    stem: str = Field(..., min_length=5, max_length=2000)
    options: list[AiCoachPublicInteractionOptionV1] | None = None
    answer_constraints: dict[str, int] = Field(default_factory=dict)
    capability_keys: list[str] = Field(default_factory=list, max_length=10)
    source_chapter_orders: list[int] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_constraints(self) -> AiCoachInteractionPublicV1:
        if self.interaction_type == "short_answer" and self.options is not None:
            raise ValueError("short_answer public interaction must not include options")
        allowed_keys = {
            "min_selected",
            "max_selected",
            "min_length",
            "max_length",
        }
        bad_keys = sorted(set(self.answer_constraints) - allowed_keys)
        if bad_keys:
            raise ValueError(f"answer_constraints has unsupported keys: {bad_keys}")
        for key, value in self.answer_constraints.items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"answer_constraints.{key} must be a non-negative int")
        min_selected = self.answer_constraints.get("min_selected")
        max_selected = self.answer_constraints.get("max_selected")
        if (
            min_selected is not None
            and max_selected is not None
            and max_selected < min_selected
        ):
            raise ValueError("answer_constraints.max_selected must be >= min_selected")
        return self


class AiCoachInteractionPublicListV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction: AiCoachInteractionPublicV1
    score_feedback_state: Literal["pending", "scored", "failed"] = "pending"


class AiCoachAnswerPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: Literal["choice", "text"]
    option_ids: list[str] | None = None
    text: str | None = Field(None, max_length=8000)

    @model_validator(mode="after")
    def validate_payload_shape(self) -> AiCoachAnswerPayloadV1:
        if self.variant == "choice":
            if not self.option_ids:
                raise ValueError("choice payload must include option_ids")
            if self.text is not None:
                raise ValueError("choice payload must not include text")
        else:  # text
            if self.text is None or not self.text.strip():
                raise ValueError("text payload must include non-empty text")
            if self.option_ids is not None:
                raise ValueError("text payload must not include option_ids")
        return self


class AiCoachScoreResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(..., ge=0, le=100)
    max_score: float = Field(100.0, ge=0, le=100)
    mastery_threshold: float | None = Field(None, ge=0, le=100)
    mastered: bool | None = None
    feedback: str = Field(..., min_length=1, max_length=4000)
    structured_feedback: AiCoachStructuredFeedbackV1 | None = None
    missed_points: list[str] = Field(default_factory=list)
    next_turn_available: bool = True
    finished: bool = False


class AiCoachTurnPublicV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: str = Field(..., min_length=1, max_length=36)
    turn_number: int = Field(..., ge=1)
    public_interaction: AiCoachInteractionPublicV1 | None = None
    user_answer_payload: dict[str, Any] | None = None
    score: float | None = None
    max_score: float | None = None
    ai_feedback: str | None = None
    missed_points: list[str] = Field(default_factory=list)
    next_turn_available: bool = True


class AiCoachSessionPublicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=36)
    module_key: str = Field(..., min_length=1, max_length=80)
    status: Literal["in_progress", "completed", "failed"]
    mastery_state: Literal["mastered", "not_mastered"] | None = None
    total_score: float | None = None
    max_score: float | None = None
    current_turn: int = Field(..., ge=0)
    min_turns: int = Field(..., ge=1)
    max_turns: int = Field(..., ge=1)
    mastery_threshold: float = Field(..., ge=0, le=100)
    overall_mastered: bool
    created_at: object
    updated_at: object
    turns: list[AiCoachTurnPublicV1] = Field(default_factory=list)


class AiCoachSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str = Field(..., min_length=1, max_length=80)
    # Optional drill mode. When set, the backend clamps the generated
    # interaction's ``interaction_type`` to a member of the module's
    # ``allowed_interaction_types`` and (for ``mixed_drill``) rotates
    # across them per turn. ``None`` means ``mixed_drill`` by default.
    coach_mode: (
        Literal[
            "single_choice_drill",
            "multiple_choice_drill",
            "short_answer_drill",
            "mixed_drill",
        ]
        | None
    ) = None
    # Optional explicit type override. ``coach_mode`` is the canonical
    # selector; this is a power-user escape hatch (e.g. admin tools).
    interaction_type: (
        Literal["single_choice", "multiple_choice", "short_answer"] | None
    ) = None


class AiCoachTurnSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_answer: str | None = Field(None, min_length=1, max_length=8000)
    # New layered-answer path: structured payload mirroring the public
    # interaction shape. When present, the legacy `user_answer` field is
    # derived from the payload (text variant) for backward compatibility
    # with scoring paths that still read it.
    answer_payload: AiCoachAnswerPayloadV1 | None = None

    @model_validator(mode="after")
    def validate_submit_shape(self) -> AiCoachTurnSubmit:
        if not self.user_answer and self.answer_payload is None:
            raise ValueError(
                "AiCoachTurnSubmit requires either user_answer or answer_payload"
            )
        if (
            self.answer_payload is not None
            and self.answer_payload.variant == "text"
            and self.answer_payload.text
            and not self.user_answer
        ):
            # Backfill legacy field from structured text payload.
            object.__setattr__(self, "user_answer", self.answer_payload.text)
        return self


class AiCoachTurnSubmitV1(BaseModel):
    """v1 turn submission; always uses the structured answer payload."""

    model_config = ConfigDict(extra="forbid")

    answer_payload: AiCoachAnswerPayloadV1


class AiCoachTurnResponse(BaseModel):
    turn_id: str
    session_id: str
    turn_number: int
    question: str
    user_answer: str
    ai_feedback: str | None = None
    score: float | None = None
    max_score: float | None = None
    missed_points: list[str] = Field(default_factory=list)
    next_question: str | None = None
    created_at: object


class AiCoachSessionResponse(BaseModel):
    session_id: str
    module_key: str
    path_key: str | None = None
    path_revision_no: int | None = None
    status: Literal["in_progress", "completed", "failed"]
    mastery_state: Literal["mastered", "not_mastered"] | None = None
    total_score: float | None = None
    max_score: float | None = None
    current_turn: int
    min_turns: int
    max_turns: int
    mastery_threshold: float
    overall_mastered: bool
    created_at: object
    updated_at: object
    turns: list[AiCoachTurnResponse] = Field(default_factory=list)


class AiCoachResultResponse(BaseModel):
    session_id: str
    status: Literal["in_progress", "completed", "failed"]
    mastery_state: Literal["mastered", "not_mastered"] | None = None
    total_score: float | None = None
    max_score: float | None = None
    turn_count: int
    turns: list[AiCoachTurnResponse] = Field(default_factory=list)


class BusinessEtiquetteTrainingUnitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_key: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    order_index: int = Field(1, ge=1)
    enabled: bool = True
    source_chapter_orders: list[int] = Field(default_factory=list)
    source_card_keys: list[str] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    unlock_after_unit_keys: list[str] = Field(default_factory=list)
    require_reading: bool = True
    require_quiz: bool = True
    require_ai_coach: bool = True
    ai_coach_required_capability_keys: list[str] = Field(default_factory=list)
    ai_coach_pass_mastery_level_key: str = Field(
        "basic_mastery",
        min_length=1,
        max_length=80,
    )
    ai_coach_ready_mastery_level_key: str = Field(
        "field_ready",
        min_length=1,
        max_length=80,
    )
    ai_coach_max_remediation_attempts: int = Field(3, ge=1, le=20)
    ai_coach_manual_review_after_max_attempts: bool = True
    ai_coach_block_next_until_passed: bool = True
    ai_coach_remediation_chapter_orders: list[int] = Field(default_factory=list)
    quiz_question_count: int = Field(5, ge=1, le=50)
    quiz_pass_threshold: float | None = Field(None, ge=0, le=100)
    quiz_allow_retake: bool = True
    quiz_max_attempts: int | None = Field(None, ge=1, le=100)
    quiz_question_type_weights: dict[str, float] = Field(default_factory=dict)
    allow_skip_reading: bool = False
    block_next_until_complete: bool = True
    empty_state_message: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def validate_training_unit(self) -> BusinessEtiquetteTrainingUnitConfig:
        if len(self.source_chapter_orders) > 20:
            raise ValueError("source_chapter_orders must contain <= 20 items")
        if len(self.source_card_keys) > 80:
            raise ValueError("source_card_keys must contain <= 80 items")
        if any(order < 1 for order in self.source_chapter_orders):
            raise ValueError("source_chapter_orders values must be >= 1")
        if len(set(self.source_chapter_orders)) != len(self.source_chapter_orders):
            raise ValueError("source_chapter_orders cannot contain duplicates")
        if len(set(self.source_card_keys)) != len(self.source_card_keys):
            raise ValueError("source_card_keys cannot contain duplicates")
        for value in self.source_card_keys:
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError(
                    "source_card_keys items must be non-empty strings <= 120 chars"
                )
        if len(self.capability_keys) > 20 or len(self.unlock_after_unit_keys) > 20:
            raise ValueError("learning unit list fields must contain <= 20 items")
        if len(self.ai_coach_required_capability_keys) > 20:
            raise ValueError(
                "ai_coach_required_capability_keys must contain <= 20 items"
            )
        if len(set(self.capability_keys)) != len(self.capability_keys):
            raise ValueError("capability_keys cannot contain duplicates")
        if len(set(self.unlock_after_unit_keys)) != len(self.unlock_after_unit_keys):
            raise ValueError("unlock_after_unit_keys cannot contain duplicates")
        if len(set(self.ai_coach_required_capability_keys)) != len(
            self.ai_coach_required_capability_keys
        ):
            raise ValueError(
                "ai_coach_required_capability_keys cannot contain duplicates"
            )
        for value in (
            *self.capability_keys,
            *self.unlock_after_unit_keys,
            *self.ai_coach_required_capability_keys,
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 80:
                raise ValueError(
                    "learning unit keys must be non-empty strings <= 80 chars"
                )
        if (self.require_quiz or self.require_ai_coach) and not self.capability_keys:
            raise ValueError(
                "capability_keys are required when quiz or ai coach is required"
            )
        unknown_ai_coach_keys = sorted(
            set(self.ai_coach_required_capability_keys) - set(self.capability_keys)
        )
        if unknown_ai_coach_keys:
            raise ValueError(
                "ai_coach_required_capability_keys must be a subset of capability_keys"
            )
        if len(self.ai_coach_remediation_chapter_orders) > 20:
            raise ValueError(
                "ai_coach_remediation_chapter_orders must contain <= 20 items"
            )
        if any(order < 1 for order in self.ai_coach_remediation_chapter_orders):
            raise ValueError("ai_coach_remediation_chapter_orders values must be >= 1")
        if len(set(self.ai_coach_remediation_chapter_orders)) != len(
            self.ai_coach_remediation_chapter_orders
        ):
            raise ValueError(
                "ai_coach_remediation_chapter_orders cannot contain duplicates"
            )
        allowed_question_types = {"single_choice", "multiple_choice", "short_answer"}
        invalid_question_types = sorted(
            set(self.quiz_question_type_weights) - allowed_question_types
        )
        if invalid_question_types:
            raise ValueError("quiz_question_type_weights contains unsupported keys")
        if any(value < 0 for value in self.quiz_question_type_weights.values()):
            raise ValueError("quiz_question_type_weights values must be >= 0")
        return self


class NewcomerRealtimeProviderReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["stepfun_realtime", "legacy", "mock"]
    ready: bool
    checked_at: str = Field(..., min_length=1, max_length=80)
    config_revision_id: str | None = Field(None, min_length=1, max_length=120)
    failure_code: str | None = Field(None, min_length=1, max_length=120)
    failure_message: str | None = Field(None, min_length=1, max_length=500)


class NewcomerRealtimePermissionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_enter: Literal["sales_trainer.enter_realtime"] = (
        "sales_trainer.enter_realtime"
    )
    admin_configure: Literal["sales_trainer.manage_modules"] = (
        "sales_trainer.manage_modules"
    )
    admin_provider_health: Literal["sales_trainer.view_settings"] = (
        "sales_trainer.view_settings"
    )


class NewcomerRealtimeFailurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terminal_codes: list[str] = Field(default_factory=list, max_length=50)
    transient_codes: list[str] = Field(default_factory=list, max_length=50)
    voluntary_codes: list[str] = Field(default_factory=list, max_length=50)
    terminal_retry_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_codes(self) -> NewcomerRealtimeFailurePolicy:
        for values in (self.terminal_codes, self.transient_codes, self.voluntary_codes):
            if len(set(values)) != len(values):
                raise ValueError("failure policy codes cannot contain duplicates")
            for value in values:
                if not isinstance(value, str) or not value.strip() or len(value) > 120:
                    raise ValueError(
                        "failure policy codes must be non-empty strings <= 120 chars"
                    )
        return self


class NewcomerRealtimeRollbackPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollback_via_active_revision: Literal[True] = True
    disable_module_on_invalid_binding: Literal[True] = True
    fallback_to_placeholder: Literal[False] = False


class NewcomerRealtimeRuntimeBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_key: Literal["newcomer_realtime_roleplay_v1"]
    runtime_owner: Literal["training_runtime"]
    runtime_descriptor_id: str = Field(..., min_length=1, max_length=120)
    scenario_key: str = Field(..., min_length=1, max_length=120)
    practice_template_id: str | None = Field(None, min_length=1, max_length=36)
    runtime_config_revision_id: str = Field(..., min_length=1, max_length=120)
    roleplay_contract_revision_id: str | None = Field(
        None, min_length=1, max_length=120
    )
    provider_readiness_snapshot: NewcomerRealtimeProviderReadinessSnapshot
    permission_policy: NewcomerRealtimePermissionPolicy = Field(
        default_factory=NewcomerRealtimePermissionPolicy
    )
    failure_policy: NewcomerRealtimeFailurePolicy = Field(
        default_factory=NewcomerRealtimeFailurePolicy
    )
    rollback_policy: NewcomerRealtimeRollbackPolicy = Field(
        default_factory=NewcomerRealtimeRollbackPolicy
    )


class NewcomerPathModuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str = Field(..., min_length=1, max_length=80)
    scenario_key: str | None = Field(None, min_length=1, max_length=80)
    module_type: Literal[
        "audio_scoring",
        "article_exam",
        "audio_scoring_group",
        "realtime_roleplay",
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
    capability_keys: list[str] = Field(default_factory=list)
    learner_level_required: list[str] = Field(default_factory=list)
    completion_rule: NewcomerPathCompletionRule = "passed"
    primary_action_label: str | None = Field(None, max_length=40)
    retry_action_label: str | None = Field(None, max_length=40)
    review_action_label: str | None = Field(None, max_length=40)
    guidance_templates: dict[str, str] = Field(default_factory=dict)
    ai_coach: AiCoachConfig | None = None
    runtime_binding: NewcomerRealtimeRuntimeBinding | None = None
    learning_units: list[BusinessEtiquetteTrainingUnitConfig] = Field(
        default_factory=list
    )
    duration_options: list[NewcomerPathDurationOptionConfig] = Field(
        default_factory=list
    )

    @field_validator("unlock_after_unit_ids")
    @classmethod
    def validate_unlock_after_unit_ids(
        cls,
        values: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        return _validate_unlock_after_unit_ids(values, info)

    @model_validator(mode="after")
    def validate_module_collections(self) -> NewcomerPathModuleConfig:
        if len(self.capability_keys) > 20:
            raise ValueError("capability_keys must contain <= 20 items")
        capability_keys = [
            value.strip() for value in self.capability_keys if value.strip()
        ]
        if len(set(capability_keys)) != len(capability_keys):
            raise ValueError("capability_keys cannot contain duplicate values")
        if len(capability_keys) != len(self.capability_keys):
            raise ValueError("capability_keys cannot contain blank values")
        for value in capability_keys:
            if len(value) > 80:
                raise ValueError("capability_keys items must be <= 80 chars")
        if len(self.learner_level_required) > 20:
            raise ValueError("learner_level_required must contain <= 20 items")
        learner_levels = [
            value.strip() for value in self.learner_level_required if value.strip()
        ]
        if len(set(learner_levels)) != len(learner_levels):
            raise ValueError("learner_level_required cannot contain duplicate values")
        if len(learner_levels) != len(self.learner_level_required):
            raise ValueError("learner_level_required cannot contain blank values")
        for value in learner_levels:
            if len(value) > 80:
                raise ValueError("learner_level_required items must be <= 80 chars")
        if len(self.learning_units) > 30:
            raise ValueError("learning_units must contain <= 30 items")
        unit_keys = [unit.unit_key for unit in self.learning_units]
        if len(set(unit_keys)) != len(unit_keys):
            raise ValueError("learning_units cannot contain duplicate unit_key values")
        if len(self.duration_options) > 12:
            raise ValueError("duration_options must contain <= 12 items")
        option_keys = [option.option_key for option in self.duration_options]
        if len(set(option_keys)) != len(option_keys):
            raise ValueError(
                "duration_options cannot contain duplicate option_key values"
            )
        target_unit_ids = [option.target_unit_id for option in self.duration_options]
        if len(set(target_unit_ids)) != len(target_unit_ids):
            raise ValueError(
                "duration_options cannot contain duplicate target_unit_id values"
            )
        if self.runtime_binding is not None and self.module_type != "realtime_roleplay":
            raise ValueError(
                "runtime_binding is only supported for realtime_roleplay modules"
            )
        return self


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


class NewcomerPathRollbackPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str = Field(..., min_length=1, max_length=36)


class NewcomerPathPublishPreviewResponse(BaseModel):
    action: Literal["newcomer_path_config.publish"]
    permission: Literal["sales_trainer.manage_modules"]
    requires_reason: bool
    requires_trace_id: bool
    future_only: bool
    risk_level: Literal["low", "medium", "high"]
    risk_reasons: list[str] = Field(default_factory=list)
    change_class: Literal[
        "non_semantic",
        "semantic",
        "binding",
        "scoring_high_risk",
    ]
    target_revision_id: str
    target_revision_no: int
    target_revision_status: Literal["working", "published", "archived"]
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any]
    audit_event: dict[str, Any]
    rollback_hint: dict[str, Any]


class NewcomerPathRollbackPreviewResponse(BaseModel):
    action: Literal["newcomer_path_config.rollback"]
    permission: Literal["sales_trainer.manage_modules"]
    requires_reason: bool
    requires_trace_id: bool
    future_only: bool
    target_revision_id: str
    target_revision_no: int
    target_revision_status: Literal["working", "published", "archived"]
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any]
    audit_event: dict[str, Any]


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


class NewcomerPathConfigPermissionPolicyDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    view: Literal["sales_trainer.manage_modules"]
    save: Literal["sales_trainer.manage_modules"]
    publish: Literal["sales_trainer.manage_modules"]
    rollback: Literal["sales_trainer.manage_modules"]
    high_risk_ai_coach: Literal["sales_trainer.manage_prompts"]
    regrade: Literal["sales_trainer.regrade_history"]


class NewcomerPathConfigHighRiskActionDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_reason: Literal[True]
    requires_trace_id: Literal[True]
    audit_action: str = Field(..., min_length=1, max_length=120)
    impact_scope: str = Field(..., min_length=1, max_length=80)
    preview_endpoint: str | None = Field(None, min_length=1, max_length=200)
    history_overwrite: bool | None = None


class NewcomerPathConfigHighRiskActionsDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publish: NewcomerPathConfigHighRiskActionDiagnostics
    rollback: NewcomerPathConfigHighRiskActionDiagnostics
    regrade: NewcomerPathConfigHighRiskActionDiagnostics


class NewcomerRealtimeProviderReadinessDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: Literal["realtime_roleplay", "realtime_roleplay_placeholder"]
    module_type: Literal["realtime_roleplay", "realtime_placeholder"]
    title: str = Field(..., min_length=1, max_length=120)
    enabled: bool
    runtime_descriptor_id: str | None = Field(None, min_length=1, max_length=120)
    provider_readiness_snapshot: NewcomerRealtimeProviderReadinessSnapshot | None = None
    ready: bool
    failure_code: str | None = Field(None, min_length=1, max_length=120)
    failure_message: str | None = Field(None, min_length=1, max_length=500)


class NewcomerPathConfigDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface_key: Literal["newcomer_training_path_v1"]
    resource_type: Literal["newcomer_training_path"]
    source: Literal["active_revision", "legacy_migration_snapshot"]
    legacy_snapshot_only: bool
    fallback_applied: bool
    fallback_reason: Literal["active_revision_missing"] | None = None
    realtime_provider_readiness: list[NewcomerRealtimeProviderReadinessDiagnostics] = (
        Field(default_factory=list)
    )
    management_entry: Literal["/admin/newcomer-training/path-config"]
    permission_policy: NewcomerPathConfigPermissionPolicyDiagnostics
    active_revision: NewcomerPathRevisionSummary | None = None
    working_revision: NewcomerPathRevisionSummary | None = None
    high_risk_actions: NewcomerPathConfigHighRiskActionsDiagnostics


class NewcomerPathConfigResponse(BaseModel):
    source: Literal["active_revision", "legacy_migration_snapshot"]
    fallback_reason: str | None = None
    legacy_snapshot_only: bool = False
    management_entry: str = "/admin/newcomer-training/path-config"
    permission: str = "sales_trainer.manage_modules"
    path: NewcomerPathConfigPayload
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    active_revision_snapshot: dict[str, Any] | None = None
    working_revision_id: str | None = None
    working_revision_no: int | None = None
    has_unpublished_revision: bool = False
    diagnostics: NewcomerPathConfigDiagnostics


class NewcomerPathRevisionListResponse(BaseModel):
    items: list[NewcomerPathRevisionSummary]
    total: int


LearningTopicScoreDisplayPolicy = Literal["quiz_attempt_score"]
NewcomerLearningTopicKey = Literal["business_etiquette", "customer_faq"]
NewcomerLearningTopicContentKind = Literal["article", "faq_cards"]
CustomerFaqCardStatus = Literal["draft", "published", "archived"]
CustomerFaqDifficultyLevel = Literal["newcomer", "advanced", "high_risk"]


class CustomerFaqEvidenceCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_key: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=120)
    summary: str | None = Field(None, max_length=1000)
    source_question_numbers: list[int] = Field(default_factory=list, max_length=20)


class CustomerFaqCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_key: str = Field(..., min_length=1, max_length=120)
    source_question_number: int | None = Field(None, ge=1, le=1000)
    question: str = Field(..., min_length=1, max_length=500)
    short_answer: str = Field(..., min_length=1, max_length=1000)
    detailed_answer: str = Field(..., min_length=1, max_length=5000)
    scenario: str = Field(..., min_length=1, max_length=80)
    category: str = Field(..., min_length=1, max_length=80)
    customer_intent: str | None = Field(None, max_length=500)
    key_points: list[str] = Field(default_factory=list, max_length=20)
    evidence_cases: list[str] = Field(default_factory=list, max_length=20)
    forbidden_claims: list[str] = Field(default_factory=list, max_length=20)
    escalation_required: bool = False
    difficulty_level: CustomerFaqDifficultyLevel = "newcomer"
    tags: list[str] = Field(default_factory=list, max_length=30)
    duplicate_group_key: str | None = Field(None, min_length=1, max_length=120)
    status: CustomerFaqCardStatus = "published"

    @model_validator(mode="after")
    def validate_card_lists(self) -> CustomerFaqCard:
        for values in (
            self.key_points,
            self.evidence_cases,
            self.forbidden_claims,
            self.tags,
        ):
            if len(set(values)) != len(values):
                raise ValueError(
                    "customer faq card list fields cannot contain duplicates"
                )
            for value in values:
                if not isinstance(value, str) or not value.strip() or len(value) > 200:
                    raise ValueError(
                        "customer faq card list values must be non-empty strings <= 200 chars"
                    )
        return self


class CustomerFaqDuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_key: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    card_keys: list[str] = Field(default_factory=list, min_length=2, max_length=20)
    reason: str = Field(..., min_length=1, max_length=500)


class CustomerFaqImportParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(..., min_length=1, max_length=300000)


class CustomerFaqImportParseResponse(BaseModel):
    cards: list[CustomerFaqCard] = Field(default_factory=list)
    duplicate_groups: list[CustomerFaqDuplicateGroup] = Field(default_factory=list)
    evidence_cases: list[CustomerFaqEvidenceCase] = Field(default_factory=list)
    total_questions: int
    high_risk_count: int
    escalation_count: int


class CustomerFaqGenerateDraftRequest(CustomerFaqImportParseRequest):
    overwrite_working: bool = False
    reason: str | None = Field(None, max_length=500)


class CustomerFaqLearningTopicResponse(BaseModel):
    topic_key: Literal["customer_faq"] = "customer_faq"
    title: str
    description: str | None = None
    revision_id: str
    revision_no: int
    units: list[BusinessEtiquetteTrainingUnitConfig] = Field(default_factory=list)
    cards: list[CustomerFaqCard] = Field(default_factory=list)
    duplicate_groups: list[CustomerFaqDuplicateGroup] = Field(default_factory=list)
    evidence_cases: list[CustomerFaqEvidenceCase] = Field(default_factory=list)
    audio_scenario_key: str | None = None
    quiz_paper_id: str | None = None
    ai_coach: AiCoachConfig | None = None


class CustomerFaqShortAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_key: str = Field(..., min_length=1, max_length=120)
    answer_text: str = Field(..., min_length=1, max_length=5000)


class CustomerFaqShortAnswerSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[CustomerFaqShortAnswerSubmit] = Field(
        default_factory=list,
        min_length=1,
        max_length=10,
    )


class CustomerFaqShortAnswerResult(BaseModel):
    card_key: str
    question: str
    answer_text: str
    score: float
    max_score: float = 100.0
    passed: bool
    feedback: str
    reason: str | None = None
    scoring_source: str
    scoring_provider: str | None = None
    scoring_model: str | None = None
    scoring_latency_ms: int | None = None


class CustomerFaqShortAnswerAttemptResponse(BaseModel):
    topic_key: Literal["customer_faq"] = "customer_faq"
    learning_unit_key: str
    learning_unit_title: str
    total_score: float
    max_score: float
    passed: bool | None = None
    pass_threshold: float | None = None
    answers: list[CustomerFaqShortAnswerResult] = Field(default_factory=list)


class NewcomerLearningTopicConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_key: NewcomerLearningTopicKey = "business_etiquette"
    source_module_key: str = Field("business_skills", min_length=1, max_length=80)
    content_kind: NewcomerLearningTopicContentKind = "article"
    enabled: bool = True
    disabled_reason: str | None = Field(None, max_length=300)
    title: str = Field("商务礼仪规范", min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    order_index: int = Field(1, ge=1)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)
    faq_cards: list[CustomerFaqCard] = Field(default_factory=list)
    duplicate_groups: list[CustomerFaqDuplicateGroup] = Field(default_factory=list)
    evidence_cases: list[CustomerFaqEvidenceCase] = Field(default_factory=list)
    audio_scenario_key: str | None = Field(None, min_length=1, max_length=80)
    quiz_paper_id: str | None = Field(None, min_length=1, max_length=36)
    learning_units: list[BusinessEtiquetteTrainingUnitConfig] = Field(
        default_factory=list
    )
    ai_coach: AiCoachConfig | None = None
    required: Literal[False] = False
    blocks_next: Literal[False] = False
    score_display_policy: LearningTopicScoreDisplayPolicy = "quiz_attempt_score"

    @model_validator(mode="after")
    def validate_learning_topic(self) -> NewcomerLearningTopicConfig:
        unit_keys = [unit.unit_key for unit in self.learning_units]
        if len(set(unit_keys)) != len(unit_keys):
            raise ValueError("learning_units cannot contain duplicate unit_key values")
        order_indexes = [unit.order_index for unit in self.learning_units]
        if len(set(order_indexes)) != len(order_indexes):
            raise ValueError(
                "learning_units cannot contain duplicate order_index values"
            )
        if self.topic_key == "business_etiquette":
            if self.content_kind != "article":
                raise ValueError(
                    "business_etiquette topic must use article content_kind"
                )
            if self.source_module_key != "business_skills":
                raise ValueError(
                    "business_etiquette source_module_key must be business_skills"
                )
        if self.topic_key == "customer_faq":
            if self.content_kind != "faq_cards":
                raise ValueError("customer_faq topic must use faq_cards content_kind")
            if self.source_module_key != "customer_faq":
                raise ValueError("customer_faq source_module_key must be customer_faq")
            card_keys = [card.card_key for card in self.faq_cards]
            if len(set(card_keys)) != len(card_keys):
                raise ValueError("faq_cards cannot contain duplicate card_key values")
            group_keys = [group.group_key for group in self.duplicate_groups]
            if len(set(group_keys)) != len(group_keys):
                raise ValueError(
                    "duplicate_groups cannot contain duplicate group_key values"
                )
        return self


class NewcomerLearningTopicsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["newcomer_learning_topics_v1"] = (
        "newcomer_learning_topics_v1"
    )
    topics: list[NewcomerLearningTopicConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_topics(self) -> NewcomerLearningTopicsPayload:
        keys = [topic.topic_key for topic in self.topics]
        if len(set(keys)) != len(keys):
            raise ValueError("topics cannot contain duplicate topic_key values")
        unsupported = sorted(set(keys) - {"business_etiquette", "customer_faq"})
        if unsupported:
            raise ValueError("unsupported learning topic keys")
        return self


class NewcomerLearningTopicsSaveRequest(NewcomerLearningTopicsPayload):
    reason: str | None = Field(None, max_length=500)


class NewcomerLearningTopicsActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)
    revision_id: str | None = Field(None, min_length=1, max_length=36)


class NewcomerLearningTopicsRollbackPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str = Field(..., min_length=1, max_length=36)


class NewcomerLearningTopicsGenerateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overwrite_working: bool = False
    reason: str | None = Field(None, max_length=500)


class NewcomerLearningTopicRevisionSummary(BaseModel):
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
    topic_count: int
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


class NewcomerLearningTopicsRevisionListResponse(BaseModel):
    items: list[NewcomerLearningTopicRevisionSummary] = Field(default_factory=list)
    total: int


class NewcomerLearningTopicsConfigResponse(BaseModel):
    source: Literal["active_revision", "not_configured"]
    fallback_reason: str | None = None
    legacy_snapshot_only: Literal[False] = False
    management_entry: Literal["/admin/sales-trainer/learning-topics"]
    permission: Literal["sales_trainer.manage_modules"]
    payload: NewcomerLearningTopicsPayload
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    active_revision_snapshot: dict[str, Any] | None = None
    working_revision_id: str | None = None
    working_revision_no: int | None = None
    has_unpublished_revision: bool
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class NewcomerLearningTopicsPreviewResponse(BaseModel):
    action: Literal[
        "newcomer_learning_topics.publish",
        "newcomer_learning_topics.rollback",
    ]
    permission: Literal["sales_trainer.manage_modules"]
    requires_reason: bool
    requires_trace_id: bool
    future_only: bool
    risk_level: Literal["low", "medium", "high"]
    risk_reasons: list[str] = Field(default_factory=list)
    change_class: Literal[
        "non_semantic",
        "semantic",
        "binding",
        "scoring_high_risk",
    ]
    target_revision_id: str
    target_revision_no: int
    target_revision_status: Literal["working", "published", "archived"]
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any]
    audit_event: dict[str, Any]
    rollback_hint: dict[str, Any]


class NewcomerDeadDataDiagnosticIssue(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    source: str
    revision_id: str | None = None
    revision_no: int | None = None
    module_key: str | None = None
    resource_type: str
    resource_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NewcomerDeadDataCandidateAction(BaseModel):
    issue_code: str
    source: str
    resource_type: str
    resource_id: str | None = None
    action: str
    reason: str
    mutates_history: bool = False
    safe_to_apply_automatically: bool = False
    requires_manual_approval: bool = True


class NewcomerDeadDataManualDecision(BaseModel):
    decision_key: str
    owner: str
    required_before: str
    issue_codes: list[str] = Field(default_factory=list)
    reason: str


class NewcomerDeadDataRollbackPlan(BaseModel):
    required: bool = False
    reason: str
    apply_endpoint: str | None = None
    rollback_endpoint: str | None = None


class NewcomerDeadDataDiagnosticsResponse(BaseModel):
    mode: Literal["dry_run"] = "dry_run"
    mutates_history: bool = False
    requires_manual_approval: bool = True
    permission: str = "sales_trainer.manage_modules"
    generated_at: str
    summary: dict[str, int]
    scanned: dict[str, Any]
    issues: list[NewcomerDeadDataDiagnosticIssue] = Field(default_factory=list)
    candidate_actions: list[NewcomerDeadDataCandidateAction] = Field(
        default_factory=list
    )
    manual_decisions: list[NewcomerDeadDataManualDecision] = Field(default_factory=list)
    rollback_plan: NewcomerDeadDataRollbackPlan


class QuizAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=36)
    answer_payload: Any


class QuizAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(..., min_length=1, max_length=36)
    answers: list[QuizAnswerSubmit] = Field(..., min_length=1)
    # 幂等键：前端生成的 uuid，重复提交同一 token 返回已存在 attempt，避免重复判分。
    client_token: str | None = Field(default=None, min_length=1, max_length=100)


class QuizAnswerResponse(BaseModel):
    answer_id: str
    question_id: str
    question_type: QuestionType
    answer_payload: Any
    question_title: str | None = None
    question_stem: str | None = None
    question_revision_id: str | None = None
    question_payload_hash: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    correct_answer: Any = None
    reference_answer: str | None = None
    explanation: str | None = None
    scoring_feedback: str | None = None
    scoring_reason: str | None = None
    normalized_score: float | None = None
    max_score: float | None = None
    scoring_dimensions: list[str] = Field(default_factory=list)
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
    question_revision_id: str | None = None
    question_payload_hash: str | None = None
    legacy_snapshot_only: bool | None = None
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
    # 幂等键：前端生成的 uuid，重复提交同一 token 返回已存在 attempt，避免重复判分。
    client_token: str | None = Field(default=None, min_length=1, max_length=100)


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


class LearningContentBindingUnitImpact(BaseModel):
    unit_key: str
    title: str
    source_chapter_orders: list[int] = Field(default_factory=list)
    ai_coach_remediation_chapter_orders: list[int] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    require_quiz: bool
    require_ai_coach: bool


class LearningContentPathBindingImpact(BaseModel):
    source: Literal["active_revision", "working_revision"]
    path_key: str
    module_key: str
    module_title: str
    revision_id: str
    revision_no: int
    learner_effective: bool
    learning_units: list[LearningContentBindingUnitImpact] = Field(default_factory=list)
    impacted_chapter_orders: list[int] = Field(default_factory=list)


class LearningContentBindingImpactResponse(BaseModel):
    learning_content_id: str
    active_bindings: list[LearningContentPathBindingImpact] = Field(
        default_factory=list
    )
    working_bindings: list[LearningContentPathBindingImpact] = Field(
        default_factory=list
    )
    has_active_binding: bool
    has_working_binding: bool
    is_bound_to_business_skills: bool
    can_archive: bool
    archive_block_reason: str | None = None
    management_entries: dict[str, str] = Field(default_factory=dict)


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


class NewcomerArticleProgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str = Field(..., min_length=1, max_length=36)
    learning_content_id: str | None = Field(None, min_length=1, max_length=36)


class NewcomerArticleProgressResponse(BaseModel):
    module_key: str
    learning_content_id: str
    completed_chapter_ids: list[str] = Field(default_factory=list)
    total_chapters: int
    is_completed: bool


class BusinessEtiquetteLearningChapterResponse(BaseModel):
    chapter_id: str
    title: str
    order_index: int
    completed: bool


class BusinessEtiquetteLearningUnitProgressResponse(BaseModel):
    completed_chapter_ids: list[str] = Field(default_factory=list)
    total_chapters: int
    completed_chapters: int
    is_completed: bool


class BusinessEtiquetteMasteryLevelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_key: str = Field(..., min_length=1, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=80)
    min_score: float = Field(..., ge=0, le=100)
    description: str | None = Field(None, max_length=500)


class BusinessEtiquetteEvidenceRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: Literal[
        "quiz_question",
        "ai_coach_card",
        "coach_feedback",
        "reading_progress",
        "manual_review",
    ]
    weight: float = Field(1.0, ge=0, le=10)
    required: bool = False
    description: str | None = Field(None, max_length=500)


class BusinessEtiquetteCapabilityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_key: str = Field(..., min_length=1, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    mastery_levels: list[BusinessEtiquetteMasteryLevelConfig] = Field(
        default_factory=list
    )
    default_threshold: float = Field(..., ge=0, le=100)
    evidence_rules: list[BusinessEtiquetteEvidenceRuleConfig] = Field(
        default_factory=list
    )
    owner_scope: Literal["business_etiquette_training_pack"] = (
        "business_etiquette_training_pack"
    )
    status: Literal["draft", "published", "archived"] = "draft"

    @model_validator(mode="after")
    def validate_capability(self) -> BusinessEtiquetteCapabilityConfig:
        if not self.mastery_levels:
            raise ValueError("mastery_levels must contain at least one item")
        ordered_scores = [level.min_score for level in self.mastery_levels]
        if ordered_scores != sorted(ordered_scores):
            raise ValueError("mastery_levels must be ordered by min_score")
        if len({level.level_key for level in self.mastery_levels}) != len(
            self.mastery_levels
        ):
            raise ValueError("mastery_levels cannot contain duplicate level_key values")
        if not self.evidence_rules:
            raise ValueError("evidence_rules must contain at least one item")
        return self


class BusinessEtiquetteChapterCapabilityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_order: int = Field(..., ge=1, le=100)
    capability_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_binding(self) -> BusinessEtiquetteChapterCapabilityBinding:
        if len(self.capability_keys) > 20:
            raise ValueError("capability_keys must contain <= 20 items")
        if len(set(self.capability_keys)) != len(self.capability_keys):
            raise ValueError("capability_keys cannot contain duplicates")
        for value in self.capability_keys:
            if not value.strip() or len(value) > 80:
                raise ValueError(
                    "capability_keys must be non-empty strings <= 80 chars"
                )
        return self


class BusinessEtiquetteLearningUnitResponse(BaseModel):
    unit_key: str
    title: str
    description: str | None = None
    order_index: int
    enabled: bool
    source_chapter_orders: list[int] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    unlock_after_unit_keys: list[str] = Field(default_factory=list)
    require_reading: bool
    require_quiz: bool
    require_ai_coach: bool
    allow_skip_reading: bool
    block_next_until_complete: bool
    empty_state_message: str | None = None
    capabilities: list[BusinessEtiquetteCapabilityConfig] = Field(default_factory=list)
    chapters: list[BusinessEtiquetteLearningChapterResponse] = Field(
        default_factory=list
    )
    progress: BusinessEtiquetteLearningUnitProgressResponse


class BusinessEtiquetteLearningUnitsResponse(BaseModel):
    module_key: str
    topic_key: str | None = None
    learning_content_id: str
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    units: list[BusinessEtiquetteLearningUnitResponse] = Field(default_factory=list)


class BusinessEtiquetteKnowledgePointResponse(BaseModel):
    title: str
    order_index: int
    line_number: int


class BusinessEtiquetteMicroChapterResponse(BaseModel):
    title: str
    order_index: int
    line_number: int
    knowledge_points: list[BusinessEtiquetteKnowledgePointResponse] = Field(
        default_factory=list
    )


class BusinessEtiquetteImportedChapterResponse(BaseModel):
    title: str
    order_index: int
    line_number: int
    content_hash: str
    micro_chapters: list[BusinessEtiquetteMicroChapterResponse] = Field(
        default_factory=list
    )


class BusinessEtiquetteImportResponse(BaseModel):
    training_pack_key: str
    learning_content_id: str
    learning_content_status: Literal["draft"]
    working_revision_id: str
    working_revision_no: int
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    has_unpublished_revision: bool
    source_filename: str
    content_type: str | None = None
    file_size_bytes: int
    content_hash: str
    imported_at: str
    allow_overwrite_draft: bool
    ai_suggestions_enabled: bool
    book_title: str
    original_chapter_count: int
    micro_chapter_count: int
    knowledge_point_count: int
    chapters: list[BusinessEtiquetteImportedChapterResponse] = Field(
        default_factory=list
    )


class BusinessEtiquetteCapabilitySnapshotSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_pack_key: str | None = Field(None, min_length=1, max_length=80)
    capabilities: list[BusinessEtiquetteCapabilityConfig] = Field(default_factory=list)
    chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding] = Field(
        default_factory=list
    )
    reason: str | None = Field(None, max_length=500)


class BusinessEtiquetteCapabilityActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_pack_key: str | None = Field(None, min_length=1, max_length=80)
    reason: str | None = Field(None, max_length=500)


class BusinessEtiquetteCapabilitySnapshotResponse(BaseModel):
    training_pack_key: str
    source: Literal["working_revision", "active_revision", "default_seed"]
    working_revision_id: str | None = None
    working_revision_no: int | None = None
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    has_unpublished_revision: bool
    schema_version: int
    capabilities: list[BusinessEtiquetteCapabilityConfig] = Field(default_factory=list)
    chapter_bindings: list[BusinessEtiquetteChapterCapabilityBinding] = Field(
        default_factory=list
    )
    original_chapter_count: int | None = None
    needs_save: bool = False
    management_entry: str = "/admin/sales-trainer/articles/capabilities"
    permission: str = "sales_trainer.manage_modules"
    effective_timing: str = "training_pack_revision_publish_time"


class BusinessEtiquetteQuestionDraftOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(..., min_length=1, max_length=20)
    label: str = Field(..., min_length=1, max_length=500)


class BusinessEtiquetteQuestionDraftGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    training_pack_key: str | None = Field(None, min_length=1, max_length=80)
    chapter_order: int = Field(..., ge=1, le=100)
    prompt_template_id: str = Field(..., min_length=1, max_length=36)
    question_types: list[BusinessEtiquetteQuestionDraftType] = Field(
        default_factory=_default_business_etiquette_question_draft_types
    )
    draft_count: int = Field(3, ge=1, le=10)
    capability_keys: list[str] = Field(default_factory=list)
    llm_model_config: dict[str, Any] = Field(
        default_factory=dict,
        alias="model_config",
    )
    reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_generation_request(
        self,
    ) -> BusinessEtiquetteQuestionDraftGenerateRequest:
        if not self.question_types:
            raise ValueError("question_types must contain at least one item")
        if len(set(self.question_types)) != len(self.question_types):
            raise ValueError("question_types cannot contain duplicates")
        _validate_business_etiquette_capability_key_list(self.capability_keys)
        return self


class BusinessEtiquetteQuestionDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    stem: str | None = Field(None, min_length=1)
    question_type: BusinessEtiquetteQuestionDraftType | None = None
    options: list[BusinessEtiquetteQuestionDraftOption] | None = None
    correct_answer: str | None = Field(None, min_length=1, max_length=20)
    correct_answers: list[str] | None = None
    reference_answer: str | None = Field(None, min_length=1, max_length=8000)
    explanation: str | None = Field(None, max_length=4000)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    capability_keys: list[str] | None = None
    source_excerpt: str | None = Field(None, max_length=4000)
    review_notes: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def validate_update_request(
        self,
    ) -> BusinessEtiquetteQuestionDraftUpdateRequest:
        if self.capability_keys is not None:
            _validate_business_etiquette_capability_key_list(self.capability_keys)
        if self.correct_answers is not None:
            _validate_business_etiquette_answer_values(self.correct_answers)
        return self


class BusinessEtiquetteQuestionDraftApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(..., min_length=1, max_length=36)
    review_notes: str | None = Field(None, max_length=2000)


class BusinessEtiquetteQuestionDraftRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_notes: str = Field(..., min_length=1, max_length=2000)


class BusinessEtiquetteQuestionDraftResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    draft_id: str
    batch_id: str
    training_pack_key: str
    training_pack_revision_id: str | None = None
    training_pack_revision_no: int | None = None
    learning_content_id: str | None = None
    chapter_id: str | None = None
    chapter_order: int
    chapter_title: str | None = None
    source_excerpt: str | None = None
    question_type: BusinessEtiquetteQuestionDraftType
    title: str
    stem: str
    options: list[BusinessEtiquetteQuestionDraftOption] = Field(default_factory=list)
    correct_answer: str | None = None
    correct_answers: list[str] = Field(default_factory=list)
    reference_answer: str | None = None
    explanation: str | None = None
    difficulty: Literal["easy", "medium", "hard"]
    capability_keys: list[str] = Field(default_factory=list)
    status: BusinessEtiquetteQuestionDraftStatus
    prompt_template_id: str
    prompt_template_name: str | None = None
    prompt_contract_hash: str
    prompt_contract_version: str
    prompt_rendered_hash: str
    llm_model_config: dict[str, Any] = Field(
        default_factory=dict,
        alias="model_config",
    )
    raw_generation: dict[str, Any] = Field(default_factory=dict)
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: object | None = None
    question_id: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object


class BusinessEtiquetteQuestionDraftGenerateResponse(BaseModel):
    batch_id: str
    items: list[BusinessEtiquetteQuestionDraftResponse] = Field(default_factory=list)
    total: int


class BusinessEtiquetteQuestionDraftListResponse(BaseModel):
    items: list[BusinessEtiquetteQuestionDraftResponse] = Field(default_factory=list)
    total: int


class BusinessEtiquetteQuizQuestionResponse(BaseModel):
    question_id: str
    title: str
    stem: str
    question_type: BusinessEtiquetteQuestionDraftType
    points: int = Field(..., gt=0, le=100)
    order_index: int = Field(..., ge=1)
    options: list[BusinessEtiquetteQuestionDraftOption] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    chapter_orders: list[int] = Field(default_factory=list)


class BusinessEtiquetteUnitQuizResponse(BaseModel):
    training_pack_key: str
    learning_unit_key: str
    learning_unit_title: str
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    training_pack_revision_id: str | None = None
    training_pack_revision_no: int | None = None
    question_count: int
    pass_threshold: float | None = None
    allow_retake: bool
    max_attempts: int | None = None
    capabilities: list[BusinessEtiquetteCapabilityConfig] = Field(default_factory=list)
    questions: list[BusinessEtiquetteQuizQuestionResponse] = Field(default_factory=list)


class BusinessEtiquetteQuizAnswerSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(..., min_length=1, max_length=36)
    answer_payload: Any


class BusinessEtiquetteUnitQuizAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[BusinessEtiquetteQuizAnswerSubmit] = Field(default_factory=list)


class BusinessEtiquetteCapabilityScoreResponse(BaseModel):
    capability_key: str
    display_name: str
    score: float | None = None
    max_score: float
    normalized_score: float | None = None
    threshold: float
    mastered: bool | None = None
    mastery_level_key: str | None = None
    mastery_level_name: str | None = None


BusinessEtiquetteAiCoachProgressStatus = Literal[
    "not_started",
    "in_progress",
    "not_mastered",
    "mastered",
    "ready",
    "manual_review",
]
BusinessEtiquetteReleaseStrategy = Literal[
    "future_learners_only",
    "allow_voluntary_switch",
    "assign_retraining",
]


class BusinessEtiquetteAiCoachProgressResponse(BaseModel):
    session_id: str
    module_key: str
    learning_unit_key: str
    learning_unit_title: str
    status: BusinessEtiquetteAiCoachProgressStatus
    passed: bool
    ready_for_field: bool
    manual_review_required: bool
    block_next: bool
    answered_card_count: int = Field(..., ge=0)
    scored_card_count: int = Field(..., ge=0)
    remediation_attempt_count: int = Field(..., ge=0)
    max_remediation_attempts: int = Field(..., ge=1)
    pass_mastery_level_key: str
    ready_mastery_level_key: str
    weak_capability_keys: list[str] = Field(default_factory=list)
    recommended_chapter_orders: list[int] = Field(default_factory=list)
    recommended_training_card_types: list[AiCoachTrainingCardTypeV1] = Field(
        default_factory=list
    )
    next_step_code: Literal[
        "start_training",
        "continue_remediation",
        "manual_review",
        "mastered",
        "ready",
    ]
    next_step: str
    capability_scores: list[BusinessEtiquetteCapabilityScoreResponse] = Field(
        default_factory=list
    )


class BusinessEtiquetteQuizAnswerResultResponse(BaseModel):
    question_id: str
    question_type: BusinessEtiquetteQuestionDraftType
    answer_payload: Any
    is_correct: bool | None = None
    score: float | None = None
    max_score: float
    capability_keys: list[str] = Field(default_factory=list)
    question_snapshot: dict[str, Any] = Field(default_factory=dict)
    analysis: str | None = None
    scoring_source: str | None = None
    scoring_provider: str | None = None
    scoring_model: str | None = None
    scoring_latency_ms: int | None = None


class BusinessEtiquetteUnitQuizAttemptResponse(BaseModel):
    attempt_id: str
    training_pack_key: str
    learning_unit_key: str
    learning_unit_title: str
    user_id: str
    user_name: str | None = None
    user_department: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    training_pack_revision_id: str | None = None
    training_pack_revision_no: int | None = None
    status: Literal["submitted", "scored", "failed"]
    total_score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    capability_scores: list[BusinessEtiquetteCapabilityScoreResponse] = Field(
        default_factory=list
    )
    weak_capability_keys: list[str] = Field(default_factory=list)
    recommended_chapter_orders: list[int] = Field(default_factory=list)
    answers: list[BusinessEtiquetteQuizAnswerResultResponse] = Field(
        default_factory=list
    )
    submitted_at: object


class BusinessEtiquetteUnitQuizAttemptListResponse(BaseModel):
    items: list[BusinessEtiquetteUnitQuizAttemptResponse] = Field(default_factory=list)
    total: int


class BusinessEtiquetteReleaseConfigResponse(BaseModel):
    default_strategy: BusinessEtiquetteReleaseStrategy
    allow_voluntary_switch: bool
    allow_assigned_retraining: bool
    max_assigned_retraining_users: int = Field(..., ge=1)
    notification_template: str
    large_change_chapter_threshold: int = Field(..., ge=1)
    management_entry: str


class BusinessEtiquetteReleaseImpactSummaryResponse(BaseModel):
    changed_chapter_count: int = Field(..., ge=0)
    impacted_learning_unit_count: int = Field(..., ge=0)
    impacted_question_count: int = Field(..., ge=0)
    impacted_question_draft_count: int = Field(..., ge=0)
    impacted_capability_count: int = Field(..., ge=0)
    impacted_ai_coach_config_count: int = Field(..., ge=0)
    active_learner_count: int = Field(..., ge=0)
    recommended_retraining_user_count: int = Field(..., ge=0)
    is_large_change: bool


class BusinessEtiquetteReleaseChapterChangeResponse(BaseModel):
    chapter_order: int = Field(..., ge=1)
    title: str
    change_type: Literal["added", "removed", "changed"]
    previous_content_hash: str | None = None
    target_content_hash: str | None = None


class BusinessEtiquetteReleaseLearningUnitImpactResponse(BaseModel):
    unit_key: str
    title: str
    source_chapter_orders: list[int] = Field(default_factory=list)
    capability_keys: list[str] = Field(default_factory=list)
    impacted_chapter_orders: list[int] = Field(default_factory=list)
    impacted_capability_keys: list[str] = Field(default_factory=list)
    require_quiz: bool
    require_ai_coach: bool


class BusinessEtiquetteReleaseQuestionImpactResponse(BaseModel):
    question_id: str
    draft_id: str
    title: str
    question_type: BusinessEtiquetteQuestionDraftType
    chapter_order: int = Field(..., ge=1)
    capability_keys: list[str] = Field(default_factory=list)


class BusinessEtiquetteReleaseQuestionDraftImpactResponse(BaseModel):
    draft_id: str
    title: str
    question_type: BusinessEtiquetteQuestionDraftType
    status: BusinessEtiquetteQuestionDraftStatus
    chapter_order: int = Field(..., ge=1)
    capability_keys: list[str] = Field(default_factory=list)


class BusinessEtiquetteReleaseCapabilityImpactResponse(BaseModel):
    capability_key: str
    display_name: str
    change_type: Literal["added", "removed", "changed"]
    previous_status: BusinessEtiquetteCapabilityStatus | None = None
    target_status: BusinessEtiquetteCapabilityStatus | None = None


class BusinessEtiquetteReleaseAiCoachConfigImpactResponse(BaseModel):
    unit_key: str
    title: str
    prompt_template_id: str | None = None
    scoring_prompt_template_id: str | None = None
    allowed_training_card_types: list[AiCoachTrainingCardTypeV1] = Field(
        default_factory=list
    )
    affected_reason: str


class BusinessEtiquetteReleaseLearnerImpactResponse(BaseModel):
    user_id: str
    user_name: str | None = None
    department: str | None = None
    source_record_types: list[Literal["quiz_attempt", "ai_coach_session"]] = Field(
        default_factory=list
    )
    latest_path_revision_no: int | None = None
    latest_training_pack_revision_no: int | None = None
    has_active_ai_coach_session: bool


class BusinessEtiquetteReleaseImpactResponse(BaseModel):
    training_pack_key: str
    active_revision_id: str | None = None
    active_revision_no: int | None = None
    target_revision_id: str
    target_revision_no: int
    target_revision_status: Literal["working", "published", "archived"]
    strategy_options: list[BusinessEtiquetteReleaseStrategy] = Field(
        default_factory=list
    )
    config: BusinessEtiquetteReleaseConfigResponse
    summary: BusinessEtiquetteReleaseImpactSummaryResponse
    chapter_changes: list[BusinessEtiquetteReleaseChapterChangeResponse] = Field(
        default_factory=list
    )
    impacted_learning_units: list[
        BusinessEtiquetteReleaseLearningUnitImpactResponse
    ] = Field(default_factory=list)
    impacted_questions: list[BusinessEtiquetteReleaseQuestionImpactResponse] = Field(
        default_factory=list
    )
    impacted_question_drafts: list[
        BusinessEtiquetteReleaseQuestionDraftImpactResponse
    ] = Field(default_factory=list)
    impacted_capabilities: list[BusinessEtiquetteReleaseCapabilityImpactResponse] = (
        Field(default_factory=list)
    )
    impacted_ai_coach_configs: list[
        BusinessEtiquetteReleaseAiCoachConfigImpactResponse
    ] = Field(default_factory=list)
    active_learners: list[BusinessEtiquetteReleaseLearnerImpactResponse] = Field(
        default_factory=list
    )
    recommended_retraining_user_ids: list[str] = Field(default_factory=list)


class BusinessEtiquetteReleasePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_pack_key: str | None = Field(None, min_length=1, max_length=80)
    strategy: BusinessEtiquetteReleaseStrategy = "future_learners_only"
    assigned_user_ids: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("assigned_user_ids")
    @classmethod
    def validate_assigned_user_ids(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values if value.strip()]
        if len(set(stripped)) != len(stripped):
            raise ValueError("assigned_user_ids cannot contain duplicates")
        return stripped


class BusinessEtiquetteReleasePublishResponse(BaseModel):
    training_pack_key: str
    active_revision_id: str
    active_revision_no: int
    previous_revision_id: str | None = None
    strategy: BusinessEtiquetteReleaseStrategy
    impact_summary: BusinessEtiquetteReleaseImpactSummaryResponse
    created_session_ids: list[str] = Field(default_factory=list)


class BusinessEtiquetteRetrainingStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(None, max_length=500)


class BusinessEtiquetteRetrainingAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_pack_key: str | None = Field(None, min_length=1, max_length=80)
    user_ids: list[str] = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values if value.strip()]
        if len(set(stripped)) != len(stripped):
            raise ValueError("user_ids cannot contain duplicates")
        if not stripped:
            raise ValueError("user_ids must contain at least one id")
        return stripped


class BusinessEtiquetteRetrainingAssignmentResponse(BaseModel):
    training_pack_key: str
    assigned_user_ids: list[str]
    created_session_ids: list[str]
    reason: str


def _validate_business_etiquette_capability_key_list(values: list[str]) -> None:
    if len(values) > 20:
        raise ValueError("capability_keys must contain <= 20 items")
    if len(set(values)) != len(values):
        raise ValueError("capability_keys cannot contain duplicates")
    for value in values:
        if not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise ValueError("capability_keys must be non-empty strings <= 80 chars")


def _validate_business_etiquette_answer_values(values: list[str]) -> None:
    if len(values) > 20:
        raise ValueError("correct_answers must contain <= 20 items")
    if len(set(values)) != len(values):
        raise ValueError("correct_answers cannot contain duplicates")
    for value in values:
        if not isinstance(value, str) or not value.strip() or len(value) > 20:
            raise ValueError("correct_answers items must be strings <= 20 chars")


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


class SalesTrainerLearnerMaterialVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version_id: str
    material_id: str
    version_label: str
    title: str
    file_name: str
    content_type: str
    file_size_bytes: int
    file_hash: str | None = None
    release_notes: str | None = None
    status: SalesTrainerStatus
    published_at: object | None = None


class SalesTrainerMaterialVersionRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_version_id: str = Field(..., min_length=1, max_length=36)
    reason: str = Field(..., min_length=1, max_length=1000)


class SalesTrainerMaterialVersionRollbackPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_version_id: str = Field(..., min_length=1, max_length=36)


class SalesTrainerMaterialVersionRollbackPreviewResponse(BaseModel):
    action: Literal["material_version.rollback"]
    permission: Literal["sales_trainer.manage_modules"]
    requires_reason: bool
    future_only: bool
    mutates_history: bool
    target_material_id: str
    current_version_id: str | None = None
    target_version: SalesTrainerMaterialVersionResponse
    future_material_current_version_changed: bool
    historical_submissions_changed: bool
    historical_replay_preserved: bool
    active_or_working_path_refs: list[dict[str, Any]] = Field(default_factory=list)
    rollback_plan: dict[str, Any]


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
    current_version: SalesTrainerLearnerMaterialVersionResponse


class SalesTrainerUnitBriefResponse(BaseModel):
    unit: SalesTrainerUnitResponse
    task_brief: SalesTrainerTaskBriefConfig
    materials: list[SalesTrainerUnitMaterialBriefItem]
    score_scheme: dict[str, Any] | None = None


TrainingJourneyStage = Literal[
    "not_started",
    "in_progress",
    "waiting_upload",
    "processing",
    "scored",
    "passed",
    "failed",
    "needs_remediation",
    "manual_review",
    "disabled",
    "archived",
    "error_terminal",
    "error_transient",
]
TrainingJourneyModuleKind = Literal[
    "audio_submission",
    "quiz_attempt",
    "ai_coach",
    "realtime_roleplay",
]
TrainingJourneyOutcomeRecordType = Literal[
    "audio_submission",
    "quiz_attempt",
    "business_etiquette_quiz_attempt",
    "ai_coach_session",
    "realtime_roleplay_session",
    "remediation",
    "regrade",
]


class TrainingJourneyDiagnostic(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "error"
    terminal: bool


class TrainingJourneyRoleCapability(BaseModel):
    capability_key: str
    allowed: bool
    scope: Literal["own", "department", "global", "none"]
    reason_code: str | None = None


class TrainingJourneyLearnerLevel(BaseModel):
    level_key: str
    label: str
    source: Literal[
        "user_profile",
        "org_rule",
        "admin_assignment",
        "training_projection",
    ]
    rank: int
    effective_from: object | None = None
    effective_to: object | None = None
    config_revision_id: str | None = None
    description: str | None = None
    fallback_applied: bool = False
    fallback_reason: str | None = None
    policy_key: str | None = None
    policy_version: str | None = None
    management_entry: str | None = None


class TrainingJourneyOutcomeEvidence(BaseModel):
    record_id: str
    record_type: TrainingJourneyOutcomeRecordType
    occurred_at: object | None = None


class TrainingJourneySnapshotRef(BaseModel):
    snapshot_type: Literal[
        "path_revision",
        "submission_snapshot",
        "attempt_snapshot",
        "session_snapshot",
        "runtime_outcome_snapshot",
        "regrade_snapshot",
    ]
    legacy_snapshot_only: bool
    regrade_unavailable: bool | None = None


class TrainingJourneyModuleOutcome(BaseModel):
    outcome_id: str
    record_type: TrainingJourneyOutcomeRecordType
    source_record_id: str
    target_unit_id: str | None = Field(None, min_length=1, max_length=36)
    module_key: str
    module_type: str
    kind: TrainingJourneyModuleKind
    status: TrainingJourneyStage
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    failure_type: Literal["terminal", "transient", "voluntary"] | None = None
    failure_code: str | None = None
    submitted_at: object | None = None
    completed_at: object | None = None
    path_revision_id: str
    path_revision_no: int | None = None
    snapshot_ref: TrainingJourneySnapshotRef
    evidence: TrainingJourneyOutcomeEvidence


class TrainingJourneyNextAction(BaseModel):
    action_key: Literal[
        "start_audio_submission",
        "retry_audio_submission",
        "start_quiz_attempt",
        "retry_quiz_attempt",
        "start_ai_coach",
        "continue_ai_coach",
        "start_realtime_roleplay",
    ]
    label: str
    target_path: str | None = None
    disabled: bool
    disabled_reason: str | None = None


class TrainingJourneyModuleProgress(BaseModel):
    module_key: str
    title: str
    display_name: str
    kind: TrainingJourneyModuleKind
    module_type: str
    order_index: int
    target_unit_id: str | None = None
    target_unit_ids: list[str] = Field(default_factory=list)
    learning_content_id: str | None = None
    exam_paper_id: str | None = None
    enabled: bool
    status: TrainingJourneyStage
    stage: TrainingJourneyStage
    passed: bool | None = None
    score: float | None = None
    max_score: float | None = None
    required: bool
    completion_satisfied: bool
    locked: bool
    block_reason: str | None = None
    learner_level_required: list[str] = Field(default_factory=list)
    completion_rule: NewcomerPathCompletionRule | Literal["passed"]
    source: dict[str, Any]
    latest_outcome: TrainingJourneyModuleOutcome | None = None
    outcome_history: list[TrainingJourneyModuleOutcome] = Field(default_factory=list)
    unmet_reasons: list[TrainingJourneyDiagnostic] = Field(default_factory=list)
    diagnostics: list[TrainingJourneyDiagnostic] = Field(default_factory=list)
    next_action: TrainingJourneyNextAction | None = None


class TrainingJourneyOverallProgress(BaseModel):
    total_modules: int
    completed_modules: int
    passed_modules: int
    failed_modules: int
    needs_remediation_modules: int


class TrainingJourneyRetrainingTargetModule(BaseModel):
    module_key: str | None = None
    title: str | None = None
    kind: str | None = None
    module_type: str | None = None
    status: str | None = None
    action_label: str | None = None
    target_path: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None


class TrainingJourneyRetrainingRequest(BaseModel):
    request_id: str
    task_id: str
    status: str
    reason: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    capability_labels: list[str] = Field(default_factory=list)
    source_evidence_count: int = 0
    target_modules: list[TrainingJourneyRetrainingTargetModule] = Field(
        default_factory=list
    )
    primary_target_path: str | None = None
    created_at: object


class TrainingJourneyLearningTopicUnitProgress(BaseModel):
    unit_key: str
    title: str
    order_index: int
    enabled: bool
    capability_keys: list[str] = Field(default_factory=list)
    require_quiz: bool
    quiz_question_count: int
    quiz_pass_threshold: float | None = None
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    status: Literal["not_started", "submitted", "scored", "passed", "failed"]
    latest_attempt_id: str | None = None
    latest_attempt_submitted_at: object | None = None


class TrainingJourneyLearningTopicProgress(BaseModel):
    topic_key: str
    source_module_key: str
    title: str
    description: str | None = None
    order_index: int
    learning_content_id: str | None = None
    required: Literal[False] = False
    blocks_next: Literal[False] = False
    score_display_policy: LearningTopicScoreDisplayPolicy
    status: Literal["not_started", "in_progress", "passed", "needs_remediation"]
    units: list[TrainingJourneyLearningTopicUnitProgress] = Field(default_factory=list)
    ai_coach: SalesTrainerAiCoachAvailabilityResponse | None = None
    source: dict[str, Any]


class TrainingJourneyResponse(BaseModel):
    journey_id: str
    learner_id: str
    learner_name: str | None = None
    department: str | None = None
    path_key: str
    path_revision_id: str
    path_revision_no: int
    source: Literal["active_revision"]
    legacy_snapshot_only: bool
    role_capabilities: list[TrainingJourneyRoleCapability] = Field(default_factory=list)
    learner_level: TrainingJourneyLearnerLevel
    role_level: TrainingJourneyLearnerLevel
    training_stage: TrainingJourneyStage
    modules: list[TrainingJourneyModuleProgress] = Field(default_factory=list)
    learning_topics: list[TrainingJourneyLearningTopicProgress] = Field(
        default_factory=list
    )
    overall_progress: TrainingJourneyOverallProgress
    retraining_requests: list[TrainingJourneyRetrainingRequest] = Field(
        default_factory=list
    )
    diagnostics: list[TrainingJourneyDiagnostic] = Field(default_factory=list)
    generated_at: object


class TrainingJourneyListResponse(BaseModel):
    items: list[TrainingJourneyResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class TrainingJourneyAnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_count: int
    loaded_learner_count: int
    passed_learner_count: int
    risk_learner_count: int
    pass_rate: float | None = None


class TrainingJourneyAnalyticsFunnelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: TrainingJourneyStage
    learner_count: int
    rate: float | None = None


class TrainingJourneyAnalyticsModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str
    title: str
    kind: str | None = None
    module_type: str | None = None
    learner_count: int
    passed_count: int
    failed_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    pass_rate: float | None = None
    average_score: float | None = None


class TrainingJourneyAnalyticsLearningTopicSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_key: str
    source_module_key: str | None = None
    title: str
    learner_count: int
    completed_count: int
    needs_remediation_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    completion_rate: float | None = None
    average_unit_score: float | None = None
    blocking_required_path: bool = False


class TrainingJourneyAnalyticsWeaknessHeatmapEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heatmap_key: str
    module_key: str
    title: str
    kind: str | None = None
    module_type: str | None = None
    learner_count: int
    risk_count: int
    passed_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    risk_rate: float | None = None
    pass_rate: float | None = None
    average_score: float | None = None


class TrainingJourneyAnalyticsTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    outcome_count: int
    passed_outcome_count: int
    risk_outcome_count: int
    active_learner_count: int
    pass_rate: float | None = None
    average_score: float | None = None


class TrainingJourneyAnalyticsLevelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    learner_count: int
    passed_count: int
    pass_rate: float | None = None
    source: str | None = None


class TrainingJourneyAnalyticsRiskLearner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str
    learner_name: str | None = None
    department: str | None = None
    training_stage: TrainingJourneyStage
    risk_reasons: list[str] = Field(default_factory=list)
    risk_module_count: int
    risk_module_keys: list[str] = Field(default_factory=list)


class TrainingJourneyAnalyticsSignalKeyCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    count: int


class TrainingJourneyAnalyticsAdditiveObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_ready: bool
    migration_applied: bool
    session_count: int
    observed_session_count: int
    observation_count: int
    source_counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    top_signal_keys: list[TrainingJourneyAnalyticsSignalKeyCount] = Field(
        default_factory=list
    )
    high_risk_session_count: int
    latest_observed_at: object | None = None


class TrainingJourneyAnalyticsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str | None = None
    training_stage: str | None = None
    module_key: str | None = None
    learner_level: str | None = None
    role_level: str | None = None
    limit: int


class TrainingJourneyAnalyticsResponse(BaseModel):
    generated_at: object
    summary: TrainingJourneyAnalyticsSummary
    funnel: list[TrainingJourneyAnalyticsFunnelEntry] = Field(default_factory=list)
    module_summaries: list[TrainingJourneyAnalyticsModuleSummary] = Field(
        default_factory=list
    )
    learning_topic_summaries: list[TrainingJourneyAnalyticsLearningTopicSummary] = (
        Field(default_factory=list)
    )
    weakness_heatmap: list[TrainingJourneyAnalyticsWeaknessHeatmapEntry] = Field(
        default_factory=list
    )
    trend_data: list[TrainingJourneyAnalyticsTrendPoint] = Field(default_factory=list)
    learner_level_summaries: list[TrainingJourneyAnalyticsLevelSummary] = Field(
        default_factory=list
    )
    role_level_summaries: list[TrainingJourneyAnalyticsLevelSummary] = Field(
        default_factory=list
    )
    risk_learners: list[TrainingJourneyAnalyticsRiskLearner] = Field(
        default_factory=list
    )
    additive_observation: TrainingJourneyAnalyticsAdditiveObservation
    filters: TrainingJourneyAnalyticsFilters


ReadinessDossierStatus = Literal[
    "not_started",
    "in_training",
    "ai_evaluating",
    "needs_remediation",
    "pending_review",
    "approved",
    "rejected",
    "manual_follow_up",
    "blocked_by_config",
]
ReadinessCapabilityStatus = Literal[
    "not_trained",
    "ai_passed",
    "ai_failed",
    "needs_retraining",
    "pending_review",
    "approved",
    "rejected",
    "blocked_by_config",
]
ReadinessReviewDecision = Literal[
    "approve",
    "require_retraining",
    "mark_manual_follow_up",
]
ReadinessWorkbenchGroupKey = Literal[
    "pending_review",
    "not_passed",
    "needs_retraining",
    "approved",
    "config_exception",
    "in_training",
]


class ReadinessDossierLearner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str
    name: str | None = None
    department: str | None = None


class ReadinessDossierPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    source: str | None = None


class ReadinessDossierModuleNextAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    target_path: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None


class ReadinessDossierModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str | None = None
    title: str | None = None
    kind: str | None = None
    module_type: str | None = None
    order_index: int | None = None
    status: str | None = None
    passed: bool | None = None
    score: float | None = None
    max_score: float | None = None
    required: bool | None = None
    completion_satisfied: bool | None = None
    locked: bool | None = None
    block_reason: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    next_action: ReadinessDossierModuleNextAction | None = None


class ReadinessDossierEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: str
    source_record_id: str
    record_type: str
    module_key: str | None = None
    module_title: str | None = None
    module_type: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    status: str | None = None
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    submitted_at: object | None = None
    completed_at: object | None = None
    target_path: str | None = None
    material_snapshot: dict[str, Any] | None = None
    scoring_snapshot: dict[str, Any] | None = None
    task_brief_snapshot: dict[str, Any] | None = None
    snapshot_ref: dict[str, Any] | None = None
    result_summary: str | None = None


class ReadinessDossierCompetency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_key: str
    display_name: str
    description: str | None = None
    status: ReadinessCapabilityStatus
    score: float | None = None
    max_score: float | None = None
    weak: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    latest_evidence_id: str | None = None
    review_decision: str | None = None
    reason: str | None = None


class ReadinessDossierRetrainingTaskComparison(BaseModel):
    model_config = ConfigDict(extra="allow")

    before_evidence_ids: list[str] = Field(default_factory=list)
    after_evidence_ids: list[str] = Field(default_factory=list)
    after_status: str | None = None
    after_passed: bool | None = None
    after_score: float | None = None
    after_max_score: float | None = None


class ReadinessDossierRetrainingTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    status: str = "pending"
    source: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    target_learner_id: str | None = None
    completed_at: object | None = None
    completed_evidence_ids: list[str] = Field(default_factory=list)
    comparison: ReadinessDossierRetrainingTaskComparison | None = None


class ReadinessDossierReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    audit_log_id: str
    decision: ReadinessReviewDecision
    decision_label: str
    reason: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    reviewer_id: str | None = None
    reviewer_role: str | None = None
    created_at: object
    retraining_task: ReadinessDossierRetrainingTask | None = None
    state_storage: Literal["readiness_review_action", "operation_log"]


class ReadinessDossierReviewActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: ReadinessReviewDecision
    reason: str = Field(..., min_length=1, max_length=1000)
    capability_keys: list[str] = Field(default_factory=list, max_length=20)
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    idempotency_key: str = Field(..., min_length=16, max_length=100)
    expected_latest_review_action_id: str | None = Field(
        ...,
        min_length=1,
        max_length=36,
    )

    @field_validator("capability_keys", "source_evidence_ids")
    @classmethod
    def validate_non_empty_strings(cls, values: list[str]) -> list[str]:
        stripped = [value.strip() for value in values if value.strip()]
        if len(set(stripped)) != len(stripped):
            raise ValueError("values cannot contain duplicates")
        return stripped


class ReadinessDossierRealtimeGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str | None = None
    status: str | None = None
    locked: bool
    reason: str | None = None
    training_gate_status: ReadinessDossierStatus
    provider_readiness: dict[str, Any] | None = None


class ReadinessDossierNextAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_key: str
    label: str
    target_path: str | None = None
    primary: bool = False
    capability_keys: list[str] = Field(default_factory=list)


class ReadinessDossierSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_modules: int = 0
    completed_modules: int = 0
    passed_modules: int = 0
    failed_modules: int = 0
    needs_remediation_modules: int = 0
    evidence_count: int = 0
    review_action_count: int = 0
    weak_capability_count: int = 0
    retraining_task_count: int = 0
    completed_retraining_task_count: int = 0
    review_state_source: Literal["readiness_review_action", "operation_log"] = (
        "operation_log"
    )


class ReadinessDossierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["readiness_dossier_v1"]
    learner: ReadinessDossierLearner
    path: ReadinessDossierPath
    status: ReadinessDossierStatus
    status_label: str
    status_reason: str
    summary: ReadinessDossierSummary
    modules: list[ReadinessDossierModuleSummary] = Field(default_factory=list)
    competencies: list[ReadinessDossierCompetency] = Field(default_factory=list)
    evidence: list[ReadinessDossierEvidence] = Field(default_factory=list)
    review_actions: list[ReadinessDossierReviewAction] = Field(default_factory=list)
    latest_review_action: ReadinessDossierReviewAction | None = None
    retraining_tasks: list[ReadinessDossierRetrainingTask] = Field(default_factory=list)
    realtime_gate: ReadinessDossierRealtimeGate
    diagnostics: list[TrainingJourneyDiagnostic] = Field(default_factory=list)
    next_actions: list[ReadinessDossierNextAction] = Field(default_factory=list)
    generated_at: object


class ReadinessWorkbenchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner: ReadinessDossierLearner
    status: ReadinessDossierStatus
    status_label: str
    status_reason: str
    path: ReadinessDossierPath
    weak_capability_keys: list[str] = Field(default_factory=list)
    weak_capability_labels: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    latest_review_action: ReadinessDossierReviewAction | None = None
    next_action: ReadinessDossierNextAction | None = None
    target_path: str | None = None


class ReadinessWorkbenchGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_key: ReadinessWorkbenchGroupKey
    label: str
    count: int
    items: list[ReadinessWorkbenchItem] = Field(default_factory=list)


class ReadinessWorkbenchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_count: int
    loaded_learner_count: int
    pending_review_count: int
    not_passed_count: int
    needs_retraining_count: int
    approved_count: int
    config_exception_count: int
    in_training_count: int


class ReadinessWorkbenchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str | None = None
    limit: int
    offset: int


class ReadinessWorkbenchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["readiness_dossier_v1"]
    generated_at: object
    groups: dict[ReadinessWorkbenchGroupKey, ReadinessWorkbenchGroup]
    summary: ReadinessWorkbenchSummary
    filters: ReadinessWorkbenchFilters


class RealtimeRoleplayStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: Literal["realtime_roleplay"] = "realtime_roleplay"


class RealtimeRoleplayRegistryReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    checked_at: str | None = Field(None, max_length=80)
    failure_code: str | None = Field(None, max_length=120)
    failure_message: str | None = Field(None, max_length=500)


class RealtimeRoleplayRegistryDescriptorSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descriptor_id: str = Field(..., min_length=1, max_length=120)
    label: str | None = Field(None, max_length=120)
    provider: Literal["stepfun_realtime", "phase4_local_stepfun", "mock"]
    runtime_owner: str = Field(..., min_length=1, max_length=120)
    enabled: bool
    runtime_profile_id: str | None = Field(None, min_length=1, max_length=120)
    config_revision_id: str | None = Field(None, min_length=1, max_length=120)
    rollback_to_descriptor_id: str | None = Field(None, min_length=1, max_length=120)
    readiness: RealtimeRoleplayRegistryReadinessSnapshot


class RealtimeRoleplayRuntimeRegistrySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_key: Literal["sales_trainer.realtime_provider.registry"]
    config_id: str | None = None
    version: int | None = None
    source: str = Field(..., min_length=1, max_length=80)
    status: str | None = Field(None, max_length=80)
    fallback_reason: str | None = Field(None, max_length=300)
    descriptor: RealtimeRoleplayRegistryDescriptorSnapshot


class RealtimeRoleplayExternalBindingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: Literal["sales_trainer"]
    path_key: Literal["newcomer_training_path_v1"]
    path_revision_id: str
    path_revision_no: int
    module_key: Literal["realtime_roleplay"]
    binding_key: Literal["newcomer_realtime_roleplay_v1"]
    runtime_descriptor_id: str
    scenario_key: str
    runtime_config_revision_id: str
    runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot
    roleplay_contract_revision_id: str | None = None
    practice_template_id: str
    provider_readiness_snapshot: NewcomerRealtimeProviderReadinessSnapshot
    failure_policy: NewcomerRealtimeFailurePolicy
    started_by_user_id: str
    started_at: str


class RealtimeRoleplayStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    module_key: Literal["realtime_roleplay"]
    path_key: Literal["newcomer_training_path_v1"]
    path_revision_id: str
    path_revision_no: int
    practice_url: str
    runtime_descriptor_id: str
    runtime_registry: RealtimeRoleplayRuntimeRegistrySnapshot
    provider_readiness_snapshot: NewcomerRealtimeProviderReadinessSnapshot
    external_binding: RealtimeRoleplayExternalBindingSnapshot


class SalesTrainerAiCoachArticleChapterSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None


class SalesTrainerAiCoachArticleSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    chapters: list[SalesTrainerAiCoachArticleChapterSnapshot] = Field(
        default_factory=list
    )


class SalesTrainerAiCoachPathConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_key: str | None = None
    module_type: str | None = None
    title: str | None = None
    learning_content_id: str | None = None
    exam_paper_id: str | None = None


class SalesTrainerAiCoachConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    chat_enabled: bool | None = None
    min_turns: int | None = None
    max_turns: int | None = None
    mastery_threshold: float | None = None
    prompt_template_id: str | None = None
    prompt_revision_id: str | None = None
    scoring_prompt_template_id: str | None = None
    scoring_prompt_revision_id: str | None = None


class SalesTrainerAiCoachStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_phase: str | None = None
    active_event_id: str | None = None
    answered_card_count: int | None = None
    correct_streak: int | None = None
    incorrect_streak: int | None = None
    current_focus: str | None = None
    difficulty: str | None = None
    last_action: str | None = None
    can_auto_advance: bool | None = None
    stopped_reason: str | None = None
    business_etiquette_progress: dict[str, Any] | None = None


class SalesTrainerAiCoachRecordSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    module_key: str | None = None
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    article_snapshot: SalesTrainerAiCoachArticleSnapshot | None = None
    path_config_snapshot: SalesTrainerAiCoachPathConfigSnapshot | None = None
    config_snapshot: SalesTrainerAiCoachConfigSnapshot | None = None
    coach_state: SalesTrainerAiCoachStateSnapshot | None = None
    prompt_template_id: str | None = None
    prompt_revision_id: str | None = None
    prompt_contract_hash: str | None = None
    mastery_state: str | None = None
    total_score: float | None = None
    max_score: float | None = None
    status: str
    trace_id: str | None = None
    created_at: object | None = None
    updated_at: object | None = None


class SalesTrainerRealtimeRecordExternalBindingSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    owner: Literal["sales_trainer"]
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    binding_key: str | None = None
    runtime_descriptor_id: str | None = None
    scenario_key: str | None = None
    runtime_config_revision_id: str | None = None
    runtime_registry: SalesTrainerRealtimeRecordRuntimeRegistrySnapshot | None = None
    roleplay_contract_revision_id: str | None = None
    practice_template_id: str | None = None
    provider_readiness_snapshot: (
        SalesTrainerRealtimeRecordProviderReadinessSnapshot | None
    ) = None
    failure_policy: SalesTrainerRealtimeRecordFailurePolicySnapshot | None = None
    started_by_user_id: str | None = None
    started_at: str | None = None


class SalesTrainerRealtimeRecordRegistryReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    ready: bool | None = None
    checked_at: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class SalesTrainerRealtimeRecordRegistryDescriptorSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    descriptor_id: str | None = None
    label: str | None = None
    provider: str | None = None
    runtime_owner: str | None = None
    enabled: bool | None = None
    runtime_profile_id: str | None = None
    config_revision_id: str | None = None
    rollback_to_descriptor_id: str | None = None
    readiness: SalesTrainerRealtimeRecordRegistryReadinessSnapshot | None = None


class SalesTrainerRealtimeRecordRuntimeRegistrySnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    registry_key: str | None = None
    config_id: str | None = None
    version: int | None = None
    source: str | None = None
    status: str | None = None
    fallback_reason: str | None = None
    descriptor: SalesTrainerRealtimeRecordRegistryDescriptorSnapshot | None = None


class SalesTrainerRealtimeRecordProviderReadinessSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str | None = None
    ready: bool | None = None
    checked_at: str | None = None
    config_revision_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class SalesTrainerRealtimeRecordFailurePolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    terminal_codes: list[str] = Field(default_factory=list)
    transient_codes: list[str] = Field(default_factory=list)
    voluntary_codes: list[str] = Field(default_factory=list)
    terminal_retry_allowed: bool | None = None


class SalesTrainerRealtimeRecordScoresSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logic_score: float | None = None
    accuracy_score: float | None = None
    completeness_score: float | None = None


class SalesTrainerRealtimeRecordVoicePolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    external_binding: SalesTrainerRealtimeRecordExternalBindingSnapshot | None = None
    voice_mode: str | None = None
    runtime_profile_id: str | None = None
    model_name: str | None = None


class SalesTrainerRealtimeRecordEffectivenessSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str | None = None
    evaluable: bool | None = None
    main_issue: dict[str, Any] | None = None
    dimension_scores: dict[str, Any] | None = None


class SalesTrainerRealtimeRecordRuntimeStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: str | None = None
    session_status: str | None = None
    ai_state: str | None = None
    turn_count: int | None = None


class SalesTrainerRealtimeRuntimeOutcomeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_binding: SalesTrainerRealtimeRecordExternalBindingSnapshot
    voice_policy_snapshot: SalesTrainerRealtimeRecordVoicePolicySnapshot = Field(
        default_factory=SalesTrainerRealtimeRecordVoicePolicySnapshot
    )
    effectiveness_snapshot: SalesTrainerRealtimeRecordEffectivenessSnapshot = Field(
        default_factory=SalesTrainerRealtimeRecordEffectivenessSnapshot
    )
    runtime_state: SalesTrainerRealtimeRecordRuntimeStateSnapshot = Field(
        default_factory=SalesTrainerRealtimeRecordRuntimeStateSnapshot
    )
    scores: SalesTrainerRealtimeRecordScoresSnapshot


class SalesTrainerRealtimeRoleplayRecordSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    module_key: str | None = None
    status: str
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    submitted_at: object | None = None
    completed_at: object | None = None
    external_binding: SalesTrainerRealtimeRecordExternalBindingSnapshot
    snapshot: SalesTrainerRealtimeRuntimeOutcomeSnapshot


class SalesTrainerRoleplayObservationErrorSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = None
    message: str | None = None


class SalesTrainerRoleplayObservationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=36)
    source_record_id: str | None = Field(None, min_length=1, max_length=36)
    source: SalesTrainerRoleplayObservationSource
    turn_index: int = Field(0, ge=0)
    evaluator_status: SalesTrainerRoleplayObservationStatus = "completed"
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    error: SalesTrainerRoleplayObservationErrorSnapshot | dict[str, Any] | None = None
    trace_id: str | None = Field(None, max_length=100)


class SalesTrainerRoleplayObservationWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stored: bool
    deduplicated: bool = False
    observation_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class SalesTrainerRoleplayObservationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    session_id: str
    source_record_id: str
    source: SalesTrainerRoleplayObservationSource
    turn_index: int = Field(..., ge=0)
    evaluator_status: SalesTrainerRoleplayObservationStatus
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    error: SalesTrainerRoleplayObservationErrorSnapshot | None = None
    trace_id: str | None = None
    created_at: object
    updated_at: object


class SalesTrainerRoleplayObservationSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    source_record_id: str
    total: int = Field(..., ge=0)
    latest_turn_index: int | None = Field(None, ge=0)
    source_counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    items: list[SalesTrainerRoleplayObservationResponse] = Field(default_factory=list)


class SalesTrainerBusinessEtiquetteCapabilitySnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    capabilities: list[Any] = Field(default_factory=list)
    chapter_bindings: list[Any] = Field(default_factory=list)


class SalesTrainerBusinessEtiquetteQuestionSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: str | None = None
    title: str | None = None
    stem: str | None = None
    question_type: str | None = None
    options: list[Any] = Field(default_factory=list)
    reference_answer: str | None = None
    explanation: str | None = None
    scoring_dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    points: float | None = None
    order_index: int | None = None
    version: int | None = None
    content_hash: str | None = None


class SalesTrainerBusinessEtiquetteAnswerSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    question_id: str | None = None
    question_type: str | None = None
    answer_payload: Any | None = None
    is_correct: bool | None = None
    score: float | None = None
    max_score: float | None = None
    capability_keys: list[str] = Field(default_factory=list)
    question_snapshot: SalesTrainerBusinessEtiquetteQuestionSnapshot | None = None
    analysis: str | None = None
    scoring_source: str | None = None
    scoring_provider: str | None = None
    scoring_model: str | None = None
    scoring_latency_ms: int | None = None


class SalesTrainerBusinessEtiquetteCapabilityScoreSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    capability_key: str
    display_name: str | None = None
    score: float | None = None
    max_score: float | None = None
    normalized_score: float | None = None
    threshold: float | None = None
    mastered: bool | None = None
    mastery_level_key: str | None = None
    mastery_level_name: str | None = None


class SalesTrainerBusinessEtiquetteQuizRecordSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    training_pack_key: str
    learning_unit_key: str
    learning_unit_title: str
    user_id: str
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    training_pack_revision_id: str | None = None
    training_pack_revision_no: int | None = None
    capability_snapshot: SalesTrainerBusinessEtiquetteCapabilitySnapshot = Field(
        default_factory=SalesTrainerBusinessEtiquetteCapabilitySnapshot
    )
    question_snapshots: list[SalesTrainerBusinessEtiquetteQuestionSnapshot] = Field(
        default_factory=list
    )
    answers: list[SalesTrainerBusinessEtiquetteAnswerSnapshot] = Field(
        default_factory=list
    )
    capability_scores: list[SalesTrainerBusinessEtiquetteCapabilityScoreSnapshot] = (
        Field(default_factory=list)
    )
    weak_capability_keys: list[str] = Field(default_factory=list)
    recommended_chapter_orders: list[int] = Field(default_factory=list)
    total_score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    status: str
    submitted_at: object | None = None


class SalesTrainerTrainingRecordOperationLogContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    training_stage: TrainingJourneyStage | None = None
    learner_level: TrainingJourneyLearnerLevel | None = None
    role_level: TrainingJourneyLearnerLevel | None = None


class SalesTrainerTrainingRecordOperationLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_id: str
    actor_id: str | None = None
    actor_role: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: object
    training_context: SalesTrainerTrainingRecordOperationLogContext | None = None


class SalesTrainerEffectiveScoreSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    source: Literal["original_record", "latest_regrade"]
    original_score: float | None = None
    original_max_score: float | None = None
    original_passed: bool | None = None
    score_delta: float | None = None
    latest_regrade_run_id: str | None = None
    latest_regrade_error_code: str | None = None
    history_overwrite: Literal[False] = False


class SalesTrainerLatestRegradeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regrade_run_id: str
    target_type: str
    target_revision_id: str | None = None
    status: str
    reason: str | None = None
    trace_id: str | None = None
    created_at: object | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None


class SalesTrainerScoreExplanationItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | None = None
    key: str | None = None
    label: str | None = None
    text: str | None = None
    score: float | None = None
    max_score: float | None = None
    is_weak: bool | None = None


class SalesTrainerScoreExplanationSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    basis: str
    summary: str | None = None
    dimensions: list[SalesTrainerScoreExplanationItem] = Field(default_factory=list)
    evidence: list[SalesTrainerScoreExplanationItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    issues: list[SalesTrainerScoreExplanationItem] = Field(default_factory=list)
    next_actions: list[SalesTrainerScoreExplanationItem] = Field(default_factory=list)


class SalesTrainerAbilityProfileSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    basis: Literal["sales_trainer_phase2_projection_v1"]
    overall_score: float | None = None
    overall_passed: bool | None = None
    dimensions: list[SalesTrainerScoreExplanationItem] = Field(default_factory=list)
    weak_dimensions: list[SalesTrainerScoreExplanationItem] = Field(
        default_factory=list
    )
    evidence_count: int = Field(0, ge=0)


class SalesTrainerRemediationSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    needed: bool
    reason: str
    action_label: str
    target_path: str
    priority: Literal["low", "medium", "high"]
    weak_dimension_keys: list[str] = Field(default_factory=list)


class SalesTrainerMaterialSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: int | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_material_version_id: str | None = None
    frozen_at: str | None = None


class SalesTrainerScoreSchemePromptSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_id: str | None = None
    name: str | None = None
    purpose: str | None = None
    system_prompt: str | None = None
    scoring_template: str | None = None
    output_schema: SalesTrainerAudioScoreOutputSchema = Field(
        default_factory=SalesTrainerAudioScoreOutputSchema
    )
    learner_rubric: SalesTrainerLearnerRubric = Field(
        default_factory=SalesTrainerLearnerRubric
    )
    version: int | None = None
    status: str | None = None

    @field_validator("output_schema", mode="before")
    @classmethod
    def coerce_output_schema(
        cls, value: Any
    ) -> SalesTrainerAudioScoreOutputSchema | dict[str, Any]:
        if isinstance(value, SalesTrainerAudioScoreOutputSchema):
            return value
        if not isinstance(value, dict):
            return {}
        try:
            return cast(
                SalesTrainerAudioScoreOutputSchema,
                SalesTrainerAudioScoreOutputSchema.model_validate(value),
            )
        except ValueError:
            return {}

    @field_validator("learner_rubric", mode="before")
    @classmethod
    def coerce_learner_rubric(
        cls, value: Any
    ) -> SalesTrainerLearnerRubric | dict[str, Any]:
        return _coerce_legacy_learner_rubric(value)


class SalesTrainerScoreSchemeSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_id: str | None = None
    name: str | None = None
    purpose: str | None = None
    version: int | None = None
    status: str | None = None
    learner_rubric: SalesTrainerLearnerRubric = Field(
        default_factory=SalesTrainerLearnerRubric
    )
    pass_threshold: float | None = None
    prompt_snapshot: SalesTrainerScoreSchemePromptSnapshot | None = None

    @field_validator("learner_rubric", mode="before")
    @classmethod
    def coerce_learner_rubric(
        cls, value: Any
    ) -> SalesTrainerLearnerRubric | dict[str, Any]:
        return _coerce_legacy_learner_rubric(value)


class SalesTrainerTaskBriefSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool | None = None
    title: str | None = None
    purpose: str | None = None
    scenario: str | None = None
    instructions: list[Any] = Field(default_factory=list)
    success_criteria: list[Any] = Field(default_factory=list)
    common_mistakes: list[Any] = Field(default_factory=list)
    upload_guidance: str | None = None
    submission_context: dict[str, Any] | None = None


class SalesTrainerTrainingRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    record_type: Literal[
        "audio_submission",
        "quiz_attempt",
        "ai_coach_session",
        "business_etiquette_quiz_attempt",
        "realtime_roleplay_session",
    ]
    path_key: str | None = None
    path_revision_id: str | None = None
    path_revision_no: int | None = None
    module_key: str | None = None
    legacy_snapshot_only: bool = True
    training_stage: TrainingJourneyStage | None = None
    learner_level: TrainingJourneyLearnerLevel | None = None
    role_level: TrainingJourneyLearnerLevel | None = None
    unit_id: str
    unit_name: str | None = None
    unit_type: (
        SalesTrainerUnitType
        | Literal[
            "ai_coach",
            "business_etiquette_quiz",
            "realtime_roleplay",
        ]
    )
    user_id: str
    user_name: str | None = None
    user_email: str | None = None
    user_department: str | None = None
    status: str
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    submitted_at: object | None = None
    material_snapshot: SalesTrainerMaterialSnapshot | None = None
    score_scheme_snapshot: SalesTrainerScoreSchemeSnapshot | None = None
    task_brief_snapshot: SalesTrainerTaskBriefSnapshot | None = None
    audio_submission: AudioSubmissionResponse | None = None
    quiz_attempt: QuizAttemptResponse | None = None
    ai_coach_session: SalesTrainerAiCoachRecordSnapshot | None = None
    business_etiquette_quiz_attempt: (
        SalesTrainerBusinessEtiquetteQuizRecordSnapshot | None
    ) = None
    realtime_roleplay_session: SalesTrainerRealtimeRoleplayRecordSnapshot | None = None
    operation_logs: list[SalesTrainerTrainingRecordOperationLog] = Field(
        default_factory=list
    )
    effective_score: SalesTrainerEffectiveScoreSnapshot | None = None
    latest_regrade: SalesTrainerLatestRegradeSnapshot | None = None
    score_explanation: SalesTrainerScoreExplanationSnapshot | None = None
    ability_profile: SalesTrainerAbilityProfileSnapshot | None = None
    remediation: SalesTrainerRemediationSnapshot | None = None


class SalesTrainerTrainingRecordListResponse(BaseModel):
    items: list[SalesTrainerTrainingRecordResponse]
    total: int


class SalesTrainerManagerDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_count: int = Field(..., ge=0)
    loaded_record_count: int = Field(..., ge=0)
    learner_count: int = Field(..., ge=0)
    completed_record_count: int = Field(..., ge=0)
    completion_rate: float | None = None
    pass_rate: float | None = None
    low_score_record_count: int = Field(..., ge=0)
    repeat_practice_learner_count: int = Field(..., ge=0)


class SalesTrainerManagerDashboardModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_key: str
    module_name: str
    record_count: int = Field(..., ge=0)
    completed_count: int = Field(..., ge=0)
    pass_rate: float | None = None
    average_score: float | None = None
    weak_record_count: int = Field(..., ge=0)


class SalesTrainerManagerDashboardWeakDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_key: str
    dimension_label: str
    record_count: int = Field(..., ge=0)
    learner_count: int = Field(..., ge=0)
    average_score: float | None = None


class SalesTrainerManagerDashboardRiskLearner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    user_name: str | None = None
    user_department: str | None = None
    risk_reasons: list[str] = Field(default_factory=list)
    latest_submitted_at: object | None = None
    lowest_score: float | None = None
    record_count: int = Field(..., ge=0)
    suggested_action: str
    suggested_action_code: str
    priority: Literal["low", "medium", "high"]


class SalesTrainerManagerDashboardInterventionSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    user_name: str | None = None
    priority: Literal["low", "medium", "high"]
    action: str
    reason_codes: list[str] = Field(default_factory=list)


class SalesTrainerPhase2PolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["sales_trainer.phase2.closed_loop_policy"]
    version: str
    enabled: bool
    low_score_threshold: float = Field(..., ge=0, le=100)
    repeat_practice_threshold: int = Field(..., ge=1, le=20)
    dashboard_record_limit: int = Field(..., ge=1, le=5000)
    source: Literal["database", "database_previous", "default"]
    config_id: str | None = None
    config_version: int | None = None
    status: str | None = None
    fallback_applied: bool
    fallback_reason: str | None = None
    management_entry: Literal["/admin/business-rules/sales-trainer-phase2"]
    permission: Literal["admin_publish_only"]
    effective_timing: Literal["request_time"]


class SalesTrainerManagerDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: object
    policy: SalesTrainerPhase2PolicyResponse
    summary: SalesTrainerManagerDashboardSummary
    module_summaries: list[SalesTrainerManagerDashboardModuleSummary] = Field(
        default_factory=list
    )
    weak_dimensions: list[SalesTrainerManagerDashboardWeakDimension] = Field(
        default_factory=list
    )
    risk_learners: list[SalesTrainerManagerDashboardRiskLearner] = Field(
        default_factory=list
    )
    intervention_suggestions: list[
        SalesTrainerManagerDashboardInterventionSuggestion
    ] = Field(default_factory=list)


class AudioScorePromptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    purpose: str = Field("general_audio_scoring", min_length=1, max_length=50)
    system_prompt: str = Field(..., min_length=1)
    scoring_template: str = Field(..., min_length=1)
    output_schema: SalesTrainerAudioScoreOutputSchema = Field(
        default_factory=SalesTrainerAudioScoreOutputSchema
    )
    learner_rubric: SalesTrainerLearnerRubric = Field(
        default_factory=SalesTrainerLearnerRubric
    )

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
    output_schema: SalesTrainerAudioScoreOutputSchema | None = None
    learner_rubric: SalesTrainerLearnerRubric | None = None

    @model_validator(mode="after")
    def validate_template_variables(self) -> AudioScorePromptUpdate:
        if (
            self.scoring_template is not None
            and "{transcript}" not in self.scoring_template
        ):
            raise ValueError("scoring_template must include {transcript}")
        return self


class AudioScorePromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prompt_id: str
    name: str
    purpose: str
    system_prompt: str
    scoring_template: str
    output_schema: SalesTrainerAudioScoreOutputSchema
    learner_rubric: SalesTrainerLearnerRubric
    version: int
    status: SalesTrainerStatus
    created_by: str | None = None
    updated_by: str | None = None
    created_at: object
    updated_at: object


class AudioScorePromptRevisionResponse(BaseModel):
    revision_id: str
    revision_no: int
    status: Literal["working", "published", "archived"]
    change_class: Literal["non_semantic", "semantic", "binding", "scoring_high_risk"]
    name: str | None = None
    purpose: str | None = None
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


class AudioScorePromptRevisionListResponse(BaseModel):
    items: list[AudioScorePromptRevisionResponse]
    total: int


class AudioScorePromptRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_revision_id: str = Field(..., min_length=1, max_length=36)
    reason: str = Field(..., min_length=1, max_length=1000)


class AudioScorePromptRollbackPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_revision_id: str = Field(..., min_length=1, max_length=36)


class AudioScorePromptRollbackPreviewResponse(BaseModel):
    action: Literal["audio_score_prompt.rollback"]
    permission: Literal["sales_trainer.manage_modules"]
    requires_reason: bool
    future_only: bool
    mutates_history: bool
    target_prompt_id: str
    current_revision_id: str | None = None
    target_revision: AudioScorePromptRevisionResponse
    changed_fields: list[str] = Field(default_factory=list)
    historical_submissions_changed: bool
    historical_regrade_required: bool
    rollback_plan: dict[str, Any]


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
    model_config = ConfigDict(extra="forbid")

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
    phase2_policy: SalesTrainerPhase2PolicyResponse | None = None


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
    material_snapshot: SalesTrainerMaterialSnapshot | None = None
    score_scheme_snapshot: SalesTrainerScoreSchemeSnapshot | None = None
    task_brief_snapshot: SalesTrainerTaskBriefSnapshot | None = None
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
