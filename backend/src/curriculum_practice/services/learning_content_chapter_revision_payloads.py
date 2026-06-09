from __future__ import annotations

from typing import Any

from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import LearningChapterCreate, LearningChapterUpdate
from curriculum_practice.services.learning_content_revision_payloads import (
    learning_content_chapter_payloads,
    learning_content_lifecycle_snapshot,
)


def learning_content_revision_payload_from_chapter_update(
    content: LearningContent,
    chapters: list[LearningChapter],
    chapter: LearningChapter,
    payload: LearningChapterUpdate,
) -> dict[str, Any]:
    next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
    patch = payload.model_dump(exclude_unset=True)
    chapter_payloads = learning_content_chapter_payloads(next_snapshot)
    for chapter_payload in chapter_payloads:
        if chapter_payload.get("chapter_id") == str(chapter.chapter_id):
            chapter_payload.update(patch)
            break
    next_snapshot["chapters"] = chapter_payloads
    next_snapshot["version"] = int(content.version or 1) + 1
    return next_snapshot


def learning_content_revision_payload_from_chapter_create(
    content: LearningContent,
    chapters: list[LearningChapter],
    payload: LearningChapterCreate,
    *,
    chapter_id: str,
) -> dict[str, Any]:
    next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
    chapter_payloads = learning_content_chapter_payloads(next_snapshot)
    order_index = payload.order_index or len(chapter_payloads) + 1
    chapter_payloads.append(
        {
            "chapter_id": chapter_id,
            "title": payload.title,
            "content": payload.content,
            "order_index": order_index,
        }
    )
    next_snapshot["chapters"] = _sort_chapters(chapter_payloads)
    next_snapshot["version"] = int(content.version or 1) + 1
    return next_snapshot


def learning_content_revision_payload_from_chapter_delete(
    content: LearningContent,
    chapters: list[LearningChapter],
    chapter: LearningChapter,
) -> dict[str, Any]:
    next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
    chapter_payloads = [
        chapter_payload
        for chapter_payload in learning_content_chapter_payloads(next_snapshot)
        if chapter_payload.get("chapter_id") != str(chapter.chapter_id)
    ]
    next_snapshot["chapters"] = _with_contiguous_order(chapter_payloads)
    next_snapshot["version"] = int(content.version or 1) + 1
    return next_snapshot


def learning_content_revision_payload_from_chapter_reorder(
    content: LearningContent,
    chapters: list[LearningChapter],
    chapter_ids: list[str],
) -> dict[str, Any]:
    next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
    chapter_payloads = {
        chapter["chapter_id"]: chapter
        for chapter in learning_content_chapter_payloads(next_snapshot)
    }
    next_snapshot["chapters"] = [
        chapter_payloads[chapter_id] | {"order_index": index}
        for index, chapter_id in enumerate(chapter_ids, start=1)
    ]
    next_snapshot["version"] = int(content.version or 1) + 1
    return next_snapshot


def _sort_chapters(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(chapters, key=_chapter_order)


def _with_contiguous_order(chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        chapter | {"order_index": index}
        for index, chapter in enumerate(_sort_chapters(chapters), start=1)
    ]


def _chapter_order(chapter: dict[str, Any]) -> int:
    order_index = chapter.get("order_index")
    if isinstance(order_index, int):
        return order_index
    return 0
