from __future__ import annotations

from typing import Any


def _iso_datetime(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


def _report_lineage_source(*, run: Any, snapshot: Any) -> str | None:
    input_reference = _dict_or_empty(getattr(run, "input_evidence_reference", None))
    evidence_source = input_reference.get("source")
    if isinstance(evidence_source, str) and evidence_source.strip():
        return evidence_source.strip()
    return getattr(snapshot, "ruleset_source", None)


def _build_report_lineage(*, run: Any, snapshot: Any) -> dict[str, Any]:
    config_lineage = _dict_or_empty(getattr(snapshot, "config_bundle_snapshot", None))
    config_bundle_id = getattr(snapshot, "config_bundle_id", None) or config_lineage.get(
        "config_bundle_id"
    )
    return {
        "snapshot_id": str(getattr(snapshot, "snapshot_id", "")),
        "evaluation_run_id": str(getattr(snapshot, "evaluation_run_id", "")),
        "generated_at": _iso_datetime(getattr(snapshot, "generated_at", None)),
        "ruleset_source": _report_lineage_source(run=run, snapshot=snapshot),
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


def build_explainability_payload(
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
            "lineage": _build_report_lineage(run=run, snapshot=snapshot),
        },
    }
