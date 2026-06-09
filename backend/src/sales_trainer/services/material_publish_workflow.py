from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import (
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.services.operation_log_service import OperationLogService


class MaterialPublishWorkflowError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def publish_material_version(
    db: AsyncSession,
    logs: OperationLogService,
    version: SalesTrainerMaterialVersion,
    *,
    actor: User,
    trace_id: str | None = None,
) -> SalesTrainerMaterialVersion:
    resolved_trace_id = trace_id or get_trace_id()
    material = await db.get(SalesTrainerMaterial, version.material_id)
    if material is None:
        raise MaterialPublishWorkflowError(
            "[SALES_TRAINER_MATERIAL_NOT_FOUND]",
            "训练材料不存在。",
            status_code=404,
        )
    if material.status == "archived" or version.status == "archived":
        raise MaterialPublishWorkflowError(
            "[SALES_TRAINER_MATERIAL_ARCHIVED]",
            "已归档材料或版本不能发布。",
            status_code=409,
        )
    previous_current_version_id = _optional_str(material.current_version_id)
    previous = await db.execute(
        select(SalesTrainerMaterialVersion).where(
            SalesTrainerMaterialVersion.material_id == version.material_id,
            SalesTrainerMaterialVersion.status == "published",
            SalesTrainerMaterialVersion.version_id != version.version_id,
        )
    )
    archived_version_ids: list[str] = []
    for item in previous.scalars().all():
        item.status = "archived"
        archived_version_ids.append(str(item.version_id))
    version.status = "published"
    version.published_at = datetime.now(UTC)
    version.published_by = str(actor.user_id)
    material.status = "published"
    material.current_version_id = version.version_id
    material.updated_by = str(actor.user_id)
    await logs.record(
        actor=actor,
        action="material_version_published",
        target_type="sales_trainer_material_version",
        target_id=version.version_id,
        request_id=resolved_trace_id,
        metadata={
            "material_id": material.material_id,
            "version_label": version.version_label,
            "before_version_id": previous_current_version_id,
            "after_version_id": version.version_id,
            "archived_version_ids": archived_version_ids,
            "trace_id": resolved_trace_id,
            "impact_scope": "future_submissions_only",
        },
    )
    await db.commit()
    await db.refresh(version)
    return version


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
