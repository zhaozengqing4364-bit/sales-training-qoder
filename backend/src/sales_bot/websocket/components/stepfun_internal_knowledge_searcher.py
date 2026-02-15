"""Helper utilities for StepFun internal knowledge retrieval orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    build_kb_not_ready_payload,
    build_missing_query_payload,
    build_no_kb_payload,
    build_search_failed_payload,
    normalize_knowledge_base_ids,
    normalize_query,
    resolve_metadata_filter,
    resolve_retrieval_params,
    transform_search_rows,
)


async def search_internal_knowledge(
    *,
    arguments_obj: dict[str, Any],
    effective_policy: dict[str, Any],
    session_factory: Callable[[], Any],
    knowledge_service_cls: type,
    record_metric: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    """Execute knowledge retrieval with consistent metrics recording."""
    query = normalize_query(arguments_obj)
    kb_ids = normalize_knowledge_base_ids(effective_policy)

    if not query:
        await record_metric(
            query="",
            result_count=0,
            status="missing_query",
            knowledge_base_ids=kb_ids,
        )
        return build_missing_query_payload()

    if not kb_ids:
        await record_metric(
            query=query,
            result_count=0,
            status="no_kb_bound",
            knowledge_base_ids=[],
        )
        return build_no_kb_payload(query)

    tool_policy = effective_policy.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}
    top_k, threshold, enable_hybrid, keyword_candidate_limit = resolve_retrieval_params(
        arguments_obj,
        tool_policy,
        query=query,
    )
    metadata_filter = resolve_metadata_filter(arguments_obj, tool_policy)

    try:
        async with session_factory() as db:
            knowledge_service = knowledge_service_cls(db)

            search_health: dict[str, Any] | None = None
            get_search_health = getattr(knowledge_service, "get_search_health", None)
            if callable(get_search_health):
                maybe_health = get_search_health(kb_ids=kb_ids)
                if asyncio.iscoroutine(maybe_health):
                    maybe_health = await cast(Awaitable[Any], maybe_health)
                if isinstance(maybe_health, dict):
                    search_health = maybe_health

            kb_ready = True
            if search_health:
                if isinstance(search_health.get("is_ready"), bool):
                    kb_ready = bool(search_health.get("is_ready"))
                else:
                    ready_document_count = int(
                        search_health.get("ready_document_count") or 0
                    )
                    ready_chunk_count = int(search_health.get("ready_chunk_count") or 0)
                    vector_chunk_count = search_health.get("vector_chunk_count")
                    if vector_chunk_count is None:
                        kb_ready = ready_document_count > 0 and ready_chunk_count > 0
                    else:
                        kb_ready = (
                            ready_document_count > 0
                            and ready_chunk_count > 0
                            and int(vector_chunk_count or 0) > 0
                        )

            if not kb_ready:
                health_info = (
                    f"ready_docs={int(search_health.get('ready_document_count') or 0)} "
                    f"ready_chunks={int(search_health.get('ready_chunk_count') or 0)} "
                    f"vector_chunks={int(search_health.get('vector_chunk_count') or 0)}"
                    if isinstance(search_health, dict)
                    else "health_unavailable"
                )
                await record_metric(
                    query=query,
                    result_count=0,
                    status="kb_not_ready",
                    knowledge_base_ids=kb_ids,
                    top_k=top_k,
                    similarity_threshold=threshold,
                    error_message=f"[KB_NOT_READY] {health_info}",
                )
                return build_kb_not_ready_payload(query)

            search_result = await knowledge_service.search_multiple(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                similarity_threshold=threshold,
                metadata_filter=metadata_filter,
                enable_hybrid=enable_hybrid,
                keyword_candidate_limit=keyword_candidate_limit,
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error_detail = f"[KNOWLEDGE_SEARCH_EXCEPTION] {exc.__class__.__name__}: {exc}"
        await record_metric(
            query=query,
            result_count=0,
            status="search_failed",
            knowledge_base_ids=kb_ids,
            top_k=top_k,
            similarity_threshold=threshold,
            error_message=error_detail,
        )
        return build_search_failed_payload(query, error_detail)

    if not search_result.is_success:
        error_detail = str(search_result.fallback or "unknown_error")
        await record_metric(
            query=query,
            result_count=0,
            status="search_failed",
            knowledge_base_ids=kb_ids,
            top_k=top_k,
            similarity_threshold=threshold,
            error_message=error_detail,
        )
        return build_search_failed_payload(query, error_detail)

    rows = search_result.value or []
    results, effective_retrieval_mode, status = transform_search_rows(
        rows,
        top_k,
        query=query,
    )

    await record_metric(
        query=query,
        result_count=len(results),
        status=status,
        knowledge_base_ids=kb_ids,
        top_k=top_k,
        similarity_threshold=threshold,
        retrieval_mode=effective_retrieval_mode,
    )

    return {
        "query": query,
        "count": len(results),
        "results": results,
        "retrieval_mode": effective_retrieval_mode,
    }
