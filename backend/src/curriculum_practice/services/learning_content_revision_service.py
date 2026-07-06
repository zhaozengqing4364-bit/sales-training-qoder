from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import LearningChapter, LearningContent
from curriculum_practice.schemas import LearningContentUpdate, PublishGateDecision
from curriculum_practice.services.learning_content_revision_apply import (
    LearningContentRevisionApplier,
)
from curriculum_practice.services.learning_content_revision_payloads import (
    LEARNING_CONTENT_RESOURCE_TYPE,
    LEARNING_CONTENT_TARGET_TYPE,
    apply_learning_content_revision_payload,
    learning_content_change_class,
    learning_content_lifecycle_metadata,
    learning_content_lifecycle_snapshot,
    learning_content_publish_decision_from_payload,
    learning_content_revision_payload_from_update,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    OperationLogService,
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)


class LearningContentRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def stage_future_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        payload: LearningContentUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _snapshot_from_revision(active, content, chapters)
        next_snapshot = learning_content_revision_payload_from_update(
            content,
            chapters,
            payload,
        )
        revision = await self._revisions.save_working_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
            payload=next_snapshot,
            actor=actor,
            change_class=learning_content_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited learning content revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="learning_content_revision_saved",
            target_type=LEARNING_CONTENT_TARGET_TYPE,
            target_id=str(content.learning_content_id),
            request_id=trace_id,
            metadata={
                **learning_content_lifecycle_metadata(
                    previous_snapshot,
                    next_snapshot,
                ),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision

    async def stage_initial_published_revision(
        self,
        content: LearningContent,
        chapters: list[LearningChapter],
        *,
        actor: User,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = learning_content_lifecycle_snapshot(content, chapters)
        result = await self._revisions.create_published_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
            payload=next_snapshot,
            actor=actor,
            change_class="semantic",
            reason="initial learning content publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="learning_content_published",
            target_type=LEARNING_CONTENT_TARGET_TYPE,
            target_id=str(content.learning_content_id),
            request_id=trace_id,
            metadata={
                **learning_content_lifecycle_metadata(
                    next_snapshot,
                    next_snapshot,
                ),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def stage_publish_working_revision(
        self,
        content: LearningContent,
        *,
        actor: User,
    ) -> Result[bool | PublishGateDecision]:
        working = await self._revisions.latest_working_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        if working is None:
            return Result.ok(False)
        payload = _payload_dict(working.payload_json)
        decision = learning_content_publish_decision_from_payload(payload)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[LEARNING_CONTENT_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=LEARNING_CONTENT_RESOURCE_TYPE,
            logical_id=str(content.learning_content_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        apply_learning_content_revision_payload(
            content,
            payload,
            actor_id=str(actor.user_id),
            revision_no=int(working.revision_no),
            published_at=datetime.now(UTC),
        )
        await LearningContentRevisionApplier(self._db).apply_chapters_from_payload(
            content,
            payload,
            actor_id=str(actor.user_id),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited learning content revision",
            trace_id=trace_id,
        )
        next_snapshot = payload | {"version": content.version}
        await self._logs.record(
            actor=actor,
            action="learning_content_revision_published",
            target_type=LEARNING_CONTENT_TARGET_TYPE,
            target_id=str(content.learning_content_id),
            request_id=trace_id,
            metadata={
                **learning_content_lifecycle_metadata(
                    previous_snapshot,
                    next_snapshot,
                ),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return Result.ok(True)


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
