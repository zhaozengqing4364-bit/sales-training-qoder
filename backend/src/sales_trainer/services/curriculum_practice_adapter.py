from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import (
    LearningChapter as _LearningChapter,
)
from curriculum_practice.models import (
    LearningContent as _LearningContent,
)
from curriculum_practice.models import (
    QuestionItem as _QuestionItem,
)


class QuestionCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    parent_id: str | None = None
    description: str | None = None
    usage_scope: str = "general"
    order_index: int = 1


class QuestionCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    parent_id: str | None = None
    description: str | None = None
    usage_scope: str | None = None
    order_index: int | None = None


class QuestionItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str
    title: str
    stem: str
    reference_answer: str | None = None
    scoring_criteria: dict[str, Any] = Field(default_factory=dict)
    scoring_dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    usage_scope: str = "general"
    difficulty: str = "medium"
    safety_flagged: bool = False
    department: str | None = None


class QuestionItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str | None = None
    title: str | None = None
    stem: str | None = None
    reference_answer: str | None = None
    scoring_criteria: dict[str, Any] | None = None
    scoring_dimensions: list[str] | None = None
    tags: list[str] | None = None
    usage_scope: str | None = None
    difficulty: str | None = None
    safety_flagged: bool | None = None
    department: str | None = None


class QuestionCategory(Protocol):
    category_id: str
    parent_id: str | None
    name: str
    description: str | None
    usage_scope: str | None
    order_index: int
    created_at: datetime | None
    updated_at: datetime | None


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
    version: int | None
    content_hash: str | None
    published_at: datetime | None
    published_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    updated_by: str | None


class LearningContentContract(Protocol):
    learning_content_id: str
    status: str


@dataclass(slots=True)
class QuestionCategoryDTO:
    category_id: str
    parent_id: str | None
    name: str
    description: str | None
    usage_scope: str
    order_index: int
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(slots=True)
class QuestionItemDTO:
    question_id: str
    category_id: str
    title: str
    stem: str
    reference_answer: str | None
    scoring_criteria: dict[str, Any]
    scoring_dimensions: list[str]
    tags: list[str]
    usage_scope: str
    difficulty: str
    department: str | None
    safety_flagged: bool
    status: str
    version: int
    content_hash: str | None
    published_at: datetime | None
    published_by: str | None
    created_at: datetime | None
    updated_at: datetime | None
    updated_by: str | None


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


@dataclass(frozen=True, slots=True)
class LearningChapterCreate:
    title: str
    content: str
    order_index: int


@dataclass(frozen=True, slots=True)
class LearningProgressChapterRef:
    chapter_id: str


