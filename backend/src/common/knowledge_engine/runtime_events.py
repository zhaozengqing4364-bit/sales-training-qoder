from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

RuntimeEventCategory = Literal["quality", "cost", "failure", "mode"]
RuntimeEventSeverity = Literal["info", "ok", "degraded", "failure"]
KnowledgePathMode = Literal["live", "compat"]


_SECRETISH_KEYS = {
    "api_key",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "base_url",
}


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _safe_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key.lower() in _SECRETISH_KEYS:
            continue
        if isinstance(raw_value, dict):
            normalized[key] = _safe_mapping(raw_value)
        elif isinstance(raw_value, list):
            normalized[key] = _safe_list(raw_value)
        else:
            normalized[key] = _safe_scalar(raw_value)
    return normalized


def _safe_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    normalized: list[Any] = []
    for item in value:
        if isinstance(item, dict):
            normalized.append(_safe_mapping(item))
        elif isinstance(item, list):
            normalized.append(_safe_list(item))
        else:
            normalized.append(_safe_scalar(item))
    return normalized


def build_runtime_event(
    *,
    event_id: str,
    category: RuntimeEventCategory,
    severity: RuntimeEventSeverity,
    status: str,
    source: str,
    summary: str,
    details: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    occurred_at: Any = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_id": str(event_id or "unknown_runtime_event"),
        "category": str(category or "quality"),
        "severity": str(severity or "info"),
        "status": str(status or "unknown"),
        "source": str(source or "runtime"),
        "summary": str(summary or "Runtime event recorded."),
        "details": _safe_mapping(details or {}),
        "metrics": _safe_mapping(metrics or {}),
    }
    normalized_occurred_at = _safe_scalar(occurred_at)
    if normalized_occurred_at not in (None, ""):
        event["occurred_at"] = normalized_occurred_at
    return event


def coerce_runtime_events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    events: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and item.get("event_id"):
            events.append(
                build_runtime_event(
                    event_id=str(item.get("event_id") or "unknown_runtime_event"),
                    category=str(item.get("category") or "quality"),
                    severity=str(item.get("severity") or "info"),
                    status=str(item.get("status") or "unknown"),
                    source=str(item.get("source") or "runtime"),
                    summary=str(item.get("summary") or "Runtime event recorded."),
                    details=item.get("details")
                    if isinstance(item.get("details"), dict)
                    else {},
                    metrics=item.get("metrics")
                    if isinstance(item.get("metrics"), dict)
                    else {},
                    occurred_at=item.get("occurred_at"),
                )
            )
    return events


