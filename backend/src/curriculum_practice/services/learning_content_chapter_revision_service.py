from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import LearningChapterCreate, LearningChapterUpdate
from curriculum_practice.services.learning_content_chapter_revision_payloads import (
    learning_content_revision_payload_from_chapter_create,
    learning_content_revision_payload_from_chapter_delete,
    learning_content_revision_payload_from_chapter_reorder,
    learning_content_revision_payload_from_chapter_update,
)
from curriculum_practice.services.learning_content_revision_payloads import (
    LEARNING_CONTENT_RESOURCE_TYPE,
    LEARNING_CONTENT_TARGET_TYPE,
    learning_content_change_class,
    learning_content_lifecycle_metadata,
    learning_content_lifecycle_snapshot,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    OperationLogService,
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)


class LearningContentChapterRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def stage_create_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        payload: LearningChapterCreate,
        *,
        chapter_id: str,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _snapshot_from_revision(active, content, chapters)
        next_snapshot = learning_content_revision_payload_from_chapter_create(
            content,
            chapters,
            payload,
            chapter_id=chapter_id,
        )
        return await self._save_chapter_revision(
            content,
            chapter_id=chapter_id,
            active=active,
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            actor=actor,
            reason="save new learning content chapter revision",
            trace_id=trace_id,
        )

    async def stage_update_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        chapter: LearningChapter,
        payload: LearningChapterUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _snapshot_from_revision(active, content, chapters)
        next_snapshot = learning_content_revision_payload_from_chapter_update(
            content,
            chapters,
            chapter,
            payload,
        )
        return await self._save_chapter_revision(
            content,
            chapter_id=str(chapter.chapter_id),
            active=active,
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            actor=actor,
            reason="save edited learning content chapter revision",
            trace_id=trace_id,
        )

    async def stage_delete_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        chapter: LearningChapter,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _snapshot_from_revision(active, content, chapters)
        next_snapshot = learning_content_revision_payload_from_chapter_delete(
            content,
            chapters,
            chapter,
        )
        return await self._save_chapter_revision(
            content,
            chapter_id=str(chapter.chapter_id),
            active=active,
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            actor=actor,
            reason="save deleted learning content chapter revision",
            trace_id=trace_id,
        )

    async def stage_reorder_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        chapter_ids: list[str],
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _snapshot_from_revision(active, content, chapters)
        next_snapshot = learning_content_revision_payload_from_chapter_reorder(
            content,
            chapters,
            chapter_ids,
        )
        return await self._save_chapter_revision(
            content,
            chapter_id="*",
            active=active,
            previous_snapshot=previous_snapshot,
            next_snapshot=next_snapshot,
            actor=actor,
            reason="save reordered learning content chapters revision",
            trace_id=trace_id,
        )

    async def _save_chapter_revision(
        self,
        content: LearningContent,
        *,
        chapter_id: str,
        active: SalesTrainerAssetRevision | None,
        previous_snapshot: dict[str, Any],
        next_snapshot: dict[str, Any],
        actor: User,
        reason: str,
        trace_id: str | None,
    ) -> SalesTrainerAssetRevision:
        revision = await self._revisions.save_working_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
            payload=next_snapshot,
            actor=actor,
            change_class=learning_content_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason=reason,
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="learning_content_chapter_revision_saved",
            target_type=LEARNING_CONTENT_TARGET_TYPE,
            target_id=str(content.learning_content_id),
            request_id=trace_id,
            metadata={
                **learning_content_lifecycle_metadata(
                    previous_snapshot,
                    next_snapshot,
                ),
                "chapter_id": chapter_id,
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    content: LearningContent,
    chapters: list[LearningChapter],
) -> dict[str, Any]:
    if revision is None:
        return learning_content_lifecycle_snapshot(content, chapters)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}
