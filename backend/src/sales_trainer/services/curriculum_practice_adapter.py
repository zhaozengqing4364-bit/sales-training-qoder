from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import VoiceRuntimeProfile
from common.db.models import ScoringRuleset
from curriculum_practice.models import (
    CaseItem as _CaseItem,
)
from curriculum_practice.models import (
    LearningChapter as _LearningChapter,
)
from curriculum_practice.models import (
    LearningContent as _LearningContent,
)
from curriculum_practice.models import PracticeTemplate as _PracticeTemplate
from curriculum_practice.models import (
    QuestionItem as _QuestionItem,
)
from curriculum_practice.models import RoleProfile as _RoleProfile
from curriculum_practice.services.asset_reference_reader import (
    CurriculumAssetReferenceReader,
)
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.practice_template_revision_metadata import (
    PRACTICE_TEMPLATE_RESOURCE_TYPE,
    template_payload_hash,
)
from curriculum_practice.services.practice_template_revision_payloads import (
    template_lifecycle_snapshot,
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


@dataclass(frozen=True, slots=True)
class RealtimeBindingAssetSnapshot:
    template_status: str
    template_version: int
    template_name: str | None
    template_description: str | None
    template_runtime_profile_id: str | None
    case_status: str | None
    case_company_profile: str | None
    case_success_criteria: tuple[object, ...]
    role_status: str | None
    role_name: str | None
    role_communication_style: str | None
    ruleset_status: str | None
    ruleset_display_name: str | None
    ruleset_description: str | None
    ruleset_version: str | None
    ruleset_definition: dict[str, object]
    runtime_is_active: bool
    runtime_voice_mode: str | None
    template_content_hash: str
    runtime_reference_hash: str
    governed_assets_hash: str


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


async def published_learning_content_ids(
    db: AsyncSession, values: set[str]
) -> set[str]:
    if not values:
        return set()
    rows = await db.execute(
        select(_LearningContent.learning_content_id)
        .join(
            _LearningChapter,
            _LearningChapter.learning_content_id
            == _LearningContent.learning_content_id,
        )
        .where(
            _LearningContent.learning_content_id.in_(values),
            _LearningContent.status == "published",
        )
        .group_by(_LearningContent.learning_content_id)
    )
    return {str(value) for value in rows.scalars()}


async def published_practice_template_ids(
    db: AsyncSession, values: set[str]
) -> set[str]:
    if not values:
        return set()
    rows = await db.scalars(
        select(_PracticeTemplate.template_id).where(
            _PracticeTemplate.template_id.in_(values),
            _PracticeTemplate.status == "published",
        )
    )
    return {str(value) for value in rows}


async def get_practice_template(db: AsyncSession, template_id: str) -> Any:
    return await db.get(_PracticeTemplate, template_id)


def practice_template_resource_type() -> str:
    return PRACTICE_TEMPLATE_RESOURCE_TYPE


async def get_realtime_binding_asset_snapshot(
    db: AsyncSession,
    template_id: str,
) -> RealtimeBindingAssetSnapshot | None:
    result = await db.execute(
        select(
            _PracticeTemplate,
            _CaseItem,
            _RoleProfile,
            ScoringRuleset,
            VoiceRuntimeProfile,
        )
        .outerjoin(
            _CaseItem,
            _CaseItem.case_item_id == _PracticeTemplate.case_item_id,
        )
        .outerjoin(
            _RoleProfile,
            _RoleProfile.role_profile_id == _PracticeTemplate.role_profile_id,
        )
        .outerjoin(
            ScoringRuleset,
            ScoringRuleset.ruleset_id == _PracticeTemplate.scoring_ruleset_id,
        )
        .outerjoin(
            VoiceRuntimeProfile,
            VoiceRuntimeProfile.id == _PracticeTemplate.runtime_profile_id,
        )
        .where(_PracticeTemplate.template_id == template_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    template, case_item, role_profile, ruleset, runtime = row
    reader = CurriculumAssetReferenceReader(db)
    runtime_reference = await reader.read_reference(
        "voice_runtime_profile",
        str(template.runtime_profile_id),
    )
    refs: list[tuple[str, str]] = [
        ("agent", str(template.agent_id)),
        ("persona", str(template.persona_id)),
        ("voice_runtime_profile", str(template.runtime_profile_id)),
        ("scoring_ruleset", str(template.scoring_ruleset_id)),
    ]
    for asset_type, asset_id in (
        ("case_item", template.case_item_id),
        ("role_profile", template.role_profile_id),
        ("learning_content", template.learning_content_id),
        ("examiner_agent", template.examiner_agent_id),
    ):
        if asset_id:
            refs.append((asset_type, str(asset_id)))
    refs.extend(
        ("knowledge_base", str(asset_id))
        for asset_id in template.knowledge_base_refs or []
    )
    governed_assets = {
        f"{asset_type}:{asset_id}": await reader.read_reference(asset_type, asset_id)
        for asset_type, asset_id in refs
    }
    definition = (
        dict(ruleset.definition_json)
        if ruleset is not None and isinstance(ruleset.definition_json, dict)
        else {}
    )
    return RealtimeBindingAssetSnapshot(
        template_status=str(template.status),
        template_version=int(template.version or 0),
        template_name=_optional_str(template.name),
        template_description=_optional_str(template.description),
        template_runtime_profile_id=_optional_str(template.runtime_profile_id),
        case_status=_optional_str(case_item.status) if case_item is not None else None,
        case_company_profile=(
            _optional_str(case_item.company_profile) if case_item is not None else None
        ),
        case_success_criteria=tuple(case_item.success_criteria or ())
        if case_item is not None
        else (),
        role_status=(
            _optional_str(role_profile.status) if role_profile is not None else None
        ),
        role_name=(
            _optional_str(role_profile.role_name) if role_profile is not None else None
        ),
        role_communication_style=(
            _optional_str(role_profile.communication_style)
            if role_profile is not None
            else None
        ),
        ruleset_status=_optional_str(ruleset.status) if ruleset is not None else None,
        ruleset_display_name=(
            _optional_str(ruleset.display_name) if ruleset is not None else None
        ),
        ruleset_description=(
            _optional_str(ruleset.description) if ruleset is not None else None
        ),
        ruleset_version=_optional_str(ruleset.version) if ruleset is not None else None,
        ruleset_definition=definition,
        runtime_is_active=bool(runtime.is_active) if runtime is not None else False,
        runtime_voice_mode=(
            _optional_str(runtime.voice_mode) if runtime is not None else None
        ),
        template_content_hash=template_payload_hash(
            template_lifecycle_snapshot(template)
        ),
        runtime_reference_hash=stable_hash(runtime_reference or {}),
        governed_assets_hash=stable_hash(governed_assets),
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
    "RealtimeBindingAssetSnapshot",
    "archive_draft_learning_content",
    "create_learning_content_with_chapters",
    "create_learning_progress_service",
    "create_test_bank_service",
    "get_learning_chapter_by_order",
    "get_learning_content",
    "get_question_item",
    "get_realtime_binding_asset_snapshot",
    "list_learning_chapters",
    "list_published_sales_trainer_questions",
    "project_question_category",
    "project_question_item",
    "practice_template_resource_type",
]
