from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any, Final

from curriculum_practice.models import QuestionItem
from curriculum_practice.schemas import (
    GateResult,
    PublishGateDecision,
    QuestionItemUpdate,
)
from curriculum_practice.services.sales_trainer_revision_adapter import AssetChangeClass

QUESTION_ITEM_RESOURCE_TYPE: Final = "curriculum_question_item"
QUESTION_ITEM_TARGET_TYPE: Final = "curriculum_question_item"


def question_item_lifecycle_snapshot(question: QuestionItem) -> dict[str, Any]:
    return {
        "question_id": str(question.question_id),
        "category_id": str(question.category_id),
        "title": question.title,
        "stem": question.stem,
        "reference_answer": question.reference_answer,
        "scoring_criteria": question.scoring_criteria or {},
        "scoring_dimensions": question.scoring_dimensions or [],
        "tags": question.tags or [],
        "usage_scope": question.usage_scope,
        "difficulty": question.difficulty,
        "status": question.status,
        "safety_flagged": bool(question.safety_flagged),
        "department": question.department,
        "version": int(question.version or 1),
        "content_hash": question.content_hash,
        "published_at": _datetime_value(question.published_at),
        "created_at": _datetime_value(question.created_at),
        "updated_at": _datetime_value(question.updated_at),
    }


def question_item_revision_payload_from_update(
    question: QuestionItem,
    payload: QuestionItemUpdate,
) -> dict[str, Any]:
    next_snapshot = question_item_lifecycle_snapshot(question)
    update = payload.model_dump(exclude_unset=True)
    if "scoring_dimensions" in update:
        update["scoring_criteria"] = _criteria_with_dimensions(
            update.get("scoring_criteria", question.scoring_criteria),
            update.get("scoring_dimensions"),
        )
    next_snapshot.update(update)
    next_snapshot["status"] = "published"
    next_snapshot["version"] = int(question.version or 1) + 1
    next_snapshot["published_at"] = _datetime_value(datetime.now(UTC))
    next_snapshot["content_hash"] = question_item_payload_hash(next_snapshot)
    return next_snapshot


def apply_question_item_revision_payload(
    question: QuestionItem,
    payload: dict[str, Any],
    *,
    actor_id: str,
) -> None:
    question.category_id = _required_str(payload, "category_id")
    question.title = _required_str(payload, "title")
    question.stem = _required_str(payload, "stem")
    question.reference_answer = _optional_str(payload, "reference_answer")
    question.scoring_criteria = _dict_value(payload, "scoring_criteria")
    question.scoring_dimensions = _list_value(payload, "scoring_dimensions")
    question.tags = _list_value(payload, "tags")
    question.usage_scope = _required_str(payload, "usage_scope")
    question.difficulty = _required_str(payload, "difficulty")
    question.safety_flagged = bool(payload.get("safety_flagged"))
    question.department = _optional_str(payload, "department")
    question.status = "published"
    question.version = _int_value(payload, "version", fallback=question.version or 1)
    question.content_hash = question_item_payload_hash(payload)
    question.published_by = actor_id
    question.published_at = datetime.now(UTC)
    question.updated_by = actor_id


def question_item_publish_decision_from_payload(
    payload: dict[str, Any],
) -> PublishGateDecision:
    results: list[GateResult] = []
    if not _optional_str(payload, "reference_answer"):
        results.append(
            _gate(
                "reference_answer",
                "missing_reference_answer",
                "QuestionItem requires a reference answer before publish.",
            )
        )
    criteria_dimensions = _dict_value(payload, "scoring_criteria").get("dimensions")
    if not isinstance(criteria_dimensions, list) or not criteria_dimensions:
        results.append(
            _gate(
                "scoring_criteria",
                "invalid_scoring_criteria",
                "QuestionItem scoring_criteria.dimensions must be non-empty.",
            )
        )
    if not _list_value(payload, "scoring_dimensions"):
        results.append(
            _gate(
                "scoring_dimensions",
                "invalid_scoring_dimensions",
                "QuestionItem scoring_dimensions must be non-empty.",
            )
        )
    if payload.get("safety_flagged") is True:
        results.append(
            _gate(
                "question_safety",
                "security_flagged_question",
                "Security flagged questions cannot be published.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def question_item_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if _high_risk_fields_changed(previous, next_snapshot):
        return "scoring_high_risk"
    if previous.get("category_id") != next_snapshot.get("category_id"):
        return "binding"
    if previous.get("title") != next_snapshot.get("title"):
        return "semantic"
    if previous.get("stem") != next_snapshot.get("stem"):
        return "semantic"
    return "non_semantic"


def question_item_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _summary(previous),
        "after": _summary(next_snapshot),
        "before_hash": question_item_payload_hash(previous),
        "after_hash": question_item_payload_hash(next_snapshot),
        "changed_fields": [
            field
            for field in _tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        ],
    }


def question_item_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        "category_id": payload.get("category_id"),
        "title": payload.get("title"),
        "stem": payload.get("stem"),
        "reference_answer": payload.get("reference_answer"),
        "scoring_criteria": payload.get("scoring_criteria"),
        "scoring_dimensions": payload.get("scoring_dimensions"),
        "tags": payload.get("tags"),
        "usage_scope": payload.get("usage_scope"),
        "difficulty": payload.get("difficulty"),
        "safety_flagged": payload.get("safety_flagged"),
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


def _criteria_with_dimensions(
    scoring_criteria: Any,
    scoring_dimensions: Any,
) -> dict[str, Any]:
    criteria = dict(scoring_criteria) if isinstance(scoring_criteria, dict) else {}
    if not isinstance(scoring_dimensions, list) or not scoring_dimensions:
        return criteria
    criteria_dimensions = criteria.get("dimensions")
    if not isinstance(criteria_dimensions, list) or not criteria_dimensions:
        criteria["dimensions"] = list(scoring_dimensions)
    return criteria


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": payload.get("question_id"),
        "category_id": payload.get("category_id"),
        "title": payload.get("title"),
        "status": payload.get("status"),
        "version": payload.get("version"),
        "difficulty": payload.get("difficulty"),
        "usage_scope": payload.get("usage_scope"),
        "safety_flagged": payload.get("safety_flagged"),
    }


def _tracked_fields() -> tuple[str, ...]:
    return (
        "category_id",
        "title",
        "stem",
        "reference_answer",
        "scoring_criteria",
        "scoring_dimensions",
        "tags",
        "usage_scope",
        "difficulty",
        "safety_flagged",
        "department",
        "version",
    )


def _high_risk_fields_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    return any(
        previous.get(field) != next_snapshot.get(field)
        for field in ("reference_answer", "scoring_criteria", "scoring_dimensions")
    )


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return ""


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value.strip() or None
    return None


def _dict_value(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    return dict(value) if isinstance(value, dict) else {}


def _list_value(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name)
    return list(value) if isinstance(value, list) else []


def _int_value(payload: dict[str, Any], field_name: str, *, fallback: int) -> int:
    value = payload.get(field_name)
    return value if isinstance(value, int) else int(fallback)


def _datetime_value(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )
