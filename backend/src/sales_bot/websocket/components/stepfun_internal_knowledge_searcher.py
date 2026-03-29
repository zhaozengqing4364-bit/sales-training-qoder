"""Helper utilities for StepFun internal knowledge retrieval orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import time
from typing import Any, cast

from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    build_kb_not_ready_payload,
    build_knowledge_retrieval_ledger_event,
    build_missing_query_payload,
    build_no_kb_payload,
    build_search_failed_payload,
    normalize_knowledge_base_ids,
    normalize_query,
    resolve_metadata_filter,
    resolve_rerank_params,
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
    started_at = time.monotonic()
    health_ms = 0.0
    search_ms = 0.0
    phase_vector_ms = 0.0
    phase_keyword_ms = 0.0
    cache_hit_health = False
    cache_hit_ready_docs = False

    def _build_diagnostics(extra: dict[str, Any] | None = None) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {
            "phase_health_ms": round(health_ms, 1),
            "phase_search_ms": round(search_ms, 1),
            "phase_vector_ms": round(phase_vector_ms, 1),
            "phase_keyword_ms": round(phase_keyword_ms, 1),
            "phase_total_ms": round((time.monotonic() - started_at) * 1000, 1),
            "cache_hit_health": cache_hit_health,
            "cache_hit_ready_docs": cache_hit_ready_docs,
        }
        if isinstance(extra, dict):
            diagnostics.update(extra)
        return diagnostics

    query = normalize_query(arguments_obj)
    kb_ids = normalize_knowledge_base_ids(effective_policy)

    if not query:
        payload = build_missing_query_payload()
        await record_metric(
            query="",
            result_count=0,
            status="missing_query",
            knowledge_base_ids=kb_ids,
            ledger_event=build_knowledge_retrieval_ledger_event(
                query="",
                status="missing_query",
                result_count=0,
                knowledge_base_ids=kb_ids,
                error_message=payload["message"],
            ),
        )
        payload["_diagnostics"] = _build_diagnostics({"status": "missing_query"})
        return payload

    if not kb_ids:
        payload = build_no_kb_payload(query)
        await record_metric(
            query=query,
            result_count=0,
            status="no_kb_bound",
            knowledge_base_ids=[],
            ledger_event=build_knowledge_retrieval_ledger_event(
                query=query,
                status="no_kb_bound",
                result_count=0,
                knowledge_base_ids=[],
                error_message=payload["message"],
            ),
        )
        payload["_diagnostics"] = _build_diagnostics({"status": "no_kb_bound"})
        return payload

    tool_policy = effective_policy.get("tool_policy")
    if not isinstance(tool_policy, dict):
        tool_policy = {}
    top_k, threshold, enable_hybrid, keyword_candidate_limit = resolve_retrieval_params(
        arguments_obj,
        tool_policy,
        query=query,
    )
    enable_rerank, rerank_top_k = resolve_rerank_params(tool_policy)
    embedding_timeout_ms_raw = arguments_obj.get("embedding_timeout_ms")
    try:
        embedding_timeout_ms = int(embedding_timeout_ms_raw)
    except (TypeError, ValueError):
        embedding_timeout_ms = 0
    embedding_timeout_ms = max(0, min(10000, embedding_timeout_ms))
    metadata_filter = resolve_metadata_filter(arguments_obj, tool_policy)

    try:
        async with session_factory() as db:
            knowledge_service = knowledge_service_cls(db)

            search_health: dict[str, Any] | None = None
            get_search_health = getattr(knowledge_service, "get_search_health", None)
            if callable(get_search_health):
                health_started_at = time.monotonic()
                maybe_health = get_search_health(kb_ids=kb_ids)
                if asyncio.iscoroutine(maybe_health):
                    maybe_health = await cast(Awaitable[Any], maybe_health)
                if isinstance(maybe_health, dict):
                    search_health = maybe_health
                health_ms = (time.monotonic() - health_started_at) * 1000
                cache_hit_health = bool(
                    getattr(knowledge_service, "_last_search_health_cache_hit", False)
                )

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
                payload = build_kb_not_ready_payload(query)
                await record_metric(
                    query=query,
                    result_count=0,
                    status="kb_not_ready",
                    knowledge_base_ids=kb_ids,
                    top_k=top_k,
                    similarity_threshold=threshold,
                    error_message=f"[KB_NOT_READY] {health_info}",
                    ledger_event=build_knowledge_retrieval_ledger_event(
                        query=query,
                        status="kb_not_ready",
                        result_count=0,
                        knowledge_base_ids=kb_ids,
                        error_message=payload["message"],
                    ),
                )
                payload["_diagnostics"] = _build_diagnostics(
                    {
                        "status": "kb_not_ready",
                        "search_health": search_health or {},
                    }
                )
                return payload

            search_started_at = time.monotonic()
            search_result = await knowledge_service.search_multiple(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                similarity_threshold=threshold,
                metadata_filter=metadata_filter,
                enable_hybrid=enable_hybrid,
                keyword_candidate_limit=keyword_candidate_limit,
                embedding_timeout_ms=embedding_timeout_ms,
                enable_rerank=enable_rerank,
                rerank_top_k=rerank_top_k,
            )
            search_ms = (time.monotonic() - search_started_at) * 1000
            if callable(getattr(knowledge_service, "get_last_search_timing", None)):
                timing = knowledge_service.get_last_search_timing()
                if isinstance(timing, dict):
                    try:
                        phase_vector_ms = float(timing.get("phase_vector_ms") or 0.0)
                    except (TypeError, ValueError):
                        phase_vector_ms = 0.0
                    try:
                        phase_keyword_ms = float(
                            timing.get("phase_keyword_ms") or 0.0
                        )
                    except (TypeError, ValueError):
                        phase_keyword_ms = 0.0
                    cache_hit_ready_docs = bool(
                        timing.get("cache_hit_ready_docs", False)
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
            ledger_event=build_knowledge_retrieval_ledger_event(
                query=query,
                status="search_failed",
                result_count=0,
                knowledge_base_ids=kb_ids,
                error_message=error_detail,
            ),
        )
        payload = build_search_failed_payload(query, error_detail)
        payload["_diagnostics"] = _build_diagnostics({"status": "search_failed"})
        return payload

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
            ledger_event=build_knowledge_retrieval_ledger_event(
                query=query,
                status="search_failed",
                result_count=0,
                knowledge_base_ids=kb_ids,
                error_message=error_detail,
            ),
        )
        payload = build_search_failed_payload(query, error_detail)
        payload["_diagnostics"] = _build_diagnostics({"status": "search_failed"})
        return payload

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
        ledger_event=build_knowledge_retrieval_ledger_event(
            query=query,
            status=status,
            result_count=len(results),
            retrieval_mode=effective_retrieval_mode,
            knowledge_base_ids=kb_ids,
            results=results,
        ),
    )

    response_payload = {
        "query": query,
        "count": len(results),
        "results": results,
        "retrieval_mode": effective_retrieval_mode,
    }
    response_payload["_diagnostics"] = _build_diagnostics(
        {
            "status": status,
            "retrieval_mode": effective_retrieval_mode,
            "result_count": len(results),
        }
    )
    return response_payload
