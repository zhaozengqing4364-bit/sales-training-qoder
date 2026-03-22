"""Manager-lite intervention endpoints for closed-loop coaching."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import PracticeSession, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/interventions", tags=["admin-interventions"])


class ReminderRequest(BaseModel):
    user_id: str
    note: str | None = Field(default=None, max_length=500)


def success_response(data: Any, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id(),
    }


@router.get("/lists")
async def get_manager_lite_lists(
    time_range: str = Query("30d"),
    limit: int = Query(20, ge=1, le=100),
    inactive_days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return not-passed / inactive-streak / improving lists for manager follow-up."""

    del current_user  # guarded by admin dependency in main.py include_router

    now = datetime.now(UTC)
    range_map = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "all_time": 3650,
    }
    days = range_map.get(str(time_range), 30)
    cutoff = now - timedelta(days=days)

    rows = (
        await db.execute(
            select(
                PracticeSession.session_id,
                PracticeSession.user_id,
                PracticeSession.start_time,
                PracticeSession.effectiveness_snapshot,
                User.name,
                User.department,
            )
            .join(User, User.user_id == PracticeSession.user_id)
            .where(PracticeSession.status == "completed")
            .where(PracticeSession.start_time >= cutoff)
            .order_by(PracticeSession.start_time.desc())
            .limit(2000)
        )
    ).all()

    not_passed: list[dict[str, Any]] = []
    not_passed_users: set[str] = set()
    sessions_by_user: dict[str, list[tuple[datetime, bool]]] = {}

    for row in rows:
        user_id = str(row.user_id)
        snapshot = row.effectiveness_snapshot
        if not isinstance(snapshot, dict) or not bool(snapshot.get("evaluable", False)):
            continue

        overall_result = str(snapshot.get("overall_result") or "fail")
        passed = overall_result in {"pass", "strong_pass"}
        sessions_by_user.setdefault(user_id, []).append((row.start_time, passed))

        if not passed and len(not_passed) < limit:
            if user_id in not_passed_users:
                continue
            not_passed_users.add(user_id)
            not_passed.append(
                {
                    "user_id": user_id,
                    "user_name": row.name,
                    "department": row.department,
                    "overall_result": overall_result,
                    "session_id": str(row.session_id),
                    "session_start_time": row.start_time.isoformat(),
                }
            )

    last_session_rows = (
        await db.execute(
            select(
                PracticeSession.user_id,
                func.max(PracticeSession.start_time).label("last_session_at"),
                User.name,
                User.department,
            )
            .join(User, User.user_id == PracticeSession.user_id)
            .where(PracticeSession.status == "completed")
            .group_by(PracticeSession.user_id, User.name, User.department)
        )
    ).all()

    inactive_streak: list[dict[str, Any]] = []
    for row in last_session_rows:
        if not row.last_session_at:
            continue
        days_inactive = int((now - row.last_session_at).total_seconds() // 86400)
        if days_inactive >= inactive_days:
            inactive_streak.append(
                {
                    "user_id": str(row.user_id),
                    "user_name": row.name,
                    "department": row.department,
                    "last_session_at": row.last_session_at.isoformat(),
                    "inactive_days": days_inactive,
                }
            )
    inactive_streak.sort(key=lambda item: item["inactive_days"], reverse=True)
    inactive_streak = inactive_streak[:limit]

    improving: list[dict[str, Any]] = []
    for user_id, points in sessions_by_user.items():
        if len(points) < 4:
            continue
        points.sort(key=lambda item: item[0])
        middle = len(points) // 2
        baseline = points[:middle]
        current = points[middle:]
        if not baseline or not current:
            continue
        baseline_pass_rate = sum(1 for _, passed in baseline if passed) / len(baseline)
        current_pass_rate = sum(1 for _, passed in current if passed) / len(current)
        gain = current_pass_rate - baseline_pass_rate
        if gain <= 0:
            continue

        sample = next((row for row in rows if str(row.user_id) == user_id), None)
        improving.append(
            {
                "user_id": user_id,
                "user_name": sample.name if sample else user_id,
                "department": sample.department if sample else None,
                "pass_gain": round(gain * 100, 2),
                "baseline_pass_rate": round(baseline_pass_rate * 100, 2),
                "current_pass_rate": round(current_pass_rate * 100, 2),
            }
        )

    improving.sort(key=lambda item: item["pass_gain"], reverse=True)
    improving = improving[:limit]

    return success_response(
        {
            "not_passed": not_passed,
            "inactive_streak": inactive_streak,
            "improving": improving,
        }
    )


@router.post("/remind")
async def remind_user(
    payload: ReminderRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Log a manager reminder action (phase-1, no external IM integration)."""
    reminder_id = str(uuid.uuid4())
    logger.info(
        "manager_lite_reminder_logged",
        reminder_id=reminder_id,
        sender_user_id=str(current_user.user_id),
        target_user_id=payload.user_id,
        note=(payload.note or "").strip(),
    )
    return success_response(
        {
            "sent": True,
            "reminder_id": reminder_id,
            "user_id": payload.user_id,
        }
    )
