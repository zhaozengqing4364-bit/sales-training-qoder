"""Helper utilities for StepFun internal knowledge retrieval flow."""

from __future__ import annotations

from copy import deepcopy
import re
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
    return [str(kb_id) for kb_id in kb_ids if kb_id]


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

        results.append(
            {
                "knowledge_base_id": row.get("knowledge_base_id"),
                "knowledge_base_name": row.get("knowledge_base_name"),
                "score": row.get("score"),
                "snippet": snippet,
                "retrieval_mode": retrieval_mode or "vector",
            }
        )

    if retrieval_modes == {"keyword_fallback"}:
        effective_retrieval_mode = "keyword_fallback"
    elif retrieval_modes == {"hybrid"}:
        effective_retrieval_mode = "hybrid"
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

    snapshot = deepcopy(base_snapshot)
    snapshot_runtime = snapshot.get("runtime_metrics")
    if not isinstance(snapshot_runtime, dict):
        snapshot_runtime = {}

    snapshot_runtime["knowledge_retrieval"] = knowledge_metrics
    snapshot["runtime_metrics"] = snapshot_runtime
    return snapshot
