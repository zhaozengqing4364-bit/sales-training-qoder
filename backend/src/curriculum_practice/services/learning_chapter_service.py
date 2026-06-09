from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import (
    LearningChapterCreate,
    LearningChapterUpdate,
)
from curriculum_practice.services.learning_content_chapter_revision_service import (
    LearningContentChapterRevisionService,
)

SERVER_ERROR = "[LEARNING_CONTENT_SERVICE_FAILED]"


class LearningChapterServiceMixin:
    _db: AsyncSession

    def _editable_result(self, content: LearningContent) -> Result[None]:
        if content.status == "archived":
            return Result.fail("[LEARNING_CONTENT_NOT_EDITABLE]")
        return Result.ok(None)

    async def _actor_result(self, actor_id: str | None) -> Result[User]:
        raise NotImplementedError

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
        if content.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
            chapters_result = await self.list_chapters(content.learning_content_id)
            if not chapters_result.is_success:
                return Result.fail(chapters_result.fallback or SERVER_ERROR)
            chapter = LearningChapter(
                chapter_id=str(uuid.uuid4()),
                learning_content_id=content.learning_content_id,
                title=payload.title,
                content=payload.content,
                order_index=order_index,
                created_by=actor_id,
                updated_by=actor_id,
            )
            try:
                await LearningContentChapterRevisionService(
                    self._db
                ).stage_create_revision(
                    content,
                    chapters_result.value or [],
                    payload,
                    chapter_id=str(chapter.chapter_id),
                    actor=actor_result.value,
                )
                await self._db.commit()
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
            return Result.ok(chapter)
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
        if content.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
            chapters_result = await self.list_chapters(content.learning_content_id)
            if not chapters_result.is_success:
                return Result.fail(chapters_result.fallback or SERVER_ERROR)
            try:
                await LearningContentChapterRevisionService(
                    self._db
                ).stage_update_revision(
                    content,
                    chapters_result.value or [],
                    chapter,
                    payload,
                    actor=actor_result.value,
                )
                await self._db.commit()
                await self._db.refresh(chapter)
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
            return Result.ok(chapter)
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
        self,
        content: LearningContent,
        chapter: LearningChapter,
        *,
        actor_id: str | None,
    ) -> Result[None]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        if content.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
            chapters_result = await self.list_chapters(content.learning_content_id)
            if not chapters_result.is_success:
                return Result.fail(chapters_result.fallback or SERVER_ERROR)
            try:
                await LearningContentChapterRevisionService(
                    self._db
                ).stage_delete_revision(
                    content,
                    chapters_result.value or [],
                    chapter,
                    actor=actor_result.value,
                )
                await self._db.commit()
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
            return Result.ok(None)
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
        if content.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
            try:
                await LearningContentChapterRevisionService(
                    self._db
                ).stage_reorder_revision(
                    content,
                    chapters,
                    chapter_ids,
                    actor=actor_result.value,
                )
                await self._db.commit()
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
            return Result.ok(chapters)
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
