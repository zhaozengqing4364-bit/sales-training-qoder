"""Manager-lite intervention endpoints for closed-loop coaching."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import ManagerIntervention, PracticeSession, User
from common.db.schemas import (
    ManagerInterventionCreate,
    ManagerInterventionDueState,
    ManagerInterventionListResponse,
    ManagerInterventionReminderRequest,
    ManagerInterventionReminderStatus,
    ManagerInterventionResponse,
    ManagerInterventionUpdate,
)
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/interventions", tags=["admin-interventions"])


def success_response(data: Any, trace_id: str | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id(),
    }


def _serialize_intervention(intervention: ManagerIntervention) -> dict[str, Any]:
    return ManagerInterventionResponse.model_validate(intervention).model_dump(mode="json")


async def _get_target_user(*, db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")
    return user


async def _get_intervention(*, db: AsyncSession, intervention_id: str) -> ManagerIntervention:
    intervention = await db.get(ManagerIntervention, intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="[INTERVENTION_NOT_FOUND]")
    return intervention


async def _validate_resolving_session(
    *,
    db: AsyncSession,
    intervention_user_id: str,
    resolving_session_id: str,
) -> None:
    session = await db.get(PracticeSession, resolving_session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="[INTERVENTION_RESOLVING_SESSION_NOT_FOUND]",
        )
    if str(session.user_id) != intervention_user_id:
        raise HTTPException(
            status_code=400,
            detail="[INTERVENTION_RESOLVING_SESSION_USER_MISMATCH]",
        )


async def _latest_open_intervention_for_user(
    *,
    db: AsyncSession,
    user_id: str,
) -> ManagerIntervention | None:
    result = await db.execute(
        select(ManagerIntervention)
        .where(
            ManagerIntervention.user_id == user_id,
            ManagerIntervention.due_state != ManagerInterventionDueState.RESOLVED.value,
        )
        .order_by(ManagerIntervention.updated_at.desc(), ManagerIntervention.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _normalize_state(
    *,
    due_state: str,
    reminder_status: str,
    resolving_session_id: str | None,
) -> tuple[str, str, datetime | None]:
    if resolving_session_id:
        return (
            ManagerInterventionDueState.RESOLVED.value,
            reminder_status,
            None if reminder_status == ManagerInterventionReminderStatus.NOT_SENT.value else datetime.now(UTC),
        )

    if due_state == ManagerInterventionDueState.RESOLVED.value:
        raise HTTPException(
            status_code=400,
            detail="[INTERVENTION_RESOLVING_SESSION_REQUIRED]",
        )

    normalized_due_state = due_state
    reminder_sent_at: datetime | None = None
    if reminder_status == ManagerInterventionReminderStatus.SENT.value:
        reminder_sent_at = datetime.now(UTC)
        if normalized_due_state == ManagerInterventionDueState.PENDING.value:
            normalized_due_state = ManagerInterventionDueState.DUE.value

    return normalized_due_state, reminder_status, reminder_sent_at


@router.get("/lists")
async def get_manager_lite_lists(
    time_range: str = Query("30d"),
    limit: int = Query(20, ge=1, le=100),
    inactive_days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return not-passed / inactive-streak / improving lists for manager follow-up."""

    del current_user

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


