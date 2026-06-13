from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import (
    LearningChapter as _LearningChapter,
)
from curriculum_practice.models import (
    LearningContent as _LearningContent,
)
from curriculum_practice.schemas import (
    QuestionCategoryCreate,
    QuestionCategoryUpdate,
    QuestionItemCreate,
    QuestionItemUpdate,
)


class QuestionCategory(Protocol):
    category_id: str
    name: str
    usage_scope: str | None


class QuestionItem(Protocol):
    question_id: str
    category_id: str
    title: str
    stem: str
    reference_answer: str | None
    scoring_criteria: dict[str, Any] | None
    scoring_dimensions: list[str] | None
    tags: list[str] | None
    usage_scope: str | None
    difficulty: str | None
    department: str | None
    safety_flagged: bool
    status: str


@dataclass(frozen=True, slots=True)
class LearningContentSummary:
    learning_content_id: str
    title: str
    summary: str | None
    owner: str | None
    source: str | None
    status: str


@dataclass(frozen=True, slots=True)
class LearningChapterSummary:
    chapter_id: str
    learning_content_id: str
    title: str
    content: str
    order_index: int


async def get_learning_content(
    db: AsyncSession,
    learning_content_id: str,
) -> LearningContentSummary | None:
    content = await db.get(_LearningContent, learning_content_id)
    if content is None:
        return None
    return LearningContentSummary(
        learning_content_id=str(content.learning_content_id),
        title=str(content.title),
        summary=content.summary,
        owner=content.owner,
        source=content.source,
        status=str(content.status),
    )


async def list_learning_chapters(
    db: AsyncSession,
    learning_content_id: str,
) -> list[LearningChapterSummary]:
    result = await db.execute(
        select(_LearningChapter)
        .where(_LearningChapter.learning_content_id == learning_content_id)
        .order_by(_LearningChapter.order_index.asc())
    )
    return [
        LearningChapterSummary(
            chapter_id=str(chapter.chapter_id),
            learning_content_id=str(chapter.learning_content_id),
            title=str(chapter.title),
            content=str(chapter.content),
            order_index=int(chapter.order_index),
        )
        for chapter in result.scalars().all()
    ]


__all__ = [
    "LearningChapterSummary",
    "LearningContentSummary",
    "QuestionCategoryCreate",
    "QuestionCategoryUpdate",
    "QuestionItemCreate",
    "QuestionItemUpdate",
    "get_learning_content",
    "list_learning_chapters",
]
