"""Unified audit trail API — aggregates ConfigBundleAuditLog, BusinessRuleConfigAuditLog, and SystemLog."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, literal, literal_column, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.permissions import CONFIG_AUDIT_READ_PERMISSION, require_admin_permission
from common.api.response import success_response
from common.db.models import (
    BusinessRuleConfigAuditLog,
    ConfigBundleAuditLog,
    SystemLog,
    User,
)
from common.db.session import get_db

router = APIRouter(prefix="/audit-trail", tags=["admin-audit-trail"])


class AuditTrailItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    source: str
    timestamp: str
    actor: str | None = None
    action: str
    domain: str | None = None
    config_key: str
    version: int | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    trace_id: str | None = None


class AuditTrailListResponse(BaseModel):
    items: list[AuditTrailItem]
    total: int
    page: int
    page_size: int
    has_more: bool


def _build_audit_union():
    cbal = ConfigBundleAuditLog.__table__
    brcal = BusinessRuleConfigAuditLog.__table__
    sl = SystemLog.__table__

    q1 = select(
        cbal.c.id.label("audit_id"),
        literal("config_bundle").label("source"),
        cbal.c.bundle_key.label("config_key"),
        cbal.c.action,
        cbal.c.actor_id.label("actor"),
        literal(None).label("domain"),
        cbal.c.before_version.label("version"),
        cbal.c.before_snapshot.label("before_state"),
        cbal.c.after_snapshot.label("after_state"),
        cbal.c.reason,
        cbal.c.trace_id,
        cbal.c.created_at.label("ts"),
    )

    q2 = select(
        brcal.c.id.label("audit_id"),
        literal("business_rule_config").label("source"),
        brcal.c.config_key.label("config_key"),
        brcal.c.action,
        brcal.c.actor_id.label("actor"),
        brcal.c.domain.label("domain"),
        brcal.c.after_version.label("version"),
        brcal.c.before_snapshot.label("before_state"),
        brcal.c.after_snapshot.label("after_state"),
        brcal.c.reason,
        brcal.c.trace_id,
        brcal.c.created_at.label("ts"),
    )

    q3 = select(
        sl.c.log_id.label("audit_id"),
        literal("system_log").label("source"),
        sl.c.action.label("config_key"),
        sl.c.action,
        # prefer user_identifier as actor since system_log actor_id is
        # the same FK label used in bundle/rule audit rows
        sl.c.user_identifier.label("actor"),
        literal(None).label("domain"),
        literal(None).label("version"),
        literal_column("NULL").label("before_state"),
        literal_column("NULL").label("after_state"),
        literal(None).label("reason"),
        literal_column("NULL").label("trace_id"),
        sl.c.created_at.label("ts"),
    )

    return union_all(q1, q2, q3)


def _row_to_item(row) -> AuditTrailItem:
    ts = row.ts
    if isinstance(ts, datetime):
        ts_str = ts.isoformat()
    elif isinstance(ts, str):
        ts_str = ts
    else:
        ts_str = str(ts)

    before = row.before_state
    if isinstance(before, str):
        import json

        try:
            before = json.loads(before)
        except (json.JSONDecodeError, TypeError):
            pass

    after = row.after_state
    if isinstance(after, str):
        import json

        try:
            after = json.loads(after)
        except (json.JSONDecodeError, TypeError):
            pass

    version = row.version
    if version is not None:
        try:
            version = int(version)
        except (TypeError, ValueError):
            pass

    return AuditTrailItem(
        audit_id=str(row.audit_id),
        source=str(row.source),
        timestamp=ts_str,
        actor=str(row.actor) if row.actor is not None else None,
        action=str(row.action) if row.action else "",
        domain=str(row.domain) if row.domain is not None else None,
        config_key=str(row.config_key) if row.config_key else "",
        version=version,
        before=before if before is not None else None,
        after=after if after is not None else None,
        reason=str(row.reason) if row.reason is not None else None,
        trace_id=str(row.trace_id) if row.trace_id is not None else None,
    )


@router.get("")
async def list_audit_trail(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    domain: str | None = Query(None, description="Filter by domain"),
    action: str | None = Query(None, description="Filter by action"),
    actor: str | None = Query(None, description="Filter by actor user_id"),
    from_date: str | None = Query(None, description="ISO date filter start"),
    to_date: str | None = Query(None, description="ISO date filter end"),
    current_user: User = Depends(require_admin_permission(CONFIG_AUDIT_READ_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user

    base = _build_audit_union().alias("audit_base")
    outer = select(base.c)
    count_query = select(func.count()).select_from(base)

    if domain:
        outer = outer.where(base.c.domain == domain)
        count_query = count_query.where(base.c.domain == domain)

    if action:
        outer = outer.where(base.c.action == action)
        count_query = count_query.where(base.c.action == action)

    if actor:
        outer = outer.where(base.c.actor == actor)
        count_query = count_query.where(base.c.actor == actor)

    if from_date:
        outer = outer.where(base.c.ts >= from_date)
        count_query = count_query.where(base.c.ts >= from_date)

    if to_date:
        outer = outer.where(base.c.ts <= to_date)
        count_query = count_query.where(base.c.ts <= to_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    outer = outer.order_by(base.c.ts.desc())
    outer = outer.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(outer)
    rows = result.all()

    items = [_row_to_item(row) for row in rows]

    response = AuditTrailListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )

    return success_response(response.model_dump())
