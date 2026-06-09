from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audit_metadata import (
    unit_lifecycle_metadata,
    unit_lifecycle_snapshot,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_revision_application import (
    UnitRevisionPayloadApplicator,
)
from sales_trainer.services.unit_revision_payloads import (
    UNIT_RESOURCE_TYPE,
    payload_dict,
)


class UnitRevisionManagementService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._payloads = UnitRevisionPayloadApplicator(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def list_revisions(self, unit_id: str) -> list[dict[str, Any]]:
        active_revision = await self._revisions.active_revision(
            resource_type=UNIT_RESOURCE_TYPE,
            logical_id=unit_id,
        )
        revisions = await self._revisions.list_revisions(
            resource_type=UNIT_RESOURCE_TYPE,
            logical_id=unit_id,
        )
        active_revision_id = (
            str(active_revision.revision_id) if active_revision is not None else None
        )
        return [
            _unit_revision_response_item(
                revision,
                active_revision_id=active_revision_id,
            )
            for revision in revisions
        ]

    async def rollback_to_revision(
        self,
        unit: SalesTrainerUnit,
        *,
        target_revision_id: str,
        reason: str,
        actor: User,
    ) -> SalesTrainerUnit:
        trace_id = get_trace_id()
        if unit.status == "archived":
            raise UnitRevisionManagementError(
                "[SALES_TRAINER_UNIT_ARCHIVED]",
                "已归档训练单元不能回滚，请先恢复归档状态。",
                409,
            )
        previous_snapshot = unit_lifecycle_snapshot(
            unit,
            await self._payloads.unit_questions(str(unit.unit_id)),
        )
        target_revision = await self._revisions.revision_by_id(target_revision_id)
        if (
            target_revision is None
            or target_revision.resource_type != UNIT_RESOURCE_TYPE
            or target_revision.logical_id != str(unit.unit_id)
        ):
            raise UnitRevisionManagementError(
                "[UNIT_REVISION_NOT_FOUND]",
                "目标训练单元修订不存在或不属于当前训练单元。",
                404,
            )
        try:
            rollback_result = await self._revisions.rollback_to_revision(
                target_revision,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise UnitRevisionManagementError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        target_payload = payload_dict(target_revision.payload_json)
        await self._payloads.apply(
            unit,
            target_payload,
            actor_id=str(actor.user_id),
        )
        await self._logs.record(
            actor=actor,
            action="unit_revision_rolled_back",
            target_type="sales_trainer_unit",
            target_id=str(unit.unit_id),
            request_id=trace_id,
            metadata={
                **unit_lifecycle_metadata(previous_snapshot, target_payload),
                "before_revision_id": rollback_result.previous_revision_id,
                "after_revision_id": target_revision.revision_id,
                "reason": reason,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit


class UnitRevisionManagementError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _unit_revision_response_item(
    revision: SalesTrainerAssetRevision,
    *,
    active_revision_id: str | None,
) -> dict[str, Any]:
    payload = payload_dict(revision.payload_json)
    questions = payload.get("questions")
    question_count = len(questions) if isinstance(questions, list) else 0
    revision_id = str(revision.revision_id)
    status = str(revision.status)
    title = payload.get("name")
    return {
        "revision_id": revision_id,
        "revision_no": int(revision.revision_no),
        "status": status,
        "change_class": str(revision.change_class),
        "title": title if isinstance(title, str) else None,
        "question_count": question_count,
        "is_active": revision_id == active_revision_id,
        "is_working": status == "working",
        "source_revision_id": revision.source_revision_id,
        "payload_hash": str(revision.payload_hash),
        "reason": revision.reason,
        "trace_id": revision.trace_id,
        "created_by": revision.created_by,
        "published_by": revision.published_by,
        "created_at": revision.created_at,
        "published_at": revision.published_at,
    }
