from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


LearningTopicScoreDisplayPolicy = Literal["quiz_attempt_score"]


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
    module_key: str = Field("configurable", min_length=1, max_length=80)
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
    has_active_path_binding: bool
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
    confirmed_scoring_rubric_revision_id: str | None = Field(
        None, min_length=1, max_length=36
    )
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


class SalesTrainerTrainingRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    record_type: Literal["newcomer_activity_attempt"]
    evidence_id: str
    user_id: str
    enrollment_id: str
    path_revision_id: str
    activity_id: str
    activity_type: Literal[
        "lesson",
        "quiz",
        "audio_assessment",
        "realtime_roleplay",
        "ai_coach",
        "assignment",
    ]
    phase_id: str | None = None
    module_id: str | None = None
    phase_title: str | None = None
    module_title: str | None = None
    activity_title: str | None = None
    status: str
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    submitted_at: object | None = None
    completed_at: object | None = None
    evidence_type: str | None = None
    source_evidence_id: str | None = None
    capability_scores: list[dict[str, Any]] = Field(default_factory=list)


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
