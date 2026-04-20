"""
Admin System Logs API - System audit log endpoints for administrators

Implements read operations for system audit logs.

References:
- Requirements: 7.1, 7.2, 7.3
- Design: Section "System Logs API"
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_admin_user
from common.db.models import SystemLog, User
from common.db.session import get_db
from common.monitoring.logger import (
    ADMIN_LOG_ALLOWLIST_FIELDS,
    ADMIN_LOG_DENYLIST_FIELDS,
    ADMIN_LOG_DIAGNOSTIC_FIELDS,
    ADMIN_LOG_REDACTION_SUMMARY,
    SYSTEM_LOG_ADMIN_POLICY_VERSION,
    build_admin_log_diagnostics,
    extract_admin_log_context,
    get_logger,
    get_trace_id,
    mask_ip_address_for_admin,
    mask_user_identifier_for_admin,
    summarize_admin_log_details,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/system-logs", tags=["admin-system-logs"])


class SystemLogExposurePolicy(BaseModel):
    """Shared support/admin visibility policy for audit logs."""

    version: str
    visible_fields: list[str]
    internal_only_fields: list[str]
    redaction_summary: str
    diagnostic_fields: list[str]


class SystemLogDiagnosticItem(BaseModel):
    """Ordered audience-safe diagnostic field rendered by admin/support surfaces."""

    key: str
    value: str


# Response schemas
class SystemLogResponse(BaseModel):
    """System log response for admin API"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    user_identifier: str
    ip_address: str | None
    status: str
    created_at: str
    details: str | None = None
    diagnostics: list[SystemLogDiagnosticItem] = Field(default_factory=list)
    trace_id: str | None = None
    error_code: str | None = None
    phase: str | None = None
    session_id: str | None = None


class SystemLogListResponse(BaseModel):
    """Paginated system log list response"""

    items: list[SystemLogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
    policy: SystemLogExposurePolicy


def success_response(data: Any, trace_id: str | None = None) -> dict:
    """Create unified success response"""
    return {
        "success": True,
        "data": data,
        "trace_id": trace_id or get_trace_id(),
    }


def build_system_log_exposure_policy() -> SystemLogExposurePolicy:
    return SystemLogExposurePolicy(
        version=SYSTEM_LOG_ADMIN_POLICY_VERSION,
        visible_fields=list(ADMIN_LOG_ALLOWLIST_FIELDS),
        internal_only_fields=list(ADMIN_LOG_DENYLIST_FIELDS),
        redaction_summary=ADMIN_LOG_REDACTION_SUMMARY,
        diagnostic_fields=list(ADMIN_LOG_DIAGNOSTIC_FIELDS),
    )


def log_to_response(log: SystemLog) -> SystemLogResponse:
    """Convert SystemLog model to the admin/support-safe response contract."""
    context = extract_admin_log_context(log.details)
    diagnostics = [SystemLogDiagnosticItem(**item) for item in build_admin_log_diagnostics(log.details)]
    return SystemLogResponse(
        id=str(log.log_id),
        action=log.action,
        user_identifier=mask_user_identifier_for_admin(log.user_identifier),
        ip_address=mask_ip_address_for_admin(log.ip_address),
        status=log.status,
        created_at=log.created_at.isoformat() if log.created_at else "",
        details=summarize_admin_log_details(log.details),
        diagnostics=diagnostics,
        trace_id=context.get("trace_id"),
        error_code=context.get("error_code"),
        phase=context.get("phase"),
        session_id=context.get("session_id"),
    )


@router.get("", response_model=dict)
async def list_system_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by action or user"),
    status: str | None = Query(None, description="Filter by status (success/failed/warning)"),
    action: str | None = Query(None, description="Filter by action type"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get paginated system logs with filtering

    Requirements: 7.1, 7.2
    """
    _ = current_user

    # Build base query
    query = select(SystemLog)
    count_query = select(func.count()).select_from(SystemLog)

    # Apply search filter
    if search:
        search_filter = or_(
            SystemLog.action.ilike(f"%{search}%"),
            SystemLog.user_identifier.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Apply status filter
    if status:
        query = query.where(SystemLog.status == status)
        count_query = count_query.where(SystemLog.status == status)

    # Apply action filter
    if action:
        query = query.where(SystemLog.action == action)
        count_query = count_query.where(SystemLog.action == action)

    # Get total count
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering (newest first)
    query = query.order_by(SystemLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    logs = result.scalars().all()

    # Convert to response format
    items = [log_to_response(log) for log in logs]

    response = SystemLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
        policy=build_system_log_exposure_policy(),
    )

    return success_response(response.model_dump())


@router.get("/{log_id}", response_model=dict)
async def get_system_log(
    log_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get system log details by ID"""
    _ = current_user

    result = await db.execute(select(SystemLog).where(SystemLog.log_id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="[SYSTEM_LOG_NOT_FOUND]")

    payload = log_to_response(log).model_dump()
    payload["policy"] = build_system_log_exposure_policy().model_dump()
    return success_response(payload)


# Utility function to create system logs (for use by other modules)
async def create_system_log(
    db: AsyncSession,
    action: str,
    user_identifier: str,
    status: str = "success",
    user_id: str | None = None,
    ip_address: str | None = None,
    details: str | None = None,
) -> SystemLog:
    """
    Create a new system log entry

    This function can be called from other modules to log system events.
    """
    import uuid

    log = SystemLog(
        log_id=str(uuid.uuid4()),
        action=action,
        user_id=user_id,
        user_identifier=user_identifier,
        ip_address=ip_address,
        status=status,
        details=details,
        created_at=datetime.now(UTC),
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return log
