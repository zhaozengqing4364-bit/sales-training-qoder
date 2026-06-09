from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import CaseItem
from curriculum_practice.schemas import CaseItemCreate
from curriculum_practice.services.content_asset_payloads import (
    apply_case_item_revision_payload,
    case_item_content_hash,
    case_item_lifecycle_snapshot,
    case_item_revision_payload_from_update,
    has_disclosure_phase,
)
from curriculum_practice.services.content_asset_revision_metadata import (
    CASE_ITEM_RESOURCE_TYPE,
    CASE_ITEM_TARGET_TYPE,
    case_item_change_class,
    case_item_lifecycle_metadata,
)
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService


class CaseItemRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def save_future_revision(
        self,
        item: CaseItem,
        payload: CaseItemCreate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
        )
        previous_snapshot = _snapshot_from_revision(active, item)
        next_snapshot = case_item_revision_payload_from_update(item, payload)
        revision = await self._revisions.save_working_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
            payload=next_snapshot,
            actor=actor,
            change_class=case_item_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited case item revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="case_item_revision_saved",
            target_type=CASE_ITEM_TARGET_TYPE,
            target_id=str(item.case_item_id),
            request_id=trace_id,
            metadata={
                **case_item_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision

    async def ensure_initial_published_revision(
        self,
        item: CaseItem,
        *,
        actor: User,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = case_item_lifecycle_snapshot(item)
        result = await self._revisions.create_published_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
            payload=next_snapshot,
            actor=actor,
            change_class="semantic",
            reason="initial case item publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="case_item_published",
            target_type=CASE_ITEM_TARGET_TYPE,
            target_id=str(item.case_item_id),
            request_id=trace_id,
            metadata={
                **case_item_lifecycle_metadata(next_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def publish_working_revision(
        self,
        item: CaseItem,
        *,
        actor: User,
    ) -> bool:
        working = await self._revisions.latest_working_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
        )
        if working is None:
            return False
        payload = _payload_dict(working.payload_json)
        if case_item_content_hash(payload) != payload.get("content_hash"):
            return False
        if not has_disclosure_phase(payload.get("allowed_disclosure_policy")):
            return False
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=CASE_ITEM_RESOURCE_TYPE,
            logical_id=str(item.case_item_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        apply_case_item_revision_payload(
            item,
            payload,
            actor_id=str(actor.user_id),
            published_at=datetime.now(UTC),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited case item revision",
            trace_id=trace_id,
        )
        next_snapshot = case_item_lifecycle_snapshot(item)
        await self._logs.record(
            actor=actor,
            action="case_item_revision_published",
            target_type=CASE_ITEM_TARGET_TYPE,
            target_id=str(item.case_item_id),
            request_id=trace_id,
            metadata={
                **case_item_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return True


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    item: CaseItem,
) -> dict[str, Any]:
    if revision is None:
        return case_item_lifecycle_snapshot(item)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}
