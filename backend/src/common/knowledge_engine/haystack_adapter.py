from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.error_handling.result import Result
from common.knowledge_engine.retrieval_planner import KnowledgeRetrievalPlan


@dataclass(frozen=True)
class KnowledgeExecutedQueryStep:
    query: str
    stage: str
    profile_key: str
    status: str
    hit_count: int = 0
    retrieval_modes: list[str] = field(default_factory=list)
    error: str | None = None
    early_stopped: bool = False


@dataclass(frozen=True)
class KnowledgeHaystackExecutionResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    executed_steps: list[KnowledgeExecutedQueryStep] = field(default_factory=list)
    search_failures: list[str] = field(default_factory=list)
    stopped_early: bool = False


class KnowledgeHaystackAdapter:
    """Execute project-owned retrieval plans against the existing search service."""

    def __init__(self, *, search_multiple) -> None:
        self._search_multiple = search_multiple

    async def execute_plan(
        self,
        *,
        plan: KnowledgeRetrievalPlan,
        knowledge_base_ids: list[str],
        top_k: int,
        similarity_threshold: float,
        metadata_filter: dict[str, Any] | None,
        enable_hybrid: bool,
        keyword_candidate_limit: int,
        embedding_timeout_ms: int,
        enable_rerank: bool,
        rerank_top_k: int,
    ) -> KnowledgeHaystackExecutionResult:
        aggregated_rows: list[dict[str, Any]] = []
        seen_row_keys: set[tuple[str, str, str]] = set()
        executed_steps: list[KnowledgeExecutedQueryStep] = []
        search_failures: list[str] = []
        stopped_early = False

        for step in plan.steps:
            search_result = await self._search_multiple(
                kb_ids=knowledge_base_ids,
                query=step.query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                metadata_filter=metadata_filter,
                enable_hybrid=enable_hybrid,
                keyword_candidate_limit=keyword_candidate_limit,
                embedding_timeout_ms=embedding_timeout_ms,
                enable_rerank=enable_rerank,
                rerank_top_k=rerank_top_k,
            )
            if not isinstance(search_result, Result):
                raise TypeError("search_multiple must return Result[list[dict[str, Any]]]")

            if not search_result.is_success:
                error = str(search_result.fallback or "unknown_error")
                search_failures.append(error)
                executed_steps.append(
                    KnowledgeExecutedQueryStep(
                        query=step.query,
                        stage=step.stage,
                        profile_key=step.profile_key,
                        status="failed",
                        error=error,
                    )
                )
                continue

            retrieval_modes: set[str] = set()
            new_rows_added = 0
            for row in search_result.value or []:
                if not isinstance(row, dict):
                    continue
                row_key = self._build_row_key(row)
                if row_key in seen_row_keys:
                    continue
                seen_row_keys.add(row_key)
                aggregated_rows.append(dict(row))
                retrieval_mode = str(row.get("retrieval_mode") or "").strip()
                if retrieval_mode:
                    retrieval_modes.add(retrieval_mode)
                new_rows_added += 1

            early_stopped = False
            if plan.stop_after_first_success and new_rows_added > 0:
                early_stopped = True
                stopped_early = True

            executed_steps.append(
                KnowledgeExecutedQueryStep(
                    query=step.query,
                    stage=step.stage,
                    profile_key=step.profile_key,
                    status="hit" if new_rows_added > 0 else "miss",
                    hit_count=new_rows_added,
                    retrieval_modes=sorted(retrieval_modes),
                    early_stopped=early_stopped,
                )
            )

            if early_stopped:
                break

        return KnowledgeHaystackExecutionResult(
            rows=aggregated_rows,
            executed_steps=executed_steps,
            search_failures=search_failures,
            stopped_early=stopped_early,
        )

    @staticmethod
    def _build_row_key(row: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(row.get("knowledge_base_id") or ""),
            str(row.get("document_title") or row.get("source") or ""),
            str(row.get("content") or ""),
        )
