from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import PracticeTemplate


async def list_published_template_references(
    db: AsyncSession,
    *,
    asset_type: Literal["case_item", "role_profile", "examiner_agent"],
    asset_id: str,
) -> list[dict[str, str]]:
    column_map = {
        "case_item": PracticeTemplate.case_item_id,
        "role_profile": PracticeTemplate.role_profile_id,
        "examiner_agent": PracticeTemplate.examiner_agent_id,
    }
    column = column_map[asset_type]
    result = await db.execute(
        select(PracticeTemplate).where(
            column == asset_id,
            PracticeTemplate.status == "published",
        )
    )
    return [
        {
            "template_id": str(template.template_id),
            "name": str(template.name),
            "status": str(template.status),
        }
        for template in result.scalars().all()
    ]
