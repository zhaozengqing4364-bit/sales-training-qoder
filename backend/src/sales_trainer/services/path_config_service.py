from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.schemas import (
    NewcomerPathConfigPayload,
    NewcomerPathConfigSaveRequest,
)
from sales_trainer.services.asset_revision_service import (
    AssetPublishResult,
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    PathProjection,
    PathUnitProjection,
    SalesTrainerPathConfigError,
    classify_change,
    module_from_unit,
    path_config_from_module,
    payload_from_revision,
    revision_summary,
)
from sales_trainer.services.path_config_operations import (
    get_path_revision,
    load_published_path_units,
    record_path_config_event,
    units_by_id,
)


class SalesTrainerPathConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)

    async def get_config(self) -> dict[str, Any]:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        source: Literal["active_revision", "unit_backfill"] = "active_revision"
        if active is None:
            path = await self._backfill_payload()
            source = "unit_backfill"
        else:
            path = payload_from_revision(active)
        return {
            "source": source,
            "path": path.model_dump(mode="json"),
            "active_revision_id": str(active.revision_id) if active else None,
            "active_revision_no": active.revision_no if active else None,
            "working_revision_id": str(working.revision_id) if working else None,
            "working_revision_no": working.revision_no if working else None,
            "has_unpublished_revision": working is not None,
        }

    async def active_projection(self) -> PathProjection | None:
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        if active is None:
            return None
        payload = payload_from_revision(active)
        items = await self._projection_items(payload)
        return PathProjection(
            source="active_revision",
            path_key=payload.path_key,
            revision_id=str(active.revision_id),
            revision_no=int(active.revision_no),
            items=tuple(items),
        )

    async def save_config(
        self,
        payload: NewcomerPathConfigSaveRequest,
        *,
        actor: User,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        path_payload = NewcomerPathConfigPayload.model_validate(
            payload.model_dump(mode="json", exclude={"reason"})
        )
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        change_class = classify_change(active, path_payload)
        try:
            revision = await self._revisions.save_working_revision(
                resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                logical_id=NEWCOMER_PATH_LOGICAL_ID,
                payload=path_payload.model_dump(mode="json"),
                actor=actor,
                change_class=change_class,
                source_revision_id=str(active.revision_id) if active else None,
                reason=payload.reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.save_working",
            after_revision_id=str(revision.revision_id),
            before_revision_id=str(active.revision_id) if active else None,
            reason=payload.reason,
            trace_id=trace_id,
            change_class=change_class,
        )
        await self._db.commit()
        return revision

    async def publish_config(
        self,
        *,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        working = await self._revisions.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        try:
            if working is None:
                result = await self._revisions.create_published_revision(
                    resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
                    logical_id=NEWCOMER_PATH_LOGICAL_ID,
                    payload=(await self._backfill_payload()).model_dump(mode="json"),
                    actor=actor,
                    change_class="binding",
                    reason=reason,
                    trace_id=trace_id,
                )
            else:
                result = await self._revisions.publish_working_revision(
                    working,
                    actor=actor,
                    reason=reason,
                    trace_id=trace_id,
                )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.publish",
            after_revision_id=str(result.revision.revision_id),
            before_revision_id=result.previous_revision_id,
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def rollback_config(
        self,
        *,
        revision_id: str,
        actor: User,
        reason: str,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        revision = await get_path_revision(self._revisions, revision_id)
        try:
            result = await self._revisions.rollback_to_revision(
                revision,
                actor=actor,
                reason=reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise SalesTrainerPathConfigError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc
        await record_path_config_event(
            self._logs,
            actor=actor,
            action="newcomer_path_config.rollback",
            after_revision_id=str(result.revision.revision_id),
            before_revision_id=result.previous_revision_id,
            reason=reason,
            trace_id=trace_id,
            change_class=str(result.revision.change_class),
        )
        await self._db.commit()
        return result

    async def list_revisions(self) -> list[dict[str, Any]]:
        revisions = await self._revisions.list_revisions(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active = await self._revisions.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active_id = str(active.revision_id) if active else None
        return [revision_summary(revision, active_id) for revision in revisions]

    async def _backfill_payload(self) -> NewcomerPathConfigPayload:
        backfill_units = await load_published_path_units(self._db)
        modules = []
        path_title = "新人训练路径"
        goal_title: str | None = None
        for item in backfill_units:
            config = item.path_config
            path_title = config.path_title or path_title
            goal_title = config.goal_title or goal_title
            modules.append(module_from_unit(item.unit, config, module_key=item.module_key))
        return NewcomerPathConfigPayload(
            path_key=NEWCOMER_PATH_LOGICAL_ID,
            title=path_title,
            goal_title=goal_title,
            modules=sorted(modules, key=lambda item: item.order_index),
        )

    async def _projection_items(
        self,
        payload: NewcomerPathConfigPayload,
    ) -> list[PathUnitProjection]:
        unit_ids = [module.target_unit_id for module in payload.modules if module.enabled]
        units = await units_by_id(self._db, [unit_id for unit_id in unit_ids if unit_id])
        items: list[PathUnitProjection] = []
        for module in sorted(payload.modules, key=lambda item: item.order_index):
            if not module.enabled or not module.target_unit_id:
                continue
            unit = units.get(module.target_unit_id)
            if unit is None or str(unit.status) != "published":
                continue
            items.append(
                PathUnitProjection(
                    unit=unit,
                    path_config=path_config_from_module(payload, module),
                )
            )
        return items
