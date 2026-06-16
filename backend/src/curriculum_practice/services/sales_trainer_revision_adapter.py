from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.services.asset_revision_service import (
    AssetChangeClass as AssetChangeClass,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService as _SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import (
    OperationLogService as _OperationLogService,
)


class SalesTrainerAssetRevision(Protocol):
    revision_id: str
    revision_no: int
    source_revision_id: str | None
    previous_revision_id: str | None
    change_class: AssetChangeClass
    payload_json: dict[str, Any]


class AssetPublishResult(Protocol):
    revision: SalesTrainerAssetRevision
    previous_revision_id: str | None


class SalesTrainerAssetRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._impl = _SalesTrainerAssetRevisionService(db)

    async def save_working_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
        payload: dict[str, Any],
        actor: User,
        change_class: AssetChangeClass,
        source_revision_id: str | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        return await self._impl.save_working_revision(
            resource_type=resource_type,
            logical_id=logical_id,
            payload=payload,
            actor=actor,
            change_class=change_class,
            source_revision_id=source_revision_id,
            reason=reason,
            trace_id=trace_id,
        )

    async def create_published_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
        payload: dict[str, Any],
        actor: User,
        change_class: AssetChangeClass,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        return await self._impl.create_published_revision(
            resource_type=resource_type,
            logical_id=logical_id,
            payload=payload,
            actor=actor,
            change_class=change_class,
            reason=reason,
            trace_id=trace_id,
        )

    async def active_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> SalesTrainerAssetRevision | None:
        return await self._impl.active_revision(
            resource_type=resource_type,
            logical_id=logical_id,
        )

    async def latest_working_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> SalesTrainerAssetRevision | None:
        return await self._impl.latest_working_revision(
            resource_type=resource_type,
            logical_id=logical_id,
        )

    async def publish_working_revision(
        self,
        revision: SalesTrainerAssetRevision,
        *,
        actor: User,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        return await self._impl.publish_working_revision(
            revision,
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )


class OperationLogService:
    def __init__(self, db: AsyncSession) -> None:
        self._impl = _OperationLogService(db)

    async def record(
        self,
        *,
        actor: User,
        action: str,
        target_type: str,
        target_id: str,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self._impl.record(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=request_id,
            metadata=metadata,
        )


__all__ = [
    "AssetChangeClass",
    "OperationLogService",
    "SalesTrainerAssetRevisionService",
]
