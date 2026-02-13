"""
Analytics API - Endpoints for analytics, leaderboard, and history

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient queries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.analytics_service import analytics_service
from common.analytics.history_service import history_service
from common.analytics.leaderboard_service import leaderboard_service
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.jobs.audio_archival import audio_archival_job
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _normalize_scenario_type(scenario_type: str | None) -> str | None:
    """Normalize scenario aliases for leaderboard APIs."""
    if not scenario_type:
        return None
    if scenario_type == "sales_bot":
        return "sales"
    return scenario_type


def _normalize_time_period(time_period: str) -> str:
    """Normalize time-period aliases to service canonical values."""
    aliases = {
        "day": "daily",
        "daily": "daily",
        "week": "weekly",
        "weekly": "weekly",
        "month": "monthly",
        "monthly": "monthly",
        "all": "all_time",
        "all_time": "all_time",
    }
    return aliases.get(time_period, "all_time")


# Leaderboard endpoints
@router.get("/analytics/leaderboard")
async def get_leaderboard(
    scenario_type: str | None = None,
    time_period: str = "all_time",
    include_me: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get leaderboard rankings"""
    try:
        normalized_scenario_type = _normalize_scenario_type(scenario_type)
        normalized_time_period = _normalize_time_period(time_period)
        result = await leaderboard_service.calculate_leaderboard(
            db=db,
            scenario_type=normalized_scenario_type,
            time_period=normalized_time_period,
            limit=limit,
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")

        stats = result.value
        response_payload = {
            "scenario_type": normalized_scenario_type,
            "time_period": stats.time_period,
            "total_users": stats.total_users,
            "entries": [
                {
                    "rank": entry.rank,
                    "user_id": str(entry.user_id),
                    "username": entry.username,
                    "total_sessions": entry.total_sessions,
                    "average_score": entry.average_score,
                    "best_score": entry.best_score,
                }
                for entry in stats.entries
            ],
        }

        if include_me:
            my_rank_result = await leaderboard_service.get_user_rank(
                db=db,
                user_id=current_user.user_id,
                scenario_type=normalized_scenario_type,
                time_period=normalized_time_period,
            )
            if my_rank_result.is_success:
                response_payload["my_rank"] = my_rank_result.value

        return response_payload

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")


@router.get("/analytics/leaderboard/my-rank")
async def get_my_rank(
    scenario_type: str | None = None,
    time_period: str = "all_time",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's rank"""
    try:
        normalized_scenario_type = _normalize_scenario_type(scenario_type)
        normalized_time_period = _normalize_time_period(time_period)
        result = await leaderboard_service.get_user_rank(
            db=db,
            user_id=current_user.user_id,
            scenario_type=normalized_scenario_type,
            time_period=normalized_time_period,
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch rank")

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get user rank: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch rank")


# Dashboard analytics endpoints
@router.get("/analytics/dashboard")
async def get_dashboard_stats(
    scenario_type: str | None = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard analytics statistics (admin only)"""
    try:
        result = await analytics_service.get_dashboard_stats(
            db=db, scenario_type=scenario_type, days=days
        )

        if not result.is_success:
            raise HTTPException(
                status_code=500, detail="Failed to fetch dashboard stats"
            )

        stats = result.value

        return {
            "scenario_type": scenario_type,
            "days": days,
            "total_sessions": stats.total_sessions,
            "completed_sessions": stats.completed_sessions,
            "completion_rate": stats.completion_rate,
            "average_scores": {
                "logic": stats.average_logic_score,
                "accuracy": stats.average_accuracy_score,
                "completeness": stats.average_completeness_score,
                "overall": stats.average_overall_score,
            },
            "engagement": {
                "average_duration_seconds": stats.average_duration_seconds,
                "average_interruptions_per_session": stats.average_interruptions_per_session,
            },
            "quality": {
                "sessions_with_high_vagueness": stats.sessions_with_high_vagueness,
                "sessions_with_forbidden_words": stats.sessions_with_forbidden_words,
            },
        }

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard stats")


@router.get("/analytics/score-distribution")
async def get_score_distribution(
    scenario_type: str | None = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get score distribution"""
    try:
        result = await analytics_service.get_score_distribution(
            db=db, scenario_type=scenario_type, days=days
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch distribution")

        dist = result.value

        return {
            "scenario_type": scenario_type,
            "days": days,
            "distribution": {
                "excellent": dist.excellent,
                "good": dist.good,
                "fair": dist.fair,
                "poor": dist.poor,
            },
        }

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get score distribution: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch distribution")


@router.get("/analytics/trends")
async def get_trend_data(
    scenario_type: str | None = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get trend data for charts"""
    try:
        result = await analytics_service.get_trend_data(
            db=db, scenario_type=scenario_type, days=days
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch trend data")

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get trend data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch trend data")


# Practice history endpoints
@router.get("/analytics/practice/history")
async def get_analytics_practice_history(
    scenario_type: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's practice history snapshot for analytics views."""
    try:
        result = await history_service.get_user_history(
            db=db,
            user_id=current_user.user_id,
            scenario_type=scenario_type,
            limit=limit,
            offset=offset,
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch history")

        sessions = result.value

        items = [
            {
                "session_id": str(session.session_id),
                "scenario_id": str(session.scenario_id),
                "start_time": session.start_time.isoformat(),
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": session.status,
                "overall_score": (
                    (session.logic_score or 0) * 0.4
                    + (session.accuracy_score or 0) * 0.3
                    + (session.completeness_score or 0) * 0.3
                ),
            }
            for session in sessions
        ]

        return {
            "items": items,
            "sessions": items,
            "total": len(items),
        }

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get practice history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.get("/practice/history/statistics")
async def get_history_statistics(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get current user's practice statistics"""
    try:
        result = await history_service.get_statistics(
            db=db, user_id=current_user.user_id
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch statistics")

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get history statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


@router.get("/practice/history/trends")
async def get_score_trends(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's score trends"""
    try:
        result = await history_service.get_score_trends(
            db=db, user_id=current_user.user_id, days=days
        )

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch trends")

        return {"trends": result.value}

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get score trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch trends")


# Storage stats endpoint (admin)
@router.get("/analytics/storage")
async def get_storage_stats(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get audio storage statistics (admin only)"""
    try:
        # TODO: Add admin role check
        result = await audio_archival_job.get_storage_stats(db=db)

        if not result.is_success:
            raise HTTPException(status_code=500, detail="Failed to fetch storage stats")

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get storage stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch storage stats")
