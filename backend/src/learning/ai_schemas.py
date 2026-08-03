"""Versioned business schemas registered by the governed AI composition root."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.schemas import OutputSchemaRegistry
from learning.contracts import LearningUnitRevisionDraft, QuestionGenerationOutput
from learning.quiz_runtime import ShortAnswerScoringOutput

QUESTION_GENERATION_INPUT_SCHEMA = "question-generation-input-v1"
QUESTION_GENERATION_OUTPUT_SCHEMA = "question-generation-output-v1"
SHORT_ANSWER_INPUT_SCHEMA = "short-answer-input-v1"
SHORT_ANSWER_OUTPUT_SCHEMA = "short-answer-output-v1"


class QuestionGenerationAnchorContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=500)
    locator_type: str = Field(min_length=1, max_length=80)


class QuestionGenerationAIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_revision_id: str = Field(min_length=1, max_length=160)
    learning_unit_revision_id: str = Field(min_length=1, max_length=160)
    requested_count: int = Field(ge=1, le=100)
    learning_unit: LearningUnitRevisionDraft
    source_anchors: tuple[QuestionGenerationAnchorContext, ...] = Field(
        min_length=1,
        max_length=200,
    )


class ShortAnswerScoringAIItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_revision_id: str = Field(min_length=1, max_length=160)
    stem: str = Field(min_length=1, max_length=5_000)
    reference_answer: str = Field(min_length=1, max_length=10_000)
    rubric: dict[str, Any]
    max_points: float = Field(gt=0)
    learner_answer: str = Field(min_length=1, max_length=20_000)


class ShortAnswerScoringAIInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quiz_revision_id: str = Field(min_length=1, max_length=160)
    answers: tuple[ShortAnswerScoringAIItem, ...] = Field(
        min_length=1,
        max_length=200,
    )


def register_learning_ai_schemas(registry: OutputSchemaRegistry) -> None:
    registry.register_input(
        QUESTION_GENERATION_INPUT_SCHEMA,
        QuestionGenerationAIInput,
    )
    registry.register_output(
        QUESTION_GENERATION_OUTPUT_SCHEMA,
        QuestionGenerationOutput,
    )
    registry.register_input(
        SHORT_ANSWER_INPUT_SCHEMA,
        ShortAnswerScoringAIInput,
    )
    registry.register_output(
        SHORT_ANSWER_OUTPUT_SCHEMA,
        ShortAnswerScoringOutput,
    )


def build_learning_ai_schema_registry() -> OutputSchemaRegistry:
    registry = OutputSchemaRegistry()
    register_learning_ai_schemas(registry)
    return registry


__all__ = [
    "QUESTION_GENERATION_INPUT_SCHEMA",
    "QUESTION_GENERATION_OUTPUT_SCHEMA",
    "QuestionGenerationAIInput",
    "SHORT_ANSWER_INPUT_SCHEMA",
    "SHORT_ANSWER_OUTPUT_SCHEMA",
    "ShortAnswerScoringAIInput",
    "build_learning_ai_schema_registry",
    "register_learning_ai_schemas",
]
