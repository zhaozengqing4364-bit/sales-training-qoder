"""Knowledge-base lock guard utilities.

Ensures backend-enforced grounding behavior is consistent across AI paths.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from common.db.session import AsyncSessionLocal
from common.knowledge.internal_searcher import search_internal_knowledge
from common.knowledge.retrieval_helpers import (
    resolve_grounding_context_limits,
)
from common.knowledge.service import KnowledgeService


@dataclass(frozen=True)
class KbLockDecision:
    """Decision result for one turn under KB lock policy."""

    lock_required: bool
    allow_generation: bool
    status: str
    grounding_context: str
    user_message: str
    result_count: int = 0
    retrieval_mode: str = ""
    error_detail: str = ""
    decision_id: str = ""
    duration_ms: float = 0.0
    phase_breakdown: dict[str, Any] | None = None


@dataclass(frozen=True)
class RetrievalGroundingDecision:
    """Canonical grounding decision for an already-executed retrieval payload."""

    allow_generation: bool
    status: str
    grounding_context: str
    user_message: str
    answerability_mode: str = "default"
    diagnostics: dict[str, Any] | None = None
    result_count: int = 0
    error_detail: str = ""
    should_apply_output_guard: bool = False


KB_LOCK_CHAIN_FAILURE_STATUSES = {
    "blocked_no_kb",
    "blocked_not_ready",
    "blocked_search_failed",
    "blocked_search_timeout",
    "coach_no_kb",
    "coach_not_ready",
    "coach_search_failed",
    "coach_search_timeout",
}


def is_kb_lock_chain_failure_status(status: str | None) -> bool:
    """Return True when KB-lock status reflects infra/setup failure, not weak evidence."""
    if not isinstance(status, str):
        return False
    return status.strip().lower() in KB_LOCK_CHAIN_FAILURE_STATUSES


def is_kb_lock_required(tool_policy: dict[str, Any] | None) -> bool:
    """Return True when strict KB grounding lock is enabled."""
    if not isinstance(tool_policy, dict):
        return False
    return bool(tool_policy.get("require_kb_grounding", False))


def resolve_kb_lock_mode(tool_policy: dict[str, Any] | None) -> str:
    if not isinstance(tool_policy, dict):
        return "strict_audit"
    mode = str(tool_policy.get("kb_lock_mode") or "strict_audit").strip().lower()
    if mode not in {"strict_audit", "coach_mode"}:
        return "strict_audit"
    return mode


def is_kb_lock_unbound_snapshot(snapshot: object) -> bool:
    """Return True when snapshot requires KB grounding but has no bound KB ids."""
    if not isinstance(snapshot, dict):
        return False
    tool_policy = snapshot.get("tool_policy")
    if not isinstance(tool_policy, dict):
        return False
    lock_required = is_kb_lock_required(tool_policy)
    if not lock_required and _should_auto_require_kb_grounding(
        effective_policy=snapshot,
        tool_policy=tool_policy,
    ):
        lock_required = True
    if not lock_required:
        return False
    knowledge_base_ids = snapshot.get("knowledge_base_ids")
    if not isinstance(knowledge_base_ids, list):
        return True
    return not bool([item for item in knowledge_base_ids if str(item).strip()])


def _normalize_tool_policy(effective_policy: dict[str, Any]) -> dict[str, Any]:
    tool_policy = effective_policy.get("tool_policy")
    if isinstance(tool_policy, dict):
        return tool_policy
    return {}


def _normalize_knowledge_base_ids(effective_policy: dict[str, Any]) -> list[str]:
    raw_ids = effective_policy.get("knowledge_base_ids")
    if not isinstance(raw_ids, list):
        return []
    return [str(item).strip() for item in raw_ids if str(item).strip()]


def _is_true_env(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_min_pass_score() -> float:
    raw_value = os.getenv("KNOWLEDGE_KB_LOCK_MIN_PASS_SCORE", "0.62")
    try:
        score = float(raw_value)
    except (TypeError, ValueError):
        score = 0.62
    return max(0.0, min(1.0, score))


def _resolve_min_pass_score_for_keyword(base_score: float) -> float:
    raw_value = os.getenv(
        "KNOWLEDGE_KB_LOCK_MIN_PASS_SCORE_KEYWORD",
        str(min(base_score, 0.55)),
    )
    try:
        score = float(raw_value)
    except (TypeError, ValueError):
        score = min(base_score, 0.55)
    return max(0.0, min(1.0, score))


def _resolve_kb_lock_embed_timeout_ms() -> int:
    raw_value = os.getenv("KNOWLEDGE_KB_LOCK_EMBED_TIMEOUT_MS", "1200")
    try:
        timeout_ms = int(raw_value)
    except (TypeError, ValueError):
        timeout_ms = 1200
    return max(0, min(10000, timeout_ms))


def _has_explicit_persona_kb_lock_flag(effective_policy: dict[str, Any]) -> bool:
    """
    Detect whether persona policy explicitly configured KB lock.

    When persona explicitly sets `require_kb_grounding`, we must respect that
    decision and skip legacy auto-backfill.
    """
    persona_policy = effective_policy.get("persona_policy")
    if not isinstance(persona_policy, dict):
        return False
    persona_tool_policy = persona_policy.get("tool_policy")
    if not isinstance(persona_tool_policy, dict):
        return False
    return "require_kb_grounding" in persona_tool_policy


def _should_auto_require_kb_grounding(
    *,
    effective_policy: dict[str, Any],
    tool_policy: dict[str, Any],
) -> bool:
    """
    Backward-compatible KB lock default for legacy session snapshots.

    If the snapshot has bound KB and persona policy did not explicitly decide
    `require_kb_grounding`, we auto-enable strict mode for legacy snapshots
    (including old snapshots that persisted `false` as profile default).
    """
    kb_ids = _normalize_knowledge_base_ids(effective_policy)
    if not kb_ids:
        return False
    if _has_explicit_persona_kb_lock_flag(effective_policy):
        return False
    if not _is_true_env("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true"):
        return False
    if "require_kb_grounding" not in tool_policy:
        return True
    return not bool(tool_policy.get("require_kb_grounding", False))


def _build_blocked_user_message(status: str) -> str:
    if status == "blocked_no_kb":
        return (
            "当前会话已开启知识库强制模式，但未绑定可用知识库。"
            "请联系管理员先完成知识库绑定后再继续。"
        )
    if status == "blocked_not_ready":
        return "当前会话已开启知识库强制模式，但知识库文档尚未处理完成。请稍后重试。"
    if status == "blocked_search_failed":
        return (
            "当前会话已开启知识库强制模式，但知识检索失败。请稍后重试或联系管理员排查。"
        )
    return (
        "当前会话已开启知识库强制模式，但未检索到可引用的内部依据。"
        "请提供更具体的产品关键词、版本或业务场景后重试。"
    )


def build_kb_coach_grounding_context(query: str, status: str) -> str:
    return (
        "当前轮处于训练辅导模式。\n"
        "内部知识未能给出足够证据时，你必须继续完成训练，但禁止编造任何具体产品事实、参数、版本或客户案例。\n"
        "不得直接抛出“知识库强制模式”“检索失败”“内部错误”之类系统报错话术。\n"
        "请优先给出表达或讲解层面的反馈；如果必须追问，最多提出1个主问题，不得连续抛出多个问题。\n"
        f"当前状态：{status}\n"
        f"用户原话：{query}\n"
        "输出要求：先给一句简短反馈，再在必要时追问一个更具体的产品关键词、版本或业务场景。"
    )


def _build_coach_mode_decision(
    *,
    query: str,
    status: str,
    started_at: float,
    decision_id: str,
    result_count: int = 0,
    retrieval_mode: str = "",
    error_detail: str = "",
    phase_breakdown: dict[str, Any] | None = None,
) -> KbLockDecision:
    duration_ms = round((time.monotonic() - started_at) * 1000, 1)
    if not isinstance(phase_breakdown, dict):
        phase_breakdown = {"phase_total_ms": duration_ms}
    else:
        phase_breakdown = dict(phase_breakdown)
        phase_breakdown.setdefault("phase_total_ms", duration_ms)
    return KbLockDecision(
        lock_required=True,
        allow_generation=True,
        status=status,
        grounding_context=build_kb_coach_grounding_context(query, status),
        user_message="",
        result_count=result_count,
        retrieval_mode=retrieval_mode,
        error_detail=error_detail,
        decision_id=decision_id,
        duration_ms=duration_ms,
        phase_breakdown=phase_breakdown,
    )


def _build_grounding_context(query: str, retrieval_payload: dict[str, Any]) -> str:
    rows = retrieval_payload.get("results")
    if not isinstance(rows, list):
        return ""

    snippet_limit, snippet_char_limit = resolve_grounding_context_limits(query)
    snippets: list[str] = []
    for index, row in enumerate(rows[:snippet_limit], start=1):
        if not isinstance(row, dict):
            continue
        snippet = str(row.get("snippet") or "").strip()
        if not snippet:
            continue
        snippets.append(f"{index}. {snippet[:snippet_char_limit]}")

    if not snippets:
        return ""

    return (
        "请在当前轮优先依据以下内部知识回答，并保持角色真实自然；若命中片段与模型既有知识冲突，必须以命中片段为准，不得自行补充片段外事实。\n"
        f"用户问题：{query}\n"
        + "\n".join(snippets)
        + "\n若信息不足，请明确说明不确定之处。"
    )


def extract_answerability_diagnostics(payload: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = payload.get("_answerability")
    if not isinstance(diagnostics, dict):
        diagnostics = payload.get("knowledge_answer_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    return dict(diagnostics)


def _extract_answerability(payload: dict[str, Any]) -> str:
    diagnostics = extract_answerability_diagnostics(payload)
    if not isinstance(diagnostics, dict):
        return ""
    return str(diagnostics.get("answerability") or "").strip().lower()


def resolve_answerability_mode(
    diagnostics: dict[str, Any] | None,
    *,
    kb_lock_required: bool,
) -> str:
    """Normalize answerability diagnostics into generation/output-guard modes."""
    if not isinstance(diagnostics, dict):
        return "default"

    answerability = str(diagnostics.get("answerability") or "").strip().lower()
    source_status = str(diagnostics.get("source_status") or "").strip().lower()

    if kb_lock_required and answerability in {"blocked", "insufficient"}:
        return "blocked"
    if answerability == "partial":
        return "partial"
    if answerability in {"blocked", "insufficient"} or source_status in {
        "miss",
        "kb_not_ready",
        "search_failed",
    }:
        return "ungrounded"
    return "grounded"


def build_answerability_instruction_overlay(
    mode: str,
    diagnostics: dict[str, Any] | None,
) -> str:
    """Build the prompt overlay for a canonical answerability mode."""
    if not isinstance(diagnostics, dict):
        return ""

    answerability = str(diagnostics.get("answerability") or "").strip().lower()
    rewritten_queries = diagnostics.get("rewritten_queries")
    citations = diagnostics.get("citations")
    query_line = ""
    if isinstance(rewritten_queries, list):
        normalized_queries = [
            str(item).strip() for item in rewritten_queries if str(item).strip()
        ]
        if normalized_queries:
            query_line = "\n本轮检索改写：" + "；".join(normalized_queries[:4])
    citation_count = len(citations) if isinstance(citations, list) else 0

    if mode == "partial":
        return (
            "\n【回答约束】当前仅有部分内部证据可用。"
            "你只能回答已被当前内部片段直接支持的部分；未被支持的部分必须明确说“当前内部知识库未提供足够依据”。"
            "禁止把推测、常识补充或模型记忆写成内部事实。"
            f"\n当前 answerability：{answerability or 'partial'}；可引用片段数：{citation_count}"
            f"{query_line}"
        )
    if mode == "ungrounded":
        return (
            "\n【回答约束】当前回答不以内部知识库确认为准。"
            "如果继续回答，只能提供一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。"
            "不得把一般性知识描述成企业内部资料、正式产品事实、报价、版本承诺或客户案例。"
            f"\n当前 answerability：{answerability or 'unknown'}；可引用片段数：{citation_count}"
            f"{query_line}"
        )
    if mode == "grounded":
        return (
            "\n【回答约束】当前轮应优先依据已命中的内部片段回答；若片段未覆盖某部分，请明确说明不确定。"
            f"\n当前 answerability：{answerability or 'sufficient'}；可引用片段数：{citation_count}"
            f"{query_line}"
        )
    return ""


def build_blocked_response_from_answerability(
    diagnostics: dict[str, Any] | None,
) -> str:
    if not isinstance(diagnostics, dict):
        return "当前内部知识库没有足够依据回答这个问题，请补充更具体的产品关键词或版本信息。"
    source_status = str(diagnostics.get("source_status") or "").strip().lower()
    if source_status == "kb_not_ready":
        return "当前内部知识库尚未就绪，暂时无法基于内部资料回答。请稍后重试，或补充更具体的产品关键词。"
    if source_status == "search_failed":
        return "当前内部知识检索失败，暂时无法基于内部资料安全回答。请稍后重试。"
    return "当前内部知识库没有足够依据回答这个问题，请补充更具体的产品关键词或版本信息。"


def _split_response_sentences(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    sentences = re.findall(r"[^。！？!?]+[。！？!?]?", normalized)
    cleaned = [sentence.strip() for sentence in sentences if sentence.strip()]
    return cleaned or [normalized]


def apply_answerability_output_guard(
    response_text: str,
    diagnostics: dict[str, Any] | None,
) -> str:
    """Trim unsupported generated claims when answerability is partial."""
    if not isinstance(diagnostics, dict):
        return response_text

    answerability = str(diagnostics.get("answerability") or "").strip().lower()
    if answerability != "partial":
        return response_text

    citations = diagnostics.get("citations")
    if not isinstance(citations, list) or not citations:
        return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"

    support_texts: list[str] = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        for key in ("claim", "snippet"):
            value = str(citation.get(key) or "").strip()
            if value:
                support_texts.append(value)

    if not support_texts:
        return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"

    kept_sentences: list[str] = []
    for sentence in _split_response_sentences(response_text):
        compact_sentence = sentence.replace(" ", "")
        if any(
            compact_sentence
            and (
                compact_sentence in support_text.replace(" ", "")
                or support_text.replace(" ", "") in compact_sentence
            )
            for support_text in support_texts
        ):
            kept_sentences.append(sentence)

    if kept_sentences:
        return "".join(kept_sentences)
    return "当前内部知识库仅支持部分信息，暂无法确认更多细节。"


def evaluate_retrieval_grounding_decision(
    *,
    query: str,
    effective_policy: dict[str, Any],
    retrieval_payload: dict[str, Any],
) -> RetrievalGroundingDecision:
    """Evaluate generation permission from a retrieval payload in one place."""
    normalized_query = str(query or "").strip()
    tool_policy = _normalize_tool_policy(effective_policy)
    kb_lock_required = is_kb_lock_required(tool_policy)
    kb_ids = _normalize_knowledge_base_ids(effective_policy)
    has_bound_knowledge_base = bool(kb_ids)
    diagnostics = extract_answerability_diagnostics(retrieval_payload)
    answerability_mode = resolve_answerability_mode(
        diagnostics,
        kb_lock_required=kb_lock_required,
    )
    result_count = max(0, int(retrieval_payload.get("count") or 0))

    if result_count <= 0:
        if has_bound_knowledge_base:
            return RetrievalGroundingDecision(
                allow_generation=False,
                status="blocked_empty",
                grounding_context="",
                user_message=(
                    "当前内部知识库没有足够依据回答这个问题，"
                    "请补充更具体的关键词、版本信息或业务场景。"
                ),
                answerability_mode=answerability_mode,
                diagnostics=diagnostics,
                result_count=result_count,
            )
        return RetrievalGroundingDecision(
            allow_generation=True,
            status="no_context",
            grounding_context="",
            user_message="",
            answerability_mode=answerability_mode,
            diagnostics=diagnostics,
            result_count=result_count,
        )

    grounding_context = _build_grounding_context(normalized_query, retrieval_payload)
    if not grounding_context:
        if has_bound_knowledge_base:
            return RetrievalGroundingDecision(
                allow_generation=False,
                status="blocked_empty",
                grounding_context="",
                user_message=(
                    "当前检索结果缺少可直接引用的内部片段，"
                    "暂时无法基于内部知识库回答这个问题。"
                ),
                answerability_mode=answerability_mode,
                diagnostics=diagnostics,
                result_count=result_count,
            )
        return RetrievalGroundingDecision(
            allow_generation=True,
            status="guardrail_context",
            grounding_context=(
                "当前检索结果缺少可直接引用的内部片段。\n"
                f"用户问题：{normalized_query}\n"
                "如果继续回答，只能给出一般性参考，并必须明确标注“以下回答不以内部知识库确认为准”。\n"
                "不得把未被内部片段支持的内容说成公司正式资料或确定产品事实。"
            ),
            user_message="",
            answerability_mode=answerability_mode,
            diagnostics=diagnostics,
            result_count=result_count,
        )

    if (
        has_bound_knowledge_base
        and answerability_mode in {"ungrounded", "blocked"}
    ):
        return RetrievalGroundingDecision(
            allow_generation=False,
            status="blocked_answerability",
            grounding_context="",
            user_message=build_blocked_response_from_answerability(diagnostics),
            answerability_mode=answerability_mode,
            diagnostics=diagnostics,
            result_count=result_count,
        )
    if answerability_mode == "blocked":
        return RetrievalGroundingDecision(
            allow_generation=False,
            status="blocked_answerability",
            grounding_context="",
            user_message=build_blocked_response_from_answerability(diagnostics),
            answerability_mode=answerability_mode,
            diagnostics=diagnostics,
            result_count=result_count,
        )

    overlay = build_answerability_instruction_overlay(answerability_mode, diagnostics)
    if overlay:
        grounding_context += overlay
    return RetrievalGroundingDecision(
        allow_generation=True,
        status="grounded",
        grounding_context=grounding_context,
        user_message="",
        answerability_mode=answerability_mode,
        diagnostics=diagnostics,
        result_count=result_count,
        should_apply_output_guard=answerability_mode == "partial",
    )


async def _noop_record_metric(**_kwargs: Any) -> None:
    return None


async def evaluate_kb_lock_decision(
    *,
    query: str,
    effective_policy: dict[str, Any],
    record_metric: Callable[..., Awaitable[None]] | None = None,
    decision_id: str = "",
) -> KbLockDecision:
    """Evaluate one-turn KB lock decision with deterministic pass/block result."""
    started_at = time.monotonic()
    normalized_query = str(query or "").strip()
    tool_policy = _normalize_tool_policy(effective_policy)
    lock_required = is_kb_lock_required(tool_policy)
    kb_lock_mode = resolve_kb_lock_mode(tool_policy)
    if not lock_required and _should_auto_require_kb_grounding(
        effective_policy=effective_policy,
        tool_policy=tool_policy,
    ):
        lock_required = True

    if not lock_required:
        return KbLockDecision(
            lock_required=False,
            allow_generation=True,
            status="pass",
            grounding_context="",
            user_message="",
            decision_id=decision_id,
            duration_ms=round((time.monotonic() - started_at) * 1000, 1),
            phase_breakdown={
                "phase_total_ms": round((time.monotonic() - started_at) * 1000, 1)
            },
        )

    kb_ids = _normalize_knowledge_base_ids(effective_policy)
    if not kb_ids:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_no_kb",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_no_kb"),
            decision_id=decision_id,
            duration_ms=round((time.monotonic() - started_at) * 1000, 1),
            phase_breakdown={
                "phase_total_ms": round((time.monotonic() - started_at) * 1000, 1)
            },
        )

    if not normalized_query:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_empty",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_empty"),
            decision_id=decision_id,
            duration_ms=round((time.monotonic() - started_at) * 1000, 1),
            phase_breakdown={
                "phase_total_ms": round((time.monotonic() - started_at) * 1000, 1)
            },
        )

    try:
        retrieval_top_k = int(tool_policy.get("retrieval_top_k", 5) or 5)
    except (TypeError, ValueError):
        retrieval_top_k = 5

    metric_cb = record_metric or _noop_record_metric
    payload = await search_internal_knowledge(
        arguments_obj={
            "query": normalized_query,
            "top_k": max(1, min(8, retrieval_top_k)),
            "embedding_timeout_ms": _resolve_kb_lock_embed_timeout_ms(),
        },
        effective_policy=effective_policy,
        session_factory=AsyncSessionLocal,
        knowledge_service_cls=KnowledgeService,
        record_metric=metric_cb,
    )
    diagnostics = payload.get("_diagnostics") if isinstance(payload, dict) else {}
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    total_ms = round((time.monotonic() - started_at) * 1000, 1)
    phase_breakdown = dict(diagnostics)
    phase_breakdown.setdefault("phase_total_ms", total_ms)

    if not isinstance(payload, dict):
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_search_failed",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_search_failed"),
            error_detail="invalid_retrieval_payload",
            decision_id=decision_id,
            duration_ms=total_ms,
            phase_breakdown=phase_breakdown,
        )

    result_count = max(0, int(payload.get("count") or 0))
    retrieval_mode = str(payload.get("retrieval_mode") or "")
    status_message = str(payload.get("message") or "")
    error_detail = str(payload.get("error") or "")
    max_score = 0.0
    has_scored_row = False
    rows = payload.get("results") if isinstance(payload, dict) else []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            score_value = row.get("score")
            if score_value is None:
                continue
            try:
                score = float(score_value)
            except (TypeError, ValueError):
                continue
            has_scored_row = True
            if score > max_score:
                max_score = score
    min_pass_score = _resolve_min_pass_score()
    min_pass_score_keyword = _resolve_min_pass_score_for_keyword(min_pass_score)
    effective_min_pass_score = min_pass_score
    if retrieval_mode in {"keyword_fallback", "mixed"}:
        effective_min_pass_score = min_pass_score_keyword
    phase_breakdown.setdefault("max_score", round(max_score, 4))
    phase_breakdown.setdefault("min_pass_score", round(effective_min_pass_score, 4))
    phase_breakdown.setdefault("min_pass_score_vector", round(min_pass_score, 4))
    phase_breakdown.setdefault(
        "min_pass_score_keyword", round(min_pass_score_keyword, 4)
    )

    if error_detail:
        status = "blocked_search_failed"
    elif has_scored_row and max_score < effective_min_pass_score:
        status = "blocked_empty"
        error_detail = (
            f"[KB_LOCK_LOW_CONFIDENCE] max_score={max_score:.4f} "
            f"< min_pass_score={effective_min_pass_score:.4f}"
        )
    elif "未关联内部知识库" in status_message:
        status = "blocked_no_kb"
    elif "尚未处理完成" in status_message:
        status = "blocked_not_ready"
    elif result_count <= 0:
        status = "blocked_empty"
    else:
        status = "pass"

    answerability = _extract_answerability(payload)
    if (
        status == "pass"
        and kb_lock_mode == "strict_audit"
        and answerability in {"blocked", "insufficient", "partial"}
    ):
        status = "blocked_empty"
        error_detail = f"[KB_LOCK_ANSWERABILITY_{answerability.upper()}]"
        phase_breakdown.setdefault("answerability", answerability)

    if status != "pass":
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status=status,
            grounding_context="",
            user_message=_build_blocked_user_message(status),
            result_count=result_count,
            retrieval_mode=retrieval_mode,
            error_detail=error_detail,
            decision_id=decision_id,
            duration_ms=total_ms,
            phase_breakdown=phase_breakdown,
        )

    grounding_context = _build_grounding_context(normalized_query, payload)
    if not grounding_context:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_empty",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_empty"),
            result_count=result_count,
            retrieval_mode=retrieval_mode,
            decision_id=decision_id,
            duration_ms=total_ms,
            phase_breakdown=phase_breakdown,
        )

    return KbLockDecision(
        lock_required=True,
        allow_generation=True,
        status="pass",
        grounding_context=grounding_context,
        user_message="",
        result_count=result_count,
        retrieval_mode=retrieval_mode,
        decision_id=decision_id,
        duration_ms=total_ms,
        phase_breakdown=phase_breakdown,
    )
