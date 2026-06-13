from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from json import dumps
from typing import Any, Final

from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import (
    GateResult,
    LearningContentUpdate,
    PublishGateDecision,
)
from curriculum_practice.services.sales_trainer_revision_adapter import AssetChangeClass

LEARNING_CONTENT_RESOURCE_TYPE: Final = "curriculum_learning_content"
LEARNING_CONTENT_TARGET_TYPE: Final = "curriculum_learning_content"


def learning_content_lifecycle_snapshot(
    content: LearningContent,
    chapters: list[LearningChapter],
) -> dict[str, Any]:
    return {
        "learning_content_id": str(content.learning_content_id),
        "title": content.title,
        "summary": content.summary,
        "owner": content.owner,
        "source": content.source,
        "safety_flagged": bool(content.safety_flagged),
        "version": int(content.version or 1),
        "chapters": [
            {
                "chapter_id": str(chapter.chapter_id),
                "title": chapter.title,
                "content": chapter.content,
                "order_index": int(chapter.order_index),
            }
            for chapter in chapters
        ],
    }


def learning_content_revision_payload_from_update(
    content: LearningContent,
    chapters: list[LearningChapter],
    payload: LearningContentUpdate,
) -> dict[str, Any]:
    next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
    next_snapshot.update(payload.model_dump(exclude_unset=True))
    next_snapshot["version"] = int(content.version or 1) + 1
    return next_snapshot


def apply_learning_content_revision_payload(
    content: LearningContent,
    payload: dict[str, Any],
    *,
    actor_id: str,
    revision_no: int,
    published_at: datetime,
) -> None:
    content.title = _required_str(payload, "title")
    content.summary = _optional_str(payload, "summary")
    content.owner = _optional_str(payload, "owner")
    content.source = _optional_str(payload, "source")
    content.safety_flagged = bool(payload.get("safety_flagged"))
    content.version = revision_no
    content.status = "published"
    content.published_by = actor_id
    content.published_at = published_at
    content.content_hash = learning_content_payload_hash(payload)
    content.updated_by = actor_id


def learning_content_publish_decision_from_payload(
    payload: dict[str, Any],
) -> PublishGateDecision:
    chapters = _chapters(payload)
    results: list[GateResult] = []
    if not chapters:
        results.append(
            _gate(
                "chapter_presence",
                "no_chapters",
                "LearningContent requires at least one chapter.",
            )
        )
    if any(not _chapter_content(chapter).strip() for chapter in chapters):
        results.append(
            _gate(
                "chapter_content",
                "empty_chapter_content",
                "Every chapter must contain content.",
            )
        )
    expected_order = list(range(1, len(chapters) + 1))
    actual_order = [_chapter_order(chapter) for chapter in chapters]
    if actual_order != expected_order:
        results.append(
            _gate(
                "chapter_order",
                "non_contiguous_chapter_order",
                "Chapter order must be contiguous from 1.",
            )
        )
    if payload.get("safety_flagged") is True:
        results.append(
            _gate(
                "content_safety",
                "security_flagged_content",
                "Security flagged content cannot be published.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def learning_content_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        "title": payload.get("title"),
        "summary": payload.get("summary"),
        "owner": payload.get("owner"),
        "source": payload.get("source"),
        "version": payload.get("version"),
        "chapters": [
            {
                "title": chapter.get("title"),
                "content": chapter.get("content"),
                "order_index": chapter.get("order_index"),
            }
            for chapter in _chapters(payload)
        ],
    }
    return "sha256:" + sha256(
        dumps(
            hash_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def learning_content_chapter_payloads(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    return _chapters(payload)


def learning_content_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if previous == next_snapshot:
        return "non_semantic"
    return "semantic"


def learning_content_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _summary(previous),
        "after": _summary(next_snapshot),
        "before_hash": learning_content_payload_hash(previous),
        "after_hash": learning_content_payload_hash(next_snapshot),
    }


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": payload.get("title"),
        "summary": payload.get("summary"),
        "owner": payload.get("owner"),
        "source": payload.get("source"),
        "safety_flagged": payload.get("safety_flagged"),
        "chapter_count": len(_chapters(payload)),
    }


def _chapters(payload: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        return []
    return [dict(chapter) for chapter in chapters if isinstance(chapter, dict)]


def _chapter_content(chapter: dict[str, Any]) -> str:
    content = chapter.get("content")
    if isinstance(content, str):
        return content
    return ""


def _chapter_order(chapter: dict[str, Any]) -> int:
    order_index = chapter.get("order_index")
    if isinstance(order_index, int):
        return order_index
    return 0


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return ""


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return None


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )
