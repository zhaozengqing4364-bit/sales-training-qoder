"""
Analytics API - Endpoints for analytics, leaderboard, and history

Implements Constitution Principles:
- I. NO ERROR POPUPS - All errors return gracefully
- V. Cost control - Efficient queries
"""

import inspect
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.analytics_service import analytics_service
from common.analytics.history_service import history_service
from common.analytics.leaderboard_service import leaderboard_service
from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user, get_current_user
from common.db.models import User
from common.db.session import get_db
from common.jobs.audio_archival import audio_archival_job
from common.monitoring.logger import get_logger
from common.monitoring.metrics import track_frontend_analytics_event

logger = get_logger(__name__)

router = APIRouter()

LEADERBOARD_MODES = {"score", "improvement", "issue_type"}


def _normalize_leaderboard_mode(leaderboard_mode: str | None) -> str:
    """Normalize and validate public leaderboard mode params."""
    mode = (leaderboard_mode or "score").strip().lower()
    if mode not in LEADERBOARD_MODES:
        allowed_modes = ", ".join(sorted(LEADERBOARD_MODES))
        raise HTTPException(
            status_code=400,
            detail={
                "code": "[INVALID_LEADERBOARD_MODE]",
                "message": f"leaderboard_mode must be one of: {allowed_modes}",
            },
        )
    return mode


def _supported_service_kwargs(service_method, **kwargs: object) -> dict[str, object]:
    """Pass Phase 6E params when the service supports them; stay compatible until then."""
    try:
        parameters = inspect.signature(service_method).parameters
    except (TypeError, ValueError):
        return kwargs

    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return kwargs

    return {key: value for key, value in kwargs.items() if key in parameters}


def _value(source: object, field_name: str, default: object = None) -> object:
    """Read dataclass/object or dict fields for service response compatibility."""
    if isinstance(source, dict):
        return source.get(field_name, default)
    return getattr(source, field_name, default)


def _leaderboard_eligibility(leaderboard_mode: str) -> dict[str, object]:
    """Describe the shared eligibility gate exposed by the leaderboard API."""
    return {
        "completed_sessions_only": True,
        "evaluable_sessions_only": True,
        "score_fields_required": True,
        "minimum_evaluable_sessions": 2 if leaderboard_mode == "improvement" else 1,
        "issue_type_required_for_entries": leaderboard_mode == "issue_type",
    }


def _serialize_leaderboard_entry(entry: object) -> dict[str, object]:
    """Serialize score entries plus optional Phase 6E mode-specific fields."""
    payload: dict[str, object] = {
        "rank": _value(entry, "rank"),
        "user_id": str(_value(entry, "user_id")),
        "username": _value(entry, "username", "Anonymous") or "Anonymous",
        "total_sessions": _value(
            entry,
            "total_sessions",
            _value(entry, "sample_size", 0),
        ),
        "average_score": _value(entry, "average_score", 0),
        "best_score": _value(entry, "best_score", 0),
        "score_basis": _value(entry, "score_basis"),
        "evaluable_sessions": _value(
            entry,
            "evaluable_sessions",
            _value(entry, "total_sessions", _value(entry, "sample_size", 0)),
        ),
        "not_evaluable_sessions": _value(entry, "not_evaluable_sessions", 0),
    }

    for optional_field in (
        "leaderboard_score",
        "improvement_score",
        "first_score",
        "latest_score",
        "sample_size",
        "issue_type",
        "issue_type_label",
        "issue_type_sessions",
    ):
        optional_value = _value(entry, optional_field)
        if optional_value is not None:
            payload[optional_field] = optional_value

    return payload


def _rank_payload_with_mode(
    rank_payload: dict[str, object],
    leaderboard_mode: str,
    issue_type: str | None,
) -> dict[str, object]:
    """Ensure rank responses echo the selected mode before/after service rollout."""
    payload = dict(rank_payload)
    payload.setdefault("leaderboard_mode", leaderboard_mode)
    if issue_type is not None:
        payload.setdefault("issue_type", issue_type)
    return payload


