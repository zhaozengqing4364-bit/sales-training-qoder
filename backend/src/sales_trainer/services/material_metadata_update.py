from __future__ import annotations

from typing import TypedDict

from common.db.models import User
from sales_trainer.models import SalesTrainerMaterial
from sales_trainer.services.operation_log_service import OperationLogService


class MaterialMetadataSnapshot(TypedDict):
    material_key: str
    name: str
    material_type: str
    description: str | None
    purpose: str
    status: str
    current_version_id: str | None


def material_metadata_snapshot(
    material: SalesTrainerMaterial,
) -> MaterialMetadataSnapshot:
    return {
        "material_key": material.material_key,
        "name": material.name,
        "material_type": material.material_type,
        "description": material.description,
        "purpose": material.purpose,
        "status": material.status,
        "current_version_id": material.current_version_id,
    }


def changed_material_metadata_fields(
    before: MaterialMetadataSnapshot,
    after: MaterialMetadataSnapshot,
) -> list[str]:
    return [field for field, value in after.items() if before[field] != value]


async def record_material_metadata_update(
    logs: OperationLogService,
    *,
    material: SalesTrainerMaterial,
    actor: User,
    before: MaterialMetadataSnapshot,
    after: MaterialMetadataSnapshot,
    trace_id: str,
) -> None:
    changed_fields = changed_material_metadata_fields(before, after)
    await logs.record(
        actor=actor,
        action="material_metadata_updated",
        target_type="sales_trainer_material",
        target_id=material.material_id,
        request_id=trace_id,
        metadata={
            "before": before,
            "after": after,
            "changed_fields": changed_fields,
            "trace_id": trace_id,
            "future_only": material.status == "published",
            "impact_scope": "future_submissions_only",
        },
    )
