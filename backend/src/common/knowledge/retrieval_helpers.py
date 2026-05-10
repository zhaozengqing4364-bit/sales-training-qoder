"""Helper utilities for StepFun internal knowledge retrieval flow."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.58
ENTITY_TOKEN_RE = re.compile(
    r"(?:[a-z]+\d+[a-z0-9-]*|v?\d+(?:\.\d+){0,2})", re.IGNORECASE
)
SALES_OBJECTION_QUERY_RE = re.compile(
    r"roi|预算|报价|价格|竞品|竞对|对比|替代|实施|落地|风险|案例|证据|收益|回报|proof|evidence|competitor|pricing|price|budget|case",
    re.IGNORECASE,
)
PRODUCT_OVERVIEW_QUERY_RE = re.compile(
    r"介绍|是什么|做什么|产品|平台|方案|系统|能力|功能|版本|定位|适用|场景",
    re.IGNORECASE,
)
MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES = 10
MAX_KNOWLEDGE_RETRIEVAL_RESULT_SUMMARIES = 3
MAX_KNOWLEDGE_RETRIEVAL_QUERY_CHARS = 160
MAX_KNOWLEDGE_RETRIEVAL_ERROR_CHARS = 240
MAX_KNOWLEDGE_RETRIEVAL_SNIPPET_CHARS = 240
MAX_KNOWLEDGE_RETRIEVAL_LEDGER_KB_IDS = 8
MAX_RETRIEVAL_QUERY_VARIANTS = 4
MAX_ANSWER_CITATIONS = 6
QUERY_EVIDENCE_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.IGNORECASE)
QUERY_STOP_PHRASES = (
    "请",
    "帮我",
    "麻烦",
    "一下",
    "介绍一下",
    "介绍",
    "讲一下",
    "说一下",
    "告诉我",
    "什么是",
    "是什么",
    "有哪些",
    "如何",
    "怎么",
    "产品介绍",
    "产品",
    "公司",
    "情况",
    "信息",
)
GENERIC_QUERY_TERMS = {
    "科技",
    "公司",
    "产品",
    "介绍",
    "一下",
    "情况",
    "信息",
    "能力",
    "功能",
    "业务",
    "服务",
}


def _normalize_whitespace(value: Any) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    return " ".join(value.split())


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _normalize_result_summary(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None

    knowledge_base_id = _normalize_whitespace(result.get("knowledge_base_id"))
    if not knowledge_base_id:
        return None

    summary: dict[str, Any] = {
        "knowledge_base_id": knowledge_base_id,
        "knowledge_base_name": _normalize_whitespace(result.get("knowledge_base_name")),
        "snippet": _truncate_text(
            _normalize_whitespace(result.get("snippet") or result.get("content")),
            MAX_KNOWLEDGE_RETRIEVAL_SNIPPET_CHARS,
        ),
        "retrieval_mode": _normalize_whitespace(result.get("retrieval_mode"))
        or "vector",
    }

    score = result.get("score")
    try:
        if score is not None and str(score).strip() != "":
            summary["score"] = round(float(score), 4)
    except (TypeError, ValueError):
        pass

    document_title = _normalize_whitespace(
        result.get("document_title")
        or result.get("source")
        or (result.get("metadata") or {}).get("document_title")
        if isinstance(result.get("metadata"), dict)
        else result.get("document_title") or result.get("source")
    )
    if document_title:
        summary["document_title"] = document_title

    return summary


def _normalize_recent_attempts(recent_attempts: Any) -> list[dict[str, Any]] | None:
    if recent_attempts is None:
        return []
    if not isinstance(recent_attempts, list):
        return None

    normalized_attempts: list[dict[str, Any]] = []
    for item in recent_attempts:
        normalized_item = normalize_knowledge_retrieval_ledger_event(item)
        if normalized_item is None:
            return None
        normalized_attempts.append(normalized_item)

    return normalized_attempts[-MAX_KNOWLEDGE_RETRIEVAL_LEDGER_ENTRIES:]


def is_sales_objection_query(query: str) -> bool:
    normalized = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query.lower()))
    if not normalized:
        return False
    return bool(SALES_OBJECTION_QUERY_RE.search(normalized))


def is_entity_focused_query(query: str) -> bool:
    normalized = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query.lower()))
    if not normalized:
        return False
    if is_sales_objection_query(query):
        return True
    if len(normalized) <= 12:
        return True
    if ENTITY_TOKEN_RE.search(normalized):
        return True
    return bool(re.search(r"产品|型号|版本|名录|清单|报价|价格|参数", normalized))


def is_product_overview_query(query: str) -> bool:
    normalized = _normalize_whitespace(query)
    if not normalized:
        return False
    return bool(PRODUCT_OVERVIEW_QUERY_RE.search(normalized))


def _build_lexicon_query_variants(
    query: str,
    tool_policy: dict[str, Any] | None,
) -> list[str]:
    """Build safe query variants from configured ASR alias lexicon."""
    if not isinstance(tool_policy, dict):
        return []
    entries = tool_policy.get("transcript_normalization_lexicon")
    if not isinstance(entries, list):
        return []

    variants: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        canonical_term = _normalize_whitespace(entry.get("canonical_term"))
        aliases = entry.get("aliases")
        if not canonical_term or not isinstance(aliases, list):
            continue
        for raw_alias in aliases:
            alias = _normalize_whitespace(raw_alias)
            if not alias or alias == canonical_term:
                continue
            if alias in query:
                variants.append(query.replace(alias, canonical_term))
            if canonical_term in query:
                variants.append(query.replace(canonical_term, alias))
    return variants


def build_rewritten_queries(
    query: str,
    tool_policy: dict[str, Any] | None = None,
) -> list[str]:
    normalized = _normalize_whitespace(query)
    if not normalized:
        return []

    variants: list[str] = [normalized]
    variants.extend(_build_lexicon_query_variants(normalized, tool_policy))
    if is_product_overview_query(normalized):
        entity_hint = normalized
        variants.extend(
            [
                f"{entity_hint} 产品介绍",
                f"{entity_hint} 核心能力",
                f"{entity_hint} 适用场景",
            ]
        )

    deduped: list[str] = []
    for item in variants:
        candidate = _normalize_whitespace(item)
        if not candidate or candidate in deduped:
            continue
        deduped.append(candidate)
        if len(deduped) >= MAX_RETRIEVAL_QUERY_VARIANTS:
            break
    return deduped


def resolve_grounding_context_limits(query: str) -> tuple[int, int]:
    compact_query = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query.lower()))
    if is_sales_objection_query(query):
        return 6, 420
    if is_entity_focused_query(query):
        return 5, 360
    if len(compact_query) >= 30:
        return 4, 280
    return 3, 220


def normalize_query(arguments_obj: dict[str, Any]) -> str:
    """Normalize retrieval query from function-call arguments."""
    return str(arguments_obj.get("query") or "").strip()


def normalize_knowledge_base_ids(effective_policy: dict[str, Any]) -> list[str]:
    """Normalize knowledge base ids list from effective policy."""
    kb_ids = effective_policy.get("knowledge_base_ids") or []
    if not isinstance(kb_ids, list):
        return []

    normalized_ids: list[str] = []
    for kb_id in kb_ids:
        normalized_kb_id = _normalize_whitespace(kb_id)
        if not normalized_kb_id or normalized_kb_id in normalized_ids:
            continue
        normalized_ids.append(normalized_kb_id)
    return normalized_ids


def resolve_retrieval_params(
    arguments_obj: dict[str, Any],
    tool_policy: dict[str, Any],
    query: str = "",
) -> tuple[int, float, bool, int]:
    """Resolve retrieval runtime parameters with safe defaults."""
    top_k_value = arguments_obj.get(
        "top_k", tool_policy.get("retrieval_top_k", DEFAULT_TOP_K)
    )
    threshold_value = tool_policy.get(
        "retrieval_similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD
    )

    try:
        top_k = max(1, int(top_k_value))
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K

    try:
        threshold = float(threshold_value)
    except (TypeError, ValueError):
        threshold = DEFAULT_SIMILARITY_THRESHOLD

    sales_objection_query = is_sales_objection_query(query)
    entity_focused_query = is_entity_focused_query(query)
    compact_query = "".join(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query.lower()))

    if "top_k" not in arguments_obj:
        if sales_objection_query:
            top_k = min(10, max(top_k, 7))
        elif entity_focused_query:
            top_k = min(8, max(top_k, 6))
        elif is_product_overview_query(query):
            top_k = min(8, max(top_k, 5))

    if sales_objection_query:
        threshold = max(0.42, threshold - 0.10)
    elif entity_focused_query:
        threshold = max(0.45, threshold - 0.08)
    elif len(compact_query) >= 30:
        threshold = max(0.5, threshold - 0.05)

    enable_hybrid = bool(tool_policy.get("retrieval_enable_hybrid", True))
    keyword_candidate_limit_raw = tool_policy.get(
        "retrieval_keyword_candidate_limit", 32
    )
    try:
        keyword_candidate_limit = max(8, int(keyword_candidate_limit_raw))
    except (TypeError, ValueError):
        keyword_candidate_limit = 32

    if sales_objection_query:
        keyword_candidate_limit = max(keyword_candidate_limit, 48)

    return top_k, round(threshold, 4), enable_hybrid, keyword_candidate_limit


def resolve_rerank_params(tool_policy: dict[str, Any]) -> tuple[bool, int]:
    """Resolve lightweight rerank stage parameters."""
    enable_rerank = bool(tool_policy.get("retrieval_enable_rerank", True))
    rerank_top_k_raw = tool_policy.get("retrieval_rerank_top_k", 8)
    try:
        rerank_top_k = max(1, int(rerank_top_k_raw))
    except (TypeError, ValueError):
        rerank_top_k = 8
    return enable_rerank, rerank_top_k


def resolve_metadata_filter(
    arguments_obj: dict[str, Any],
    tool_policy: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve optional metadata filter from request args/tool policy."""
    raw_filter = arguments_obj.get("metadata_filter")
    if not isinstance(raw_filter, dict):
        raw_filter = tool_policy.get("retrieval_metadata_filter")

    if not isinstance(raw_filter, dict):
        return None

    normalized_filter: dict[str, Any] = {}
    for key, value in raw_filter.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        if isinstance(value, list):
            candidates = [
                item
                for item in value
                if isinstance(item, (str, int, float, bool)) and str(item).strip()
            ]
            if candidates:
                normalized_filter[normalized_key] = candidates
        elif isinstance(value, (str, int, float, bool)):
            if str(value).strip():
                normalized_filter[normalized_key] = value

    return normalized_filter or None


