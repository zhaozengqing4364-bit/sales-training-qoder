from __future__ import annotations

from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from common.assets.lineage import resolve_active_revision_lineage

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
    if asset_type not in REVISION_RESOURCE_TYPES:
        return {}
    return await resolve_active_revision_lineage(
        db,
        asset_type=asset_type,
        logical_id=logical_id,
    )
