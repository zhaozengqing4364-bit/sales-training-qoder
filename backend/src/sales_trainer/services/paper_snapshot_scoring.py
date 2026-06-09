from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sales_trainer.services.path_attempt_context_service import (
    PathAttemptContextPayload,
)


@dataclass(frozen=True, slots=True)
class RevisionQuestion:
    question_id: str
    title: str
    stem: str
    reference_answer: str | None
    scoring_criteria: dict[str, Any]
    scoring_dimensions: list[str]
    points: int
    order_index: int
    question_revision_id: str | None
    question_payload_hash: str | None


def question_type(question: RevisionQuestion) -> str:
    return str(question.scoring_criteria.get("question_type") or "short_answer")


def grade_snapshot_question(
    question: RevisionQuestion,
    *,
    answer_payload: Any,
) -> tuple[bool | None, float | None]:
    resolved_type = question_type(question)
    criteria = question.scoring_criteria
    if resolved_type == "single_choice":
        is_correct = str(answer_payload) == str(criteria.get("correct_answer") or "")
        return is_correct, float(question.points if is_correct else 0)
    if resolved_type == "multiple_choice":
        correct_values = {str(item) for item in criteria.get("correct_answers") or []}
        answer_values = answer_payload if isinstance(answer_payload, list) else []
        is_correct = {str(item) for item in answer_values} == correct_values
        return is_correct, float(question.points if is_correct else 0)
    if resolved_type == "true_false":
        is_correct = parse_bool(answer_payload) is bool(criteria.get("correct_bool"))
        return is_correct, float(question.points if is_correct else 0)
    return None, None


def answer_payload_snapshot(
    question: RevisionQuestion,
    *,
    answer_payload: Any,
    attempt_context: PathAttemptContextPayload | None = None,
    is_correct: bool | None,
    score: float | None,
    scoring_feedback: str | None,
    scoring_reason: str | None,
    normalized_score: float | None,
) -> dict[str, Any]:
    criteria = question.scoring_criteria
    resolved_type = question_type(question)
    return {
        "value": answer_payload,
        "attempt_context": attempt_context,
        "question_snapshot": {
            "question_id": question.question_id,
            "question_revision_id": question.question_revision_id,
            "question_payload_hash": question.question_payload_hash,
            "title": question.title,
            "stem": question.stem,
            "question_type": resolved_type,
            "options": criteria.get("options") or [],
            "correct_answer": correct_answer_snapshot(criteria, resolved_type),
            "reference_answer": question.reference_answer,
            "explanation": criteria.get("explanation"),
            "scoring_dimensions": question.scoring_dimensions,
            "points": question.points,
        },
        "scoring": {
            "is_correct": is_correct,
            "score": score,
            "normalized_score": normalized_score,
            "feedback": scoring_feedback,
            "reason": scoring_reason,
        },
    }


def correct_answer_snapshot(criteria: dict[str, Any], resolved_type: str) -> Any:
    if resolved_type == "multiple_choice":
        return criteria.get("correct_answers") or []
    if resolved_type == "true_false":
        return criteria.get("correct_bool")
    return criteria.get("correct_answer")


def parse_bool(value: Any) -> bool | None:
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


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return None