def build_missing_query_payload() -> dict[str, Any]:
    return {
        "query": "",
        "count": 0,
        "results": [],
        "message": "缺少 query 参数",
    }


def build_no_kb_payload(query: str) -> dict[str, Any]:
    return {
        "query": query,
        "count": 0,
        "results": [],
        "message": "当前会话未关联内部知识库",
    }


def build_kb_not_ready_payload(query: str) -> dict[str, Any]:
    return {
        "query": query,
        "count": 0,
        "results": [],
        "message": "内部知识库文档尚未处理完成，请稍后重试",
    }


def build_search_failed_payload(query: str, error_detail: str) -> dict[str, Any]:
    return {
        "query": query,
        "count": 0,
        "results": [],
        "message": "知识检索失败",
        "error": error_detail,
    }


def build_answerability_assessment(
    *,
    query: str,
    results: list[dict[str, Any]],
    source_status: str,
    strict_kb_mode: bool,
    rewritten_queries: list[str] | None = None,
) -> dict[str, Any]:
    citations = [
        {
            "claim": _truncate_text(
                _normalize_whitespace(item.get("snippet") or ""), 120
            ),
            "knowledge_base_id": item.get("knowledge_base_id"),
            "knowledge_base_name": item.get("knowledge_base_name"),
            "document_title": item.get("document_title") or None,
            "snippet": item.get("snippet"),
            "score": item.get("score"),
        }
        for item in results[:MAX_ANSWER_CITATIONS]
        if isinstance(item, dict) and _normalize_whitespace(item.get("snippet"))
    ]

    evidence_supported = _has_query_evidence_support(
        query=query,
        results=results,
        rewritten_queries=rewritten_queries,
    )

    if source_status in {
        "search_failed",
        "kb_not_ready",
        "no_kb_bound",
        "missing_query",
    }:
        answerability = "blocked"
    elif not results:
        answerability = "insufficient"
    elif not evidence_supported:
        answerability = "insufficient"
    elif is_product_overview_query(query) and len(results) < 2:
        answerability = "partial"
    else:
        answerability = "sufficient"

    return {
        "mode": "grounded_strict" if strict_kb_mode else "grounded_preferred",
        "answerability": answerability,
        "source_status": source_status,
        "query": query,
        "rewritten_queries": list(rewritten_queries or []),
        "citations": citations,
        "evidence_supported": evidence_supported,
    }


