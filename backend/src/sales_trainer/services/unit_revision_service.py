from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.schemas import SalesTrainerUnitUpdate
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
    snapshot_from_revision,
)
from sales_trainer.services.unit_revision_management import (
    UnitRevisionManagementError,
    UnitRevisionManagementService,
)
from sales_trainer.services.unit_revision_payloads import (
    UNIT_RESOURCE_TYPE,
    payload_dict,
    unit_change_class,
    unit_revision_payload_from_update,
)


class UnitRevisionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnitRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._payloads = UnitRevisionPayloadApplicator(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def save_future_revision(
        self,
        unit: SalesTrainerUnit,
        current_questions: list[Any],
        payload: SalesTrainerUnitUpdate,
        *,
        actor: User,
    ) -> SalesTrainerUnit:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=UNIT_RESOURCE_TYPE,
            logical_id=str(unit.unit_id),
        )
        previous_snapshot = snapshot_from_revision(active, unit, current_questions)
        next_snapshot = unit_revision_payload_from_update(
            unit,
            current_questions,
            payload,
        )
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=UNIT_RESOURCE_TYPE,
                logical_id=str(unit.unit_id),
                payload=next_snapshot,
                actor=actor,
                change_class=unit_change_class(previous_snapshot, next_snapshot),
                source_revision_id=str(active.revision_id) if active is not None else None,
                reason="save edited unit revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise UnitRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="unit_revision_saved",
            target_type="sales_trainer_unit",
            target_id=str(unit.unit_id),
            request_id=trace_id,
            metadata={
                **unit_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def latest_working_revision(
        self,
        unit_id: str,
    ) -> SalesTrainerAssetRevision | None:
        return await self._revisions.latest_working_revision(
            resource_type=UNIT_RESOURCE_TYPE,
            logical_id=unit_id,
        )

    async def list_revisions(self, unit_id: str) -> list[dict[str, Any]]:
        return await UnitRevisionManagementService(self._db).list_revisions(unit_id)

    async def rollback_to_revision(
        self,
        unit: SalesTrainerUnit,
        *,
        target_revision_id: str,
        reason: str,
        actor: User,
    ) -> SalesTrainerUnit:
        try:
            return await UnitRevisionManagementService(self._db).rollback_to_revision(
                unit,
                target_revision_id=target_revision_id,
                reason=reason,
                actor=actor,
            )
        except UnitRevisionManagementError as exc:
            raise UnitRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

    async def publish_working_revision(
        self,
        unit: SalesTrainerUnit,
        revision: SalesTrainerAssetRevision,
        *,
        actor: User,
    ) -> SalesTrainerUnit:
        trace_id = get_trace_id()
        previous_snapshot = unit_lifecycle_snapshot(
            unit,
            await self._payloads.unit_questions(str(unit.unit_id)),
        )
        revision_payload = payload_dict(revision.payload_json)
        await self._payloads.apply(
            unit,
            revision_payload,
            actor_id=str(actor.user_id),
        )
        try:
            publish_result = await self._revisions.publish_working_revision(
                revision,
                actor=actor,
                reason="publish edited unit revision",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise UnitRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="unit_revision_published",
            target_type="sales_trainer_unit",
            target_id=str(unit.unit_id),
            request_id=trace_id,
            metadata={
                **unit_lifecycle_metadata(previous_snapshot, revision_payload),
                "before_revision_id": publish_result.previous_revision_id,
                "after_revision_id": revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(unit)
        return unit

    async def create_initial_published_revision(
        self,
        unit: SalesTrainerUnit,
        questions: list[Any],
        *,
        actor: User,
        previous_snapshot: dict[str, Any],
    ) -> None:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=UNIT_RESOURCE_TYPE,
            logical_id=str(unit.unit_id),
        )
        if active is not None:
            return
        next_snapshot = unit_lifecycle_snapshot(unit, questions)
        try:
            publish_result = await self._revisions.create_published_revision(
                resource_type=UNIT_RESOURCE_TYPE,
                logical_id=str(unit.unit_id),
                payload=next_snapshot,
                actor=actor,
                change_class="scoring_high_risk",
                reason="initial unit publish",
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise UnitRevisionServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await self._logs.record(
            actor=actor,
            action="unit_published",
            target_type="sales_trainer_unit",
            target_id=str(unit.unit_id),
            request_id=trace_id,
            metadata={
                **unit_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": publish_result.previous_revision_id,
                "after_revision_id": publish_result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