class FrontendErrorEvent(BaseModel):
    error: str
    stack: str | None = None
    component_stack: str | None = Field(default=None, alias="componentStack")
    url: str
    user_agent: str | None = Field(default=None, alias="userAgent")
    timestamp: str
    source: str | None = None
    boundary: str | None = None


class FrontendPerformanceEvent(BaseModel):
    name: str
    value: float
    rating: str | None = None
    delta: float | None = None
    id: str | None = None
    url: str
    timestamp: str


class FrontendCustomEvent(BaseModel):
    name: str
    value: float
    metadata: dict[str, Any] | None = None
    url: str
    timestamp: str


@router.post("/analytics/error", status_code=202)
async def ingest_frontend_error(event: FrontendErrorEvent):
    """Accept frontend route and boundary error beacons on a real backend sink."""
    track_frontend_analytics_event("error")
    logger.warning(
        "Accepted frontend analytics/error beacon",
        source=event.source or "frontend.unknown",
        boundary=event.boundary or "",
        url=event.url,
        error=event.error,
        component_stack_present=bool(event.component_stack),
        user_agent=event.user_agent or "",
        observed_at=event.timestamp,
    )
    return {"accepted": True, "event_type": "error"}


@router.post("/analytics/performance", status_code=202)
async def ingest_frontend_performance_metric(event: FrontendPerformanceEvent):
    """Accept Web Vitals beacons on a real backend sink."""
    track_frontend_analytics_event("performance")
    logger.info(
        "Accepted frontend analytics/performance beacon",
        metric_name=event.name,
        metric_value=event.value,
        rating=event.rating or "",
        delta=event.delta,
        metric_id=event.id or "",
        url=event.url,
        observed_at=event.timestamp,
    )
    return {"accepted": True, "event_type": "performance"}


@router.post("/analytics/custom", status_code=202)
async def ingest_frontend_custom_metric(event: FrontendCustomEvent):
    """Accept custom frontend metrics on a real backend sink."""
    track_frontend_analytics_event("custom")
    logger.info(
        "Accepted frontend analytics/custom beacon",
        metric_name=event.name,
        metric_value=event.value,
        metadata=event.metadata or {},
        url=event.url,
        observed_at=event.timestamp,
    )
    return {"accepted": True, "event_type": "custom"}


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


def _server_error(
    error_code: str,
    message: str,
    *,
    exc: Exception | None = None,
    **context: object,
):
    return build_server_error(error_code, message=message, exc=exc, **context)


