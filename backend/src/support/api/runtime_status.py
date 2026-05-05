"""Support runtime release-health API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.db.schemas import LinkedAssetChangeReference
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from support.services.runtime_status_service import RuntimeStatusService

logger = get_logger(__name__)

router = APIRouter(prefix="/support/runtime", tags=["support-runtime"])


def success_response(data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "trace_id": get_trace_id(),
    }


class SupportRuntimeKindSummary(BaseModel):
    kind: str
    count: int


class SupportRuntimeEvent(BaseModel):
    event_id: str
    category: str
    severity: str
    status: str
    source: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None


class SupportRuntimeAnomalySummary(BaseModel):
    blocking: list[SupportRuntimeKindSummary] = Field(default_factory=list)
    warning: list[SupportRuntimeKindSummary] = Field(default_factory=list)


class SupportRuntimeSessionHealth(BaseModel):
    active_sessions: int = 0
    total_sessions_window: int = 0
    completed_sessions_window: int = 0
    scoring_sessions: int = 0
    stuck_scoring_sessions: int = 0
    not_evaluable_completed_sessions_window: int = 0
    completion_rate: float = 0.0


class SupportRuntimeReleaseHealth(BaseModel):
    status: str
    blocking_count: int = 0
    warning_count: int = 0
    typed_anomaly_count: int = 0
    blocking_sessions_count: int = 0
    warning_sessions_count: int = 0
    supplemental_warning_log_count: int = 0


class SupportRuntimeOverviewData(BaseModel):
    generated_at: datetime
    window_hours: int
    session_health: SupportRuntimeSessionHealth
    release_health: SupportRuntimeReleaseHealth
    anomaly_summary: SupportRuntimeAnomalySummary


class SupportRuntimeFaultDiagnostics(BaseModel):
    model_config = ConfigDict(extra="allow")

    linked_asset_changes: list[LinkedAssetChangeReference] = Field(default_factory=list)
    runtime_events: list[SupportRuntimeEvent] = Field(default_factory=list)


class SupportRuntimeFaultItem(BaseModel):
    source: str
    severity: str
    kind: str
    summary: str
    detected_at: datetime | None = None
    session_id: str | None = None
    scenario_type: str | None = None
    session_status: str | None = None
    report_status: str | None = None
    diagnostics: SupportRuntimeFaultDiagnostics = Field(
        default_factory=SupportRuntimeFaultDiagnostics
    )


class SupportRuntimeFaultsData(BaseModel):
    generated_at: datetime
    items: list[SupportRuntimeFaultItem] = Field(default_factory=list)
    count: int = 0
    limit: int = 0
    severity: str | None = None


class SupportRuntimeOverviewEnvelope(BaseModel):
    success: bool = True
    data: SupportRuntimeOverviewData
    trace_id: str | None = None


class SupportRuntimeFaultsEnvelope(BaseModel):
    success: bool = True
    data: SupportRuntimeFaultsData
    trace_id: str | None = None


@router.get("/overview", response_model=SupportRuntimeOverviewEnvelope)
async def get_runtime_overview(
    window_hours: int = Query(
        24, ge=1, le=168, description="Rolling time window in hours"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        payload = await RuntimeStatusService(db).get_overview(window_hours=window_hours)
    except Exception as exc:
        logger.warning(f"runtime overview computation failed: {exc}")
        return JSONResponse(
            status_code=503,
            content=error_response(
                "[RUNTIME_STATUS_UNAVAILABLE]",
                message="runtime status is degraded",
            )
            | {
                "degraded": True,
                "data": jsonable_encoder(
                    SupportRuntimeOverviewData(
                    generated_at=datetime.now(UTC),
                    window_hours=window_hours,
                    session_health=SupportRuntimeSessionHealth(),
                    release_health=SupportRuntimeReleaseHealth(status="degraded"),
                    anomaly_summary=SupportRuntimeAnomalySummary(),
                )
                ),
            },
        )
    return success_response(payload)


@router.get("/faults", response_model=SupportRuntimeFaultsEnvelope)
async def get_fault_summaries(
    limit: int = Query(20, ge=1, le=100, description="Max fault items"),
    severity: str | None = Query(
        None,
        description="Optional severity filter: blocking|warning",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    allowed_severities = {"blocking", "warning"}
    if severity is not None and severity not in allowed_severities:
        raise HTTPException(status_code=400, detail="[INVALID_SEVERITY_FILTER]")

    try:
        payload = await RuntimeStatusService(db).get_faults(
            limit=limit,
            severity=severity,
        )
    except Exception as exc:
        logger.warning(f"runtime faults computation failed: {exc}")
        return JSONResponse(
            status_code=503,
            content=error_response(
                "[RUNTIME_STATUS_UNAVAILABLE]",
                message="runtime status is degraded",
            )
            | {
                "degraded": True,
                "data": jsonable_encoder(
                    SupportRuntimeFaultsData(
                    generated_at=datetime.now(UTC),
                    items=[],
                    count=0,
                    limit=limit,
                    severity=severity,
                )
                ),
            },
        )
    return success_response(payload)