@router.get("")
async def list_manager_interventions(
    user_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List persisted manager interventions, optionally scoped to one learner."""

    del current_user

    query = select(ManagerIntervention)
    count_query = select(func.count()).select_from(ManagerIntervention)
    if user_id:
        await _get_target_user(db=db, user_id=user_id)
        query = query.where(ManagerIntervention.user_id == user_id)
        count_query = count_query.where(ManagerIntervention.user_id == user_id)

    query = query.order_by(ManagerIntervention.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    total = (await db.execute(count_query)).scalar() or 0

    response = ManagerInterventionListResponse(
        items=[ManagerInterventionResponse.model_validate(row) for row in rows],
        total=int(total),
    )
    return success_response(response.model_dump(mode="json"))


@router.post("")
async def create_manager_intervention(
    payload: ManagerInterventionCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a minimal manager intervention record tied to the current admin chain."""

    target_user_id = str(payload.user_id)
    await _get_target_user(db=db, user_id=target_user_id)

    resolving_session_id = (
        str(payload.resolving_session_id) if payload.resolving_session_id is not None else None
    )
    if resolving_session_id:
        await _validate_resolving_session(
            db=db,
            intervention_user_id=target_user_id,
            resolving_session_id=resolving_session_id,
        )

    due_state, reminder_status, reminder_sent_at = _normalize_state(
        due_state=payload.due_state.value,
        reminder_status=payload.reminder_status.value,
        resolving_session_id=resolving_session_id,
    )

    intervention = ManagerIntervention(
        manager_user_id=str(current_user.user_id),
        user_id=target_user_id,
        issue_family=payload.issue_family,
        note=payload.note,
        due_state=due_state,
        reminder_status=reminder_status,
        reminder_sent_at=reminder_sent_at,
        resolving_session_id=resolving_session_id,
    )
    db.add(intervention)
    await db.commit()
    await db.refresh(intervention)

    logger.info(
        "manager_intervention_created",
        intervention_id=str(intervention.intervention_id),
        manager_user_id=str(current_user.user_id),
        target_user_id=target_user_id,
        issue_family=intervention.issue_family,
        due_state=intervention.due_state,
    )

    return success_response(_serialize_intervention(intervention))


@router.patch("/{intervention_id}")
async def update_manager_intervention(
    intervention_id: str,
    payload: ManagerInterventionUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update intervention lifecycle fields without introducing a new task system."""

    del current_user

    intervention = await _get_intervention(db=db, intervention_id=intervention_id)
    fields_set = set(payload.model_fields_set)
    if not fields_set:
        raise HTTPException(status_code=400, detail="[INTERVENTION_EMPTY_UPDATE]")

    if "note" in fields_set:
        intervention.note = payload.note

    if "reminder_status" in fields_set:
        intervention.reminder_status = payload.reminder_status.value
        if payload.reminder_status == ManagerInterventionReminderStatus.SENT:
            intervention.reminder_sent_at = datetime.now(UTC)
        else:
            intervention.reminder_sent_at = None

    if "resolving_session_id" in fields_set:
        intervention.resolving_session_id = (
            str(payload.resolving_session_id)
            if payload.resolving_session_id is not None
            else None
        )
        if intervention.resolving_session_id:
            await _validate_resolving_session(
                db=db,
                intervention_user_id=str(intervention.user_id),
                resolving_session_id=str(intervention.resolving_session_id),
            )

    requested_due_state = (
        payload.due_state.value if payload.due_state is not None else intervention.due_state
    )
    due_state, reminder_status, reminder_sent_at = _normalize_state(
        due_state=requested_due_state,
        reminder_status=str(intervention.reminder_status),
        resolving_session_id=(
            str(intervention.resolving_session_id)
            if intervention.resolving_session_id is not None
            else None
        ),
    )
    intervention.due_state = due_state
    intervention.reminder_status = reminder_status
    if reminder_sent_at is not None:
        intervention.reminder_sent_at = reminder_sent_at
    intervention.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(intervention)

    return success_response(_serialize_intervention(intervention))


@router.post("/remind")
async def remind_user(
    payload: ManagerInterventionReminderRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Log a manager reminder and update the current intervention when one exists."""
    target_user_id = str(payload.user_id)
    await _get_target_user(db=db, user_id=target_user_id)

    reminder_id = str(uuid.uuid4())
    intervention: ManagerIntervention | None = None
    if payload.intervention_id is not None:
        intervention = await _get_intervention(
            db=db,
            intervention_id=str(payload.intervention_id),
        )
        if str(intervention.user_id) != target_user_id:
            raise HTTPException(status_code=400, detail="[INTERVENTION_USER_MISMATCH]")
    else:
        intervention = await _latest_open_intervention_for_user(db=db, user_id=target_user_id)

    if intervention is not None:
        if payload.note is not None:
            intervention.note = payload.note
        intervention.reminder_status = ManagerInterventionReminderStatus.SENT.value
        intervention.reminder_sent_at = datetime.now(UTC)
        if intervention.due_state != ManagerInterventionDueState.RESOLVED.value:
            intervention.due_state = ManagerInterventionDueState.DUE.value
        intervention.updated_at = datetime.now(UTC)
        await db.commit()

    logger.info(
        "manager_lite_reminder_logged",
        reminder_id=reminder_id,
        intervention_id=(
            str(intervention.intervention_id) if intervention is not None else None
        ),
        sender_user_id=str(current_user.user_id),
        target_user_id=target_user_id,
        note=(payload.note or "").strip(),
    )
    return success_response(
        {
            "sent": True,
            "reminder_id": reminder_id,
            "user_id": target_user_id,
            "intervention_id": (
                str(intervention.intervention_id) if intervention is not None else None
            ),
        }
    )
