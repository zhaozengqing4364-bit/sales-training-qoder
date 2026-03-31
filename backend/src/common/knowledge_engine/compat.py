from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from common.knowledge_engine.answerability import (
    KnowledgeAnswerabilityEvaluator,
    KnowledgeAnswerabilityResult,
)
from common.knowledge_engine.assembler import KnowledgeAnswerAssembler
from common.knowledge_engine.audit_repo import KnowledgeAnswerAuditRepository
from common.knowledge_engine.engine import KnowledgeAnswerEngine
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackAdapter
from common.knowledge_engine.reranker import KnowledgeReranker
from common.knowledge_engine.schemas import (
    KnowledgeAnswerRequest,
    KnowledgeAnswerResult,
    KnowledgeAuditStep,
    KnowledgeCitation,
)

KnowledgeAnswerRolloutMode = Literal["legacy", "enabled", "dual_run"]


@dataclass(frozen=True)
class KnowledgeAnswerExecutionOutcome:
    result: KnowledgeAnswerResult
    payload: dict[str, Any]
    rollout_mode: KnowledgeAnswerRolloutMode


class _StaticConfigRepository:
    def __init__(self, snapshot: Any) -> None:
        self._snapshot = snapshot

    def get_active_config(self) -> Any:
        return self._snapshot


def build_answerability_diagnostics(
    *,
    request_query: str,
    result: KnowledgeAnswerResult,
    strict_kb_mode: bool,
) -> dict[str, Any]:
    compat_source_status = str(
        result.retrieval_summary.get("compat_source_status") or result.source_status
    ).strip() or result.source_status
    resolved_query = str(
        result.retrieval_summary.get("resolved_query") or request_query
    ).strip()

    return {
        "mode": "grounded_strict" if strict_kb_mode else "grounded_preferred",
        "answerability": result.answerability,
        "source_status": compat_source_status,
        "query": resolved_query,
        "audit_run_id": result.audit_run_id,
        "rewritten_queries": list(result.rewritten_queries),
        "citations": [_compat_citation_payload(item) for item in result.citations],
        "unsupported_claims": list(result.unsupported_claims),
        "blocked_text": result.blocked_text,
        "final_text": result.final_text,
        "retrieval_summary": dict(result.retrieval_summary),
    }


def build_search_payload_from_answer_result(
    *,
    request_query: str,
    result: KnowledgeAnswerResult,
    strict_kb_mode: bool,
) -> dict[str, Any]:
    diagnostics = build_answerability_diagnostics(
        request_query=request_query,
        result=result,
        strict_kb_mode=strict_kb_mode,
    )
    compat_source_status = str(
        result.retrieval_summary.get("compat_source_status") or result.source_status
    ).strip() or result.source_status
    retrieval_mode = _derive_retrieval_mode(result)
    results = [_compat_result_row(item) for item in result.citations]

    payload: dict[str, Any] = {
        "query": diagnostics["query"],
        "count": len(results),
        "results": results,
        "retrieval_mode": retrieval_mode,
        "rewritten_queries": list(result.rewritten_queries),
        "status": compat_source_status,
        "_answerability": diagnostics,
    }
    if compat_source_status == "search_failed":
        payload["message"] = "知识检索失败"
        error_detail = str(
            result.retrieval_summary.get("search_failures", [""])[0]
            if isinstance(result.retrieval_summary.get("search_failures"), list)
            and result.retrieval_summary.get("search_failures")
            else ""
        ).strip()
        if error_detail:
            payload["error"] = error_detail

    for key in ("entity_resolution", "intent", "retrieval_plan", "execution_trace"):
        value = result.retrieval_summary.get(key)
        if isinstance(value, dict):
            payload[key] = dict(value)

    return payload


