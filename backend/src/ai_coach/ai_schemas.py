"""Versioned structured schemas used by governed Coach invocations."""

from __future__ import annotations

from ai_coach.contracts import (
    CoachAnswerEvaluationInput,
    CoachAnswerEvaluationOutput,
    CoachCardGenerationInput,
    CoachCardGenerationOutput,
    CoachExplanationAIInput,
    CoachExplanationAIOutput,
)
from ai_platform.schemas import OutputSchemaRegistry

COACH_CARD_GENERATION_INPUT_SCHEMA = "coach-card-generation-input-v1"
COACH_CARD_GENERATION_OUTPUT_SCHEMA = "coach-card-generation-output-v1"
COACH_ANSWER_EVALUATION_INPUT_SCHEMA = "coach-answer-evaluation-input-v1"
COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA = "coach-answer-evaluation-output-v1"
COACH_EXPLANATION_INPUT_SCHEMA = "coach-explanation-input-v1"
COACH_EXPLANATION_OUTPUT_SCHEMA = "coach-explanation-output-v1"


def register_coach_ai_schemas(registry: OutputSchemaRegistry) -> None:
    registry.register_input(
        COACH_CARD_GENERATION_INPUT_SCHEMA,
        CoachCardGenerationInput,
    )
    registry.register_output(
        COACH_CARD_GENERATION_OUTPUT_SCHEMA,
        CoachCardGenerationOutput,
    )
    registry.register_input(
        COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
        CoachAnswerEvaluationInput,
    )
    registry.register_output(
        COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
        CoachAnswerEvaluationOutput,
    )
    registry.register_input(
        COACH_EXPLANATION_INPUT_SCHEMA,
        CoachExplanationAIInput,
    )
    registry.register_output(
        COACH_EXPLANATION_OUTPUT_SCHEMA,
        CoachExplanationAIOutput,
    )


def build_coach_ai_schema_registry() -> OutputSchemaRegistry:
    registry = OutputSchemaRegistry()
    register_coach_ai_schemas(registry)
    return registry


__all__ = [
    "COACH_ANSWER_EVALUATION_INPUT_SCHEMA",
    "COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA",
    "COACH_CARD_GENERATION_INPUT_SCHEMA",
    "COACH_CARD_GENERATION_OUTPUT_SCHEMA",
    "COACH_EXPLANATION_INPUT_SCHEMA",
    "COACH_EXPLANATION_OUTPUT_SCHEMA",
    "build_coach_ai_schema_registry",
    "register_coach_ai_schemas",
]
