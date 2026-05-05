"""Shared runtime diagnostics helpers for knowledge-check and support health readers."""

from __future__ import annotations

import os
from typing import Any

from common.db.models import PracticeSession
from common.effectiveness import coerce_live_session_conclusion_summary
from common.knowledge.kb_lock_guard import is_kb_lock_chain_failure_status
from common.knowledge_engine.runtime_events import (
    build_claim_truth_runtime_event,
    build_kb_lock_runtime_event,
    enrich_knowledge_answer_diagnostics,
    merge_runtime_events,
)

DEFAULT_KB_LOCK_TIMEOUT_BUDGET_MS = 2200
DEFAULT_KB_LOCK_MIN_PASS_SCORE = 0.62


def extract_voice_policy_snapshot(session: PracticeSession) -> dict[str, Any]:
    snapshot = getattr(session, "voice_policy_snapshot", None)
    return snapshot if isinstance(snapshot, dict) else {}


def _normalize_claim_truth_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    source = value.get("source")
    if not isinstance(status, str) or not status.strip():
        return None
    if not isinstance(source, str) or not source.strip():
        return None

    payload = dict(value)
    payload["status"] = status.strip()
    payload["source"] = source.strip()
    evidence_score = payload.get("evidence_score")
    try:
        if evidence_score is not None:
            payload["evidence_score"] = round(float(evidence_score), 2)
    except (TypeError, ValueError):
        payload.pop("evidence_score", None)
    return payload


def _normalize_main_issue_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    issue_type = value.get("issue_type")
    issue_text = value.get("issue_text")
    recovery_rule = value.get("recovery_rule")
    if not all(
        isinstance(item, str) and item.strip()
        for item in (issue_type, issue_text, recovery_rule)
    ):
        return None
    return {
        "issue_type": issue_type.strip(),
        "issue_text": issue_text.strip(),
        "recovery_rule": recovery_rule.strip(),
    }


def _normalize_next_goal_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    goal_type = value.get("goal_type")
    goal_text = value.get("goal_text")
    rule = value.get("rule")
    if not all(
        isinstance(item, str) and item.strip() for item in (goal_type, goal_text, rule)
    ):
        return None
    return {
        "goal_type": goal_type.strip(),
        "goal_text": goal_text.strip(),
        "rule": rule.strip(),
    }


def _normalize_coach_health_payload(value: Any) -> dict[str, Any]:
    default_payload = {
        "status": "healthy",
        "reason": None,
        "message": "实时辅导正常。",
    }
    if not isinstance(value, dict):
        return default_payload

    status = str(value.get("status") or "healthy").strip().lower()
    if status not in {"healthy", "degraded", "resumed"}:
        status = "healthy"
    reason = value.get("reason")
    message = value.get("message")
    if not isinstance(message, str) or not message.strip():
        message = (
            default_payload["message"]
            if status == "healthy"
            else (
                "实时辅导暂不可用，训练仍可继续。"
                if status == "degraded"
                else "实时辅导已恢复，后续建议会继续更新。"
            )
        )
    return {
        "status": status,
        "reason": reason.strip()
        if isinstance(reason, str) and reason.strip()
        else None,
        "message": message.strip(),
    }