def merge_runtime_events(*event_groups: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group in event_groups:
        for event in coerce_runtime_events(group):
            key = (
                str(event.get("event_id") or ""),
                str(event.get("status") or ""),
                str(event.get("source") or ""),
                str(event.get("occurred_at") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(deepcopy(event))
    return merged


def resolve_knowledge_path_mode(
    rollout_mode: str | None,
    *,
    path_mode: str | None = None,
) -> KnowledgePathMode:
    normalized_path = str(path_mode or "").strip().lower()
    if normalized_path == "live":
        return "live"
    if normalized_path == "compat":
        return "compat"
    normalized_rollout = str(rollout_mode or "").strip().lower()
    return "live" if normalized_rollout == "enabled" else "compat"


def _knowledge_quality_severity(
    answerability: str, source_status: str
) -> RuntimeEventSeverity:
    if source_status in {"search_failed", "kb_not_ready", "blocked", "missing_query"}:
        return "failure"
    if answerability in {"blocked", "insufficient"}:
        return "failure"
    if answerability in {"partial", "unanswered"}:
        return "degraded"
    if source_status in {"miss", "no_kb_bound", "not_run"}:
        return "degraded"
    return "ok"


def build_knowledge_answer_runtime_events(
    diagnostics: dict[str, Any] | None,
    *,
    occurred_at: Any = None,
) -> list[dict[str, Any]]:
    if not isinstance(diagnostics, dict):
        return []

    rollout_mode = str(diagnostics.get("rollout_mode") or "legacy").strip() or "legacy"
    path_mode = resolve_knowledge_path_mode(
        rollout_mode,
        path_mode=str(diagnostics.get("path_mode") or "").strip() or None,
    )
    answerability = (
        str(diagnostics.get("answerability") or "unanswered").strip() or "unanswered"
    )
    source_status = (
        str(diagnostics.get("source_status") or "not_run").strip() or "not_run"
    )
    query = str(diagnostics.get("query") or "").strip()
    live_audit_run_id = str(diagnostics.get("live_audit_run_id") or "").strip() or None
    shadow_audit_run_id = (
        str(diagnostics.get("shadow_audit_run_id") or "").strip() or None
    )

    quality_severity = _knowledge_quality_severity(answerability, source_status)
    quality_summary = {
        "ok": "Knowledge answer returned grounded support without degradation.",
        "degraded": "Knowledge answer completed with degraded grounding quality.",
        "failure": "Knowledge answer could not provide reliable grounded support.",
    }[quality_severity]

    return [
        build_runtime_event(
            event_id="knowledge_answer_path_mode",
            category="mode",
            severity="info",
            status=path_mode,
            source="knowledge_answer",
            summary=(
                "Knowledge answer served the live path."
                if path_mode == "live"
                else "Knowledge answer served the compatibility path."
            ),
            details={
                "rollout_mode": rollout_mode,
                "live_audit_run_id": live_audit_run_id,
                "shadow_audit_run_id": shadow_audit_run_id,
            },
            occurred_at=occurred_at,
        ),
        build_runtime_event(
            event_id="knowledge_answer_quality",
            category="quality" if quality_severity != "failure" else "failure",
            severity=quality_severity,
            status=answerability,
            source="knowledge_answer",
            summary=quality_summary,
            details={
                "source_status": source_status,
                "query": query,
                "path_mode": path_mode,
                "rollout_mode": rollout_mode,
                "citation_count": len(diagnostics.get("citations") or [])
                if isinstance(diagnostics.get("citations"), list)
                else 0,
                "rewritten_query_count": len(diagnostics.get("rewritten_queries") or [])
                if isinstance(diagnostics.get("rewritten_queries"), list)
                else 0,
                "live_audit_run_id": live_audit_run_id,
                "shadow_audit_run_id": shadow_audit_run_id,
            },
            occurred_at=occurred_at,
        ),
    ]


def enrich_knowledge_answer_diagnostics(
    diagnostics: dict[str, Any] | None,
    *,
    rollout_mode: str | None = None,
    path_mode: str | None = None,
    live_audit_run_id: str | None = None,
    shadow_audit_run_id: str | None = None,
    occurred_at: Any = None,
) -> dict[str, Any]:
    normalized = _safe_mapping(diagnostics or {})
    normalized_rollout_mode = (
        str(rollout_mode or normalized.get("rollout_mode") or "legacy").strip()
        or "legacy"
    )
    normalized_path_mode = resolve_knowledge_path_mode(
        normalized_rollout_mode,
        path_mode=path_mode or str(normalized.get("path_mode") or "").strip() or None,
    )
    normalized["rollout_mode"] = normalized_rollout_mode
    normalized["path_mode"] = normalized_path_mode

    resolved_live_audit_run_id = (
        str(live_audit_run_id or normalized.get("live_audit_run_id") or "").strip()
        or None
    )
    resolved_shadow_audit_run_id = (
        str(shadow_audit_run_id or normalized.get("shadow_audit_run_id") or "").strip()
        or None
    )
    if resolved_live_audit_run_id:
        normalized["live_audit_run_id"] = resolved_live_audit_run_id
    if resolved_shadow_audit_run_id:
        normalized["shadow_audit_run_id"] = resolved_shadow_audit_run_id

    normalized["runtime_events"] = build_knowledge_answer_runtime_events(
        normalized,
        occurred_at=occurred_at,
    )
    return normalized


def build_claim_truth_runtime_event(
    claim_truth: dict[str, Any] | None,
    *,
    occurred_at: Any = None,
) -> dict[str, Any] | None:
    if not isinstance(claim_truth, dict):
        return None
    status = str(claim_truth.get("status") or "").strip()
    if not status:
        return None
    source = str(claim_truth.get("source") or "unknown").strip() or "unknown"
    severity: RuntimeEventSeverity
    category: RuntimeEventCategory
    if status in {"unsupported_claim"}:
        severity = "failure"
        category = "failure"
    elif status in {"weak_evidence", "evidence_pending"}:
        severity = "degraded"
        category = "quality"
    elif status in {"evidence_verified"}:
        severity = "ok"
        category = "quality"
    else:
        severity = "info"
        category = "quality"
    return build_runtime_event(
        event_id="claim_truth_status",
        category=category,
        severity=severity,
        status=status,
        source="claim_truth",
        summary=f"Claim truth status is {status}.",
        details={"source": source},
        occurred_at=occurred_at,
    )


def build_kb_lock_runtime_event(
    knowledge_diagnostics: dict[str, Any] | None,
    *,
    occurred_at: Any = None,
) -> dict[str, Any] | None:
    if not isinstance(knowledge_diagnostics, dict):
        return None
    kb_lock_required = bool(knowledge_diagnostics.get("kb_lock_required"))
    kb_lock_status = str(knowledge_diagnostics.get("kb_lock_status") or "").strip()
    if not kb_lock_required and not kb_lock_status.startswith("blocked_"):
        return None

    if kb_lock_status.startswith("blocked_"):
        severity: RuntimeEventSeverity = "failure"
        category: RuntimeEventCategory = "failure"
        summary = f"KB lock blocked grounded answering: {kb_lock_status}."
    elif kb_lock_status == "pass":
        severity = "ok"
        category = "quality"
        summary = "KB lock passed grounded answering checks."
    else:
        severity = "info"
        category = "quality"
        summary = f"KB lock status is {kb_lock_status or 'unknown'}."

    return build_runtime_event(
        event_id="kb_lock_status",
        category=category,
        severity=severity,
        status=kb_lock_status or "unknown",
        source="knowledge_retrieval",
        summary=summary,
        details={
            "last_status": knowledge_diagnostics.get("last_status"),
            "status": knowledge_diagnostics.get("status"),
        },
        occurred_at=occurred_at,
    )
