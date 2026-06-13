from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

QuestionType = Literal[
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_answer",
]


@dataclass(frozen=True)
class ResolvedQuestion:
    question_id: str
    title: str
    stem: str
    reference_answer: str | None
    scoring_criteria: dict[str, Any]
    scoring_dimensions: list[str] | None


@dataclass(frozen=True)
class UnsupportedQuestionType:
    question_id: str
    declared_type: str
    reason: str


class QuestionBankProvider(Protocol):
    async def get_published_questions(
        self,
        question_ids: list[str],
    ) -> dict[str, ResolvedQuestion]: ...

    async def get_questions(
        self,
        question_ids: list[str],
    ) -> dict[str, ResolvedQuestion]: ...


QuestionBankProviderFactory = Callable[[AsyncSession], QuestionBankProvider]

_provider_factories: dict[str, QuestionBankProviderFactory] = {}


def register_question_bank_provider(
    scope: str,
    provider_factory: QuestionBankProviderFactory,
) -> None:
    normalized_scope = scope.strip()
    if not normalized_scope:
        raise ValueError("question bank provider scope is required")
    _provider_factories[normalized_scope] = provider_factory


def clear_question_bank_providers() -> None:
    _provider_factories.clear()


def resolve_question_bank_provider(
    scope: str,
    db: AsyncSession,
) -> QuestionBankProvider | None:
    factory = _provider_factories.get(scope)
    return factory(db) if factory is not None else None
