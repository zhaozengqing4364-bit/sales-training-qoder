from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import (
    GateResult,
    LearningChapterCreate,
    LearningChapterResponse,
    LearningChapterUpdate,
    LearningContentCreate,
    LearningContentResponse,
    LearningContentUpdate,
    PublishGateDecision,
)

SERVER_ERROR = "[LEARNING_CONTENT_SERVICE_FAILED]"


class LearningContentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_contents(
        self, *, status: str | None = None
    ) -> Result[list[LearningContent]]:
        stmt = select(LearningContent)
        if status:
            stmt = stmt.where(LearningContent.status == status)
        try:
            result = await self._db.execute(
                stmt.order_by(LearningContent.updated_at.desc())
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def get_content(self, content_id: str) -> Result[LearningContent]:
        try:
            content = await self._db.get(LearningContent, content_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if content is None:
            return Result.fail("[LEARNING_CONTENT_NOT_FOUND]")
        return Result.ok(content)

    async def list_chapters(self, content_id: str) -> Result[list[LearningChapter]]:
        try:
            result = await self._db.execute(
                select(LearningChapter)
                .where(LearningChapter.learning_content_id == content_id)
                .order_by(LearningChapter.order_index.asc())
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def create_content(
        self, payload: LearningContentCreate, *, actor_id: str | None
    ) -> Result[LearningContent]:
        content = LearningContent(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(content)
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def update_content(
        self,
        content: LearningContent,
        payload: LearningContentUpdate,
        *,
        actor_id: str | None,
    ) -> Result[LearningContent]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(content, field, value)
        content.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def archive_content(
        self, content: LearningContent, *, actor_id: str | None
    ) -> Result[LearningContent]:
        content.status = "archived"
        content.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def delete_content(self, content: LearningContent) -> Result[None]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        try:
            await self._db.delete(content)
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(None)

    async def add_chapter(
        self,
        content: LearningContent,
        payload: LearningChapterCreate,
        *,
        actor_id: str | None,
    ) -> Result[LearningChapter]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        order_index = payload.order_index
        if order_index is None:
            chapters_result = await self.list_chapters(content.learning_content_id)
            if not chapters_result.is_success:
                return Result.fail(chapters_result.fallback or SERVER_ERROR)
            order_index = len(chapters_result.value or []) + 1
        chapter = LearningChapter(
            learning_content_id=content.learning_content_id,
            title=payload.title,
            content=payload.content,
            order_index=order_index,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._db.add(chapter)
        try:
            await self._db.commit()
            await self._db.refresh(chapter)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(chapter)

    async def get_chapter(
        self, content_id: str, chapter_id: str
    ) -> Result[LearningChapter]:
        try:
            chapter = await self._db.get(LearningChapter, chapter_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if chapter is None or chapter.learning_content_id != content_id:
            return Result.fail("[LEARNING_CHAPTER_NOT_FOUND]")
        return Result.ok(chapter)

    async def update_chapter(
        self,
        content: LearningContent,
        chapter: LearningChapter,
        payload: LearningChapterUpdate,
        *,
        actor_id: str | None,
    ) -> Result[LearningChapter]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(chapter, field, value)
        chapter.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(chapter)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(chapter)

    async def delete_chapter(
        self, content: LearningContent, chapter: LearningChapter
    ) -> Result[None]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        try:
            await self._db.delete(chapter)
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(None)

    async def reorder_chapters(
        self,
        content: LearningContent,
        chapter_ids: list[str],
        *,
        actor_id: str | None,
    ) -> Result[list[LearningChapter]]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        chapters_result = await self.list_chapters(content.learning_content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        chapters = chapters_result.value or []
        chapter_by_id = {chapter.chapter_id: chapter for chapter in chapters}
        if set(chapter_ids) != set(chapter_by_id):
            return Result.fail("[LEARNING_CHAPTER_REORDER_INVALID]")
        try:
            offset = len(chapters)
            for index, chapter in enumerate(chapters, start=1):
                chapter.order_index = offset + index
            await self._db.flush()
            for index, chapter_id in enumerate(chapter_ids, start=1):
                chapter = chapter_by_id[chapter_id]
                chapter.order_index = index
                chapter.updated_by = actor_id
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return await self.list_chapters(content.learning_content_id)

    async def publish_content(
        self, content: LearningContent, *, actor_id: str | None
    ) -> Result[LearningContent]:
        if content.status == "archived":
            return Result.fail("[LEARNING_CONTENT_NOT_EDITABLE]")
        chapters_result = await self.list_chapters(content.learning_content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        chapters = chapters_result.value or []
        decision = _publish_decision(content, chapters)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[LEARNING_CONTENT_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        content.status = "published"
        content.published_by = actor_id
        content.published_at = datetime.now(UTC)
        content.content_hash = _content_hash(content, chapters)
        content.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    def _editable_result(self, content: LearningContent) -> Result[None]:
        if content.status == "archived":
            return Result.fail("[LEARNING_CONTENT_NOT_EDITABLE]")
        return Result.ok(None)


async def serialize_learning_content(
    service: LearningContentService, content: LearningContent
) -> Result[LearningContentResponse]:
    chapters_result = await service.list_chapters(content.learning_content_id)
    if not chapters_result.is_success:
        return Result.fail(chapters_result.fallback or SERVER_ERROR)
    response = LearningContentResponse.model_validate(
        {
            "learning_content_id": content.learning_content_id,
            "title": content.title,
            "summary": content.summary,
            "owner": content.owner,
            "source": content.source,
            "status": content.status,
            "safety_flagged": bool(content.safety_flagged),
            "version": content.version,
            "content_hash": content.content_hash,
            "published_at": content.published_at,
            "created_at": content.created_at,
            "updated_at": content.updated_at,
            "chapters": [
                serialize_chapter(chapter) for chapter in (chapters_result.value or [])
            ],
        }
    )
    return Result.ok(response)


def serialize_chapter(chapter: LearningChapter) -> LearningChapterResponse:
    return LearningChapterResponse.model_validate(chapter)


def _publish_decision(
    content: LearningContent, chapters: list[LearningChapter]
) -> PublishGateDecision:
    results: list[GateResult] = []
    if not chapters:
        results.append(_gate("chapter_presence", "no_chapters", "LearningContent requires at least one chapter."))
    if any(not chapter.content.strip() for chapter in chapters):
        results.append(_gate("chapter_content", "empty_chapter_content", "Every chapter must contain content."))
    expected_order = list(range(1, len(chapters) + 1))
    actual_order = [chapter.order_index for chapter in chapters]
    if actual_order != expected_order:
        results.append(_gate("chapter_order", "non_contiguous_chapter_order", "Chapter order must be contiguous from 1."))
    if content.safety_flagged:
        results.append(_gate("content_safety", "security_flagged_content", "Security flagged content cannot be published."))
    return PublishGateDecision(can_publish=not results, results=results)


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )


def _content_hash(content: LearningContent, chapters: list[LearningChapter]) -> str:
    payload: dict[str, Any] = {
        "title": content.title,
        "summary": content.summary,
        "owner": content.owner,
        "source": content.source,
        "version": content.version,
        "chapters": [
            {
                "title": chapter.title,
                "content": chapter.content,
                "order_index": chapter.order_index,
            }
            for chapter in chapters
        ],
    }
    return "sha256:" + sha256(
        dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
