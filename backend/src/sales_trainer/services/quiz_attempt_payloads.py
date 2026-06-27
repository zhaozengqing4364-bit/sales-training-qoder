from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
)


def answer_payload_snapshot(
    question: Any,
    *,
    answer_payload: Any,
    points: int,
    is_correct: bool | None,
    score: float | None,
    scoring_feedback: str | None,
    scoring_reason: str | None,
    normalized_score: float | None,
) -> dict[str, Any]:
    criteria = question.scoring_criteria or {}
    question_type = str(criteria.get("question_type") or "short_answer")
    return {
        "value": answer_payload,
        "question_snapshot": {
            "question_id": str(question.question_id),
            "title": question.title,
            "stem": question.stem,
            "question_type": question_type,
            "options": criteria.get("options") or [],
            "correct_answer": _correct_answer_snapshot(criteria, question_type),
            "reference_answer": question.reference_answer,
            "explanation": criteria.get("explanation"),
            "scoring_dimensions": question.scoring_dimensions or [],
            "points": points,
        },
        "scoring": {
            "is_correct": is_correct,
            "score": score,
            "normalized_score": normalized_score,
            "feedback": scoring_feedback,
            "reason": scoring_reason,
        },
    }


async def serialize_quiz_attempt(
    db: AsyncSession,
    attempt: SalesTrainerQuizAttempt,
) -> dict[str, Any]:
    result = await db.execute(
        select(SalesTrainerQuizAnswer)
        .where(SalesTrainerQuizAnswer.attempt_id == attempt.attempt_id)
        .order_by(SalesTrainerQuizAnswer.created_at.asc())
    )
    answers = list(result.scalars().all())
    user = await db.get(User, attempt.user_id)
    return {
        "attempt_id": attempt.attempt_id,
        "unit_id": attempt.unit_id,
        "user_id": attempt.user_id,
        "user_name": user.name if user else None,
        "user_email": user.email if user else None,
        "user_department": user.department if user else None,
        "total_score": float(attempt.total_score)
        if attempt.total_score is not None
        else None,
        "max_score": float(attempt.max_score)
        if attempt.max_score is not None
        else None,
        "passed": attempt.passed,
        "status": attempt.status,
        "submitted_at": attempt.submitted_at,
        "answers": [_serialize_answer(answer) for answer in answers],
    }


def _serialize_answer(answer: SalesTrainerQuizAnswer) -> dict[str, Any]:
    return {
        "answer_id": answer.answer_id,
        "question_id": answer.question_id,
        "question_type": answer.question_type,
        "answer_payload": _answer_value(answer.answer_payload),
        "question_title": _answer_snapshot_value(answer.answer_payload, "title"),
        "question_stem": _answer_snapshot_value(answer.answer_payload, "stem"),
        "question_revision_id": _answer_snapshot_value(
            answer.answer_payload,
            "question_revision_id",
        ),
        "question_payload_hash": _answer_snapshot_value(
            answer.answer_payload,
            "question_payload_hash",
        ),
        "options": _answer_snapshot_list(answer.answer_payload, "options"),
        "correct_answer": _answer_snapshot_value(
            answer.answer_payload,
            "correct_answer",
        ),
        "reference_answer": _answer_snapshot_value(
            answer.answer_payload,
            "reference_answer",
        ),
        "explanation": _answer_snapshot_value(answer.answer_payload, "explanation"),
        "scoring_feedback": _answer_scoring_value(answer.answer_payload, "feedback"),
        "scoring_reason": _answer_scoring_value(answer.answer_payload, "reason"),
        "normalized_score": _answer_scoring_number(
            answer.answer_payload,
            "normalized_score",
        ),
        "max_score": _answer_snapshot_number(answer.answer_payload, "points"),
        "scoring_dimensions": _answer_snapshot_str_list(
            answer.answer_payload,
            "scoring_dimensions",
        ),
        "attempt_context": _answer_attempt_context(answer.answer_payload),
        "is_correct": answer.is_correct,
        "score": float(answer.score) if answer.score is not None else None,
        "created_at": answer.created_at,
    }


def _correct_answer_snapshot(criteria: dict[str, Any], question_type: str) -> Any:
    if question_type == "multiple_choice":
        return criteria.get("correct_answers") or []
    if question_type == "true_false":
        return criteria.get("correct_bool")
    return criteria.get("correct_answer")


def _answer_value(payload: Any) -> Any:
    if isinstance(payload, dict) and "value" in payload:
        return payload.get("value")
    return payload


def _answer_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    snapshot = payload.get("question_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _answer_snapshot_value(payload: Any, key: str) -> Any:
    return _answer_snapshot(payload).get(key)


def _answer_snapshot_list(payload: Any, key: str) -> list[dict[str, Any]]:
    value = _answer_snapshot(payload).get(key)
    return value if isinstance(value, list) else []


def _answer_snapshot_str_list(payload: Any, key: str) -> list[str]:
    value = _answer_snapshot(payload).get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _answer_snapshot_number(payload: Any, key: str) -> float | None:
    value = _answer_snapshot(payload).get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _answer_scoring(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    scoring = payload.get("scoring")
    return scoring if isinstance(scoring, dict) else {}


def _answer_scoring_value(payload: Any, key: str) -> str | None:
    value = _answer_scoring(payload).get(key)
    return value if isinstance(value, str) else None


def _answer_scoring_number(payload: Any, key: str) -> float | None:
    value = _answer_scoring(payload).get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _answer_attempt_context(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    context = payload.get("attempt_context")
    return context if isinstance(context, dict) else None
