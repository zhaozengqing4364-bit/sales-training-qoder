"""Shared runtime diagnostics helpers for knowledge-check and support health readers."""

from __future__ import annotations

import os
from typing import Any

from common.db.models import PracticeSession
from common.effectiveness import coerce_live_session_conclusion_summary
from common.knowledge.kb_lock_guard import is_kb_lock_chain_failure_status


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
        isinstance(item, str) and item.strip()
        for item in (goal_type, goal_text, rule)
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
        message = default_payload["message"] if status == "healthy" else (
            "实时辅导暂不可用，训练仍可继续。"
            if status == "degraded"
            else "实时辅导已恢复，后续建议会继续更新。"
        )
    return {
        "status": status,
        "reason": reason.strip() if isinstance(reason, str) and reason.strip() else None,
        "message": message.strip(),
    }


def build_session_runtime_diagnostics(
    *,
    session: PracticeSession,
    snapshot: dict[str, Any] | None,
    effective_tool_types: list[str] | None = None,
    live_claim_truth: dict[str, Any] | None = None,
    live_coach_health: dict[str, Any] | None = None,
    live_session_summary: dict[str, Any] | None = None,
    live_runtime_active: bool = False,
    projection_effectiveness_snapshot: dict[str, Any] | None = None,
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

    attempt_count = int(knowledge_metrics.get("attempt_count") or 0)
    hit_query_count = int(knowledge_metrics.get("hit_query_count") or 0)
    total_results = int(knowledge_metrics.get("total_results") or 0)
    last_result_count = int(knowledge_metrics.get("last_result_count") or 0)
    hit_rate = _coerce_float(knowledge_metrics.get("hit_rate") or 0.0)

    last_status = str(knowledge_metrics.get("last_status") or "not_triggered")
    last_error = str(knowledge_metrics.get("last_error") or "")
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
    has_recent_kb_lock_decisions = isinstance(kb_lock_decision_timestamps, list) and bool(
        kb_lock_decision_timestamps
    )
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
            (
                normalized_live_session_summary.get("claim_truth")
                if isinstance(normalized_live_session_summary, dict)
                else None
            )
            or _normalize_claim_truth_payload(live_claim_truth)
        )
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
            or _normalize_next_goal_payload(session_effectiveness_snapshot.get("next_goal"))
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
            or _normalize_claim_truth_payload(session_effectiveness_snapshot.get("claim_truth"))
        )
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

    if not normalized_kb_ids:
        status = "no_knowledge_base"
        summary = "当前会话未绑定知识库"
    elif not internal_retrieval_enabled:
        status = "disabled"
        summary = "内部知识检索未启用"
    elif last_status == "kb_not_ready" or "[KB_NOT_READY]" in last_error:
        status = "kb_not_ready"
        summary = "知识库文档尚未处理完成"
    elif last_status == "search_failed" or "[KNOWLEDGE_SEARCH_UNAVAILABLE]" in last_error:
        status = "search_failed"
        summary = "知识检索触发失败，请检查知识库或 Embedding 服务"
    elif attempt_count == 0:
        status = "not_triggered"
        summary = "本次对话尚未触发知识检索"
    elif hit_query_count > 0:
        status = "hit"
        summary = "知识检索已触发并命中知识库"
    else:
        status = "miss"
        summary = "知识检索已触发，但本次未命中有效内容"

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
        "last_query": str(knowledge_metrics.get("last_query") or ""),
        "last_result_count": last_result_count,
        "last_status": last_status,
        "last_top_k": knowledge_metrics.get("last_top_k"),
        "last_similarity_threshold": knowledge_metrics.get("last_similarity_threshold"),
        "last_error": last_error,
        "last_retrieval_mode": str(knowledge_metrics.get("last_retrieval_mode") or ""),
        "recent_queries": knowledge_metrics.get("recent_queries")
        if isinstance(knowledge_metrics.get("recent_queries"), list)
        else [],
        "updated_at": knowledge_metrics.get("updated_at"),
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