def _normalize_knowledge_retrieval_attempt(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    status = str(value.get("status") or "").strip()
    if not status:
        return None

    query = str(value.get("query") or "").strip()
    attempted_at = str(value.get("attempted_at") or "").strip() or None
    retrieval_mode = str(value.get("retrieval_mode") or "").strip() or None
    error_summary = (
        str(value.get("error_summary") or value.get("error_message") or "").strip()
        or None
    )
    try:
        result_count = max(0, int(value.get("result_count") or 0))
    except (TypeError, ValueError):
        result_count = 0

    return {
        "status": status,
        "query": query,
        "attempted_at": attempted_at,
        "retrieval_mode": retrieval_mode,
        "error_summary": error_summary,
        "result_count": result_count,
    }


def _resolve_latest_valid_knowledge_retrieval_attempt(
    knowledge_metrics: dict[str, Any],
) -> dict[str, Any] | None:
    recent_attempts = knowledge_metrics.get("recent_attempts")
    if not isinstance(recent_attempts, list):
        return None

    for attempt in reversed(recent_attempts):
        normalized_attempt = _normalize_knowledge_retrieval_attempt(attempt)
        if normalized_attempt is not None:
            return normalized_attempt
    return None


# ---------------------------------------------------------------------------
# Shared retrieval-facts read model (used by both projection and diagnostics)
# Bounds reference: stepfun_knowledge_helpers.py
#   MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES = 10
#   MAX_KNOWLEDGE_RETRIEVAL_RESULT_SUMMARIES = 3
#   MAX_KNOWLEDGE_RETRIEVAL_SNIPPET_CHARS = 240
#   MAX_KNOWLEDGE_RETRIEVAL_LEDGER_KB_IDS = 8
# ---------------------------------------------------------------------------
_RETRIEVAL_FACTS_MAX_RECENT = 10
_RETRIEVAL_FACTS_MAX_KB_IDS = 8
_RETRIEVAL_FACTS_MAX_SUMMARIES = 3
_RETRIEVAL_FACTS_SNIPPET_CHARS = 240


def _normalize_retrieval_attempt_full(value: Any) -> dict[str, Any] | None:
    """Normalize a single ledger entry, *preserving* knowledge_base_ids and result_summaries.

    Unlike `_normalize_knowledge_retrieval_attempt` which strips those fields for
    the lean diagnostics summary, this richer normaliser keeps them so that
    projection (report) and diagnostics (knowledge-check) can share the same
    truth.
    """
    if not isinstance(value, dict):
        return None

    status = str(value.get("status") or "").strip()
    if not status:
        return None

    query = str(value.get("query") or "").strip()
    attempted_at = str(value.get("attempted_at") or "").strip() or None
    retrieval_mode = str(value.get("retrieval_mode") or "").strip() or None
    error_summary = (
        str(value.get("error_summary") or value.get("error_message") or "").strip()
        or None
    )
    try:
        result_count = max(0, int(value.get("result_count") or 0))
    except (TypeError, ValueError):
        result_count = 0

    # --- Preserve knowledge_base_ids (bounded to 8) ---
    raw_kb_ids = value.get("knowledge_base_ids")
    kb_ids: list[str] = []
    if isinstance(raw_kb_ids, list):
        for kb_id in raw_kb_ids:
            s = str(kb_id).strip()
            if s and len(kb_ids) < _RETRIEVAL_FACTS_MAX_KB_IDS:
                kb_ids.append(s)

    # --- Preserve result_summaries (bounded to 3, snippet ≤ 240 chars) ---
    raw_summaries = value.get("result_summaries")
    summaries: list[dict[str, Any]] = []
    if isinstance(raw_summaries, list):
        for item in raw_summaries:
            if not isinstance(item, dict):
                continue
            if len(summaries) >= _RETRIEVAL_FACTS_MAX_SUMMARIES:
                break
            kb_id = str(item.get("knowledge_base_id") or "").strip()
            if not kb_id:
                continue
            summary_entry: dict[str, Any] = {
                "knowledge_base_id": kb_id,
                "knowledge_base_name": str(
                    item.get("knowledge_base_name") or ""
                ).strip(),
                "snippet": str(item.get("snippet") or item.get("content") or "")[
                    :_RETRIEVAL_FACTS_SNIPPET_CHARS
                ],
                "retrieval_mode": str(item.get("retrieval_mode") or "vector").strip(),
            }
            score = item.get("score")
            try:
                if score is not None and str(score).strip() != "":
                    summary_entry["score"] = round(float(score), 4)
            except (TypeError, ValueError):
                pass
            summaries.append(summary_entry)

    normalized: dict[str, Any] = {
        "status": status,
        "query": query,
        "attempted_at": attempted_at,
        "retrieval_mode": retrieval_mode,
        "error_summary": error_summary,
        "result_count": result_count,
        "knowledge_base_ids": kb_ids,
        "result_summaries": summaries,
    }
    return normalized


def _derive_retrieval_status_and_summary(
    *,
    normalized_kb_ids: list[str],
    internal_retrieval_enabled: bool,
    last_status: str,
    last_error: str,
    attempt_count: int,
    hit_query_count: int,
) -> tuple[str, str]:
    """Derive the canonical retrieval *status* and Chinese *summary* string.

    This logic is extracted from `build_session_runtime_diagnostics` so that
    both that function and the new `build_retrieval_facts` share the same
    vocabulary without duplication.
    """
    if not normalized_kb_ids:
        return "no_knowledge_base", "当前会话未绑定知识库"
    if not internal_retrieval_enabled:
        return "disabled", "内部知识检索未启用"
    if last_status == "kb_not_ready" or "[KB_NOT_READY]" in last_error:
        return "kb_not_ready", "知识库文档尚未处理完成"
    if last_status == "search_failed" or "[KNOWLEDGE_SEARCH_UNAVAILABLE]" in last_error:
        return "search_failed", "知识检索触发失败，请检查知识库或 Embedding 服务"
    if attempt_count == 0:
        return "not_triggered", "本次对话尚未触发知识检索"
    if hit_query_count > 0:
        return "hit", "知识检索已触发并命中知识库"
    return "miss", "知识检索已触发，但本次未命中有效内容"


def build_retrieval_facts(
    voice_policy_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build the shared retrieval-truth read model from a persisted voice_policy_snapshot.

    Returns ``None`` when the snapshot is absent or has no ``runtime_metrics``.
    This is the single normalisation point that both projection (report) and
    diagnostics (knowledge-check) should call to prevent parity drift.
    """
    if not isinstance(voice_policy_snapshot, dict):
        return None

    runtime_metrics = voice_policy_snapshot.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        return None

    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    if not isinstance(knowledge_metrics, dict):
        knowledge_metrics = {}

    # --- KB binding ---
    raw_kb_ids = voice_policy_snapshot.get("knowledge_base_ids")
    if not isinstance(raw_kb_ids, list):
        raw_kb_ids = []
    normalized_kb_ids = [str(kb_id) for kb_id in raw_kb_ids if kb_id]
    kb_bound = bool(normalized_kb_ids)

    # --- Tool-policy flags ---
    tool_policy = voice_policy_snapshot.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}
    internal_retrieval_enabled = bool(
        tool_policy.get("enable_internal_retrieval", False)
    )

    # --- Flat aggregate metrics ---
    attempt_count = int(knowledge_metrics.get("attempt_count") or 0)
    hit_query_count = int(knowledge_metrics.get("hit_query_count") or 0)
    hit_rate = _coerce_float(knowledge_metrics.get("hit_rate") or 0.0)

    # --- Resolve latest status from flat metrics + ledger ---
    last_status = str(knowledge_metrics.get("last_status") or "").strip()
    last_error = str(knowledge_metrics.get("last_error") or "").strip()

    # --- Normalise recent_attempts (full, bounded to 10) ---
    raw_recent = knowledge_metrics.get("recent_attempts")
    recent_attempts: list[dict[str, Any]] = []
    if isinstance(raw_recent, list):
        for entry in reversed(raw_recent):  # iterate from newest
            normalized_entry = _normalize_retrieval_attempt_full(entry)
            if normalized_entry is not None:
                recent_attempts.append(normalized_entry)
                if len(recent_attempts) >= _RETRIEVAL_FACTS_MAX_RECENT:
                    break
    recent_attempts.reverse()  # restore chronological order

    # Fill missing flat status from the latest valid ledger entry
    latest_attempt: dict[str, Any] | None = (
        recent_attempts[-1] if recent_attempts else None
    )
    if latest_attempt is not None:
        ledger_status = str(latest_attempt.get("status") or "").strip()
        if not last_status or (attempt_count > 0 and last_status == "not_triggered"):
            last_status = ledger_status
        if not last_error:
            last_error = str(latest_attempt.get("error_summary") or "").strip()
    if not last_status:
        last_status = "not_triggered"

    # --- Derive canonical status / summary ---
    status, summary = _derive_retrieval_status_and_summary(
        normalized_kb_ids=normalized_kb_ids,
        internal_retrieval_enabled=internal_retrieval_enabled,
        last_status=last_status,
        last_error=last_error,
        attempt_count=attempt_count,
        hit_query_count=hit_query_count,
    )

    # --- Miss / failure explanations ---
    miss_explanation: str | None = None
    failure_explanation: str | None = None
    if status == "miss":
        last_query = ""
        if latest_attempt:
            last_query = str(latest_attempt.get("query") or "").strip()
        if last_query:
            miss_explanation = (
                f"查询「{last_query}」未命中知识库内容，可能需要补充相关文档"
            )
        else:
            miss_explanation = "知识检索已触发但未命中，可能需要补充知识库文档覆盖范围"
    if status == "search_failed":
        if latest_attempt:
            error_msg = str(latest_attempt.get("error_summary") or "").strip()
            if error_msg:
                failure_explanation = f"检索失败：{error_msg}"
        if not failure_explanation:
            failure_explanation = "检索失败，请检查知识库或 Embedding 服务状态"

    return {
        "kb_bound": kb_bound,
        "knowledge_base_ids": normalized_kb_ids,
        "knowledge_base_count": len(normalized_kb_ids),
        "retrieval_enabled": internal_retrieval_enabled,
        "status": status,
        "summary": summary,
        "attempt_count": attempt_count,
        "hit_count": hit_query_count,
        "hit_rate": round(hit_rate, 4),
        "latest_attempt": latest_attempt,
        "recent_attempts": recent_attempts,
        "miss_explanation": miss_explanation,
        "failure_explanation": failure_explanation,
    }


def build_session_runtime_diagnostics(
    *,
    session: PracticeSession,
    snapshot: dict[str, Any] | None,
    effective_tool_types: list[str] | None = None,
    live_claim_truth: dict[str, Any] | None = None,
    live_coach_health: dict[str, Any] | None = None,
    live_session_summary: dict[str, Any] | None = None,
    live_knowledge_answer_diagnostics: dict[str, Any] | None = None,
    live_runtime_active: bool = False,
    projection_effectiveness_snapshot: dict[str, Any] | None = None,
    conclusion_evidence: dict[str, Any] | None = None,
    evidence_degradation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    tool_policy = snapshot.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}

    network_access_mode = str(tool_policy.get("network_access_mode") or "off").lower()
    enforcement_level = str(tool_policy.get("enforcement_level") or "strict").lower()
    allow_web_search_without_kb = bool(
        tool_policy.get("allow_web_search_without_kb", False)
    )
    require_kb_grounding = bool(tool_policy.get("require_kb_grounding", False))
    internal_retrieval_enabled = bool(
        tool_policy.get("enable_internal_retrieval", False)
    )
    web_search_enabled = bool(tool_policy.get("enable_web_search", False))

    knowledge_base_ids = snapshot.get("knowledge_base_ids")
    if not isinstance(knowledge_base_ids, list):
        knowledge_base_ids = []
    normalized_kb_ids = [str(kb_id) for kb_id in knowledge_base_ids if kb_id]
    kb_bound = bool(normalized_kb_ids)

    runtime_metrics = snapshot.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    if not isinstance(knowledge_metrics, dict):
        knowledge_metrics = {}
    snapshot_knowledge_answer_diagnostics = runtime_metrics.get(
        "knowledge_answer_diagnostics"
    )
    if not isinstance(snapshot_knowledge_answer_diagnostics, dict):
        snapshot_knowledge_answer_diagnostics = None
    latest_valid_attempt = _resolve_latest_valid_knowledge_retrieval_attempt(
        knowledge_metrics
    )

    attempt_count = int(knowledge_metrics.get("attempt_count") or 0)
    hit_query_count = int(knowledge_metrics.get("hit_query_count") or 0)
    total_results = int(knowledge_metrics.get("total_results") or 0)

    raw_last_result_count = knowledge_metrics.get("last_result_count")
    if raw_last_result_count is None and latest_valid_attempt is not None:
        raw_last_result_count = latest_valid_attempt.get("result_count")
    last_result_count = int(raw_last_result_count or 0)

    hit_rate = _coerce_float(knowledge_metrics.get("hit_rate") or 0.0)

    last_status = str(knowledge_metrics.get("last_status") or "").strip()
    if latest_valid_attempt is not None and (
        not last_status or (attempt_count > 0 and last_status == "not_triggered")
    ):
        last_status = str(latest_valid_attempt.get("status") or "").strip()
    if not last_status:
        last_status = "not_triggered"

    last_error = str(knowledge_metrics.get("last_error") or "").strip()
    if not last_error and latest_valid_attempt is not None:
        last_error = str(latest_valid_attempt.get("error_summary") or "").strip()

    last_query = str(knowledge_metrics.get("last_query") or "").strip()
    if not last_query and latest_valid_attempt is not None:
        last_query = str(latest_valid_attempt.get("query") or "").strip()

    last_retrieval_mode = str(
        knowledge_metrics.get("last_retrieval_mode") or ""
    ).strip()
    if not last_retrieval_mode and latest_valid_attempt is not None:
        last_retrieval_mode = str(
            latest_valid_attempt.get("retrieval_mode") or ""
        ).strip()

    updated_at = knowledge_metrics.get("updated_at")
    if updated_at is None and latest_valid_attempt is not None:
        updated_at = latest_valid_attempt.get("attempted_at")

    kb_lock_required = require_kb_grounding
    kb_lock_block_count = int(knowledge_metrics.get("kb_lock_block_count") or 0)
    kb_lock_last_status = str(
        knowledge_metrics.get("kb_lock_last_status") or "not_required"
    )
    last_decision_id = str(knowledge_metrics.get("last_decision_id") or "")
    last_decision_duration_ms = _coerce_float(
        knowledge_metrics.get("last_decision_duration_ms") or 0.0
    )
    last_decision_phase_breakdown = knowledge_metrics.get(
        "last_decision_phase_breakdown"
    )
    if not isinstance(last_decision_phase_breakdown, dict):
        last_decision_phase_breakdown = None
    timeout_rate_5m = _coerce_float(knowledge_metrics.get("timeout_rate_5m") or 0.0)
    kb_lock_decision_timestamps = knowledge_metrics.get("kb_lock_decision_timestamps")
    has_recent_kb_lock_decisions = isinstance(
        kb_lock_decision_timestamps, list
    ) and bool(kb_lock_decision_timestamps)
    upstream_disconnect_count_5m = int(
        knowledge_metrics.get("upstream_disconnect_count_5m") or 0
    )
    upstream_unstable = bool(knowledge_metrics.get("upstream_unstable", False))

    session_effectiveness_snapshot = getattr(session, "effectiveness_snapshot", None)
    if not isinstance(session_effectiveness_snapshot, dict):
        session_effectiveness_snapshot = {}
    projection_effectiveness_snapshot = (
        projection_effectiveness_snapshot
        if isinstance(projection_effectiveness_snapshot, dict)
        else {}
    )
    normalized_live_session_summary = coerce_live_session_conclusion_summary(
        live_session_summary
    )
    knowledge_answer_diagnostics = None
    if isinstance(live_knowledge_answer_diagnostics, dict):
        knowledge_answer_diagnostics = dict(live_knowledge_answer_diagnostics)
    elif isinstance(live_session_summary, dict):
        raw_answer_diagnostics = live_session_summary.get(
            "knowledge_answer_diagnostics"
        )
        if isinstance(raw_answer_diagnostics, dict):
            knowledge_answer_diagnostics = dict(raw_answer_diagnostics)
    elif isinstance(snapshot_knowledge_answer_diagnostics, dict):
        knowledge_answer_diagnostics = dict(snapshot_knowledge_answer_diagnostics)

    if live_runtime_active:
        main_issue = (
            normalized_live_session_summary.get("main_issue")
            if isinstance(normalized_live_session_summary, dict)
            else None
        )
        next_goal = (
            normalized_live_session_summary.get("next_goal")
            if isinstance(normalized_live_session_summary, dict)
            else None
        )
        claim_truth = (
            normalized_live_session_summary.get("claim_truth")
            if isinstance(normalized_live_session_summary, dict)
            else None
        ) or _normalize_claim_truth_payload(live_claim_truth)
    else:
        main_issue = (
            (
                normalized_live_session_summary.get("main_issue")
                if isinstance(normalized_live_session_summary, dict)
                else None
            )
            or _normalize_main_issue_payload(
                projection_effectiveness_snapshot.get("main_issue")
            )
            or _normalize_main_issue_payload(
                session_effectiveness_snapshot.get("main_issue")
            )
        )
        next_goal = (
            (
                normalized_live_session_summary.get("next_goal")
                if isinstance(normalized_live_session_summary, dict)
                else None
            )
            or _normalize_next_goal_payload(
                projection_effectiveness_snapshot.get("next_goal")
            )
            or _normalize_next_goal_payload(
                session_effectiveness_snapshot.get("next_goal")
            )
        )
        claim_truth = (
            (
                normalized_live_session_summary.get("claim_truth")
                if isinstance(normalized_live_session_summary, dict)
                else None
            )
            or _normalize_claim_truth_payload(live_claim_truth)
            or _normalize_claim_truth_payload(
                projection_effectiveness_snapshot.get("claim_truth")
            )
            or _normalize_claim_truth_payload(
                session_effectiveness_snapshot.get("claim_truth")
            )
        )
    # --- retrieval_facts: reuse projection truth for completed sessions ---
    retrieval_facts = None
    if not live_runtime_active and isinstance(projection_effectiveness_snapshot, dict):
        retrieval_facts = projection_effectiveness_snapshot.get("retrieval_facts")

    coach_health = _normalize_coach_health_payload(live_coach_health)

    kb_lock_timeout_budget_ms = _bounded_int_env(
        "STEPFUN_KB_LOCK_DECISION_TIMEOUT_MS",
        DEFAULT_KB_LOCK_TIMEOUT_BUDGET_MS,
        minimum=100,
        maximum=8000,
    )
    kb_lock_min_pass_score = _bounded_float_env(
        "KNOWLEDGE_KB_LOCK_MIN_PASS_SCORE",
        DEFAULT_KB_LOCK_MIN_PASS_SCORE,
    )
    kb_lock_min_pass_score_keyword = _bounded_float_env(
        "KNOWLEDGE_KB_LOCK_MIN_PASS_SCORE_KEYWORD",
        min(kb_lock_min_pass_score, 0.55),
    )

    kb_lock_status = "pass"
    if kb_lock_required:
        if not kb_bound:
            kb_lock_status = "blocked_no_kb"
        elif kb_lock_last_status and kb_lock_last_status != "not_required":
            kb_lock_status = kb_lock_last_status
        elif last_status == "kb_not_ready" or "[KB_NOT_READY]" in last_error:
            kb_lock_status = "blocked_not_ready"
        elif last_status == "search_failed" or last_error:
            kb_lock_status = "blocked_search_failed"
        elif attempt_count > 0 and hit_query_count <= 0:
            kb_lock_status = "blocked_empty"
    kb_lock_chain_failure = is_kb_lock_chain_failure_status(kb_lock_status)

    status, summary = _derive_retrieval_status_and_summary(
        normalized_kb_ids=normalized_kb_ids,
        internal_retrieval_enabled=internal_retrieval_enabled,
        last_status=last_status,
        last_error=last_error,
        attempt_count=attempt_count,
        hit_query_count=hit_query_count,
    )

    if isinstance(knowledge_answer_diagnostics, dict):
        knowledge_answer_diagnostics = enrich_knowledge_answer_diagnostics(
            knowledge_answer_diagnostics,
            occurred_at=updated_at,
        )

    runtime_events = merge_runtime_events(
        (
            knowledge_answer_diagnostics.get("runtime_events")
            if isinstance(knowledge_answer_diagnostics, dict)
            else []
        ),
        [
            build_kb_lock_runtime_event(
                {
                    "kb_lock_required": kb_lock_required,
                    "kb_lock_status": kb_lock_status,
                    "last_status": last_status,
                    "status": status,
                },
                occurred_at=updated_at,
            )
        ]
        if (kb_lock_required or kb_lock_status.startswith("blocked_"))
        else [],
        [build_claim_truth_runtime_event(claim_truth, occurred_at=updated_at)]
        if isinstance(claim_truth, dict)
        else [],
    )

    return {
        "session_id": str(getattr(session, "session_id", "")),
        "voice_mode": getattr(session, "voice_mode", None),
        "status": status,
        "summary": summary,
        "internal_retrieval_enabled": internal_retrieval_enabled,
        "web_search_enabled": web_search_enabled,
        "network_access_mode": network_access_mode,
        "enforcement_level": enforcement_level,
        "allow_web_search_without_kb": allow_web_search_without_kb,
        "require_kb_grounding": require_kb_grounding,
        "kb_bound": kb_bound,
        "effective_tool_types": list(effective_tool_types or []),
        "instruction_contract_hash": str(
            snapshot.get("instruction_contract_hash") or ""
        ),
        "knowledge_base_ids": normalized_kb_ids,
        "knowledge_base_count": len(normalized_kb_ids),
        "attempt_count": attempt_count,
        "hit_query_count": hit_query_count,
        "total_results": total_results,
        "hit_rate": round(hit_rate, 4),
        "last_query": last_query,
        "last_result_count": last_result_count,
        "last_status": last_status,
        "last_top_k": knowledge_metrics.get("last_top_k"),
        "last_similarity_threshold": knowledge_metrics.get("last_similarity_threshold"),
        "last_error": last_error,
        "last_retrieval_mode": last_retrieval_mode,
        "recent_queries": knowledge_metrics.get("recent_queries")
        if isinstance(knowledge_metrics.get("recent_queries"), list)
        else [],
        "updated_at": updated_at,
        "knowledge_answer_diagnostics": knowledge_answer_diagnostics,
        "runtime_events": runtime_events,
        "kb_lock_required": kb_lock_required,
        "kb_lock_status": kb_lock_status,
        "kb_lock_chain_failure": kb_lock_chain_failure,
        "kb_lock_block_count": kb_lock_block_count,
        "kb_lock_last_status": kb_lock_last_status,
        "kb_lock_updated_at": knowledge_metrics.get("kb_lock_updated_at"),
        "kb_lock_timeout_budget_ms": kb_lock_timeout_budget_ms,
        "kb_lock_min_pass_score": round(kb_lock_min_pass_score, 4),
        "kb_lock_min_pass_score_keyword": round(kb_lock_min_pass_score_keyword, 4),
        "live_session_summary": normalized_live_session_summary,
        "main_issue": main_issue,
        "next_goal": next_goal,
        "claim_truth": claim_truth,
        "claim_truth_status": (
            str(claim_truth.get("status")) if isinstance(claim_truth, dict) else None
        ),
        "claim_truth_source": (
            str(claim_truth.get("source")) if isinstance(claim_truth, dict) else None
        ),
        "coach_health": coach_health,
        "coach_health_status": str(coach_health.get("status") or "healthy"),
        "coach_health_reason": coach_health.get("reason"),
        "coach_health_summary": str(coach_health.get("message") or "实时辅导正常。"),
        "last_decision_id": last_decision_id,
        "last_decision_duration_ms": round(max(0.0, last_decision_duration_ms), 1),
        "last_decision_phase_breakdown": last_decision_phase_breakdown,
        "timeout_rate_5m": round(max(0.0, timeout_rate_5m), 4)
        if has_recent_kb_lock_decisions
        else None,
        "upstream_disconnect_count_5m": upstream_disconnect_count_5m,
        "upstream_unstable": upstream_unstable,
        "retrieval_facts": retrieval_facts,
        "conclusion_evidence": conclusion_evidence,
        "evidence_degradation": None if live_runtime_active else evidence_degradation,
    }


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _bounded_int_env(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(0.0, min(1.0, value))