def build_message_transcript_metadata(
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(diagnostics, dict):
        return None
    return {"knowledge_answer_diagnostics": dict(diagnostics)}


def evaluate_answerability_from_rows(
    *,
    profile_key: str,
    rows: list[dict[str, Any]],
    execution_result: Any,
    answerability_profiles: dict[str, Any],
) -> KnowledgeAnswerabilityResult:
    evaluator = KnowledgeAnswerabilityEvaluator(
        answerability_profiles=answerability_profiles
    )
    return evaluator.evaluate(
        profile_key=profile_key,
        rows=rows,
        execution_result=execution_result,
    )


def assemble_answer_from_rows(
    *,
    query: str,
    rows: list[dict[str, Any]],
    answerability_result: KnowledgeAnswerabilityResult,
    execution_result: Any,
) -> KnowledgeAnswerResult:
    assembler = KnowledgeAnswerAssembler()
    return assembler.assemble(
        query=query,
        rows=rows,
        answerability_result=answerability_result,
        execution_result=execution_result,
    )


def is_knowledge_answer_engine_enabled() -> bool:
    return _env_flag("KNOWLEDGE_ANSWER_ENGINE_ENABLED", default=False)


def is_knowledge_answer_engine_dual_run() -> bool:
    return _env_flag("KNOWLEDGE_ANSWER_ENGINE_DUAL_RUN", default=False)


def resolve_knowledge_answer_rollout_mode() -> KnowledgeAnswerRolloutMode:
    if is_knowledge_answer_engine_enabled():
        return "enabled"
    if is_knowledge_answer_engine_dual_run():
        return "dual_run"
    return "legacy"


async def execute_knowledge_answer_engine(
    *,
    db: Any,
    config_snapshot: Any,
    search_multiple: Any,
    request_query: str,
    session_id: str | None,
    knowledge_base_ids: list[str],
    entrypoint: str,
    runtime_options: dict[str, Any],
    strict_kb_mode: bool,
) -> KnowledgeAnswerExecutionOutcome:
    async def _compat_search_multiple(**kwargs):
        result = await search_multiple(**kwargs)
        rows = result.value if getattr(result, "is_success", False) else None
        if not getattr(result, "is_success", False) or not isinstance(rows, list):
            return result

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            normalized_row = dict(row)
            snippet = str(normalized_row.get("snippet") or "").strip()
            content = str(normalized_row.get("content") or "").strip()
            if not snippet and content:
                normalized_row["snippet"] = content
            normalized_rows.append(normalized_row)
        return result.__class__.ok(normalized_rows)

    engine = KnowledgeAnswerEngine(
        config_repository=_StaticConfigRepository(config_snapshot),
        haystack_adapter=KnowledgeHaystackAdapter(search_multiple=_compat_search_multiple),
        reranker=KnowledgeReranker(
            ranking_profiles=getattr(config_snapshot, "ranking_profiles", {})
        ),
    )
    request = KnowledgeAnswerRequest(
        query=request_query,
        session_id=session_id,
        knowledge_base_ids=list(knowledge_base_ids),
        entrypoint=entrypoint,
        runtime_options=dict(runtime_options),
    )
    result = await asyncio.to_thread(engine.answer, request)

    if session_id:
        audit_run_id = await _persist_answer_result_audit(
            db=db,
            request=request,
            result=result,
        )
        if audit_run_id:
            result = result.model_copy(update={"audit_run_id": audit_run_id})

    payload = build_search_payload_from_answer_result(
        request_query=request_query,
        result=result,
        strict_kb_mode=strict_kb_mode,
    )
    attach_rollout_diagnostics(
        payload,
        rollout_mode="enabled",
        live_audit_run_id=result.audit_run_id,
    )
    return KnowledgeAnswerExecutionOutcome(
        result=result,
        payload=payload,
        rollout_mode="enabled",
    )


def attach_rollout_diagnostics(
    payload: dict[str, Any],
    *,
    rollout_mode: KnowledgeAnswerRolloutMode,
    live_audit_run_id: str | None = None,
    shadow_audit_run_id: str | None = None,
) -> dict[str, Any]:
    diagnostics = payload.get("_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        payload["_diagnostics"] = diagnostics

    rollout_payload: dict[str, Any] = {"mode": rollout_mode}
    if live_audit_run_id:
        rollout_payload["live_audit_run_id"] = live_audit_run_id
    if shadow_audit_run_id:
        rollout_payload["shadow_audit_run_id"] = shadow_audit_run_id
    diagnostics["knowledge_answer_rollout"] = rollout_payload
    return payload


async def _persist_answer_result_audit(
    *,
    db: Any,
    request: KnowledgeAnswerRequest,
    result: KnowledgeAnswerResult,
) -> str | None:
    if not request.session_id:
        return None

    def _persist(sync_session: Session) -> str | None:
        repo = KnowledgeAnswerAuditRepository(sync_session)
        persisted = repo.create_run(
            session_id=request.session_id,
            config_version_id=_optional_text(result.retrieval_summary.get("config_version_id")),
            entrypoint=str(request.entrypoint or "unknown"),
            query_text=str(result.retrieval_summary.get("resolved_query") or request.query),
            answerability=result.answerability,
            final_status="blocked" if result.answerability == "blocked" else "completed",
            blocked_reason=_optional_text(result.retrieval_summary.get("blocked_reason")),
            citations=[citation.model_dump() for citation in result.citations],
            retrieval_summary=dict(result.retrieval_summary),
            steps=_synthesized_audit_steps(request=request, result=result),
        )
        return str(persisted.id) if persisted is not None else None

    run_sync = getattr(db, "run_sync", None)
    if callable(run_sync):
        return await run_sync(_persist)
    return _persist(db)


def _synthesized_audit_steps(
    *,
    request: KnowledgeAnswerRequest,
    result: KnowledgeAnswerResult,
) -> list[KnowledgeAuditStep]:
    retrieval_summary = dict(result.retrieval_summary)
    resolved_query = str(retrieval_summary.get("resolved_query") or request.query)
    steps: list[KnowledgeAuditStep] = [
        KnowledgeAuditStep(
            step_name="resolve",
            input_payload={"query": request.query},
            output_payload=_dict_payload(retrieval_summary.get("entity_resolution")),
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="classify",
            input_payload={"query": request.query, "normalized_query": resolved_query},
            output_payload=_dict_payload(retrieval_summary.get("intent")),
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="plan",
            input_payload={"profile_key": retrieval_summary.get("profile_key")},
            output_payload=_dict_payload(retrieval_summary.get("retrieval_plan")),
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="retrieve",
            input_payload={
                "knowledge_base_ids": list(request.knowledge_base_ids),
                "runtime_options": dict(request.runtime_options),
            },
            output_payload=_dict_payload(retrieval_summary.get("execution_trace")),
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="rank",
            input_payload={"profile_key": retrieval_summary.get("profile_key")},
            output_payload={
                "citation_count": len(result.citations),
                "citations": [_compat_citation_payload(citation) for citation in result.citations],
            },
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="answerability",
            input_payload={"query": resolved_query},
            output_payload={
                "answerability": result.answerability,
                "source_status": result.source_status,
                "blocked_reason": retrieval_summary.get("blocked_reason"),
            },
            duration_ms=0,
            status="completed",
        ),
        KnowledgeAuditStep(
            step_name="assemble",
            input_payload={"query": resolved_query},
            output_payload={
                "final_text": result.final_text,
                "blocked_text": result.blocked_text,
                "rewritten_queries": list(result.rewritten_queries),
            },
            duration_ms=0,
            status="completed",
        ),
    ]
    return steps


def _compat_citation_payload(item: KnowledgeCitation) -> dict[str, Any]:
    metadata = dict(item.metadata or {})
    return {
        "claim": item.snippet,
        "knowledge_base_id": metadata.get("knowledge_base_id"),
        "knowledge_base_name": metadata.get("knowledge_base_name"),
        "document_id": item.document_id,
        "document_title": item.document_title,
        "chunk_id": item.chunk_id,
        "snippet": item.snippet,
        "score": item.score,
    }


def _compat_result_row(item: KnowledgeCitation) -> dict[str, Any]:
    metadata = dict(item.metadata or {})
    row: dict[str, Any] = {
        "knowledge_base_id": metadata.get("knowledge_base_id"),
        "knowledge_base_name": metadata.get("knowledge_base_name"),
        "score": item.score,
        "snippet": item.snippet,
        "retrieval_mode": metadata.get("retrieval_mode") or "vector",
        "document_title": item.document_title,
    }
    if isinstance(metadata.get("score_breakdown"), dict):
        row["score_breakdown"] = dict(metadata["score_breakdown"])
    if metadata.get("ranking_passed") is not None:
        row["ranking_passed"] = bool(metadata.get("ranking_passed"))
    return row


def _derive_retrieval_mode(result: KnowledgeAnswerResult) -> str:
    explicit = str(result.retrieval_summary.get("retrieval_mode") or "").strip()
    if explicit:
        return explicit
    modes = {
        str(citation.metadata.get("retrieval_mode") or "").strip()
        for citation in result.citations
        if isinstance(citation.metadata, dict)
        and str(citation.metadata.get("retrieval_mode") or "").strip()
    }
    if modes == {"keyword_fallback"}:
        return "keyword_fallback"
    if modes == {"hybrid"}:
        return "hybrid"
    if modes == {"vector"}:
        return "vector"
    if len(modes) > 1:
        return "mixed"
    return "vector"


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _env_flag(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
