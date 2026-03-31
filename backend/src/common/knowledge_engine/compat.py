from __future__ import annotations

from collections.abc import Callable
from typing import Any

from common.knowledge_engine.answerability import (
    KnowledgeAnswerabilityEvaluator,
    KnowledgeAnswerabilityResult,
)
from common.knowledge_engine.assembler import KnowledgeAnswerAssembler
from common.knowledge_engine.schemas import KnowledgeAnswerResult, KnowledgeCitation


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
