from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.services.learning_content_revision_payloads import (
    learning_content_chapter_payloads,
)
from curriculum_practice.services.orm_payload_typing import set_orm_field


class LearningContentRevisionApplier:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def apply_chapters_from_payload(
        self,
        content: LearningContent,
        payload: dict[str, Any],
        *,
        actor_id: str,
    ) -> None:
        existing_chapters = await self._load_chapters(str(content.learning_content_id))
        existing_by_id = {
            str(chapter.chapter_id): chapter for chapter in existing_chapters
        }
        incoming_payloads = learning_content_chapter_payloads(payload)
        incoming_ids = {
            str(chapter_payload.get("chapter_id"))
            for chapter_payload in incoming_payloads
            if isinstance(chapter_payload.get("chapter_id"), str)
        }
        offset = len(existing_chapters) + len(incoming_payloads) + 1
        for index, chapter in enumerate(existing_chapters, start=1):
            set_orm_field(chapter, "order_index", offset + index)
        await self._db.flush()
        for chapter_payload in incoming_payloads:
            chapter_id = _optional_str(chapter_payload.get("chapter_id"))
            existing_chapter = existing_by_id.get(chapter_id or "")
            if existing_chapter is None:
                chapter = LearningChapter(
                    learning_content_id=str(content.learning_content_id),
                    title=_required_str(chapter_payload.get("title")),
                    content=_required_str(chapter_payload.get("content")),
                    order_index=_required_int(chapter_payload.get("order_index")),
                    created_by=actor_id,
                    updated_by=actor_id,
                )
                if chapter_id is not None:
                    set_orm_field(chapter, "chapter_id", chapter_id)
                self._db.add(chapter)
            else:
                set_orm_field(
                    existing_chapter,
                    "title",
                    _required_str(chapter_payload.get("title")),
                )
                set_orm_field(
                    existing_chapter,
                    "content",
                    _required_str(chapter_payload.get("content")),
                )
                set_orm_field(
                    existing_chapter,
                    "order_index",
                    _required_int(chapter_payload.get("order_index")),
                )
                set_orm_field(existing_chapter, "updated_by", actor_id)
        for chapter in existing_chapters:
            if str(chapter.chapter_id) not in incoming_ids:
                await self._db.delete(chapter)
        await self._db.flush()

    async def _load_chapters(self, content_id: str) -> list[LearningChapter]:
        result = await self._db.execute(
            select(LearningChapter)
            .where(LearningChapter.learning_content_id == content_id)
            .order_by(LearningChapter.order_index.asc())
        )
        return list(result.scalars().all())


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _required_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def _required_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return 1