# Leaderboard endpoints
@router.get("/analytics/leaderboard")
async def get_leaderboard(
    scenario_type: str | None = None,
    time_period: str = "all_time",
    leaderboard_mode: str = Query("score"),
    issue_type: str | None = None,
    include_me: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get leaderboard rankings."""
    try:
        normalized_scenario_type = _normalize_scenario_type(scenario_type)
        normalized_time_period = _normalize_time_period(time_period)
        normalized_leaderboard_mode = _normalize_leaderboard_mode(leaderboard_mode)
        result = await leaderboard_service.calculate_leaderboard(
            **_supported_service_kwargs(
                leaderboard_service.calculate_leaderboard,
                db=db,
                scenario_type=normalized_scenario_type,
                time_period=normalized_time_period,
                limit=limit,
                leaderboard_mode=normalized_leaderboard_mode,
                issue_type=issue_type,
            )
        )

        if not result.is_success:
            return _server_error(
                "[LEADERBOARD_FETCH_FAILED]",
                "Failed to fetch leaderboard",
                scenario_type=normalized_scenario_type,
                time_period=normalized_time_period,
                leaderboard_mode=normalized_leaderboard_mode,
                issue_type=issue_type,
            )

        stats = result.value
        response_payload = {
            "scenario_type": normalized_scenario_type,
            "time_period": _value(stats, "time_period", normalized_time_period),
            "leaderboard_mode": normalized_leaderboard_mode,
            "score_basis": _value(stats, "score_basis"),
            "eligibility": _value(
                stats,
                "eligibility",
                _leaderboard_eligibility(normalized_leaderboard_mode),
            ),
            "evaluable_sessions": _value(stats, "evaluable_sessions", 0),
            "not_evaluable_sessions": _value(stats, "not_evaluable_sessions", 0),
            "total_users": _value(stats, "total_users", 0),
            "entries": [
                _serialize_leaderboard_entry(entry)
                for entry in _value(stats, "entries", [])
            ],
        }

        if issue_type is not None:
            response_payload["issue_type"] = issue_type

        issue_type_buckets = _value(stats, "issue_type_buckets")
        if issue_type_buckets is not None:
            response_payload["issue_type_buckets"] = issue_type_buckets

        if include_me:
            my_rank_result = await leaderboard_service.get_user_rank(
                **_supported_service_kwargs(
                    leaderboard_service.get_user_rank,
                    db=db,
                    user_id=current_user.user_id,
                    scenario_type=normalized_scenario_type,
                    time_period=normalized_time_period,
                    leaderboard_mode=normalized_leaderboard_mode,
                    issue_type=issue_type,
                )
            )
            if my_rank_result.is_success:
                response_payload["my_rank"] = _rank_payload_with_mode(
                    my_rank_result.value,
                    normalized_leaderboard_mode,
                    issue_type,
                )

        logger.info(
            "Leaderboard API response prepared",
            scenario_type=normalized_scenario_type,
            time_period=normalized_time_period,
            leaderboard_mode=normalized_leaderboard_mode,
            issue_type=issue_type,
            entries_count=len(response_payload["entries"]),
        )
        return response_payload

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get leaderboard: {str(e)}")
        return _server_error(
            "[LEADERBOARD_FETCH_FAILED]",
            "Failed to fetch leaderboard",
            exc=e,
        )


@router.get("/analytics/leaderboard/my-rank")
async def get_my_rank(
    scenario_type: str | None = None,
    time_period: str = "all_time",
    leaderboard_mode: str = Query("score"),
    issue_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's rank."""
    try:
        normalized_scenario_type = _normalize_scenario_type(scenario_type)
        normalized_time_period = _normalize_time_period(time_period)
        normalized_leaderboard_mode = _normalize_leaderboard_mode(leaderboard_mode)
        result = await leaderboard_service.get_user_rank(
            **_supported_service_kwargs(
                leaderboard_service.get_user_rank,
                db=db,
                user_id=current_user.user_id,
                scenario_type=normalized_scenario_type,
                time_period=normalized_time_period,
                leaderboard_mode=normalized_leaderboard_mode,
                issue_type=issue_type,
            )
        )

        if not result.is_success:
            return _server_error(
                "[LEADERBOARD_RANK_FETCH_FAILED]",
                "Failed to fetch rank",
                scenario_type=normalized_scenario_type,
                time_period=normalized_time_period,
                leaderboard_mode=normalized_leaderboard_mode,
                issue_type=issue_type,
            )

        return _rank_payload_with_mode(
            result.value,
            normalized_leaderboard_mode,
            issue_type,
        )

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get user rank: {str(e)}")
        return _server_error(
            "[LEADERBOARD_RANK_FETCH_FAILED]",
            "Failed to fetch rank",
            exc=e,
        )


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
            return _server_error(
                "[ANALYTICS_DASHBOARD_FETCH_FAILED]",
                "Failed to fetch dashboard stats",
                scenario_type=scenario_type,
                days=days,
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
            "effectiveness": {
                "pass_rate_3min_flow": stats.pass_rate_3min_flow,
                "pass_rate_5turn_defense": stats.pass_rate_5turn_defense,
                "pass_rate_4step_structure": stats.pass_rate_4step_structure,
                "next_day_retry_rate": stats.next_day_retry_rate,
            },
        }

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get dashboard stats: {str(e)}")
        return _server_error(
            "[ANALYTICS_DASHBOARD_FETCH_FAILED]",
            "Failed to fetch dashboard stats",
            exc=e,
        )


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
            return _server_error(
                "[ANALYTICS_DISTRIBUTION_FETCH_FAILED]",
                "Failed to fetch distribution",
                scenario_type=scenario_type,
                days=days,
            )

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
        return _server_error(
            "[ANALYTICS_DISTRIBUTION_FETCH_FAILED]",
            "Failed to fetch distribution",
            exc=e,
        )


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
            return _server_error(
                "[ANALYTICS_TREND_FETCH_FAILED]",
                "Failed to fetch trend data",
                scenario_type=scenario_type,
                days=days,
            )

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get trend data: {str(e)}")
        return _server_error(
            "[ANALYTICS_TREND_FETCH_FAILED]",
            "Failed to fetch trend data",
            exc=e,
        )


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
        normalized_scenario_type = _normalize_scenario_type(scenario_type)
        result = await history_service.get_user_history(
            db=db,
            user_id=current_user.user_id,
            scenario_type=normalized_scenario_type,
            limit=limit,
            offset=offset,
        )

        if not result.is_success:
            return _server_error(
                "[ANALYTICS_HISTORY_FETCH_FAILED]",
                "Failed to fetch history",
                scenario_type=normalized_scenario_type,
                limit=limit,
                offset=offset,
            )

        sessions = result.value

        items = [
            {
                "session_id": session.session_id,
                "scenario_id": session.scenario_id,
                "scenario_name": session.scenario_name,
                "scenario_type": session.scenario_type,
                "start_time": session.start_time.isoformat()
                if session.start_time
                else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": session.status,
                "overall_score": session.overall_score,
                "logic_score": session.logic_score,
                "accuracy_score": session.accuracy_score,
                "completeness_score": session.completeness_score,
                "duration_seconds": session.duration_seconds,
                "agent_name": session.agent_name,
                "persona_name": session.persona_name,
                "title": session.title,
                "effectiveness_snapshot": session.effectiveness_snapshot,
                "feedback_summary": session.feedback_summary,
                "evaluable": session.evaluable,
                "not_evaluable_reason": session.not_evaluable_reason,
                "evidence_completeness": session.evidence_completeness,
                "stage_summary": session.stage_summary,
                "main_issue": session.main_issue,
                "next_goal": session.next_goal,
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
        return _server_error(
            "[ANALYTICS_HISTORY_FETCH_FAILED]",
            "Failed to fetch history",
            exc=e,
        )


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
            return _server_error(
                "[PRACTICE_HISTORY_STATISTICS_FETCH_FAILED]",
                "Failed to fetch statistics",
            )

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get history statistics: {str(e)}")
        return _server_error(
            "[PRACTICE_HISTORY_STATISTICS_FETCH_FAILED]",
            "Failed to fetch statistics",
            exc=e,
        )


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
            return _server_error(
                "[PRACTICE_HISTORY_TRENDS_FETCH_FAILED]",
                "Failed to fetch trends",
                days=days,
            )

        return {"trends": result.value}

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get score trends: {str(e)}")
        return _server_error(
            "[PRACTICE_HISTORY_TRENDS_FETCH_FAILED]",
            "Failed to fetch trends",
            exc=e,
        )


# Storage stats endpoint (admin)
@router.get("/analytics/storage")
async def get_storage_stats(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audio storage statistics (admin only)"""
    try:
        # Role guard handled via get_current_admin_user dependency.
        result = await audio_archival_job.get_storage_stats(db=db)

        if not result.is_success:
            return _server_error(
                "[ANALYTICS_STORAGE_FETCH_FAILED]",
                "Failed to fetch storage stats",
            )

        return result.value

    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Failed to get storage stats: {str(e)}")
        return _server_error(
            "[ANALYTICS_STORAGE_FETCH_FAILED]",
            "Failed to fetch storage stats",
            exc=e,
        )
