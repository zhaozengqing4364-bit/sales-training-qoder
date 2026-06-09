from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)

REVISION_RESOURCE_TYPES: Final = {
    "case_item": "curriculum_case_item",
    "role_profile": "curriculum_role_profile",
    "learning_content": "curriculum_learning_content",
    "examiner_agent": "curriculum_examiner_agent",
    "question_item": "curriculum_question_item",
    "practice_template": "curriculum_practice_template",
}


async def active_revision_lineage(
    db: AsyncSession,
    *,
    asset_type: str,
    logical_id: str,
) -> dict[str, Any]:
    resource_type = REVISION_RESOURCE_TYPES.get(asset_type)
    if resource_type is None:
        return {}
    result = await db.execute(
        select(SalesTrainerAssetActiveRevision).where(
            SalesTrainerAssetActiveRevision.resource_type == resource_type,
            SalesTrainerAssetActiveRevision.logical_id == logical_id,
        )
    )
    active = result.scalar_one_or_none()
    if active is None:
        return {}
    revision = await db.get(
        SalesTrainerAssetRevision,
        active.active_revision_id,
    )
    return {
        "logical_id": logical_id,
        "revision_id": str(active.active_revision_id),
        "revision_no": int(revision.revision_no) if revision is not None else None,
    }
