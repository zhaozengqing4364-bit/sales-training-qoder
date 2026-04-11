"""
Admin Analytics API - System-wide analytics endpoints for administrators

Provides endpoints for system overview, trends, Agent statistics, 
user leaderboard, and data export.

References:
- Requirements: Admin Analytics Page
- Constitution Principles:
  - I. NO ERROR POPUPS - Graceful degradation
  - VI. Data privacy - Admin-only access
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.admin_analytics_service import admin_analytics_service
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


# Response schemas
class GrowthMetrics(BaseModel):
    """Growth metrics compared to previous period"""
    users_rate: float
    sessions_rate: float
    score_rate: float


class OverviewResponse(BaseModel):
    """System overview response"""
    total_users: int
    active_users_today: int
    active_users_week: int
    total_sessions: int
    sessions_today: int
    completed_sessions: int
    completion_rate: float
    average_score: float
    average_duration_minutes: float
    growth: GrowthMetrics


class TrendDataPoint(BaseModel):
    """Single trend data point"""
    date: str
    sessions_count: int
    average_score: float
    active_users: int


class ScoreDistribution(BaseModel):
    """Score distribution buckets"""
    excellent: int  # 90-100
    good: int       # 70-89
    fair: int       # 50-69
    poor: int       # 0-49


class TrendsResponse(BaseModel):
    """Trends data response"""
    trend_data: list[TrendDataPoint]
    score_distribution: ScoreDistribution


class AgentStatsItem(BaseModel):
    """Agent statistics item"""
    agent_id: str
    agent_name: str
    category: str
    usage_count: int
    average_score: float
    completion_rate: float


class PersonaStatsItem(BaseModel):
    """Persona statistics item"""
    persona_id: str
    persona_name: str
    difficulty: str
    usage_count: int
    average_score: float


class AgentsResponse(BaseModel):
    """Agent and Persona statistics response"""
    agent_stats: list[AgentStatsItem]
    persona_stats: list[PersonaStatsItem]
    scenario_distribution: dict[str, int]


class LeaderboardEntry(BaseModel):
    """Leaderboard entry"""
    rank: int
    user_id: str
    user_name: str
    department: str | None
    total_sessions: int
    average_score: float
    best_score: float
    total_duration_minutes: float


class LeaderboardResponse(BaseModel):
    """Leaderboard response"""
    leaderboard: list[LeaderboardEntry]


def success_response(data: Any, trace_id: str | None = None) -> dict:
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str, trace_id: str | None = None) -> dict:
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message,
        "trace_id": trace_id or get_trace_id()
    }


@router.get("/overview", response_model=dict)
async def get_analytics_overview(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    scenario_type: Literal["presentation", "sales"] | None = Query(None, description="Filter by scenario type"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get system overview statistics
    
    Returns aggregated statistics including:
    - Total users and active users
    - Total sessions and completion rate
    - Average score and duration
    - Growth metrics compared to previous period
    """
    logger.info(
        "Getting analytics overview",
        extra={
            "time_range": time_range,
            "scenario_type": scenario_type,
            "user_id": str(current_user.user_id)
        }
    )

    result = await admin_analytics_service.get_overview_stats(
        db=db,
        time_range=time_range,
        scenario_type=scenario_type
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[OVERVIEW_FAILED]",
            "Failed to load overview statistics"
        )

    # Convert dataclass to dict
    from dataclasses import asdict
    data = asdict(result.value)
    
    return success_response(data)


