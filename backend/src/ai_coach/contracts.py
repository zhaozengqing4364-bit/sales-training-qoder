"""Provider-neutral structured contracts for the newcomer AI Coach."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CoachCardType = Literal[
    "single_choice",
    "multiple_choice",
    "ordering",
    "short_answer_rewrite",
    "scenario_choice",
    "key_points_completion",
    "example_comparison",
    "summary",
]


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CoachAIContractSnapshot(StrictFrozenModel):
    business_purpose: str = Field(min_length=1, max_length=160)
    prompt_template_id: str = Field(min_length=1, max_length=160)
    prompt_revision_id: str = Field(min_length=1, max_length=160)
    model_routing_profile_id: str = Field(min_length=1, max_length=160)
    model_routing_revision_id: str = Field(min_length=1, max_length=160)
    input_schema_version: str = Field(min_length=1, max_length=120)
    output_schema_version: str = Field(min_length=1, max_length=120)
    timeout_policy_ref: str = Field(min_length=1, max_length=160)
    retry_policy_ref: str = Field(min_length=1, max_length=160)
    allow_fallback: bool = True


class CoachAIContracts(StrictFrozenModel):
    card_generation: CoachAIContractSnapshot
    answer_evaluation: CoachAIContractSnapshot
    feedback_explanation: CoachAIContractSnapshot


class CoachCheckpointDefinition(StrictFrozenModel):
    checkpoint_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1_000)
    competency_keys: tuple[str, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_competencies(self) -> CoachCheckpointDefinition:
        if len(set(self.competency_keys)) != len(self.competency_keys):
            raise ValueError("checkpoint competency_keys must be unique")
        return self


class CoachMasteryRule(StrictFrozenModel):
    threshold_percent: float = Field(default=80, ge=0, le=100)
    minimum_scored_cards: int = Field(default=3, ge=3, le=5)
    maximum_uncertainty: float = Field(default=0.35, ge=0, le=1)


class CoachRemediationPolicy(StrictFrozenModel):
    cards_per_cycle_min: int = Field(default=3, ge=3, le=5)
    cards_per_cycle_max: int = Field(default=5, ge=3, le=5)
    maximum_automatic_cycles: int = Field(default=2, ge=0, le=2)

    @model_validator(mode="after")
    def valid_card_range(self) -> CoachRemediationPolicy:
        if self.cards_per_cycle_min > self.cards_per_cycle_max:
            raise ValueError("cards_per_cycle_min cannot exceed maximum")
        return self


class CoachSafetyPolicy(StrictFrozenModel):
    reject_arbitrary_markup: bool = True
    reject_external_instructions: bool = True
    require_source_references: bool = True
    human_help_on_missing_evidence: bool = True


class CoachProfileSnapshot(StrictFrozenModel):
    contract_version: Literal["coach_profile_v1"] = "coach_profile_v1"
    title: str = Field(min_length=1, max_length=240)
    training_goal: str = Field(min_length=1, max_length=2_000)
    applicable_competency_keys: tuple[str, ...] = Field(min_length=1, max_length=50)
    allowed_knowledge_scope: tuple[str, ...] = Field(min_length=1, max_length=200)
    tone_principles: tuple[str, ...] = Field(min_length=1, max_length=30)
    feedback_principles: tuple[str, ...] = Field(min_length=1, max_length=30)
    checkpoints: tuple[CoachCheckpointDefinition, ...] = Field(
        min_length=3,
        max_length=3,
    )
    card_type_whitelist: tuple[CoachCardType, ...] = Field(
        min_length=1,
        max_length=8,
    )
    mastery_rule: CoachMasteryRule = Field(default_factory=CoachMasteryRule)
    remediation_policy: CoachRemediationPolicy = Field(
        default_factory=CoachRemediationPolicy
    )
    ai: CoachAIContracts
    safety: CoachSafetyPolicy = Field(default_factory=CoachSafetyPolicy)

    @model_validator(mode="after")
    def validate_profile(self) -> CoachProfileSnapshot:
        checkpoint_keys = [item.checkpoint_key for item in self.checkpoints]
        if len(set(checkpoint_keys)) != 3:
            raise ValueError("profile must define three unique checkpoints")
        if len(set(self.card_type_whitelist)) != len(self.card_type_whitelist):
            raise ValueError("card_type_whitelist must be unique")
        if len(set(self.applicable_competency_keys)) != len(
            self.applicable_competency_keys
        ):
            raise ValueError("applicable_competency_keys must be unique")
        unknown = {
            key
            for checkpoint in self.checkpoints
            for key in checkpoint.competency_keys
            if key not in self.applicable_competency_keys
        }
        if unknown:
            raise ValueError("checkpoint references an unsupported competency")
        return self


class CoachContextReference(StrictFrozenModel):
    ref_id: str = Field(min_length=1, max_length=160)
    resource_type: Literal[
        "learning_unit",
        "source_anchor",
        "quiz_outcome",
        "audio_outcome",
        "competency_evidence_summary",
    ]
    resource_id: str = Field(min_length=1, max_length=160)
    revision_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=500)
    excerpt: str | None = Field(default=None, max_length=8_000)


class CoachWeaknessInput(StrictFrozenModel):
    competency_key: str = Field(min_length=1, max_length=120)
    source_ref_ids: tuple[str, ...] = Field(min_length=1, max_length=30)
    summary: str = Field(min_length=1, max_length=1_000)
    confidence: float = Field(ge=0, le=1)


class CoachContextSnapshot(StrictFrozenModel):
    references: tuple[CoachContextReference, ...] = Field(
        min_length=1,
        max_length=200,
    )
    weaknesses: tuple[CoachWeaknessInput, ...] = Field(max_length=50)
    degradations: tuple[str, ...] = Field(default_factory=tuple, max_length=30)

    @model_validator(mode="after")
    def validate_references(self) -> CoachContextSnapshot:
        ref_ids = [item.ref_id for item in self.references]
        if len(set(ref_ids)) != len(ref_ids):
            raise ValueError("context reference ids must be unique")
        known = set(ref_ids)
        if any(
            source_ref not in known
            for weakness in self.weaknesses
            for source_ref in weakness.source_ref_ids
        ):
            raise ValueError("weakness source ref is outside the context snapshot")
        return self


class CoachChoiceOption(StrictFrozenModel):
    option_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2_000)


class CoachOrderingItem(StrictFrozenModel):
    item_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2_000)


class _CardBase(StrictFrozenModel):
    card_type: CoachCardType
    prompt: str = Field(min_length=1, max_length=8_000)
    source_ref_ids: tuple[str, ...] = Field(min_length=1, max_length=30)


class SingleChoiceCardDraft(_CardBase):
    card_type: Literal["single_choice"]
    options: tuple[CoachChoiceOption, ...] = Field(min_length=2, max_length=8)
    correct_option_ids: tuple[str, ...] = Field(min_length=1, max_length=1)


class MultipleChoiceCardDraft(_CardBase):
    card_type: Literal["multiple_choice"]
    options: tuple[CoachChoiceOption, ...] = Field(min_length=2, max_length=8)
    correct_option_ids: tuple[str, ...] = Field(min_length=1, max_length=8)


class OrderingCardDraft(_CardBase):
    card_type: Literal["ordering"]
    items: tuple[CoachOrderingItem, ...] = Field(min_length=2, max_length=12)
    correct_order_ids: tuple[str, ...] = Field(min_length=2, max_length=12)


class ShortAnswerRewriteCardDraft(_CardBase):
    card_type: Literal["short_answer_rewrite"]
    instruction: str = Field(min_length=1, max_length=2_000)
    reference_points: tuple[str, ...] = Field(min_length=1, max_length=20)


class ScenarioChoiceCardDraft(_CardBase):
    card_type: Literal["scenario_choice"]
    scenario: str = Field(min_length=1, max_length=8_000)
    options: tuple[CoachChoiceOption, ...] = Field(min_length=2, max_length=8)
    correct_option_ids: tuple[str, ...] = Field(min_length=1, max_length=1)


class KeyPointsCompletionCardDraft(_CardBase):
    card_type: Literal["key_points_completion"]
    hints: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    reference_points: tuple[str, ...] = Field(min_length=1, max_length=20)


class ExampleComparisonCardDraft(_CardBase):
    card_type: Literal["example_comparison"]
    examples: tuple[str, ...] = Field(min_length=2, max_length=6)
    comparison_criteria: tuple[str, ...] = Field(min_length=1, max_length=12)
    reference_points: tuple[str, ...] = Field(min_length=1, max_length=20)


class SummaryCardDraft(_CardBase):
    card_type: Literal["summary"]
    scope: str = Field(min_length=1, max_length=2_000)
    reference_points: tuple[str, ...] = Field(min_length=1, max_length=20)


CoachCardDraft = Annotated[
    SingleChoiceCardDraft
    | MultipleChoiceCardDraft
    | OrderingCardDraft
    | ShortAnswerRewriteCardDraft
    | ScenarioChoiceCardDraft
    | KeyPointsCompletionCardDraft
    | ExampleComparisonCardDraft
    | SummaryCardDraft,
    Field(discriminator="card_type"),
]


class CoachCardGenerationInput(StrictFrozenModel):
    profile_revision_id: str = Field(min_length=1, max_length=160)
    session_id: str = Field(min_length=1, max_length=160)
    checkpoint: CoachCheckpointDefinition
    cycle_no: int = Field(ge=0, le=2)
    card_count_min: int = Field(ge=3, le=5)
    card_count_max: int = Field(ge=3, le=5)
    allowed_card_types: tuple[CoachCardType, ...] = Field(min_length=1, max_length=8)
    context: CoachContextSnapshot
    remediation_inputs: tuple[str, ...] = Field(default_factory=tuple, max_length=30)


class CoachCardGenerationOutput(StrictFrozenModel):
    cards: tuple[CoachCardDraft, ...] = Field(min_length=3, max_length=5)
    generation_strategy: str = Field(min_length=1, max_length=1_000)


class ChoiceCardAnswer(StrictFrozenModel):
    answer_type: Literal["choice"]
    selected_option_ids: tuple[str, ...] = Field(min_length=1, max_length=8)


class OrderingCardAnswer(StrictFrozenModel):
    answer_type: Literal["ordering"]
    ordered_item_ids: tuple[str, ...] = Field(min_length=2, max_length=12)


class TextCardAnswer(StrictFrozenModel):
    answer_type: Literal["text"]
    text: str = Field(min_length=1, max_length=20_000)


CoachCardAnswer = Annotated[
    ChoiceCardAnswer | OrderingCardAnswer | TextCardAnswer,
    Field(discriminator="answer_type"),
]


class SubmitCoachAnswerInput(StrictFrozenModel):
    card_id: str = Field(min_length=1, max_length=160)
    client_token: str = Field(min_length=8, max_length=200)
    answer: CoachCardAnswer


class CoachAnswerEvaluationInput(StrictFrozenModel):
    session_id: str = Field(min_length=1, max_length=160)
    card_id: str = Field(min_length=1, max_length=160)
    card_type: CoachCardType
    prompt: str = Field(min_length=1, max_length=8_000)
    public_card: dict[str, Any]
    reference_points: tuple[str, ...] = Field(min_length=1, max_length=20)
    learner_answer: CoachCardAnswer
    sources: tuple[CoachContextReference, ...] = Field(min_length=1, max_length=30)


class CoachAnswerEvaluationOutput(StrictFrozenModel):
    score_percent: float = Field(ge=0, le=100)
    mastered: bool
    evidence_from_answer: tuple[str, ...] = Field(min_length=1, max_length=20)
    missing_points: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    misconception: str | None = Field(default=None, max_length=2_000)
    feedback: str = Field(min_length=1, max_length=5_000)
    improvement_action: str = Field(min_length=1, max_length=2_000)
    next_suggestion: str = Field(min_length=1, max_length=2_000)
    uncertainty: float = Field(ge=0, le=1)
    source_ref_ids: tuple[str, ...] = Field(min_length=1, max_length=30)


class RequestCoachAssistanceInput(StrictFrozenModel):
    assistance_type: Literal["explain", "example"]
    card_id: str = Field(min_length=1, max_length=160)


class CoachExplanationAIInput(StrictFrozenModel):
    session_id: str = Field(min_length=1, max_length=160)
    assistance_type: Literal["explain", "example"]
    card: dict[str, Any]
    feedback: dict[str, Any] | None = None
    sources: tuple[CoachContextReference, ...] = Field(min_length=1, max_length=30)


class CoachExplanationAIOutput(StrictFrozenModel):
    explanation: str = Field(min_length=1, max_length=8_000)
    source_ref_ids: tuple[str, ...] = Field(min_length=1, max_length=30)
    uncertainty: float = Field(ge=0, le=1)


class CoachHumanInterventionInput(StrictFrozenModel):
    action: Literal[
        "add_guidance",
        "assign_learning",
        "assign_audio",
        "restart_coach",
        "no_further_action",
    ]
    reason: str = Field(min_length=1, max_length=2_000)
    guidance: str | None = Field(default=None, max_length=8_000)
    target_resource_id: str | None = Field(default=None, max_length=160)


__all__ = [
    "CoachAIContractSnapshot",
    "CoachAIContracts",
    "CoachAnswerEvaluationInput",
    "CoachAnswerEvaluationOutput",
    "CoachCardAnswer",
    "CoachCardDraft",
    "CoachCardGenerationInput",
    "CoachCardGenerationOutput",
    "CoachCardType",
    "CoachCheckpointDefinition",
    "CoachContextReference",
    "CoachContextSnapshot",
    "CoachExplanationAIInput",
    "CoachExplanationAIOutput",
    "CoachHumanInterventionInput",
    "CoachMasteryRule",
    "CoachProfileSnapshot",
    "CoachRemediationPolicy",
    "CoachSafetyPolicy",
    "CoachWeaknessInput",
    "RequestCoachAssistanceInput",
    "SubmitCoachAnswerInput",
]
