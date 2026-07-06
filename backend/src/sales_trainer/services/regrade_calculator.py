from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.typing import json_dict_or_empty, orm_scalar
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerQuizAttempt
from sales_trainer.services.paper_snapshot_scoring import (
    RevisionQuestion,
    answer_payload_snapshot,
    float_or_none,
    grade_snapshot_question,
    optional_str,
    question_type,
)
from sales_trainer.services.quiz_attempt_payloads import serialize_quiz_attempt


@dataclass(frozen=True, slots=True)
class QuizRegradePreview:
    target_type: str
    target_id: str
    target_revision_id: str
    impact_scope: dict[str, Any]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]


async def build_quiz_regrade_preview(
    db: AsyncSession,
    attempt: SalesTrainerQuizAttempt,
    target_revision: SalesTrainerAssetRevision,
) -> QuizRegradePreview:
    attempt_id = orm_scalar(attempt.attempt_id, str)
    target_revision_id = orm_scalar(target_revision.revision_id, str)
    before_snapshot = await _attempt_snapshot(db, attempt)
    after_snapshot = _regrade_against_revision(
        before_snapshot,
        target_revision,
    )
    return QuizRegradePreview(
        target_type="quiz_attempt",
        target_id=attempt_id,
        target_revision_id=target_revision_id,
        impact_scope=_impact_scope(attempt_id),
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


async def _attempt_snapshot(
    db: AsyncSession,
    attempt: SalesTrainerQuizAttempt,
) -> dict[str, Any]:
    serialized = await serialize_quiz_attempt(db, attempt)
    return {
        "attempt_id": serialized["attempt_id"],
        "unit_id": serialized["unit_id"],
        "user_id": serialized["user_id"],
        "paper_revision_id": attempt.paper_revision_id,
        "total_score": _float_value(serialized.get("total_score")),
        "max_score": _float_value(serialized.get("max_score")),
        "passed": serialized["passed"],
        "status": serialized["status"],
        "answers": [
            {
                "question_id": answer["question_id"],
                "question_type": answer["question_type"],
                "answer_payload": answer["answer_payload"],
                "question_title": answer["question_title"],
                "question_stem": answer["question_stem"],
                "correct_answer": answer["correct_answer"],
                "score": _float_value(answer.get("score")),
                "is_correct": answer["is_correct"],
                "scoring_feedback": answer["scoring_feedback"],
                "scoring_reason": answer["scoring_reason"],
            }
            for answer in serialized["answers"]
        ],
    }


def _regrade_against_revision(
    before_snapshot: dict[str, Any],
    revision: SalesTrainerAssetRevision,
) -> dict[str, Any]:
    revision_payload = json_dict_or_empty(revision.payload_json)
    answer_map = _answer_map(before_snapshot)
    answers: list[dict[str, Any]] = []
    total_score = 0.0
    max_score = 0.0
    has_unscored = False
    for question in _revision_questions(revision_payload):
        answer_payload = answer_map.get(question.question_id)
        is_correct, score = grade_snapshot_question(
            question,
            answer_payload=answer_payload,
        )
        if score is None:
            has_unscored = True
        else:
            total_score += score
        max_score += float(question.points)
        answers.append(
            {
                "question_id": question.question_id,
                "answer_payload": answer_payload,
                "question_type": question_type(question),
                "is_correct": is_correct,
                "score": score,
                "question_snapshot": answer_payload_snapshot(
                    question,
                    answer_payload=answer_payload,
                    is_correct=is_correct,
                    score=score,
                    scoring_feedback=None,
                    scoring_reason=None,
                    normalized_score=None,
                )["question_snapshot"],
            }
        )
    threshold = float_or_none(revision_payload.get("pass_threshold"))
    return {
        "attempt_id": before_snapshot["attempt_id"],
        "source_revision_id": before_snapshot.get("paper_revision_id"),
        "target_revision_id": revision.revision_id,
        "target_revision_no": revision.revision_no,
        "total_score": None if has_unscored else total_score,
        "max_score": max_score,
        "passed": (
            total_score >= threshold
            if threshold is not None and not has_unscored
            else None
        ),
        "answers": answers,
        "has_unscored_questions": has_unscored,
    }


def _revision_questions(payload: dict[str, Any]) -> list[RevisionQuestion]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        _revision_question(item)
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("question_snapshot"), dict)
    ]


def _revision_question(item: dict[str, Any]) -> RevisionQuestion:
    snapshot = dict(item.get("question_snapshot") or {})
    return RevisionQuestion(
        question_id=str(item["question_id"]),
        title=str(snapshot.get("title") or ""),
        stem=str(snapshot.get("stem") or ""),
        reference_answer=optional_str(snapshot.get("reference_answer")),
        scoring_criteria=dict(snapshot.get("scoring_criteria") or {}),
        scoring_dimensions=[
            str(value) for value in snapshot.get("scoring_dimensions") or []
        ],
        points=int(item["points"]),
        order_index=int(item["order_index"]),
        question_revision_id=optional_str(item.get("question_revision_id")),
        question_payload_hash=optional_str(item.get("question_payload_hash")),
    )


def _answer_map(snapshot: dict[str, Any]) -> dict[str, Any]:
    answers = snapshot.get("answers")
    if not isinstance(answers, list):
        return {}
    return {
        str(answer["question_id"]): answer.get("answer_payload")
        for answer in answers
        if isinstance(answer, dict) and isinstance(answer.get("question_id"), str)
    }


def _impact_scope(attempt_id: str) -> dict[str, Any]:
    return {
        "record_count": 1,
        "affected_attempt_ids": [attempt_id],
        "future_records_changed": False,
        "history_overwrite": False,
        "requires_reason": True,
    }


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return None
