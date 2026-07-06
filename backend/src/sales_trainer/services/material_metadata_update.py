from __future__ import annotations

from typing import Literal, TypedDict, cast

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


MaterialMetadataField = Literal[
    "material_key",
    "name",
    "material_type",
    "description",
    "purpose",
    "status",
    "current_version_id",
]

_MATERIAL_METADATA_FIELDS: tuple[MaterialMetadataField, ...] = (
    "material_key",
    "name",
    "material_type",
    "description",
    "purpose",
    "status",
    "current_version_id",
)


def material_metadata_snapshot(
    material: SalesTrainerMaterial,
) -> MaterialMetadataSnapshot:
    return {
        "material_key": cast(str, material.material_key),
        "name": cast(str, material.name),
        "material_type": cast(str, material.material_type),
        "description": cast(str | None, material.description),
        "purpose": cast(str, material.purpose),
        "status": cast(str, material.status),
        "current_version_id": cast(str | None, material.current_version_id),
    }


def changed_material_metadata_fields(
    before: MaterialMetadataSnapshot,
    after: MaterialMetadataSnapshot,
) -> list[str]:
    return [field for field in _MATERIAL_METADATA_FIELDS if before[field] != after[field]]


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
        target_id=str(material.material_id),
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
