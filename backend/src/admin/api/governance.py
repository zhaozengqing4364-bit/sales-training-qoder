"""Read-only admin governance inventory surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_admin_user
from common.db.models import (
    EvaluationRun,
    PracticeSession,
    Scenario,
    TrainingReportSnapshot,
    User,
)
from common.db.session import get_db

from .security_inventory import (
    ADMIN_PERMISSION_POSITIVE_CONTROL,
    ADMIN_ROUTE_PERMISSION_MATRIX,
    ADMIN_SUPPORT_BACKEND_ONLY_FIELDS,
    ADMIN_SUPPORT_DIAGNOSTIC_ALLOWLIST,
    ADMIN_SUPPORT_LOG_REDACTION_GUIDANCE,
    ADMIN_SUPPORT_LOG_VISIBLE_FIELDS,
    FIX_FIRST_ADMIN_ROUTE_FAMILIES,
    M021_QUALITY_EVENT_ADMIN_SUPPORT_PREREQUISITE,
)

router = APIRouter(
    prefix="/governance",
    tags=["admin-governance"],
    dependencies=[Depends(get_current_admin_user)],
)

ai_governance_router = APIRouter(
    prefix="/ai-governance",
    tags=["admin-ai-governance"],
    dependencies=[Depends(get_current_admin_user)],
)

SETTINGS_GOVERNANCE_BACKLOG: tuple[dict[str, Any], ...] = (
    {
        "surface": "general",
        "label": "常规设置",
        "status": "persisted",
        "missing_capabilities": (),
        "fallback_policy": "managed by /api/v1/admin/settings/general with bundled safe defaults",
    },
    {
        "surface": "security",
        "label": "安全与访问",
        "status": "persisted",
        "missing_capabilities": (
            "runtime enforcement remains code-owned until each security policy is explicitly wired",
        ),
        "fallback_policy": "managed by /api/v1/admin/settings/security; runtime security baseline stays code-owned",
    },
    {
        "surface": "notifications",
        "label": "通知设置",
        "status": "persisted",
        "missing_capabilities": (
            "delivered notification jobs must explicitly consume the governed config before enabling new sends",
        ),
        "fallback_policy": "managed by /api/v1/admin/settings/notifications with disabled-state metadata",
    },
    {
        "surface": "models",
        "label": "模型配置",
        "status": "persisted",
        "missing_capabilities": (),
        "fallback_policy": "managed by /api/v1/admin/model-configs with admin guard",
    },
)


def _permission_entry_payload(entry: Any) -> dict[str, Any]:
    return {
        "route_family": entry.route_family,
        "auth_surface": entry.auth_surface,
        "routes": list(entry.routes),
        "allowed_roles": list(entry.allowed_roles),
        "non_admin_deny_path": entry.non_admin_deny_path,
        "current_evidence": list(entry.current_evidence),
        "risk": entry.risk,
        "priority": entry.priority,
        "rationale": entry.rationale,
    }


def _iso_datetime(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _explainability_error(
    *,
    session_id: str,
    missing: list[str],
) -> JSONResponse:
    payload = error_response(
        "[AI_GOVERNANCE_EXPLAINABILITY_INCOMPLETE]",
        message="AI governance explainability lineage is incomplete for this session.",
    )
    payload["data"] = {
        "session_id": session_id,
        "missing": missing,
        "guidance": "Regenerate or backfill the EvaluationRun and TrainingReportSnapshot lineage before displaying explainability.",
    }
    return JSONResponse(status_code=409, content=payload)


def _build_session_lineage(session: Any) -> dict[str, Any]:
    scenario = getattr(session, "scenario", None)
    return {
        "session_id": str(getattr(session, "session_id", "")),
        "scenario_id": str(getattr(session, "scenario_id", "")),
        "scenario_type": getattr(
            session,
            "scenario_type",
            getattr(scenario, "scenario_type", None),
        ),
        "user_id": str(getattr(session, "user_id", "")),
        "status": getattr(session, "status", None),
        "report_status": getattr(session, "report_status", None),
        "report_generated_at": _iso_datetime(
            getattr(session, "report_generated_at", None)
        ),
    }


def _build_evaluation_lineage(run: Any) -> dict[str, Any]:
    config_bundle_id = getattr(run, "config_bundle_id", None)
    config_version_id = getattr(run, "config_version_id", None)
    return {
        "run_id": str(getattr(run, "run_id", "")),
        "status": getattr(run, "status", None),
        "started_at": _iso_datetime(getattr(run, "started_at", None)),
        "finished_at": _iso_datetime(getattr(run, "finished_at", None)),
        "input_evidence_reference": _dict_or_empty(
            getattr(run, "input_evidence_reference", None)
        ),
        "result_payload": _dict_or_empty(getattr(run, "result_payload", None)),
        "result_summary": getattr(run, "result_summary", None),
        "error_message": getattr(run, "error_message", None),
        "config_bundle_id": str(config_bundle_id) if config_bundle_id else None,
        "config_version_id": str(config_version_id) if config_version_id else None,
        "created_at": _iso_datetime(getattr(run, "created_at", None)),
        "updated_at": _iso_datetime(getattr(run, "updated_at", None)),
    }


def _build_report_lineage(snapshot: Any) -> dict[str, Any]:
    config_lineage = _dict_or_empty(getattr(snapshot, "config_bundle_snapshot", None))
    config_bundle_id = getattr(snapshot, "config_bundle_id", None) or config_lineage.get(
        "config_bundle_id"
    )
    return {
        "snapshot_id": str(getattr(snapshot, "snapshot_id", "")),
        "evaluation_run_id": str(getattr(snapshot, "evaluation_run_id", "")),
        "generated_at": _iso_datetime(getattr(snapshot, "generated_at", None)),
        "ruleset_source": getattr(snapshot, "ruleset_source", None),
        "ruleset_version": getattr(snapshot, "ruleset_version", None),
        "score_basis": getattr(snapshot, "score_basis", None),
        "non_evaluable_reason": getattr(snapshot, "non_evaluable_reason", None),
        "config_bundle_id": str(config_bundle_id) if config_bundle_id else None,
        "config_version_id": config_lineage.get("config_version_id"),
        "bundle_key": config_lineage.get("bundle_key"),
        "source": config_lineage.get("source"),
        "config_bundle_snapshot": config_lineage,
        "created_at": _iso_datetime(getattr(snapshot, "created_at", None)),
    }


def _build_evidence_lineage(
    *,
    run: Any,
    snapshot: Any,
) -> dict[str, Any]:
    report_payload = _dict_or_empty(getattr(snapshot, "report_payload", None))
    return {
        "input_reference": _dict_or_empty(
            getattr(run, "input_evidence_reference", None)
        ),
        "completeness": _dict_or_empty(
            getattr(snapshot, "evidence_completeness", None)
        ),
        "report_evidence": report_payload.get("evidence")
        if isinstance(report_payload.get("evidence"), dict)
        else None,
    }


def _build_explainability_payload(
    *,
    session: Any,
    run: Any,
    snapshot: Any,
) -> dict[str, Any]:
    config_lineage = _dict_or_empty(getattr(snapshot, "config_bundle_snapshot", None))
    config_snapshot = _dict_or_empty(config_lineage.get("config_snapshot"))
    return {
        "session": _build_session_lineage(session),
        "model": config_snapshot.get("model"),
        "prompt": config_snapshot.get("prompt"),
        "rag": config_snapshot.get("rag"),
        "knowledge": config_snapshot.get("knowledge"),
        "scoring": config_snapshot.get("scoring"),
        "evidence": _build_evidence_lineage(run=run, snapshot=snapshot),
        "evaluation": _build_evaluation_lineage(run),
        "report": {
            "payload": _dict_or_empty(getattr(snapshot, "report_payload", None)),
            "lineage": _build_report_lineage(snapshot),
        },
    }


async def _get_session(db: AsyncSession, session_id: str) -> Any | None:
    result = await db.execute(
        select(
            PracticeSession.session_id,
            PracticeSession.scenario_id,
            PracticeSession.user_id,
            PracticeSession.status,
            PracticeSession.report_status,
            PracticeSession.report_generated_at,
            Scenario.scenario_type.label("scenario_type"),
        )
        .join(Scenario, Scenario.scenario_id == PracticeSession.scenario_id)
        .where(PracticeSession.session_id == session_id)
    )
    return result.one_or_none()


async def _get_evaluation_run(
    db: AsyncSession,
    session_id: str,
) -> Any | None:
    result = await db.execute(
        select(
            EvaluationRun.run_id,
            EvaluationRun.session_id,
            EvaluationRun.status,
            EvaluationRun.started_at,
            EvaluationRun.finished_at,
            EvaluationRun.input_evidence_reference,
            EvaluationRun.result_payload,
            EvaluationRun.result_summary,
            EvaluationRun.error_message,
            EvaluationRun.created_at,
            EvaluationRun.updated_at,
        ).where(EvaluationRun.session_id == session_id)
    )
    return result.one_or_none()


async def _get_report_snapshot(
    db: AsyncSession,
    session_id: str,
) -> Any | None:
    result = await db.execute(
        select(
            TrainingReportSnapshot.snapshot_id,
            TrainingReportSnapshot.session_id,
            TrainingReportSnapshot.evaluation_run_id,
            TrainingReportSnapshot.report_payload,
            TrainingReportSnapshot.ruleset_source,
            TrainingReportSnapshot.ruleset_version,
            TrainingReportSnapshot.score_basis,
            TrainingReportSnapshot.evidence_completeness,
            TrainingReportSnapshot.non_evaluable_reason,
            TrainingReportSnapshot.generated_at,
            TrainingReportSnapshot.created_at,
        ).where(
            TrainingReportSnapshot.session_id == session_id
        )
    )
    return result.one_or_none()


@router.get("/permissions-matrix")
async def get_permissions_matrix(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    _ = current_user
    items = [_permission_entry_payload(entry) for entry in ADMIN_ROUTE_PERMISSION_MATRIX]
    return success_response(
        {
            "items": items,
            "total": len(items),
            "fix_first_route_families": list(FIX_FIRST_ADMIN_ROUTE_FAMILIES),
            "positive_control_route_families": list(ADMIN_PERMISSION_POSITIVE_CONTROL),
            "support_log_redaction": {
                "visible_fields": list(ADMIN_SUPPORT_LOG_VISIBLE_FIELDS),
                "diagnostic_allowlist": list(ADMIN_SUPPORT_DIAGNOSTIC_ALLOWLIST),
                "backend_only_fields": list(ADMIN_SUPPORT_BACKEND_ONLY_FIELDS),
                "guidance": ADMIN_SUPPORT_LOG_REDACTION_GUIDANCE,
                "quality_event_prerequisite": M021_QUALITY_EVENT_ADMIN_SUPPORT_PREREQUISITE,
            },
        }
    )


@router.get("/settings-backlog")
async def get_settings_governance_backlog(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    _ = current_user
    return success_response(
        {
            "items": [dict(item) for item in SETTINGS_GOVERNANCE_BACKLOG],
            "total": len(SETTINGS_GOVERNANCE_BACKLOG),
            "policy": (
                "Admin settings are governed through BusinessRuleConfig-backed "
                "/api/v1/admin/settings/{surface} APIs with defaults, validation, "
                "audit logs, and rollback. Runtime consumers must opt in explicitly."
            ),
        }
    )


@ai_governance_router.get("/explain/{session_id}", response_model=None)
async def get_ai_governance_explainability(
    session_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    _ = current_user
    session = await _get_session(db, session_id)
    if session is None:
        payload = error_response(
            "[AI_GOVERNANCE_SESSION_NOT_FOUND]",
            message="Practice session not found for AI governance explainability.",
        )
        return JSONResponse(status_code=404, content=payload)

    run = await _get_evaluation_run(db, session_id)
    snapshot = await _get_report_snapshot(db, session_id)
    missing: list[str] = []
    if run is None:
        missing.append("EvaluationRun")
    if snapshot is None:
        missing.append("TrainingReportSnapshot")
    if missing:
        return _explainability_error(session_id=session_id, missing=missing)

    return success_response(
        _build_explainability_payload(
            session=session,
            run=run,
            snapshot=snapshot,
        )
    )
