from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import QuestionItem

QuestionType = Literal[
    "single_choice", "multiple_choice", "true_false", "short_answer"
]


@dataclass(frozen=True)
class ResolvedQuestion:
    question_id: str
    title: str
    stem: str
    question_type: QuestionType
    reference_answer: str | None
    scoring_criteria: dict[str, Any]
    points: int
    order_index: int


@dataclass(frozen=True)
class UnsupportedQuestionType:
    question_id: str
    declared_type: str
    reason: str


class QuestionBankAdapter:
    """Read existing QuestionItem records without coupling callers to test-bank internals."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_published_questions(
        self, question_ids: list[str]
    ) -> dict[str, QuestionItem]:
        if not question_ids:
            return {}
        result = await self._db.execute(
            select(QuestionItem).where(
                QuestionItem.question_id.in_(question_ids),
                QuestionItem.status == "published",
                QuestionItem.usage_scope == "sales_trainer",
            )
        )
        return {str(question.question_id): question for question in result.scalars().all()}

    async def get_questions(self, question_ids: list[str]) -> dict[str, QuestionItem]:
        if not question_ids:
            return {}
        result = await self._db.execute(
            select(QuestionItem).where(QuestionItem.question_id.in_(question_ids))
        )
        return {str(question.question_id): question for question in result.scalars().all()}

    def resolve_type(self, question: QuestionItem) -> QuestionType:
        criteria = question.scoring_criteria or {}
        raw_type = str(criteria.get("question_type") or "short_answer")
        if raw_type == "single_choice" and self._has_choice_contract(criteria):
            return "single_choice"
        if raw_type == "multiple_choice" and self._has_choice_contract(criteria):
            return "multiple_choice"
        if raw_type == "true_false" and isinstance(criteria.get("correct_bool"), bool):
            return "true_false"
        return "short_answer"

    def unsupported_reason(self, question: QuestionItem) -> UnsupportedQuestionType | None:
        criteria = question.scoring_criteria or {}
        raw_type = str(criteria.get("question_type") or "")
        if raw_type == "single_choice":
            if not self._has_choice_options(criteria):
                return UnsupportedQuestionType(
                    question_id=str(question.question_id),
                    declared_type=raw_type,
                    reason="missing_choice_options",
                )
            if "correct_answer" not in criteria:
                return UnsupportedQuestionType(
                    question_id=str(question.question_id),
                    declared_type=raw_type,
                    reason="missing_correct_answer",
                )
        if raw_type == "multiple_choice":
            if not self._has_choice_options(criteria):
                return UnsupportedQuestionType(
                    question_id=str(question.question_id),
                    declared_type=raw_type,
                    reason="missing_choice_options",
                )
            if "correct_answers" not in criteria:
                return UnsupportedQuestionType(
                    question_id=str(question.question_id),
                    declared_type=raw_type,
                    reason="missing_correct_answers",
                )
        if raw_type == "true_false" and not isinstance(criteria.get("correct_bool"), bool):
            return UnsupportedQuestionType(
                question_id=str(question.question_id),
                declared_type=raw_type,
                reason="missing_correct_bool",
            )
        return None

    def serialize_for_learner(
        self,
        question: QuestionItem,
        *,
        points: int,
        order_index: int,
    ) -> dict[str, Any]:
        question_type = self.resolve_type(question)
        criteria = question.scoring_criteria or {}
        payload: dict[str, Any] = {
            "question_id": question.question_id,
            "title": question.title,
            "stem": question.stem,
            "question_type": question_type,
            "points": points,
            "order_index": order_index,
        }
        if question_type in {"single_choice", "multiple_choice"}:
            payload["options"] = criteria.get("options") or []
        return payload

    def grade(
        self,
        question: QuestionItem,
        *,
        answer_payload: Any,
        points: int,
    ) -> tuple[bool | None, float | None]:
        question_type = self.resolve_type(question)
        criteria = question.scoring_criteria or {}
        if question_type == "single_choice":
            correct = str(criteria.get("correct_answer") or "")
            is_correct = str(answer_payload) == correct
            return is_correct, float(points if is_correct else 0)
        if question_type == "multiple_choice":
            correct_values = criteria.get("correct_answers") or []
            answer_values = answer_payload if isinstance(answer_payload, list) else []
            is_correct = {str(item) for item in answer_values} == {
                str(item) for item in correct_values
            }
            return is_correct, float(points if is_correct else 0)
        if question_type == "true_false":
            parsed_answer = _parse_bool(answer_payload)
            is_correct = parsed_answer is bool(criteria.get("correct_bool"))
            return is_correct, float(points if is_correct else 0)
        return None, None

    @staticmethod
    def _has_choice_contract(criteria: dict[str, Any]) -> bool:
        if not QuestionBankAdapter._has_choice_options(criteria):
            return False
        return "correct_answer" in criteria or "correct_answers" in criteria

    @staticmethod
    def _has_choice_options(criteria: dict[str, Any]) -> bool:
        options = criteria.get("options")
        if not isinstance(options, list) or not options:
            return False
        return True


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "正确", "对"}:
            return True
        if normalized in {"false", "0", "no", "n", "错误", "错"}:
            return False
    return None