class LearningProgressAdapter:
    """Adapter boundary for curriculum learning progress operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._service = create_learning_progress_service(db)

    async def progress_for_user(
        self,
        *,
        user_id: str,
        content_id: str,
        chapters: Sequence[object],
    ) -> Any:
        return await self._service.progress_for_user(
            user_id=user_id,
            content_id=content_id,
            chapters=list(chapters),
        )

    async def study_content(self, *, user_id: str, content_id: str) -> Any:
        return await self._service.get_study_content(
            user_id=user_id,
            content_id=content_id,
        )

    async def complete_chapter(
        self,
        *,
        user_id: str,
        content_id: str,
        chapter_id: str,
    ) -> Any:
        return await self._service.complete_chapter(
            user_id=user_id,
            content_id=content_id,
            chapter_id=chapter_id,
        )


def create_test_bank_service(db: AsyncSession) -> Any:
    module = import_module("curriculum_practice.services.test_bank")
    return module.TestBankService(db)


def create_learning_progress_service(db: AsyncSession) -> Any:
    module = import_module("curriculum_practice.services.learning_progress_service")
    return module.LearningProgressService(db)


def project_question_category(category: QuestionCategory) -> QuestionCategoryDTO:
    return QuestionCategoryDTO(
        category_id=str(category.category_id),
        parent_id=_optional_str(category.parent_id),
        name=str(category.name),
        description=_optional_str(category.description),
        usage_scope=str(category.usage_scope or ""),
        order_index=int(category.order_index),
        created_at=_datetime_or_none(category.created_at),
        updated_at=_datetime_or_none(category.updated_at),
    )


def project_question_item(question: QuestionItem) -> QuestionItemDTO:
    return QuestionItemDTO(
        question_id=str(question.question_id),
        category_id=str(question.category_id),
        title=str(question.title),
        stem=str(question.stem),
        reference_answer=_optional_str(question.reference_answer),
        scoring_criteria=_dict_value(question.scoring_criteria),
        scoring_dimensions=_str_list(question.scoring_dimensions),
        tags=_str_list(question.tags),
        usage_scope=str(question.usage_scope or ""),
        difficulty=str(question.difficulty or "medium"),
        department=_optional_str(question.department),
        safety_flagged=bool(question.safety_flagged),
        status=str(question.status),
        version=int(question.version or 1),
        content_hash=_optional_str(question.content_hash),
        published_at=_datetime_or_none(question.published_at),
        published_by=_optional_str(question.published_by),
        created_at=_datetime_or_none(question.created_at),
        updated_at=_datetime_or_none(question.updated_at),
        updated_by=_optional_str(question.updated_by),
    )


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
        summary=_optional_str(content.summary),
        owner=_optional_str(content.owner),
        source=_optional_str(content.source),
        status=str(content.status),
    )


async def create_learning_content_with_chapters(
    db: AsyncSession,
    *,
    title: str,
    summary: str,
    owner: str,
    source: str,
    status: str,
    content_hash: str,
    actor_id: str,
    chapters: list[LearningChapterCreate],
) -> LearningContentContract:
    learning_content = _LearningContent(
        title=title,
        summary=summary,
        owner=owner,
        source=source,
        status=status,
        content_hash=content_hash,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(learning_content)
    await db.flush()
    db.add_all(
        [
            _LearningChapter(
                learning_content_id=learning_content.learning_content_id,
                title=chapter.title,
                content=chapter.content,
                order_index=chapter.order_index,
                created_by=actor_id,
                updated_by=actor_id,
            )
            for chapter in chapters
        ]
    )
    await db.flush()
    return cast(LearningContentContract, learning_content)


async def archive_draft_learning_content(
    db: AsyncSession,
    learning_content_id: str,
) -> bool:
    result = await db.execute(
        select(_LearningContent).where(
            _LearningContent.learning_content_id == learning_content_id
        )
    )
    content = result.scalar_one_or_none()
    if content is None or str(content.status) != "draft":
        return False
    setattr(content, "status", "archived")
    await db.flush()
    return True


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


async def get_learning_chapter_by_order(
    db: AsyncSession,
    learning_content_id: str,
    order_index: int,
) -> LearningChapterSummary | None:
    result = await db.execute(
        select(_LearningChapter)
        .where(
            _LearningChapter.learning_content_id == learning_content_id,
            _LearningChapter.order_index == order_index,
        )
        .limit(1)
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        return None
    return LearningChapterSummary(
        chapter_id=str(chapter.chapter_id),
        learning_content_id=str(chapter.learning_content_id),
        title=str(chapter.title),
        content=str(chapter.content),
        order_index=int(chapter.order_index),
    )


async def get_question_item(
    db: AsyncSession,
    question_id: str,
) -> QuestionItem | None:
    return cast(QuestionItem | None, await db.get(_QuestionItem, question_id))


async def list_published_sales_trainer_questions(
    db: AsyncSession,
) -> list[QuestionItem]:
    result = await db.execute(
        select(_QuestionItem)
        .where(
            _QuestionItem.status == "published",
            _QuestionItem.usage_scope == "sales_trainer",
            _QuestionItem.safety_flagged.is_(False),
        )
        .order_by(_QuestionItem.updated_at.desc())
    )
    return [cast(QuestionItem, question) for question in result.scalars().all()]


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _datetime_or_none(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _dict_value(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


__all__ = [
    "LearningChapterCreate",
    "LearningChapterSummary",
    "LearningContentContract",
    "LearningContentSummary",
    "LearningProgressAdapter",
    "LearningProgressChapterRef",
    "QuestionCategory",
    "QuestionCategoryCreate",
    "QuestionCategoryDTO",
    "QuestionCategoryUpdate",
    "QuestionItem",
    "QuestionItemCreate",
    "QuestionItemDTO",
    "QuestionItemUpdate",
    "archive_draft_learning_content",
    "create_learning_content_with_chapters",
    "create_learning_progress_service",
    "create_test_bank_service",
    "get_learning_chapter_by_order",
    "get_learning_content",
    "get_question_item",
    "list_learning_chapters",
    "list_published_sales_trainer_questions",
    "project_question_category",
    "project_question_item",
]
