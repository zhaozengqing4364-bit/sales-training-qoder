from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import (
    LearningChapterResponse,
    LearningContentResponse,
    LearningContentSummaryResponse,
)
from curriculum_practice.services.learning_content_revision_state import (
    learning_content_revision_state,
)
from curriculum_practice.services.orm_payload_typing import orm_str

SERVER_ERROR = "[LEARNING_CONTENT_SERVICE_FAILED]"


class LearningChapterReader(Protocol):
    async def list_chapters(
        self,
        content_id: str,
    ) -> Result[list[LearningChapter]]: ...

    @property
    def db(self) -> AsyncSession: ...


async def serialize_learning_content(
    service: LearningChapterReader,
    content: LearningContent,
) -> Result[LearningContentResponse]:
    chapters_result = await service.list_chapters(orm_str(content.learning_content_id))
    if not chapters_result.is_success:
        return Result.fail(chapters_result.fallback or SERVER_ERROR)
    revision_state = await learning_content_revision_state(
        service.db,
        content,
    )
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
            "revision_state": revision_state,
        }
    )
    return Result.ok(response)


def serialize_learning_content_summary(
    content: LearningContent,
) -> LearningContentSummaryResponse:
    return LearningContentSummaryResponse.model_validate(content)


def serialize_chapter(chapter: LearningChapter) -> LearningChapterResponse:
    return LearningChapterResponse.model_validate(chapter)
