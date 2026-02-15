"""Knowledge-base lock guard utilities.

Ensures backend-enforced grounding behavior is consistent across AI paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from common.db.session import AsyncSessionLocal
from common.knowledge.service import KnowledgeService
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)
from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    resolve_grounding_context_limits,
)


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


def is_kb_lock_required(tool_policy: dict[str, Any] | None) -> bool:
    """Return True when strict KB grounding lock is enabled."""
    if not isinstance(tool_policy, dict):
        return False
    return bool(tool_policy.get("require_kb_grounding", False))


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


def _build_blocked_user_message(status: str) -> str:
    if status == "blocked_no_kb":
        return (
            "当前会话已开启知识库强制模式，但未绑定可用知识库。"
            "请联系管理员先完成知识库绑定后再继续。"
        )
    if status == "blocked_not_ready":
        return (
            "当前会话已开启知识库强制模式，但知识库文档尚未处理完成。"
            "请稍后重试。"
        )
    if status == "blocked_search_failed":
        return (
            "当前会话已开启知识库强制模式，但知识检索失败。"
            "请稍后重试或联系管理员排查。"
        )
    return (
        "当前会话已开启知识库强制模式，但未检索到可引用的内部依据。"
        "请提供更具体的产品关键词、版本或业务场景后重试。"
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
        "你必须仅依据以下内部知识回答，禁止联网搜索或臆测。\n"
        f"用户问题：{query}\n"
        + "\n".join(snippets)
        + "\n若证据不足，请明确说明知识库中暂无足够依据。"
    )


async def _noop_record_metric(**_kwargs: Any) -> None:
    return None


async def evaluate_kb_lock_decision(
    *,
    query: str,
    effective_policy: dict[str, Any],
    record_metric=None,
) -> KbLockDecision:
    """Evaluate one-turn KB lock decision with deterministic pass/block result."""
    normalized_query = str(query or "").strip()
    tool_policy = _normalize_tool_policy(effective_policy)
    lock_required = is_kb_lock_required(tool_policy)

    if not lock_required:
        return KbLockDecision(
            lock_required=False,
            allow_generation=True,
            status="pass",
            grounding_context="",
            user_message="",
        )

    kb_ids = _normalize_knowledge_base_ids(effective_policy)
    if not kb_ids:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_no_kb",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_no_kb"),
        )

    if not normalized_query:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_empty",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_empty"),
        )

    try:
        retrieval_top_k = int(tool_policy.get("retrieval_top_k", 5) or 5)
    except (TypeError, ValueError):
        retrieval_top_k = 5

    metric_cb = record_metric or _noop_record_metric
    payload = await search_internal_knowledge(
        arguments_obj={"query": normalized_query, "top_k": max(1, min(8, retrieval_top_k))},
        effective_policy=effective_policy,
        session_factory=AsyncSessionLocal,
        knowledge_service_cls=KnowledgeService,
        record_metric=metric_cb,
    )

    if not isinstance(payload, dict):
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_search_failed",
            grounding_context="",
            user_message=_build_blocked_user_message("blocked_search_failed"),
            error_detail="invalid_retrieval_payload",
        )

    result_count = max(0, int(payload.get("count") or 0))
    retrieval_mode = str(payload.get("retrieval_mode") or "")
    status_message = str(payload.get("message") or "")
    error_detail = str(payload.get("error") or "")

    if error_detail:
        status = "blocked_search_failed"
    elif "未关联内部知识库" in status_message:
        status = "blocked_no_kb"
    elif "尚未处理完成" in status_message:
        status = "blocked_not_ready"
    elif result_count <= 0:
        status = "blocked_empty"
    else:
        status = "pass"

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
        )

    return KbLockDecision(
        lock_required=True,
        allow_generation=True,
        status="pass",
        grounding_context=grounding_context,
        user_message="",
        result_count=result_count,
        retrieval_mode=retrieval_mode,
    )
