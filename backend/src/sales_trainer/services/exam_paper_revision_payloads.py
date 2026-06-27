from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import QuestionItem
from sales_trainer.models import SalesTrainerUnitQuestion
from sales_trainer.schemas import UnitQuestionBinding
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.question_bank import (
    QUESTION_RESOURCE_TYPE,
    question_lifecycle_snapshot,
)
from sales_trainer.services.question_bank.payloads import question_payload_hash


async def freeze_paper_question_revisions(
    db: AsyncSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return payload
    frozen_questions = [
        await _freeze_question_binding(db, item)
        for item in questions
        if isinstance(item, dict)
    ]
    return {
        **payload,
        "questions": frozen_questions,
        "question_ids": [str(item["question_id"]) for item in frozen_questions],
    }


def paper_revision_has_question_snapshots(payload: dict[str, Any]) -> bool:
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        return False
    return all(
        isinstance(item, dict) and isinstance(item.get("question_snapshot"), dict)
        for item in questions
    )


def paper_revision_unit_bindings(payload: dict[str, Any]) -> list[UnitQuestionBinding]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        UnitQuestionBinding(
            question_id=str(item["question_id"]),
            order_index=int(item["order_index"]),
            points=int(item["points"]),
        )
        for item in questions
        if isinstance(item, dict)
    ]


def paper_revision_questions_for_learner(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        _learner_question(item)
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("question_snapshot"), dict)
    ]


def unit_question_revision_seed(
    item: SalesTrainerUnitQuestion,
) -> dict[str, Any]:
    return {
        "question_id": str(item.question_id),
        "order_index": int(item.order_index),
        "points": _points(item.points),
    }


async def _freeze_question_binding(
    db: AsyncSession,
    item: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(item.get("question_snapshot"), dict):
        return _normalize_existing_snapshot(item)
    question_id = str(item["question_id"])
    active_revision = await SalesTrainerAssetRevisionService(db).active_revision(
        resource_type=QUESTION_RESOURCE_TYPE,
        logical_id=question_id,
    )
    if active_revision is not None and isinstance(active_revision.payload_json, dict):
        return _binding_with_snapshot(
            item,
            question_snapshot=dict(active_revision.payload_json),
            question_revision_id=str(active_revision.revision_id),
            question_revision_no=int(active_revision.revision_no),
            question_payload_hash=str(active_revision.payload_hash),
            legacy_snapshot_only=False,
        )
    question = await db.get(QuestionItem, question_id)
    snapshot = question_lifecycle_snapshot(question) if question is not None else {}
    return _binding_with_snapshot(
        item,
        question_snapshot=snapshot,
        question_revision_id=None,
        question_revision_no=None,
        question_payload_hash=_legacy_question_payload_hash(question),
        legacy_snapshot_only=True,
    )


def _binding_with_snapshot(
    item: dict[str, Any],
    *,
    question_snapshot: dict[str, Any],
    question_revision_id: str | None,
    question_revision_no: int | None,
    question_payload_hash: str | None,
    legacy_snapshot_only: bool,
) -> dict[str, Any]:
    return {
        "question_id": str(item["question_id"]),
        "order_index": int(item["order_index"]),
        "points": _points(item.get("points")),
        "question_revision_id": question_revision_id,
        "question_revision_no": question_revision_no,
        "question_payload_hash": question_payload_hash,
        "legacy_snapshot_only": legacy_snapshot_only,
        "question_snapshot": _question_snapshot(question_snapshot),
    }


def _normalize_existing_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "question_id": str(item["question_id"]),
        "order_index": int(item["order_index"]),
        "points": _points(item.get("points")),
        "question_snapshot": _question_snapshot(
            dict(item.get("question_snapshot") or {})
        ),
    }


def _question_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    criteria = payload.get("scoring_criteria")
    dimensions = payload.get("scoring_dimensions")
    return {
        "question_id": str(payload.get("question_id") or ""),
        "title": payload.get("title"),
        "stem": payload.get("stem"),
        "reference_answer": payload.get("reference_answer"),
        "scoring_criteria": criteria if isinstance(criteria, dict) else {},
        "scoring_dimensions": dimensions if isinstance(dimensions, list) else [],
        "content_hash": payload.get("content_hash"),
        "version": payload.get("version"),
    }


def _learner_question(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = item["question_snapshot"]
    criteria = snapshot.get("scoring_criteria") or {}
    question_type = str(criteria.get("question_type") or "short_answer")
    payload = {
        "question_id": str(item["question_id"]),
        "order_index": int(item["order_index"]),
        "points": _points(item.get("points")),
        "question_revision_id": item.get("question_revision_id"),
        "title": snapshot.get("title"),
        "stem": snapshot.get("stem"),
        "question_type": question_type,
    }
    if question_type in {"single_choice", "multiple_choice"}:
        payload["options"] = criteria.get("options") or []
    return payload


def _points(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


def _legacy_question_payload_hash(question: QuestionItem | None) -> str | None:
    if question is None:
        return None
    if question.content_hash is not None:
        return str(question.content_hash)
    return question_payload_hash(question_lifecycle_snapshot(question))
