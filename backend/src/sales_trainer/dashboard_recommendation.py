from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.recommendations.dashboard_provider import (
    DashboardRecommendationPayload,
    register_dashboard_recommendation_provider,
)
from sales_trainer.services.path_service import SalesTrainerPathService

SALES_TRAINER_DASHBOARD_RECOMMENDATION_PROVIDER = "sales_trainer.path"


def build_sales_trainer_path_recommendation(
    paths: list[dict[str, Any]],
) -> DashboardRecommendationPayload | None:
    for path in paths:
        goal_context = path.get("goal_context")
        if not isinstance(goal_context, dict):
            continue
        next_recommendation = goal_context.get("next_recommendation")
        if not isinstance(next_recommendation, dict):
            continue
        target_path = next_recommendation.get("target_path")
        if not isinstance(target_path, str) or not target_path:
            continue
        title = str(
            next_recommendation.get("title")
            or path.get("title")
            or "继续销售训练"
        )
        reason = str(
            next_recommendation.get("reason")
            or goal_context.get("goal_title")
            or "继续推进当前销售训练目标。"
        )
        return {
            "title": title,
            "reason": reason,
            "action_label": str(next_recommendation.get("action_label") or "继续训练"),
            "target_path": target_path,
            "score_basis": str(
                goal_context.get("score_basis")
                or "sales_trainer_path_projection_v1"
            ),
            "recommendation_kind": "sales_trainer_path",
            "scenario_type": "sales_trainer",
            "source_session_id": str(next_recommendation.get("unit_id") or ""),
            "due_reason": "销售训练路径已生成下一步关卡建议。",
            "focus": str(next_recommendation.get("level_title") or ""),
            "suggested_duration_minutes": 10,
            "is_due_today": True,
        }
    return None


async def sales_trainer_dashboard_recommendation_provider(
    db: AsyncSession,
    user_id: str,
) -> DashboardRecommendationPayload | None:
    paths = await SalesTrainerPathService(db).list_paths_for_user(user_id)
    return build_sales_trainer_path_recommendation(paths)


def register_sales_trainer_dashboard_recommendation_provider() -> None:
    register_dashboard_recommendation_provider(
        SALES_TRAINER_DASHBOARD_RECOMMENDATION_PROVIDER,
        sales_trainer_dashboard_recommendation_provider,
    )
