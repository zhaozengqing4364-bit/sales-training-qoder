"""
Support Runtime Status API - Read-only runtime health and fault visibility.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, SystemLog
from common.db.session import get_db
from common.monitoring.logger import get_trace_id

router = APIRouter(prefix="/support/runtime", tags=["support-runtime"])


def success_response(data: Any) -> dict[str, Any]:
    """Create unified success response."""
    return {
        "success": True,
        "data": data,
        "trace_id": get_trace_id(),
    }


def _parse_log_details(details: Any) -> dict[str, Any] | str | None:
    """Normalize stored log details into a safe read-only payload."""
    if details is None:
        return None
    if isinstance(details, dict):
        return details
    if isinstance(details, str):
        try:
            parsed = json.loads(details)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return details
        return details
    return str(details)


@router.get("/overview", response_model=dict)
async def get_runtime_overview(
    window_hours: int = Query(24, ge=1, le=168, description="Rolling time window in hours"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get support runtime overview in read-only mode."""
    window_start = datetime.now(UTC) - timedelta(hours=window_hours)

    active_statuses = ("preparing", "in_progress", "paused")
    completed_statuses = ("completed", "scoring")

    active_sessions_result = await db.execute(
        select(func.count())
        .select_from(PracticeSession)
        .where(PracticeSession.status.in_(active_statuses))
    )
    active_sessions = int(active_sessions_result.scalar() or 0)

    total_sessions_result = await db.execute(
        select(func.count())
        .select_from(PracticeSession)
        .where(PracticeSession.start_time >= window_start)
    )
    total_sessions_window = int(total_sessions_result.scalar() or 0)

    completed_sessions_result = await db.execute(
        select(func.count())
        .select_from(PracticeSession)
        .where(
            PracticeSession.start_time >= window_start,
            PracticeSession.status.in_(completed_statuses),
        )
    )
    completed_sessions_window = int(completed_sessions_result.scalar() or 0)

    fault_logs_result = await db.execute(
        select(func.count())
        .select_from(SystemLog)
        .where(
            SystemLog.created_at >= window_start,
            SystemLog.status.in_(("failed", "warning")),
        )
    )
    fault_log_count = int(fault_logs_result.scalar() or 0)

    completion_rate = (
        round((completed_sessions_window / total_sessions_window) * 100, 2)
        if total_sessions_window > 0
        else 0.0
    )

    return success_response(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "window_hours": window_hours,
            "session_health": {
                "active_sessions": active_sessions,
                "total_sessions_window": total_sessions_window,
                "completed_sessions_window": completed_sessions_window,
                "completion_rate": completion_rate,
            },
            "fault_health": {
                "failed_or_warning_logs_window": fault_log_count,
            },
        }
    )


@router.get("/faults", response_model=dict)
async def get_fault_summaries(
    limit: int = Query(20, ge=1, le=100, description="Max fault items"),
    status: str | None = Query(None, description="Optional status filter: failed|warning"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get recent fault summaries in read-only mode."""
    allowed_statuses = {"failed", "warning"}
    if status is not None and status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="[INVALID_STATUS_FILTER]")

    query = select(SystemLog)
    if status:
        query = query.where(SystemLog.status == status)
    else:
        query = query.where(SystemLog.status.in_(("failed", "warning")))

    query = query.order_by(SystemLog.created_at.desc()).limit(limit)
    rows = await db.execute(query)
    logs = rows.scalars().all()

    items = [
        {
            "log_id": str(log.log_id),
            "action": log.action,
            "status": log.status,
            "user_identifier": log.user_identifier,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "details": _parse_log_details(log.details),
        }
        for log in logs
    ]

    return success_response(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "items": items,
            "count": len(items),
            "limit": limit,
        }
    )
