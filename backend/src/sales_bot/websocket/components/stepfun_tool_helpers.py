"""Helper utilities for StepFun tool definition building."""

from __future__ import annotations

from typing import Any


def build_stepfun_tools_from_policy(
    effective_policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build StepFun tool definitions from resolved effective policy."""
    tool_policy = effective_policy.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}

    knowledge_base_ids = effective_policy.get("knowledge_base_ids")
    has_bound_knowledge_base = isinstance(knowledge_base_ids, list) and bool(
        [item for item in knowledge_base_ids if str(item).strip()]
    )

    enable_web_search = bool(tool_policy.get("enable_web_search", False))
    enable_internal_retrieval = bool(tool_policy.get("enable_internal_retrieval", True))
    retrieval_priority = (
        str(tool_policy.get("retrieval_priority") or "").strip().lower()
    )
    network_access_mode = str(tool_policy.get("network_access_mode") or "off").lower()
    allow_web_search_without_kb = bool(
        tool_policy.get("allow_web_search_without_kb", False)
    )

    if retrieval_priority == "kb_only":
        enable_internal_retrieval = True
        enable_web_search = False
    elif has_bound_knowledge_base:
        enable_internal_retrieval = True
        enable_web_search = False
    elif not allow_web_search_without_kb:
        enable_web_search = False

    if network_access_mode == "off":
        enable_web_search = False

    web_top_k = _safe_int(tool_policy.get("web_search_top_k", 5), default=5)
    web_timeout = _safe_int(
        tool_policy.get("web_search_timeout_seconds", 3),
        default=3,
    )

    tools: list[dict[str, Any]] = []
    if enable_web_search:
        tools.append(
            {
                "type": "web_search",
                "function": {
                    "description": "当问题依赖最新公开信息时使用网络搜索补充答案。",
                    "options": {
                        "top_k": max(1, web_top_k),
                        "timeout_seconds": max(1, web_timeout),
                    },
                },
            }
        )

    if enable_internal_retrieval:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "search_internal_knowledge",
                    "description": "检索企业内部知识库，用于回答产品、流程和策略问题。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "用户问题或检索关键词",
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回条数（可选）",
                            },
                            "metadata_filter": {
                                "type": "object",
                                "description": "按知识条目元数据过滤（可选，例如 product_line 或 region）",
                            },
                        },
                        "required": ["query"],
                    },
                },
            }
        )

    return tools


def _safe_int(value: Any, *, default: int) -> int:
    """Convert runtime config value to integer with fallback default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
