from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from curriculum_practice.models import QuestionCategory, QuestionItem
from sales_trainer.schemas import SalesTrainerQuestionUpdate
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.question_contracts import to_question_item_update

SALES_TRAINER_QUESTION_SCOPE = "sales_trainer"
QUESTION_RESOURCE_TYPE = "sales_trainer_question"


def serialize_sales_trainer_category(category: QuestionCategory) -> dict[str, Any]:
    return {
        "category_id": category.category_id,
        "parent_id": category.parent_id,
        "name": category.name,
        "description": category.description,
        "usage_scope": category.usage_scope,
        "order_index": category.order_index,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def serialize_sales_trainer_question(question: QuestionItem) -> dict[str, Any]:
    criteria = question.scoring_criteria or {}
    question_type = str(criteria.get("question_type") or "short_answer")
    return {
        **question_lifecycle_snapshot(question),
        "question_type": question_type,
        "options": criteria.get("options") or [],
        "correct_answer": criteria.get("correct_answer"),
        "correct_answers": criteria.get("correct_answers") or [],
        "correct_bool": criteria.get("correct_bool"),
        "explanation": criteria.get("explanation"),
        "ai_scoring": criteria.get("ai_scoring"),
    }


def question_lifecycle_snapshot(question: QuestionItem) -> dict[str, Any]:
    return {
        "question_id": str(question.question_id),
        "title": question.title,
        "stem": question.stem,
        "reference_answer": question.reference_answer,
        "category_id": str(question.category_id),
        "difficulty": question.difficulty,
        "status": question.status,
        "tags": question.tags or [],
        "scoring_dimensions": question.scoring_dimensions or [],
        "scoring_criteria": question.scoring_criteria or {},
        "safety_flagged": question.safety_flagged,
        "department": question.department,
        "usage_scope": question.usage_scope,
        "version": question.version,
        "content_hash": question.content_hash,
        "published_at": _datetime_value(question.published_at),
        "created_at": _datetime_value(question.created_at),
        "updated_at": _datetime_value(question.updated_at),
    }


def question_revision_payload_from_update(
    current: QuestionItem,
    payload: SalesTrainerQuestionUpdate,
) -> dict[str, Any]:
    base = question_lifecycle_snapshot(current)
    update = to_question_item_update(current, payload).model_dump(exclude_unset=True)
    next_payload = {
        **base,
        **update,
        "status": "published",
        "version": int(base.get("version") or 1) + 1,
        "published_at": _datetime_value(datetime.now(UTC)),
    }
    next_payload["content_hash"] = question_payload_hash(next_payload)
    return next_payload


def apply_question_revision_payload(
    question: QuestionItem,
    payload: dict[str, Any],
    *,
    actor_id: str,
) -> None:
    question.title = str(payload["title"])
    question.stem = str(payload["stem"])
    question.reference_answer = payload.get("reference_answer")
    question.category_id = str(payload["category_id"])
    question.difficulty = str(payload.get("difficulty") or "medium")
    question.tags = list(payload.get("tags") or [])
    question.scoring_criteria = dict(payload.get("scoring_criteria") or {})
    question.scoring_dimensions = list(payload.get("scoring_dimensions") or [])
    question.safety_flagged = bool(payload.get("safety_flagged") or False)
    question.department = payload.get("department")
    question.usage_scope = SALES_TRAINER_QUESTION_SCOPE
    question.status = "published"
    question.version = int(payload.get("version") or question.version or 1)
    question.content_hash = question_payload_hash(question_lifecycle_snapshot(question))
    question.published_by = actor_id
    question.published_at = datetime.now(UTC)
    question.updated_by = actor_id


def question_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    fields = (
        "title",
        "stem",
        "reference_answer",
        "category_id",
        "difficulty",
        "tags",
        "scoring_dimensions",
        "scoring_criteria",
        "safety_flagged",
        "department",
        "status",
        "version",
    )
    return {
        "previous": previous,
        "next": next_snapshot,
        "changed_fields": [
            field for field in fields if previous.get(field) != next_snapshot.get(field)
        ],
        "previous_status": previous.get("status"),
        "next_status": next_snapshot.get("status"),
        "question_id": next_snapshot.get("question_id"),
        "category_id": next_snapshot.get("category_id"),
    }


def question_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if _scoring_fields_changed(previous, next_snapshot):
        return "scoring_high_risk"
    if previous.get("category_id") != next_snapshot.get("category_id"):
        return "binding"
    if previous.get("title") == next_snapshot.get("title") and previous.get(
        "stem"
    ) == next_snapshot.get("stem"):
        return "non_semantic"
    return "semantic"


def question_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        "category_id": payload.get("category_id"),
        "title": payload.get("title"),
        "stem": payload.get("stem"),
        "reference_answer": payload.get("reference_answer"),
        "scoring_criteria": payload.get("scoring_criteria"),
        "scoring_dimensions": payload.get("scoring_dimensions"),
        "tags": payload.get("tags"),
        "difficulty": payload.get("difficulty"),
        "department": payload.get("department"),
        "version": payload.get("version"),
    }
    return "sha256:" + sha256(
        dumps(
            hash_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _datetime_value(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _scoring_fields_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    if previous.get("reference_answer") != next_snapshot.get("reference_answer"):
        return True
    if previous.get("scoring_dimensions") != next_snapshot.get("scoring_dimensions"):
        return True
    previous_criteria = previous.get("scoring_criteria")
    next_criteria = next_snapshot.get("scoring_criteria")
    if not isinstance(previous_criteria, dict) or not isinstance(next_criteria, dict):
        return previous_criteria != next_criteria
    high_risk_keys = (
        "correct_answer",
        "correct_answers",
        "correct_bool",
        "ai_scoring",
    )
    return any(
        previous_criteria.get(key) != next_criteria.get(key)
        for key in high_risk_keys
    )
