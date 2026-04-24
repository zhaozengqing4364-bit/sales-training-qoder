"""Growth center API for learner retention loops."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.growth.growth_service import GrowthCenterService

router = APIRouter(prefix="/growth", tags=["growth"])


class GoalUpsertRequest(BaseModel):
    goal_type: str = Field(pattern="^(weekly_sessions|monthly_presentations)$")
    target_count: int = Field(ge=1, le=100)
    period: str = Field(pattern="^(weekly|monthly)$")
    start_date: date
    end_date: date


@router.get("/dashboard")
async def get_growth_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await GrowthCenterService().get_dashboard_growth(
        db=db,
        user_id=str(current_user.user_id),
    )
    if not result.is_success:
        return error_response("[GROWTH_DASHBOARD_FAILED]", "成长中心暂时无法读取。")
    return success_response(result.value)


@router.get("/adaptive-difficulty/dry-run")
async def get_adaptive_difficulty_dry_run(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await GrowthCenterService().get_adaptive_difficulty_dry_run(
        db=db,
        user_id=str(current_user.user_id),
        limit=limit,
    )
    if not result.is_success:
        return error_response(
            "[ADAPTIVE_DRY_RUN_FAILED]",
            "自适应难度 dry-run 暂时无法读取。",
        )
    return success_response(result.value)


@router.get("/notifications")
async def list_notifications(
    include_read: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await GrowthCenterService().list_notifications(
        db=db,
        user_id=str(current_user.user_id),
        include_read=include_read,
    )
    if not result.is_success:
        return error_response("[NOTIFICATION_LIST_FAILED]", "通知暂时无法读取。")
    return success_response(result.value)


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await GrowthCenterService().mark_notification_read(
        db=db,
        user_id=str(current_user.user_id),
        notification_id=notification_id,
    )
    if not result.is_success:
        return error_response("[NOTIFICATION_NOT_FOUND]", "通知不存在或无权访问。")
    return success_response(result.value)


@router.put("/goals/current")
async def upsert_current_goal(
    payload: GoalUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data: dict[str, Any] = payload.model_dump()
    result = await GrowthCenterService().upsert_goal(
        db=db,
        user_id=str(current_user.user_id),
        goal_type=str(data["goal_type"]),
        target_count=int(data["target_count"]),
        period=str(data["period"]),
        start_date=data["start_date"],
        end_date=data["end_date"],
    )
    if not result.is_success:
        return error_response("[GOAL_UPSERT_FAILED]", "目标暂时无法保存。")
    return success_response(result.value)
