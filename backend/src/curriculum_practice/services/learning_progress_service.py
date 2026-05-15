from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    LearningProgress,
)
from curriculum_practice.schemas import (
    ChapterCompleteResponse,
    LearnerStudyContentResponse,
    LearningChapterResponse,
    LearningProgressResponse,
)

SERVER_ERROR = "[LEARNING_PROGRESS_SERVICE_FAILED]"


class LearningProgressService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_study_content(
        self, *, user_id: str, content_id: str
    ) -> Result[LearnerStudyContentResponse]:
        content_result = await self._published_content(content_id)
        if not content_result.is_success or content_result.value is None:
            return Result.fail(content_result.fallback or "[LEARNING_CONTENT_NOT_FOUND]")
        chapters_result = await self._chapters(content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        progress_result = await self.progress_for_user(
            user_id=user_id,
            content_id=content_id,
            chapters=chapters_result.value or [],
        )
        if not progress_result.is_success or progress_result.value is None:
            return Result.fail(progress_result.fallback or SERVER_ERROR)
        content = content_result.value
        return Result.ok(
            LearnerStudyContentResponse(
                learning_content_id=content.learning_content_id,
                title=content.title,
                summary=content.summary,
                owner=content.owner,
                source=content.source,
                chapters=[
                    LearningChapterResponse.model_validate(chapter)
                    for chapter in (chapters_result.value or [])
                ],
                progress=progress_result.value,
            )
        )

    async def complete_chapter(
        self, *, user_id: str, content_id: str, chapter_id: str
    ) -> Result[ChapterCompleteResponse]:
        content_result = await self._published_content(content_id)
        if not content_result.is_success:
            return Result.fail(content_result.fallback or "[LEARNING_CONTENT_NOT_FOUND]")
        chapter_result = await self._chapter(content_id=content_id, chapter_id=chapter_id)
        if not chapter_result.is_success:
            return Result.fail(chapter_result.fallback or "[LEARNING_CHAPTER_NOT_FOUND]")

        existing_result = await self._existing_progress(
            user_id=user_id, content_id=content_id, chapter_id=chapter_id
        )
        if not existing_result.is_success:
            return Result.fail(existing_result.fallback or SERVER_ERROR)
        already_completed = existing_result.value is not None
        if not already_completed:
            self._db.add(
                LearningProgress(
                    user_id=user_id,
                    learning_content_id=content_id,
                    chapter_id=chapter_id,
                )
            )
            try:
                await self._db.commit()
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)

        chapters_result = await self._chapters(content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        progress_result = await self.progress_for_user(
            user_id=user_id,
            content_id=content_id,
            chapters=chapters_result.value or [],
        )
        if not progress_result.is_success or progress_result.value is None:
            return Result.fail(progress_result.fallback or SERVER_ERROR)
        return Result.ok(
            ChapterCompleteResponse(
                chapter_id=chapter_id,
                already_completed=already_completed,
                progress=progress_result.value,
            )
        )

    async def progress_for_user(
        self,
        *,
        user_id: str,
        content_id: str,
        chapters: list[LearningChapter],
    ) -> Result[LearningProgressResponse]:
        try:
            result = await self._db.execute(
                select(LearningProgress.chapter_id).where(
                    LearningProgress.user_id == user_id,
                    LearningProgress.learning_content_id == content_id,
                )
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        known_chapter_ids = [chapter.chapter_id for chapter in chapters]
        completed_ids = set(result.scalars().all())
        completed = [chapter_id for chapter_id in known_chapter_ids if chapter_id in completed_ids]
        total = len(chapters)
        is_completed = total > 0 and len(completed) == total
        state = "completed" if is_completed else "in_progress" if completed else "not_started"
        return Result.ok(
            LearningProgressResponse(
                completed_chapter_ids=completed,
                completed_count=len(completed),
                total_chapters=total,
                is_completed=is_completed,
                state=state,
                primary_cta="start exam" if is_completed else "continue learning",
            )
        )

    async def first_published_content_progress(
        self, *, user_id: str
    ) -> Result[tuple[LearningContent, LearningProgressResponse] | None]:
        try:
            result = await self._db.execute(
                select(LearningContent)
                .where(LearningContent.status == "published")
                .order_by(LearningContent.updated_at.desc())
                .limit(1)
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        content = result.scalar_one_or_none()
        if content is None:
            return Result.ok(None)
        chapters_result = await self._chapters(content.learning_content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        if not chapters_result.value:
            return Result.ok(None)
        progress_result = await self.progress_for_user(
            user_id=user_id,
            content_id=content.learning_content_id,
            chapters=chapters_result.value,
        )
        if not progress_result.is_success or progress_result.value is None:
            return Result.fail(progress_result.fallback or SERVER_ERROR)
        return Result.ok((content, progress_result.value))

    async def _published_content(self, content_id: str) -> Result[LearningContent]:
        try:
            content = await self._db.get(LearningContent, content_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if content is None or content.status != "published":
            return Result.fail("[LEARNING_CONTENT_NOT_FOUND]")
        return Result.ok(content)

    async def _chapters(self, content_id: str) -> Result[list[LearningChapter]]:
        try:
            result = await self._db.execute(
                select(LearningChapter)
                .where(LearningChapter.learning_content_id == content_id)
                .order_by(LearningChapter.order_index.asc())
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def _chapter(self, *, content_id: str, chapter_id: str) -> Result[LearningChapter]:
        try:
            chapter = await self._db.get(LearningChapter, chapter_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if chapter is None or chapter.learning_content_id != content_id:
            return Result.fail("[LEARNING_CHAPTER_NOT_FOUND]")
        return Result.ok(chapter)

    async def _existing_progress(
        self, *, user_id: str, content_id: str, chapter_id: str
    ) -> Result[LearningProgress | None]:
        try:
            result = await self._db.execute(
                select(LearningProgress).where(
                    LearningProgress.user_id == user_id,
                    LearningProgress.learning_content_id == content_id,
                    LearningProgress.chapter_id == chapter_id,
                )
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(result.scalar_one_or_none())


async def count_completed_chapters(
    db: AsyncSession, *, user_id: str, content_id: str
) -> Result[int]:
    try:
        result = await db.execute(
            select(func.count()).select_from(LearningProgress).where(
                LearningProgress.user_id == user_id,
                LearningProgress.learning_content_id == content_id,
            )
        )
    except SQLAlchemyError:
        return Result.fail(SERVER_ERROR)
    return Result.ok(int(result.scalar_one()))
