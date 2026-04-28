"""
Admin Users API - User management endpoints for administrators

Implements CRUD operations for user management.

References:
- Requirements: 4.1, 4.2, 4.3, 4.4
- Design: Section "Admin Users API"
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.analytics.history_service import history_service
from common.auth.service import get_current_admin_user
from common.db.models import SystemLog, User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# Request schemas
class CreateUserRequest(BaseModel):
    """Request to create a new user"""
    username: str
    email: EmailStr
    password: str
    name: str | None = None
    department: str | None = None
    role: str = "user"  # user | admin
    audit_reason: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码至少需要8位")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码需要包含字母")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码需要包含数字")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"user", "support", "admin"}:
            raise ValueError("角色仅支持 user、support 或 admin")
        return v

    @field_validator("audit_reason")
    @classmethod
    def validate_audit_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if len(cleaned) > 500:
            raise ValueError("审计原因不能超过500个字符")
        return cleaned or None


class UpdateUserRequest(BaseModel):
    """Request to update user"""
    name: str | None = None
    email: EmailStr | None = None
    department: str | None = None
    role: str | None = None
    is_active: bool | None = None
    audit_reason: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in {"user", "support", "admin"}:
            raise ValueError("角色仅支持 user、support 或 admin")
        return v

    @field_validator("audit_reason")
    @classmethod
    def validate_audit_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if len(cleaned) > 500:
            raise ValueError("审计原因不能超过500个字符")
        return cleaned or None


class UpdateUserRoleRequest(BaseModel):
    """Request to update user role only."""
    role: str
    audit_reason: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("角色不能为空")
        return cleaned

    @field_validator("audit_reason")
    @classmethod
    def validate_audit_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if len(cleaned) > 500:
            raise ValueError("审计原因不能超过500个字符")
        return cleaned or None


class UserAuditReasonRequest(BaseModel):
    """Optional audit reason payload for account status actions."""
    audit_reason: str | None = None

    @field_validator("audit_reason")
    @classmethod
    def validate_audit_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if len(cleaned) > 500:
            raise ValueError("审计原因不能超过500个字符")
        return cleaned or None


# Response schemas
class AdminUserResponse(BaseModel):
    """User response for admin API"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    email: str | None
    role: str
    status: str
    last_active_at: str | None
    department: str | None
    created_at: str | None


class UserListResponse(BaseModel):
    """Paginated user list response"""
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


def success_response(data: Any, trace_id: str | None = None) -> dict:
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id()
    }


def error_response(error_code: str, message: str | None = None, trace_id: str | None = None) -> dict:
    """Create unified error response"""
    return {
        "success": False,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id()
    }


def _resolve_time_range_start(time_range: str) -> datetime:
    """Map supported time-range aliases to a UTC lower bound."""
    now = datetime.now(UTC)
    if time_range == "7d":
        return now - timedelta(days=7)
    if time_range == "30d":
        return now - timedelta(days=30)
    if time_range == "90d":
        return now - timedelta(days=90)
    return datetime(2000, 1, 1, tzinfo=UTC)


