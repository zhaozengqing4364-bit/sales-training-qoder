"""Support runtime release-health API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from support.services.runtime_status_service import RuntimeStatusService

router = APIRouter(prefix="/support/runtime", tags=["support-runtime"])


def success_response(data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "trace_id": get_trace_id(),
    }


@router.get("/overview", response_model=dict)
async def get_runtime_overview(
    window_hours: int = Query(24, ge=1, le=168, description="Rolling time window in hours"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    payload = await RuntimeStatusService(db).get_overview(window_hours=window_hours)
    return success_response(payload)


@router.get("/faults", response_model=dict)
async def get_fault_summaries(
    limit: int = Query(20, ge=1, le=100, description="Max fault items"),
    severity: str | None = Query(
        None,
        description="Optional severity filter: blocking|warning",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    allowed_severities = {"blocking", "warning"}
    if severity is not None and severity not in allowed_severities:
        raise HTTPException(status_code=400, detail="[INVALID_SEVERITY_FILTER]")

    payload = await RuntimeStatusService(db).get_faults(
        limit=limit,
        severity=severity,
    )
    return success_response(payload)
