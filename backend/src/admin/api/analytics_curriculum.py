from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.analytics import error_response, success_response
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger
from curriculum_analytics.service import curriculum_analytics_service

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/analytics", tags=["admin-curriculum-analytics"])


@router.get("/curriculum", response_model=dict)
async def get_curriculum_analytics_dashboard(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query(
        "30d", description="Time range filter"
    ),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    logger.info(
        "Getting curriculum analytics dashboard",
        extra={"time_range": time_range, "user_id": str(current_user.user_id)},
    )
    result = await curriculum_analytics_service.get_dashboard(
        db=db,
        time_range=time_range,
    )
    if not result.is_success:
        return error_response(
            result.fallback or "[CURRICULUM_ANALYTICS_FAILED]",
            "Failed to load curriculum analytics dashboard",
        )
    return success_response(asdict(result.unwrap()))