def user_to_response(user: User) -> AdminUserResponse:
    """Convert User model to AdminUserResponse"""
    return AdminUserResponse(
        id=str(user.user_id),
        username=user.name or "",
        display_name=user.name or user.email or "",
        email=user.email,
        role=getattr(user, 'role', 'user'),  # Use actual role field
        status="active" if user.is_active else "inactive",
        last_active_at=user.last_login.isoformat() if user.last_login else None,
        department=user.department,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


def _mask_email(email: str | None) -> str | None:
    """Mask email local-part for audit log safety."""
    if not email:
        return None

    if "@" not in email:
        return "***"

    local_part, domain_part = email.split("@", 1)
    if not local_part:
        return f"***@{domain_part}"

    visible_prefix = local_part[: min(2, len(local_part))]
    return f"{visible_prefix}***@{domain_part}"


def _user_audit_snapshot(user: User) -> dict[str, Any]:
    """Create a sanitized user snapshot suitable for audit details."""
    return {
        "user_id": str(user.user_id),
        "name": user.name,
        "email": _mask_email(user.email),
        "department": user.department,
        "role": user.role,
        "is_active": bool(user.is_active),
    }


def _normalize_audit_reason(reason: str | None) -> str:
    """Normalize optional audit reason to explicit text."""
    cleaned = (reason or "").strip()
    return cleaned if cleaned else "not-provided"


def _operator_identifier(user: User) -> str:
    """Pick a stable operator identifier for audit logs."""
    return user.email or user.name or str(user.user_id)


def _queue_user_audit_log(
    db: AsyncSession,
    *,
    action: str,
    operator: User,
    target_user_id: str,
    reason: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    ip_address: str | None,
) -> None:
    """Queue an audit log row in the current transaction."""
    details = {
        "operator_id": str(operator.user_id),
        "operator_email_masked": _mask_email(operator.email),
        "target_user_id": target_user_id,
        "reason": _normalize_audit_reason(reason),
        "timestamp": datetime.now(UTC).isoformat(),
        "before": before,
        "after": after,
    }

    db.add(
        SystemLog(
            action=action,
            user_id=str(operator.user_id),
            user_identifier=_operator_identifier(operator),
            ip_address=ip_address,
            status="success",
            details=json.dumps(details, ensure_ascii=False),
        )
    )


def _assert_role_transition_allowed(
    *,
    is_self: bool,
    current_role: str | None,
    new_role: str,
) -> None:
    """Validate caller-independent role transition guardrails."""
    if new_role not in {"user", "support", "admin"}:
        raise HTTPException(status_code=400, detail="[INVALID_ROLE]")

    if is_self and new_role != "admin":
        raise HTTPException(status_code=400, detail="[CANNOT_DOWNGRADE_SELF]")


_ROW_LOCKING_DIALECTS = frozenset({"postgresql", "mysql", "mariadb", "oracle"})


def _requires_last_admin_guard(*, current_role: str | None, new_role: str) -> bool:
    """Return whether a role transition could remove an active administrator."""
    return current_role == "admin" and new_role != "admin"


def _dialect_supports_row_locks(dialect_name: str | None) -> bool:
    """Return whether SELECT ... FOR UPDATE can serialize the admin recount."""
    return (dialect_name or "").split("+", maxsplit=1)[0] in _ROW_LOCKING_DIALECTS


def _active_admin_recount_statement(*, lock_rows: bool):
    """Build the authoritative active-admin recount statement.

    Row locks are requested only for dialects that support them. SQLite ignores
    row-level locking, so tests document that limitation while the service still
    avoids stale caller-provided counts by recounting inside the active
    transaction immediately before mutation.
    """
    statement = select(User.user_id).where(
        User.role == "admin",
        User.is_active.is_(True),
    )
    return statement.with_for_update() if lock_rows else statement


def _session_dialect_name(db: AsyncSession) -> str:
    """Resolve the SQLAlchemy dialect name for guard capability checks."""
    bind = db.get_bind()
    return str(getattr(getattr(bind, "dialect", None), "name", "") or "unknown")


async def _count_active_admins_for_role_guard(db: AsyncSession) -> int:
    """Recount active admins in the current transaction, locking rows if possible."""
    dialect_name = _session_dialect_name(db)
    lock_rows = _dialect_supports_row_locks(dialect_name)
    result = await db.execute(_active_admin_recount_statement(lock_rows=lock_rows))

    if not lock_rows:
        logger.warning(
            "admin_last_admin_guard_row_lock_unavailable",
            dialect=dialect_name,
        )

    return len(result.scalars().all())


async def _assert_admin_demotion_keeps_active_admin(
    db: AsyncSession,
    *,
    current_role: str | None,
    new_role: str,
) -> None:
    """Reject admin demotion when the transaction-local recount sees no backup admin."""
    if not _requires_last_admin_guard(current_role=current_role, new_role=new_role):
        return

    if await _count_active_admins_for_role_guard(db) <= 1:
        raise HTTPException(status_code=400, detail="[CANNOT_REMOVE_LAST_ADMIN]")


@router.get("", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by name or email"),
    status: str | None = Query(None, description="Filter by status (active/inactive)"),
    role: str | None = Query(None, description="Filter by role"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get paginated user list with filtering

    Requirements: 4.1, 4.2, 4.3
    """
    # Build base query
    query = select(User)
    count_query = select(func.count()).select_from(User)

    # Apply search filter
    if search:
        search_filter = or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Apply status filter
    if status:
        is_active = status.lower() == "active"
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    # Note: role filter is handled at response level since User model doesn't have role field

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    # Convert to response format
    items = [user_to_response(u) for u in users]

    # Apply role filter at response level if needed
    if role:
        items = [item for item in items if item.role == role]

    response = UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total
    )

    return success_response(response.model_dump())


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get user details by ID"""
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    return success_response(user_to_response(user).model_dump())


@router.get("/{user_id}/stats", response_model=dict)
async def get_user_stats(
    user_id: str,
    time_range: str = Query("all_time", description="Time range: 7d, 30d, 90d, all_time"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get detailed statistics for a specific user

    Returns:
    - Total sessions, completed sessions, completion rate
    - Average score, best score, worst score
    - Total practice duration
    - Agent/Persona usage breakdown
    - Recent activity info
    """
    from sqlalchemy import case, distinct

    from agent.models import Agent, Persona
    from common.db.models import PracticeSession

    del current_user

    # Verify user exists
    user_result = await db.execute(select(User).where(User.user_id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    start_date = _resolve_time_range_start(time_range)
    projection_score_result = await history_service.get_projection_score_summary(
        db=db,
        user_id=uuid.UUID(user_id),
        cutoff_time=start_date,
    )
    if not projection_score_result.is_success:
        raise HTTPException(status_code=500, detail="[ADMIN_USER_STATS_FAILED]")
    projection_scores = projection_score_result.value

    # Session statistics that are still truthful from raw session rows.
    stats_query = select(
        func.count(PracticeSession.session_id).label("total_sessions"),
        func.sum(case((PracticeSession.status == "completed", 1), else_=0)).label("completed_sessions"),
        func.sum(PracticeSession.total_duration_seconds).label("total_duration"),
        func.max(PracticeSession.start_time).label("last_practice"),
        func.count(distinct(PracticeSession.agent_id)).label("unique_agents"),
        func.count(distinct(PracticeSession.persona_id)).label("unique_personas")
    ).where(
        PracticeSession.user_id == user_id,
        PracticeSession.start_time >= start_date
    )

    result = await db.execute(stats_query)
    row = result.one()

    total_sessions = row.total_sessions or 0
    completed_sessions = row.completed_sessions or 0
    completion_rate = round((completed_sessions / total_sessions * 100) if total_sessions > 0 else 0, 1)

    # Agent usage breakdown
    agent_usage_query = select(
        Agent.id,
        Agent.name,
        func.count(PracticeSession.session_id).label("count")
    ).join(
        PracticeSession, Agent.id == PracticeSession.agent_id
    ).where(
        PracticeSession.user_id == user_id,
        PracticeSession.start_time >= start_date
    ).group_by(Agent.id, Agent.name).order_by(func.count(PracticeSession.session_id).desc()).limit(5)

    agent_result = await db.execute(agent_usage_query)
    agent_usage = [{"agent_id": str(r.id), "name": r.name, "count": r.count} for r in agent_result.all()]

    # Persona usage breakdown
    persona_usage_query = select(
        Persona.id,
        Persona.name,
        func.count(PracticeSession.session_id).label("count")
    ).join(
        PracticeSession, Persona.id == PracticeSession.persona_id
    ).where(
        PracticeSession.user_id == user_id,
        PracticeSession.start_time >= start_date
    ).group_by(Persona.id, Persona.name).order_by(func.count(PracticeSession.session_id).desc()).limit(5)

    persona_result = await db.execute(persona_usage_query)
    persona_usage = [{"persona_id": str(r.id), "name": r.name, "count": r.count} for r in persona_result.all()]

    stats_data = {
        "user": user_to_response(user).model_dump(),
        "statistics": {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": completion_rate,
            "average_score": round(float(projection_scores["average_score"] or 0), 1),
            "best_score": round(float(projection_scores["best_score"] or 0), 1),
            "worst_score": round(float(projection_scores["worst_score"] or 0), 1),
            "evaluable_sessions": int(projection_scores.get("evaluable_sessions") or 0),
            "not_evaluable_sessions": int(
                projection_scores.get("not_evaluable_sessions") or 0
            ),
            "score_basis": str(
                projection_scores.get("score_basis") or "session_evidence_projection_evaluable_only"
            ),
            "total_duration_minutes": round((row.total_duration or 0) / 60, 1),
            "last_practice": row.last_practice.isoformat() if row.last_practice else None,
            "unique_agents_used": row.unique_agents or 0,
            "unique_personas_used": row.unique_personas or 0,
        },
        "agent_usage": agent_usage,
        "persona_usage": persona_usage,
    }

    return success_response(stats_data)


@router.get("/{user_id}/sessions", response_model=dict)
async def get_user_sessions(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    status: str | None = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get paginated practice sessions for a specific user

    Returns detailed session history including:
    - Session ID, start/end time, status, duration
    - Agent and Persona used
    - Projection-backed preview fields for completed rows
    """
    from collections import defaultdict

    from agent.models import Agent, Persona
    from common.conversation.models import ConversationMessage
    from common.conversation.session_evidence import SessionEvidenceService
    from common.db.models import PracticeSession, Scenario, SessionStatus

    del current_user

    # Verify user exists
    user_result = await db.execute(select(User).where(User.user_id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    # Build query
    query = select(
        PracticeSession,
        Agent.name.label("agent_name"),
        Persona.name.label("persona_name"),
        Scenario.name.label("scenario_name"),
        Scenario.scenario_type,
    ).outerjoin(
        Agent, PracticeSession.agent_id == Agent.id
    ).outerjoin(
        Persona, PracticeSession.persona_id == Persona.id
    ).outerjoin(
        Scenario, PracticeSession.scenario_id == Scenario.scenario_id
    ).where(PracticeSession.user_id == user_id)

    count_query = select(func.count()).select_from(PracticeSession).where(PracticeSession.user_id == user_id)

    if status:
        query = query.where(PracticeSession.status == status)
        count_query = count_query.where(PracticeSession.status == status)

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(PracticeSession.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    completed_session_ids = [
        str(row.PracticeSession.session_id)
        for row in rows
        if row.PracticeSession.status == SessionStatus.COMPLETED.value
    ]
    messages_by_session: dict[str, list[ConversationMessage]] = {}
    if completed_session_ids:
        messages_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id.in_(completed_session_ids))
            .order_by(
                ConversationMessage.session_id,
                ConversationMessage.turn_number,
                ConversationMessage.timestamp,
            )
        )
        grouped_messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        for message in messages_result.scalars().all():
            grouped_messages[str(message.session_id)].append(message)
        messages_by_session = dict(grouped_messages)

    projections_by_session = {
        session_id: SessionEvidenceService.build_projection(
            session=row.PracticeSession,
            messages=list(messages_by_session.get(session_id, [])),
        )
        for row in rows
        for session_id in [str(row.PracticeSession.session_id)]
        if row.PracticeSession.status == SessionStatus.COMPLETED.value
    }

    manager_intervention_results: list[dict[str, Any]] = []
    intervention_results_result = await history_service.get_manager_intervention_results(
        db=db,
        user_id=uuid.UUID(user_id),
    )
    if intervention_results_result.is_success:
        manager_intervention_results = intervention_results_result.value
    else:
        logger.warning(
            "admin_user_intervention_results_degraded",
            user_id=user_id,
            error=intervention_results_result.fallback,
        )

    sessions = []
    for row in rows:
        session = row.PracticeSession
        session_id = str(session.session_id)
        projection = projections_by_session.get(session_id)

        logic_score = projection.logic_score if projection else session.logic_score
        accuracy_score = projection.accuracy_score if projection else session.accuracy_score
        completeness_score = projection.completeness_score if projection else session.completeness_score
        overall_score = projection.overall_score if projection else None
        main_issue = projection.main_issue if projection else None
        next_goal = projection.next_goal if projection else None
        feedback_summary = None
        if isinstance(main_issue, dict):
            feedback_summary = main_issue.get("issue_text")
        if not feedback_summary and isinstance(next_goal, dict):
            feedback_summary = next_goal.get("goal_text")

        suggestions: list[str] = []
        if isinstance(main_issue, dict) and main_issue.get("issue_text"):
            suggestions.append(f"主问题：{main_issue['issue_text']}")
        if isinstance(next_goal, dict) and next_goal.get("goal_text"):
            suggestions.append(f"下一轮：{next_goal['goal_text']}")

        sessions.append({
            "session_id": session_id,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "duration_minutes": round((session.total_duration_seconds or 0) / 60, 1),
            "scenario_name": row.scenario_name,
            "scenario_type": row.scenario_type,
            "agent_name": row.agent_name,
            "persona_name": row.persona_name,
            "scores": {
                "logic": logic_score,
                "accuracy": accuracy_score,
                "completeness": completeness_score,
                "overall": overall_score,
            },
            "interruption_count": session.interruption_count or 0,
            "overall_result": projection.overall_result if projection else None,
            "evaluable": projection.evaluable if projection else None,
            "not_evaluable_reason": projection.not_evaluable_reason if projection else None,
            "evidence_completeness": projection.evidence_completeness if projection else None,
            "main_issue": main_issue,
            "next_goal": next_goal,
            "feedback_summary": feedback_summary,
            "suggestions": suggestions,
        })

    return success_response({
        "items": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
        "manager_intervention_results": manager_intervention_results,
    })


@router.get("/{user_id}/progress", response_model=dict)
async def get_user_progress(
    user_id: str,
    time_range: str = Query("30d", description="Time range: 7d, 30d, 90d, all_time"),
    granularity: str = Query("day", description="Granularity: day, week"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get user progress/improvement trend over time.

    Returns projection-backed score trends plus repeated blocker/next-goal buckets,
    not-evaluable counts, and a conservative focus recommendation.
    """
    del current_user

    # Verify user exists
    user_result = await db.execute(select(User).where(User.user_id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    normalized_granularity = granularity.lower()
    if normalized_granularity not in {"day", "week"}:
        raise HTTPException(status_code=400, detail="[INVALID_GRANULARITY]")

    start_date = _resolve_time_range_start(time_range)
    progress_result = await history_service.get_supervisor_progress_snapshot(
        db=db,
        user_id=uuid.UUID(user_id),
        cutoff_time=start_date,
        granularity=normalized_granularity,
    )
    if not progress_result.is_success:
        raise HTTPException(status_code=500, detail="[ADMIN_USER_PROGRESS_FAILED]")

    return success_response(progress_result.value)


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: str,
    request_context: Request,
    payload: UserAuditReasonRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Delete a user (soft delete by setting is_active=False)

    Requirements: 4.4
    """
    # Prevent self-deletion
    if str(current_user.user_id) == user_id:
        raise HTTPException(status_code=400, detail="[CANNOT_DELETE_SELF]")

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    # Soft delete - set is_active to False
    before_snapshot = _user_audit_snapshot(user)
    user.is_active = False
    after_snapshot = _user_audit_snapshot(user)
    _queue_user_audit_log(
        db,
        action="admin.user.deactivated",
        operator=current_user,
        target_user_id=user_id,
        reason=payload.audit_reason if payload else None,
        before=before_snapshot,
        after=after_snapshot,
        ip_address=request_context.client.host if request_context.client else None,
    )
    await db.commit()

    return success_response({"deleted": True})


@router.post("", response_model=dict)
async def create_user(
    payload: CreateUserRequest,
    request_context: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Create a new user

    Requirements: 4.1
    """
    # Check if email already exists
    existing = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="[EMAIL_ALREADY_EXISTS]")

    # Create new user
    new_user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_created_{uuid.uuid4().hex[:8]}",  # Placeholder for admin-created users
        name=payload.name or payload.username,
        email=payload.email,
        department=payload.department,
        role=payload.role,
        is_active=True,
        created_at=datetime.now(UTC)
    )

    db.add(new_user)
    await db.flush()
    _queue_user_audit_log(
        db,
        action="admin.user.created",
        operator=current_user,
        target_user_id=str(new_user.user_id),
        reason=payload.audit_reason,
        before=None,
        after=_user_audit_snapshot(new_user),
        ip_address=request_context.client.host if request_context.client else None,
    )
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"User created: {new_user.user_id} by admin {current_user.user_id}")

    return success_response(user_to_response(new_user).model_dump())


@router.put("/{user_id}", response_model=dict)
async def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    request_context: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Update user information

    Requirements: 4.2
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    if payload.role is not None:
        raise HTTPException(
            status_code=400,
            detail="[ROLE_UPDATE_REQUIRES_DEDICATED_ENDPOINT]",
        )

    is_self = str(current_user.user_id) == user_id
    before_snapshot = _user_audit_snapshot(user)

    # Prevent self deactivation
    if is_self and payload.is_active is False:
        raise HTTPException(status_code=400, detail="[CANNOT_DEACTIVATE_SELF]")

    # Check email uniqueness if changing
    if payload.email and payload.email != user.email:
        existing = await db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="[EMAIL_ALREADY_EXISTS]")
        user.email = payload.email

    # Update fields
    if payload.name is not None:
        user.name = payload.name
    if payload.department is not None:
        user.department = payload.department
    if payload.is_active is not None:
        user.is_active = payload.is_active

    after_snapshot = _user_audit_snapshot(user)
    _queue_user_audit_log(
        db,
        action="admin.user.updated",
        operator=current_user,
        target_user_id=user_id,
        reason=payload.audit_reason,
        before=before_snapshot,
        after=after_snapshot,
        ip_address=request_context.client.host if request_context.client else None,
    )

    await db.commit()
    await db.refresh(user)

    logger.info(f"User updated: {user_id} by admin {current_user.user_id}")

    return success_response(user_to_response(user).model_dump())


@router.put("/{user_id}/role", response_model=dict)
async def update_user_role(
    user_id: str,
    payload: UpdateUserRoleRequest,
    request_context: Request,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Update user role with dedicated RBAC and audit safeguards.
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    is_self = str(current_user.user_id) == user_id

    _assert_role_transition_allowed(
        is_self=is_self,
        current_role=user.role,
        new_role=payload.role,
    )
    await _assert_admin_demotion_keeps_active_admin(
        db,
        current_role=user.role,
        new_role=payload.role,
    )

    before_snapshot = _user_audit_snapshot(user)
    user.role = payload.role
    after_snapshot = _user_audit_snapshot(user)

    _queue_user_audit_log(
        db,
        action="admin.user.role.updated",
        operator=current_user,
        target_user_id=user_id,
        reason=payload.audit_reason,
        before=before_snapshot,
        after=after_snapshot,
        ip_address=request_context.client.host if request_context.client else None,
    )

    await db.commit()
    await db.refresh(user)

    logger.info(f"User role updated: {user_id} by admin {current_user.user_id}")

    return success_response(user_to_response(user).model_dump())


@router.post("/{user_id}/suspend", response_model=dict)
async def suspend_user(
    user_id: str,
    request_context: Request,
    payload: UserAuditReasonRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Suspend a user account

    Requirements: 4.3
    """
    # Prevent self-suspension
    if str(current_user.user_id) == user_id:
        raise HTTPException(status_code=400, detail="[CANNOT_SUSPEND_SELF]")

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    before_snapshot = _user_audit_snapshot(user)
    user.is_active = False
    after_snapshot = _user_audit_snapshot(user)
    _queue_user_audit_log(
        db,
        action="admin.user.suspended",
        operator=current_user,
        target_user_id=user_id,
        reason=payload.audit_reason if payload else None,
        before=before_snapshot,
        after=after_snapshot,
        ip_address=request_context.client.host if request_context.client else None,
    )
    await db.commit()

    logger.info(f"User suspended: {user_id} by admin {current_user.user_id}")

    return success_response({"suspended": True, "user_id": user_id})


@router.post("/{user_id}/activate", response_model=dict)
async def activate_user(
    user_id: str,
    request_context: Request,
    payload: UserAuditReasonRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Activate a suspended user account
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="[USER_NOT_FOUND]")

    before_snapshot = _user_audit_snapshot(user)
    user.is_active = True
    after_snapshot = _user_audit_snapshot(user)
    _queue_user_audit_log(
        db,
        action="admin.user.activated",
        operator=current_user,
        target_user_id=user_id,
        reason=payload.audit_reason if payload else None,
        before=before_snapshot,
        after=after_snapshot,
        ip_address=request_context.client.host if request_context.client else None,
    )
    await db.commit()

    logger.info(f"User activated: {user_id} by admin {current_user.user_id}")

    return success_response({"activated": True, "user_id": user_id})


@router.get("/export", response_class=StreamingResponse)
async def export_users(
    format: str = Query("csv", description="Export format: csv or json"),
    search: str | None = Query(None, description="Search filter"),
    status: str | None = Query(None, description="Status filter"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export users to CSV or JSON

    Requirements: 4.5
    """
    # Build query
    query = select(User)

    if search:
        search_filter = or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)

    if status:
        is_active = status.lower() == "active"
        query = query.where(User.is_active == is_active)

    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()

    # Convert to response format
    user_data = [user_to_response(u).model_dump() for u in users]

    if format.lower() == "json":
        # JSON export
        content = json.dumps(user_data, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=users_export.json"}
        )
    else:
        # CSV export
        output = io.StringIO()
        if user_data:
            writer = csv.DictWriter(output, fieldnames=user_data[0].keys())
            writer.writeheader()
            writer.writerows(user_data)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users_export.csv"}
        )
