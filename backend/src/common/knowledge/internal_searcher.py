"""Helper utilities for StepFun internal knowledge retrieval orchestration."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from common.knowledge.retrieval_helpers import (
    build_answerability_assessment,
    build_kb_not_ready_payload,
    build_knowledge_retrieval_ledger_event,
    build_missing_query_payload,
    build_no_kb_payload,
    build_rewritten_queries,
    build_search_failed_payload,
    is_product_overview_query,
    normalize_knowledge_base_ids,
    normalize_query,
    resolve_metadata_filter,
    resolve_rerank_params,
    resolve_retrieval_params,
    transform_search_rows,
)
from common.knowledge_engine.compat import (
    attach_rollout_diagnostics,
    execute_knowledge_answer_engine,
    resolve_knowledge_answer_rollout_mode,
)
from common.knowledge_engine.config_repo import (
    KnowledgeAnswerConfigRepository,
    KnowledgeAnswerConfigSnapshot,
)


async def search_internal_knowledge(
    *,
    arguments_obj: dict[str, Any],
    effective_policy: dict[str, Any],
    session_factory: Callable[[], Any],
    knowledge_service_cls: Callable[[Any], Any],
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
    response_query = query
    kb_ids = normalize_knowledge_base_ids(effective_policy)
    strict_kb_mode = bool(
        isinstance(effective_policy.get("tool_policy"), dict)
        and effective_policy.get("tool_policy", {}).get("require_kb_grounding", False)
    )
    rollout_mode = resolve_knowledge_answer_rollout_mode()

    def _finalize_payload(
        payload: dict[str, Any],
        *,
        path_mode: Literal["live", "compat"],
        live_audit_run_id: str | None = None,
        shadow_audit_run_id: str | None = None,
    ) -> dict[str, Any]:
        return attach_rollout_diagnostics(
            payload,
            rollout_mode=rollout_mode,
            path_mode=path_mode,
            live_audit_run_id=live_audit_run_id,
            shadow_audit_run_id=shadow_audit_run_id,
        )

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
        payload["_answerability"] = build_answerability_assessment(
            query="",
            results=[],
            source_status="missing_query",
            strict_kb_mode=strict_kb_mode,
            rewritten_queries=[],
        )
        return _finalize_payload(
            payload,
            path_mode="live" if rollout_mode == "enabled" else "compat",
        )

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
        payload["_answerability"] = build_answerability_assessment(
            query=query,
            results=[],
            source_status="no_kb_bound",
            strict_kb_mode=strict_kb_mode,
            rewritten_queries=[],
        )
        return _finalize_payload(
            payload,
            path_mode="live" if rollout_mode == "enabled" else "compat",
        )

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
        embedding_timeout_ms = int(embedding_timeout_ms_raw or 0)
    except (TypeError, ValueError):
        embedding_timeout_ms = 0
    embedding_timeout_ms = max(0, min(10000, embedding_timeout_ms))
    metadata_filter = resolve_metadata_filter(arguments_obj, tool_policy)
    rewritten_queries = build_rewritten_queries(query, tool_policy=tool_policy)
    session_id = str(arguments_obj.get("session_id") or "").strip() or None

    entity_resolution_payload: dict[str, Any] | None = None
    intent_payload: dict[str, Any] | None = None
    retrieval_plan_payload: dict[str, Any] | None = None
    execution_trace_payload: dict[str, Any] | None = None
    shadow_audit_run_id: str | None = None

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
                        "rewritten_queries": rewritten_queries,
                    }
                )
                payload["_answerability"] = build_answerability_assessment(
                    query=query,
                    results=[],
                    source_status="kb_not_ready",
                    strict_kb_mode=strict_kb_mode,
                    rewritten_queries=rewritten_queries,
                )
                return _finalize_payload(
                    payload,
                    path_mode="live" if rollout_mode == "enabled" else "compat",
                )

            active_dictionary_lexicon = []
            get_active_dictionary_lexicon = getattr(
                knowledge_service, "active_dictionary_lexicon", None
            )
            if callable(get_active_dictionary_lexicon):
                maybe_lexicon = get_active_dictionary_lexicon(kb_ids)
                if asyncio.iscoroutine(maybe_lexicon):
                    maybe_lexicon = await cast(Awaitable[Any], maybe_lexicon)
                if isinstance(maybe_lexicon, list):
                    active_dictionary_lexicon = [
                        item for item in maybe_lexicon if isinstance(item, dict)
                    ]
            if active_dictionary_lexicon:
                tool_policy = dict(tool_policy)
                existing_lexicon = tool_policy.get("transcript_normalization_lexicon")
                merged_lexicon = (
                    list(existing_lexicon) if isinstance(existing_lexicon, list) else []
                )
                merged_lexicon.extend(active_dictionary_lexicon)
                tool_policy["transcript_normalization_lexicon"] = merged_lexicon
                rewritten_queries = build_rewritten_queries(
                    query,
                    tool_policy=tool_policy,
                )

            config_snapshot = await _load_active_config_snapshot(db)
            aggregated_rows: list[dict[str, Any]] = []
            search_started_at = time.monotonic()
            search_failures: list[str] = []

            if (
                config_snapshot is not None
                and config_snapshot.query_profiles
                and rollout_mode in {"enabled", "dual_run"}
            ):
                engine_outcome = await execute_knowledge_answer_engine(
                    db=db,
                    config_snapshot=config_snapshot,
                    search_multiple=knowledge_service.search_multiple,
                    request_query=query,
                    session_id=session_id,
                    knowledge_base_ids=kb_ids,
                    entrypoint="stepfun_realtime",
                    runtime_options={
                        "top_k": top_k,
                        "similarity_threshold": threshold,
                        "enable_hybrid": enable_hybrid,
                        "keyword_candidate_limit": keyword_candidate_limit,
                        "embedding_timeout_ms": embedding_timeout_ms,
                        "enable_rerank": enable_rerank,
                        "rerank_top_k": rerank_top_k,
                        "metadata_filter": metadata_filter or {},
                        "tool_policy": dict(tool_policy),
                    },
                    strict_kb_mode=strict_kb_mode,
                )
                search_ms = (time.monotonic() - search_started_at) * 1000

                if rollout_mode == "enabled":
                    payload = engine_outcome.payload
                    compat_status = str(payload.get("status") or "hit").strip() or "hit"
                    compat_retrieval_mode = (
                        str(payload.get("retrieval_mode") or "vector").strip()
                        or "vector"
                    )
                    await record_metric(
                        query=str(payload.get("query") or query),
                        result_count=int(payload.get("count") or 0),
                        status=compat_status,
                        knowledge_base_ids=kb_ids,
                        top_k=top_k,
                        similarity_threshold=threshold,
                        retrieval_mode=compat_retrieval_mode,
                        ledger_event=build_knowledge_retrieval_ledger_event(
                            query=str(payload.get("query") or query),
                            status=compat_status,
                            result_count=int(payload.get("count") or 0),
                            retrieval_mode=compat_retrieval_mode,
                            knowledge_base_ids=kb_ids,
                            results=payload.get("results")
                            if isinstance(payload.get("results"), list)
                            else [],
                        ),
                    )
                    payload["_diagnostics"] = _build_diagnostics(
                        {
                            "status": compat_status,
                            "retrieval_mode": compat_retrieval_mode,
                            "result_count": int(payload.get("count") or 0),
                            "rewritten_queries": list(
                                payload.get("rewritten_queries") or []
                            ),
                            "execution_trace": dict(
                                payload.get("execution_trace") or {}
                            ),
                        }
                    )
                    return _finalize_payload(
                        payload,
                        path_mode="live",
                        live_audit_run_id=engine_outcome.result.audit_run_id,
                    )

                shadow_audit_run_id = engine_outcome.result.audit_run_id

            if (
                config_snapshot is not None
                and config_snapshot.query_profiles
                and rollout_mode == "legacy"
            ):
                pass

            (
                aggregated_rows,
                search_failures,
                rewritten_queries,
            ) = await _execute_legacy_retrieval(
                knowledge_service=knowledge_service,
                kb_ids=kb_ids,
                rewritten_queries=rewritten_queries,
                top_k=top_k,
                threshold=threshold,
                metadata_filter=metadata_filter,
                enable_hybrid=enable_hybrid,
                keyword_candidate_limit=keyword_candidate_limit,
                embedding_timeout_ms=embedding_timeout_ms,
                enable_rerank=enable_rerank,
                rerank_top_k=rerank_top_k,
                stop_after_first_success=is_product_overview_query(query),
            )

            search_ms = (time.monotonic() - search_started_at) * 1000
            if search_failures and not aggregated_rows:
                error_detail = search_failures[0]
                await record_metric(
                    query=response_query,
                    result_count=0,
                    status="search_failed",
                    knowledge_base_ids=kb_ids,
                    top_k=top_k,
                    similarity_threshold=threshold,
                    error_message=error_detail,
                    ledger_event=build_knowledge_retrieval_ledger_event(
                        query=response_query,
                        status="search_failed",
                        result_count=0,
                        knowledge_base_ids=kb_ids,
                        error_message=error_detail,
                    ),
                )
                payload = build_search_failed_payload(response_query, error_detail)
                payload["_diagnostics"] = _build_diagnostics(
                    {
                        "status": "search_failed",
                        "rewritten_queries": rewritten_queries,
                        "execution_trace": execution_trace_payload or {},
                    }
                )
                payload["_answerability"] = build_answerability_assessment(
                    query=response_query,
                    results=[],
                    source_status="search_failed",
                    strict_kb_mode=strict_kb_mode,
                    rewritten_queries=rewritten_queries,
                )
                if entity_resolution_payload is not None:
                    payload["entity_resolution"] = entity_resolution_payload
                if intent_payload is not None:
                    payload["intent"] = intent_payload
                if retrieval_plan_payload is not None:
                    payload["retrieval_plan"] = retrieval_plan_payload
                if execution_trace_payload is not None:
                    payload["execution_trace"] = execution_trace_payload
                if rollout_mode == "dual_run":
                    return _finalize_payload(
                        payload,
                        path_mode="compat",
                        shadow_audit_run_id=shadow_audit_run_id,
                    )
                return _finalize_payload(payload, path_mode="compat")

            if callable(getattr(knowledge_service, "get_last_search_timing", None)):
                timing = knowledge_service.get_last_search_timing()
                if isinstance(timing, dict):
                    try:
                        phase_vector_ms = float(timing.get("phase_vector_ms") or 0.0)
                    except (TypeError, ValueError):
                        phase_vector_ms = 0.0
                    try:
                        phase_keyword_ms = float(timing.get("phase_keyword_ms") or 0.0)
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
            query=response_query,
            result_count=0,
            status="search_failed",
            knowledge_base_ids=kb_ids,
            top_k=top_k,
            similarity_threshold=threshold,
            error_message=error_detail,
            ledger_event=build_knowledge_retrieval_ledger_event(
                query=response_query,
                status="search_failed",
                result_count=0,
                knowledge_base_ids=kb_ids,
                error_message=error_detail,
            ),
        )
        payload = build_search_failed_payload(response_query, error_detail)
        payload["_diagnostics"] = _build_diagnostics(
            {"status": "search_failed", "rewritten_queries": rewritten_queries}
        )
        payload["_answerability"] = build_answerability_assessment(
            query=response_query,
            results=[],
            source_status="search_failed",
            strict_kb_mode=strict_kb_mode,
            rewritten_queries=rewritten_queries,
        )
        if rollout_mode == "dual_run":
            return _finalize_payload(
                payload,
                path_mode="compat",
                shadow_audit_run_id=shadow_audit_run_id,
            )
        return _finalize_payload(
            payload,
            path_mode="live" if rollout_mode == "enabled" else "compat",
        )

    rows = aggregated_rows
    results, effective_retrieval_mode, status = transform_search_rows(
        rows,
        top_k=max(top_k, 6),
        query=response_query,
    )

    await record_metric(
        query=response_query,
        result_count=len(results),
        status=status,
        knowledge_base_ids=kb_ids,
        top_k=top_k,
        similarity_threshold=threshold,
        retrieval_mode=effective_retrieval_mode,
        ledger_event=build_knowledge_retrieval_ledger_event(
            query=response_query,
            status=status,
            result_count=len(results),
            retrieval_mode=effective_retrieval_mode,
            knowledge_base_ids=kb_ids,
            results=results,
        ),
    )

    response_payload = {
        "query": response_query,
        "count": len(results),
        "results": results,
        "retrieval_mode": effective_retrieval_mode,
        "rewritten_queries": rewritten_queries,
    }
    if entity_resolution_payload is not None:
        response_payload["entity_resolution"] = entity_resolution_payload
    if intent_payload is not None:
        response_payload["intent"] = intent_payload
    if retrieval_plan_payload is not None:
        response_payload["retrieval_plan"] = retrieval_plan_payload
    if execution_trace_payload is not None:
        response_payload["execution_trace"] = execution_trace_payload
    response_payload["_diagnostics"] = _build_diagnostics(
        {
            "status": status,
            "retrieval_mode": effective_retrieval_mode,
            "result_count": len(results),
            "rewritten_queries": rewritten_queries,
            "execution_trace": execution_trace_payload or {},
        }
    )
    response_payload["_answerability"] = build_answerability_assessment(
        query=response_query,
        results=results,
        source_status=status,
        strict_kb_mode=strict_kb_mode,
        rewritten_queries=rewritten_queries,
    )
    if rollout_mode == "dual_run":
        return _finalize_payload(
            response_payload,
            path_mode="compat",
            shadow_audit_run_id=shadow_audit_run_id,
        )
    return _finalize_payload(
        response_payload,
        path_mode="live" if rollout_mode == "enabled" else "compat",
    )


async def _load_active_config_snapshot(
    db: Any,
) -> KnowledgeAnswerConfigSnapshot | None:
    try:
        run_sync = getattr(db, "run_sync", None)
        if callable(run_sync):
            maybe_config = run_sync(
                lambda sync_session: KnowledgeAnswerConfigRepository(
                    sync_session
                ).get_active_config()
            )
            if asyncio.iscoroutine(maybe_config):
                return await cast(
                    Awaitable[KnowledgeAnswerConfigSnapshot | None], maybe_config
                )
            return cast(KnowledgeAnswerConfigSnapshot | None, maybe_config)
        return KnowledgeAnswerConfigRepository(db).get_active_config()
    except Exception:
        return None


async def _execute_legacy_retrieval(
    *,
    knowledge_service: Any,
    kb_ids: list[str],
    rewritten_queries: list[str],
    top_k: int,
    threshold: float,
    metadata_filter: dict[str, Any] | None,
    enable_hybrid: bool,
    keyword_candidate_limit: int,
    embedding_timeout_ms: int,
    enable_rerank: bool,
    rerank_top_k: int,
    stop_after_first_success: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    aggregated_rows: list[dict[str, Any]] = []
    seen_row_keys: set[tuple[str, str, str]] = set()
    search_failures: list[str] = []

    for rewritten_query in rewritten_queries:
        search_result = await knowledge_service.search_multiple(
            kb_ids=kb_ids,
            query=rewritten_query,
            top_k=top_k,
            similarity_threshold=threshold,
            metadata_filter=metadata_filter,
            enable_hybrid=enable_hybrid,
            keyword_candidate_limit=keyword_candidate_limit,
            embedding_timeout_ms=embedding_timeout_ms,
            enable_rerank=enable_rerank,
            rerank_top_k=rerank_top_k,
        )
        if not search_result.is_success:
            search_failures.append(str(search_result.fallback or "unknown_error"))
            continue
        new_rows_added = 0
        for row in search_result.value or []:
            if not isinstance(row, dict):
                continue
            row_key = (
                str(row.get("knowledge_base_id") or ""),
                str(row.get("document_title") or row.get("source") or ""),
                str(row.get("content") or ""),
            )
            if row_key in seen_row_keys:
                continue
            seen_row_keys.add(row_key)
            aggregated_rows.append(dict(row))
            new_rows_added += 1
        if stop_after_first_success and new_rows_added > 0:
            break

    return aggregated_rows, search_failures, rewritten_queries
