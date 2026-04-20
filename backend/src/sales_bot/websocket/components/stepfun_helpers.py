"""Helper utilities for StepFun realtime websocket handler."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES,
    normalize_knowledge_retrieval_ledger_event,
)


def format_stage_name(stage_id: str | None) -> str:
    """Map internal stage IDs to display names."""
    mapping = {
        "opening": "开场破冰",
        "discovery": "需求挖掘",
        "presentation": "方案呈现",
        "objection": "异议处理",
        "closing": "促成成交",
    }
    if not isinstance(stage_id, str):
        return ""
    return mapping.get(stage_id, stage_id)


def extract_text_payload(data: dict[str, Any]) -> str:
    """Extract text payload with legacy fallback support."""
    text = data.get("text")
    if isinstance(text, str) and text.strip():
        return text

    legacy_text = data.get("content")
    if isinstance(legacy_text, str) and legacy_text.strip():
        return legacy_text

    return ""


def extract_response_text(response_done_event: dict[str, Any]) -> str:
    """Extract assistant text from `response.done` payload."""
    response = response_done_event.get("response")
    if not isinstance(response, dict):
        return ""

    output = response.get("output", [])
    if not isinstance(output, list):
        return ""

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if "text" in part and isinstance(part["text"], str):
                text_parts.append(part["text"])
            elif "transcript" in part and isinstance(part["transcript"], str):
                text_parts.append(part["transcript"])

    return "".join(text_parts).strip()


def ensure_knowledge_runtime_metrics(policy: dict[str, Any]) -> dict[str, Any]:
    """Ensure knowledge retrieval metrics structure exists in policy snapshot."""
    runtime_metrics = policy.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
        policy["runtime_metrics"] = runtime_metrics

    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    if not isinstance(knowledge_metrics, dict):
        knowledge_metrics = {}

    knowledge_metrics.setdefault("attempt_count", 0)
    knowledge_metrics.setdefault("hit_query_count", 0)
    knowledge_metrics.setdefault("total_results", 0)
    knowledge_metrics.setdefault("last_query", "")
    knowledge_metrics.setdefault("last_result_count", 0)
    knowledge_metrics.setdefault("last_status", "not_triggered")
    knowledge_metrics.setdefault("last_top_k", None)
    knowledge_metrics.setdefault("last_similarity_threshold", None)
    knowledge_metrics.setdefault("bound_knowledge_base_ids", [])
    knowledge_metrics.setdefault("updated_at", None)
    knowledge_metrics.setdefault("recent_queries", [])
    knowledge_metrics.setdefault("recent_attempts", [])
    knowledge_metrics.setdefault("last_error", None)
    knowledge_metrics.setdefault("last_retrieval_mode", None)
    knowledge_metrics.setdefault("mode_counts", {})
    knowledge_metrics.setdefault("kb_lock_required", False)
    knowledge_metrics.setdefault("kb_lock_block_count", 0)
    knowledge_metrics.setdefault("kb_lock_last_status", "not_required")
    knowledge_metrics.setdefault("kb_lock_updated_at", None)
    knowledge_metrics.setdefault("last_decision_id", "")
    knowledge_metrics.setdefault("last_decision_duration_ms", 0.0)
    knowledge_metrics.setdefault("last_decision_phase_breakdown", None)
    knowledge_metrics.setdefault("timeout_rate_5m", 0.0)
    knowledge_metrics.setdefault("kb_lock_decision_timestamps", [])
    knowledge_metrics.setdefault("kb_lock_timeout_timestamps", [])
    knowledge_metrics.setdefault("upstream_disconnect_count_5m", 0)
    knowledge_metrics.setdefault("upstream_disconnect_timestamps", [])
    knowledge_metrics.setdefault("upstream_unstable", False)
    knowledge_metrics.setdefault("upstream_disconnect_last_code", None)
    knowledge_metrics.setdefault("upstream_disconnect_last_reason", "")
    knowledge_metrics.setdefault("upstream_disconnect_last_event_type", "")
    knowledge_metrics.setdefault("upstream_disconnect_last_ws_lifetime_ms", None)
    knowledge_metrics.setdefault("upstream_disconnect_last_at", None)

    runtime_metrics["knowledge_retrieval"] = knowledge_metrics
    return knowledge_metrics


def update_knowledge_runtime_metrics(
    metrics: dict[str, Any],
    *,
    query: str,
    result_count: int,
    status: str,
    knowledge_base_ids: list[str],
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    error_message: str | None = None,
    retrieval_mode: str | None = None,
    ledger_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one retrieval event mutation to knowledge runtime metrics."""
    previous_attempt = int(metrics.get("attempt_count") or 0)
    previous_hit_query = int(metrics.get("hit_query_count") or 0)
    previous_total_results = int(metrics.get("total_results") or 0)

    safe_result_count = max(0, int(result_count))
    metrics["attempt_count"] = previous_attempt + 1
    metrics["hit_query_count"] = previous_hit_query + (
        1 if safe_result_count > 0 else 0
    )
    metrics["total_results"] = previous_total_results + safe_result_count
    metrics["last_query"] = query
    metrics["last_result_count"] = safe_result_count
    metrics["last_status"] = status
    metrics["last_top_k"] = top_k
    metrics["last_similarity_threshold"] = similarity_threshold
    metrics["bound_knowledge_base_ids"] = knowledge_base_ids
    metrics["updated_at"] = datetime.now(UTC).isoformat()
    metrics["last_error"] = str(error_message).strip() if error_message else None
    metrics["last_retrieval_mode"] = retrieval_mode or None

    mode_counts = metrics.get("mode_counts")
    if not isinstance(mode_counts, dict):
        mode_counts = {}
    normalized_mode = str(retrieval_mode or "unknown").strip() or "unknown"
    mode_counts[normalized_mode] = int(mode_counts.get(normalized_mode) or 0) + 1
    metrics["mode_counts"] = mode_counts

    recent_queries = metrics.get("recent_queries")
    if not isinstance(recent_queries, list):
        recent_queries = []
    if query:
        recent_queries = [
            query,
            *[str(item) for item in recent_queries if str(item) and str(item) != query],
        ][:5]
    metrics["recent_queries"] = recent_queries

    recent_attempts = metrics.get("recent_attempts")
    if not isinstance(recent_attempts, list):
        recent_attempts = []
    normalized_ledger_event = normalize_knowledge_retrieval_ledger_event(ledger_event)
    if normalized_ledger_event is not None:
        recent_attempts = [item for item in recent_attempts if isinstance(item, dict)]
        recent_attempts.append(normalized_ledger_event)
        recent_attempts = recent_attempts[-MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES:]
    metrics["recent_attempts"] = recent_attempts

    hit_query_count = int(metrics.get("hit_query_count") or 0)
    attempt_count = int(metrics.get("attempt_count") or 0)
    metrics["hit_rate"] = (
        round(hit_query_count / attempt_count, 4) if attempt_count > 0 else 0.0
    )
    return metrics
