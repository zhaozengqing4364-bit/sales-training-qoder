from __future__ import annotations

from typing import Any

from common.knowledge_engine.answerability import KnowledgeAnswerabilityResult
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackExecutionResult
from common.knowledge_engine.schemas import KnowledgeAnswerResult, KnowledgeCitation

_BLOCKED_TEXT = "当前无法基于知识库证据生成回答，请稍后重试。"


class KnowledgeAnswerAssembler:
    """Assemble a project-owned answer result from deterministic evidence rows."""

    def assemble(
        self,
        *,
        query: str,
        rows: list[dict[str, Any]],
        answerability_result: KnowledgeAnswerabilityResult,
        execution_result: KnowledgeHaystackExecutionResult,
    ) -> KnowledgeAnswerResult:
        _ = query
        blocked_reason = _normalize_optional(answerability_result.audit.get("blocked_reason"))
        rewritten_queries = _collect_rewritten_queries(execution_result)
        retrieval_summary = {
            "hit_count": sum(1 for row in rows if isinstance(row, dict)),
            "executed_query_count": len(execution_result.executed_steps),
            "search_failure_count": len(execution_result.search_failures),
            "blocked_reason": blocked_reason,
        }

        if answerability_result.answerability == "blocked" or answerability_result.source_status == "blocked":
            return KnowledgeAnswerResult(
                final_text=None,
                blocked_text=_BLOCKED_TEXT,
                answerability=answerability_result.answerability,
                source_status=answerability_result.source_status,
                citations=[],
                rewritten_queries=rewritten_queries,
                unsupported_claims=[],
                retrieval_summary=retrieval_summary,
            )

        supported_claims: list[str] = []
        citations: list[KnowledgeCitation] = []
        unsupported_claims: list[str] = []
        seen_citation_keys: set[tuple[str | None, str | None, str]] = set()
        seen_supported_claims: set[str] = set()
        seen_unsupported_claims: set[str] = set()

        for row in rows:
            if not isinstance(row, dict):
                continue
            snippet = _normalize_text(row.get("snippet"))
            content = _normalize_text(row.get("content"))
            citation_key = (
                _normalize_optional(row.get("document_id")),
                _normalize_optional(row.get("chunk_id")),
                snippet or content,
            )

            if snippet:
                if snippet not in seen_supported_claims:
                    seen_supported_claims.add(snippet)
                    supported_claims.append(snippet)
                if citation_key not in seen_citation_keys:
                    seen_citation_keys.add(citation_key)
                    citations.append(
                        KnowledgeCitation(
                            document_id=_normalize_optional(row.get("document_id")),
                            document_title=_normalize_optional(row.get("document_title")),
                            chunk_id=_normalize_optional(row.get("chunk_id")),
                            snippet=snippet,
                            score=_normalize_score(row.get("score")),
                            metadata=_normalize_metadata(row),
                        )
                    )
                continue

            if content and content not in seen_unsupported_claims:
                seen_unsupported_claims.add(content)
                unsupported_claims.append(content)

        final_text = _render_final_text(supported_claims)

        return KnowledgeAnswerResult(
            final_text=final_text,
            blocked_text=None,
            answerability=answerability_result.answerability,
            source_status=answerability_result.source_status,
            citations=citations,
            rewritten_queries=rewritten_queries,
            unsupported_claims=unsupported_claims,
            retrieval_summary=retrieval_summary,
        )


def _collect_rewritten_queries(
    execution_result: KnowledgeHaystackExecutionResult,
) -> list[str]:
    rewritten_queries: list[str] = []
    seen_queries: set[str] = set()
    for step in execution_result.executed_steps:
        query = _normalize_text(step.query)
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)
        rewritten_queries.append(query)
    return rewritten_queries


def _render_final_text(claims: list[str]) -> str | None:
    if not claims:
        return None
    numbered_claims = [f"{index}. {claim}" for index, claim in enumerate(claims, start=1)]
    return "根据知识库证据：\n" + "\n".join(numbered_claims)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_optional(value: Any) -> str | None:
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    normalized = dict(metadata)
    for key in ("knowledge_base_id", "knowledge_base_name", "retrieval_mode", "ranking_passed", "score_breakdown"):
        if key in row:
            normalized[key] = row.get(key)
    return normalized