@router.get("/trends", response_model=dict)
async def get_trends_data(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    granularity: Literal["day", "week", "month"] = Query("day", description="Data granularity"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get trend data for charts
    
    Returns:
    - Daily/weekly/monthly trend data (sessions, scores, active users)
    - Score distribution (excellent, good, fair, poor)
    """
    logger.info(
        "Getting trends data",
        extra={
            "time_range": time_range,
            "granularity": granularity,
            "user_id": str(current_user.user_id)
        }
    )

    result = await admin_analytics_service.get_trends_data(
        db=db,
        time_range=time_range,
        granularity=granularity
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[TRENDS_FAILED]",
            "Failed to load trends data"
        )

    return success_response(result.value)


@router.get("/agents", response_model=dict)
async def get_agent_stats(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get Agent and Persona usage statistics
    
    Returns:
    - Agent usage ranking (by session count)
    - Persona usage ranking
    - Scenario type distribution
    """
    logger.info(
        "Getting agent stats",
        extra={
            "time_range": time_range,
            "limit": limit,
            "user_id": str(current_user.user_id)
        }
    )

    result = await admin_analytics_service.get_agent_stats(
        db=db,
        time_range=time_range,
        limit=limit
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[AGENTS_FAILED]",
            "Failed to load agent statistics"
        )

    return success_response(result.value)


@router.get("/leaderboard", response_model=dict)
async def get_leaderboard(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    limit: int = Query(50, ge=1, le=100, description="Max users to return"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get user leaderboard
    
    Returns users ranked by average score, including:
    - Rank, name, department
    - Total sessions and average/best score
    - Total practice duration
    """
    logger.info(
        "Getting leaderboard",
        extra={
            "time_range": time_range,
            "limit": limit,
            "user_id": str(current_user.user_id)
        }
    )

    result = await admin_analytics_service.get_leaderboard(
        db=db,
        time_range=time_range,
        limit=limit
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[LEADERBOARD_FAILED]",
            "Failed to load leaderboard"
        )

    return success_response({"leaderboard": result.value})


@router.get("/operating-pack", response_model=dict)
async def get_operating_pack(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("7d", description="Time range filter"),
    scenario_type: Literal["presentation", "sales"] | None = Query(None, description="Filter by scenario type"),
    limit: int = Query(10, ge=1, le=50, description="Max users per operating list"),
    inactive_days: int = Query(7, ge=1, le=90, description="Minimum inactivity days for risk list"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get the weekly operating pack for cohort issue review.

    Returns:
    - Weekly summary counts on the projection-backed score basis
    - Cohort and department blocker buckets
    - Degradation / not-evaluable breakdowns
    - Risk and improving manager lists aligned to the same evidence line
    """
    logger.info(
        "Getting analytics operating pack",
        extra={
            "time_range": time_range,
            "scenario_type": scenario_type,
            "limit": limit,
            "inactive_days": inactive_days,
            "user_id": str(current_user.user_id),
        },
    )

    result = await admin_analytics_service.get_operating_pack(
        db=db,
        time_range=time_range,
        scenario_type=scenario_type,
        limit=limit,
        inactive_days=inactive_days,
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[OPERATING_PACK_FAILED]",
            "Failed to load operating pack",
        )

    return success_response(result.value)


@router.get("/runtime-metrics", response_model=dict)
async def get_runtime_metrics(
    time_range: Literal["1h", "24h", "7d", "30d", "90d"] = Query("30d", description="Time range filter"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get key runtime metrics for dashboard (FR39)

    Returns:
    - Recovery success rate (NFR8: >=99%)
    - False trigger rate (NFR11: <1%)
    - Completeness rate (NFR10: >=98%)
    - Session metrics and voice mode distribution
    """
    from common.analytics.runtime_metrics_service import runtime_metrics_service
    from dataclasses import asdict

    logger.info(
        "Getting runtime metrics",
        extra={
            "time_range": time_range,
            "user_id": str(current_user.user_id)
        }
    )

    result = await runtime_metrics_service.get_runtime_metrics(
        db=db,
        time_range=time_range
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[RUNTIME_METRICS_FAILED]",
            "Failed to load runtime metrics"
        )

    return success_response(asdict(result.value))


@router.get("/policy-effectiveness", response_model=dict)
async def get_policy_effectiveness(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    limit: int = Query(10, ge=1, le=50, description="Max items to return"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get policy effectiveness metrics by Agent (FR39)

    Returns metrics comparing different Agents and their policy effectiveness
    """
    from common.analytics.runtime_metrics_service import runtime_metrics_service
    from dataclasses import asdict

    logger.info(
        "Getting policy effectiveness",
        extra={
            "time_range": time_range,
            "limit": limit,
            "user_id": str(current_user.user_id)
        }
    )

    result = await runtime_metrics_service.get_policy_effectiveness(
        db=db,
        time_range=time_range,
        limit=limit
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[POLICY_EFFECTIVENESS_FAILED]",
            "Failed to load policy effectiveness"
        )

    return success_response({
        "effectiveness": [asdict(item) for item in result.value]
    })


@router.get("/voice-mode-comparison", response_model=dict)
async def get_voice_mode_comparison(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Compare performance between voice modes (StepFun vs Legacy) (FR39)

    Returns comparison metrics for different voice modes
    """
    from common.analytics.runtime_metrics_service import runtime_metrics_service
    from dataclasses import asdict

    logger.info(
        "Getting voice mode comparison",
        extra={
            "time_range": time_range,
            "user_id": str(current_user.user_id)
        }
    )

    result = await runtime_metrics_service.get_voice_mode_comparison(
        db=db,
        time_range=time_range
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[VOICE_MODE_COMPARISON_FAILED]",
            "Failed to load voice mode comparison"
        )

    return success_response({
        "comparison": [asdict(item) for item in result.value]
    })


@router.get("/fallback-metrics", response_model=dict)
async def get_fallback_metrics(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get fallback and degradation metrics (FR39)

    Returns metrics about TTS/ASR/LLM fallbacks and browser TTS usage
    """
    from common.analytics.runtime_metrics_service import runtime_metrics_service
    from dataclasses import asdict

    logger.info(
        "Getting fallback metrics",
        extra={
            "time_range": time_range,
            "user_id": str(current_user.user_id)
        }
    )

    result = await runtime_metrics_service.get_fallback_metrics(
        db=db,
        time_range=time_range
    )

    if not result.is_success:
        return error_response(
            result.fallback or "[FALLBACK_METRICS_FAILED]",
            "Failed to load fallback metrics"
        )

    return success_response(asdict(result.value))


@router.get("/export")
async def export_analytics(
    time_range: Literal["7d", "30d", "90d", "all_time"] = Query("30d", description="Time range filter"),
    format: Literal["csv"] = Query("csv", description="Export format"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export analytics data as CSV
    
    Exports overview, trends, and leaderboard data to a CSV file.
    """
    logger.info(
        "Exporting analytics",
        extra={
            "time_range": time_range,
            "format": format,
            "user_id": str(current_user.user_id)
        }
    )

    # Fetch all data
    overview_result = await admin_analytics_service.get_overview_stats(db, time_range)
    trends_result = await admin_analytics_service.get_trends_data(db, time_range)
    leaderboard_result = await admin_analytics_service.get_leaderboard(db, time_range, limit=100)

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output)

    # Overview section
    writer.writerow(["=== 系统概览 ==="])
    writer.writerow(["指标", "数值"])
    
    if overview_result.is_success:
        from dataclasses import asdict
        overview = asdict(overview_result.value)
        writer.writerow(["总用户数", overview["total_users"]])
        writer.writerow(["今日活跃用户", overview["active_users_today"]])
        writer.writerow(["本周活跃用户", overview["active_users_week"]])
        writer.writerow(["总练习次数", overview["total_sessions"]])
        writer.writerow(["今日练习次数", overview["sessions_today"]])
        writer.writerow(["完成率 (%)", overview["completion_rate"]])
        writer.writerow(["平均分", overview["average_score"]])
        writer.writerow(["平均时长 (分钟)", overview["average_duration_minutes"]])

    writer.writerow([])

    # Score distribution
    writer.writerow(["=== 分数分布 ==="])
    writer.writerow(["等级", "数量"])
    
    if trends_result.is_success:
        dist = trends_result.value.get("score_distribution", {})
        writer.writerow(["优秀 (90-100)", dist.get("excellent", 0)])
        writer.writerow(["良好 (70-89)", dist.get("good", 0)])
        writer.writerow(["及格 (50-69)", dist.get("fair", 0)])
        writer.writerow(["待提升 (<50)", dist.get("poor", 0)])

    writer.writerow([])

    # Trends section
    writer.writerow(["=== 趋势数据 ==="])
    writer.writerow(["日期", "练习次数", "平均分", "活跃用户"])
    
    if trends_result.is_success:
        for point in trends_result.value.get("trend_data", []):
            writer.writerow([
                point["date"],
                point["sessions_count"],
                point["average_score"],
                point["active_users"]
            ])

    writer.writerow([])

    # Leaderboard section
    writer.writerow(["=== 用户排行榜 ==="])
    writer.writerow(["排名", "姓名", "部门", "练习次数", "平均分", "最高分", "总时长(分钟)"])
    
    if leaderboard_result.is_success:
        for entry in leaderboard_result.value:
            writer.writerow([
                entry["rank"],
                entry["user_name"],
                entry["department"] or "-",
                entry["total_sessions"],
                entry["average_score"],
                entry["best_score"],
                entry["total_duration_minutes"]
            ])

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analytics_report_{timestamp}.csv"

    # Return as streaming response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8-sig"  # BOM for Excel
        }
    )