def _normalize_for_query_evidence(value: Any) -> str:
    return "".join(QUERY_EVIDENCE_RE.findall(str(value or "").lower()))


def _strip_query_stop_phrases(value: str) -> str:
    stripped = value
    for phrase in QUERY_STOP_PHRASES:
        stripped = stripped.replace(_normalize_for_query_evidence(phrase), "")
    return stripped


def _collect_query_terms(value: str) -> list[str]:
    normalized = _strip_query_stop_phrases(_normalize_for_query_evidence(value))
    if not normalized:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    if len(normalized) >= 2 and normalized not in GENERIC_QUERY_TERMS:
        seen.add(normalized)
        terms.append(normalized)
    for ngram_size in (4, 3, 2):
        if len(normalized) < ngram_size:
            continue
        for index in range(0, len(normalized) - ngram_size + 1):
            term = normalized[index : index + ngram_size]
            if term in seen or term in GENERIC_QUERY_TERMS:
                continue
            seen.add(term)
            terms.append(term)
    return terms[:16]


def _collect_evidence_text(results: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        raw_metadata = item.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        for key in ("snippet", "content", "document_title", "source"):
            value = str(item.get(key) or "").strip()
            if value:
                parts.append(value)
        for key in ("document_title", "section", "doc_type"):
            value = str(metadata.get(key) or "").strip()
            if value:
                parts.append(value)
    return _normalize_for_query_evidence(" ".join(parts))


def _has_query_evidence_support(
    *,
    query: str,
    results: list[dict[str, Any]],
    rewritten_queries: list[str] | None = None,
) -> bool:
    evidence_text = _collect_evidence_text(results)
    if not evidence_text:
        return False

    query_candidates = [query, *(rewritten_queries or [])]
    has_meaningful_candidate = False
    for candidate in query_candidates:
        terms = _collect_query_terms(candidate)
        if not terms:
            continue
        has_meaningful_candidate = True
        if any(len(term) >= 3 and term in evidence_text for term in terms):
            return True
        supported_short_terms = [
            term for term in terms if len(term) == 2 and term in evidence_text
        ]
        if len(supported_short_terms) >= 2:
            return True
    return not has_meaningful_candidate


def build_knowledge_retrieval_ledger_event(
    *,
    query: str,
    status: str,
    result_count: Any,
    retrieval_mode: str | None = None,
    knowledge_base_ids: list[Any] | None = None,
    error_message: str | None = None,
    results: list[dict[str, Any]] | None = None,
    attempted_at: str | None = None,
) -> dict[str, Any]:
    """Build one provider-neutral, bounded retrieval ledger event."""
    try:
        safe_result_count = max(0, int(result_count))
    except (TypeError, ValueError):
        safe_result_count = 0

    normalized_results: list[dict[str, Any]] = []
    for result in results or []:
        normalized_result = _normalize_result_summary(result)
        if normalized_result is None:
            continue
        normalized_results.append(normalized_result)
        if len(normalized_results) >= MAX_KNOWLEDGE_RETRIEVAL_RESULT_SUMMARIES:
            break

    normalized_kb_ids = normalize_knowledge_base_ids(
        {"knowledge_base_ids": knowledge_base_ids or []}
    )[:MAX_KNOWLEDGE_RETRIEVAL_LEDGER_KB_IDS]

    attempted_at_value = _normalize_whitespace(attempted_at)
    if not attempted_at_value:
        attempted_at_value = datetime.now(UTC).isoformat()

    return {
        "attempted_at": attempted_at_value,
        "query": _truncate_text(
            _normalize_whitespace(query),
            MAX_KNOWLEDGE_RETRIEVAL_QUERY_CHARS,
        ),
        "status": _normalize_whitespace(status) or "unknown",
        "result_count": safe_result_count,
        "retrieval_mode": _normalize_whitespace(retrieval_mode) or None,
        "knowledge_base_ids": normalized_kb_ids,
        "error_summary": _truncate_text(
            _normalize_whitespace(error_message),
            MAX_KNOWLEDGE_RETRIEVAL_ERROR_CHARS,
        )
        or None,
        "result_summaries": normalized_results,
    }


def normalize_knowledge_retrieval_ledger_event(
    ledger_event: Any,
) -> dict[str, Any] | None:
    """Normalize a possibly malformed ledger event payload for persistence."""
    if ledger_event is None:
        return None
    if not isinstance(ledger_event, dict):
        return None

    raw_results = ledger_event.get("result_summaries")
    if raw_results is None:
        raw_results = ledger_event.get("results")
    if raw_results is not None and not isinstance(raw_results, list):
        return None

    return build_knowledge_retrieval_ledger_event(
        query=str(ledger_event.get("query") or ""),
        status=str(ledger_event.get("status") or "unknown"),
        result_count=ledger_event.get("result_count"),
        retrieval_mode=(
            str(ledger_event.get("retrieval_mode"))
            if ledger_event.get("retrieval_mode") is not None
            else None
        ),
        knowledge_base_ids=ledger_event.get("knowledge_base_ids") or [],
        error_message=(
            str(ledger_event.get("error_summary"))
            if ledger_event.get("error_summary") is not None
            else (
                str(ledger_event.get("error_message"))
                if ledger_event.get("error_message") is not None
                else None
            )
        ),
        results=raw_results,
        attempted_at=(
            str(ledger_event.get("attempted_at"))
            if ledger_event.get("attempted_at") is not None
            else None
        ),
    )


def transform_search_rows(
    rows: list[dict[str, Any]],
    top_k: int,
    query: str = "",
) -> tuple[list[dict[str, Any]], str, str]:
    """
    Transform raw retrieval rows to response payload items.

    Returns: (results, effective_retrieval_mode, status)
    """
    results: list[dict[str, Any]] = []
    retrieval_modes: set[str] = set()
    _, snippet_char_limit = resolve_grounding_context_limits(query)

    for row in rows[:top_k]:
        content = str(row.get("content") or "")
        snippet = content[:snippet_char_limit]
        retrieval_mode = str(row.get("retrieval_mode") or "").strip()
        if retrieval_mode:
            retrieval_modes.add(retrieval_mode)

        raw_metadata = row.get("metadata")
        metadata: dict[str, Any] = (
            raw_metadata if isinstance(raw_metadata, dict) else {}
        )
        result_item = {
            "knowledge_base_id": row.get("knowledge_base_id"),
            "knowledge_base_name": row.get("knowledge_base_name"),
            "score": row.get("score"),
            "snippet": snippet,
            "retrieval_mode": retrieval_mode or "vector",
            "document_title": row.get("document_title")
            or row.get("source")
            or metadata.get("document_title"),
        }
        if isinstance(row.get("score_breakdown"), dict):
            result_item["score_breakdown"] = dict(row["score_breakdown"])
        if row.get("ranking_passed") is not None:
            result_item["ranking_passed"] = bool(row.get("ranking_passed"))
        results.append(result_item)

    if retrieval_modes == {"keyword_fallback"}:
        effective_retrieval_mode = "keyword_fallback"
    elif retrieval_modes == {"hybrid"}:
        effective_retrieval_mode = "hybrid"
    elif retrieval_modes == {"vector"}:
        effective_retrieval_mode = "vector"
    elif retrieval_modes:
        effective_retrieval_mode = "mixed"
    else:
        effective_retrieval_mode = "vector"

    status = "hit" if results else "miss"
    if results and effective_retrieval_mode == "keyword_fallback":
        status = "hit_keyword_fallback"

    return results, effective_retrieval_mode, status


def merge_runtime_metrics_snapshot(
    *,
    base_snapshot: dict[str, Any],
    runtime_metrics: dict[str, Any],
) -> dict[str, Any] | None:
    """Merge runtime_metrics.knowledge_retrieval into existing snapshot immutably."""
    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    if not isinstance(knowledge_metrics, dict):
        return None

    normalized_recent_attempts = _normalize_recent_attempts(
        knowledge_metrics.get("recent_attempts")
    )
    if normalized_recent_attempts is None:
        return None

    normalized_knowledge_metrics = deepcopy(knowledge_metrics)
    normalized_knowledge_metrics["recent_attempts"] = normalized_recent_attempts

    snapshot = deepcopy(base_snapshot)
    snapshot_runtime = snapshot.get("runtime_metrics")
    if not isinstance(snapshot_runtime, dict):
        snapshot_runtime = {}
    else:
        snapshot_runtime = deepcopy(snapshot_runtime)

    snapshot_runtime["knowledge_retrieval"] = normalized_knowledge_metrics
    snapshot["runtime_metrics"] = snapshot_runtime
    return snapshot
