"""Deep module for StepFun grounding and KB-lock decisions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from common.knowledge.kb_lock_guard import (
    KbLockDecision,
    RetrievalGroundingDecision,
    apply_answerability_output_guard,
    build_answerability_instruction_overlay,
    build_blocked_response_from_answerability,
    evaluate_kb_lock_decision,
    evaluate_retrieval_grounding_decision,
    extract_answerability_diagnostics,
)

RecordMetric = Callable[..., Awaitable[None]]
KbLockEvaluator = Callable[..., Awaitable[KbLockDecision]]
KnowledgeRetriever = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class GroundingDecisionContext:
    """Runtime policy and metric seams for one grounding decision."""

    effective_policy: dict[str, Any]
    record_metric: RecordMetric | None = None


class GroundingDecisionPipeline:
    """Small interface around KB-lock and retrieval grounding semantics."""

    def __init__(
        self,
        *,
        kb_lock_evaluator: KbLockEvaluator = evaluate_kb_lock_decision,
        retriever: KnowledgeRetriever | None = None,
    ) -> None:
        self._kb_lock_evaluator = kb_lock_evaluator
        self._retriever = retriever

    async def evaluate(
        self,
        query: str,
        context: GroundingDecisionContext,
        *,
        decision_id: str = "",
    ) -> KbLockDecision:
        """Evaluate strict KB-lock generation permission for one query."""
        return await self._kb_lock_evaluator(
            query=str(query or "").strip(),
            effective_policy=context.effective_policy,
            record_metric=context.record_metric,
            decision_id=decision_id,
        )

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch grounding evidence through the injected retrieval seam."""
        if self._retriever is None:
            raise RuntimeError("GroundingDecisionPipeline retriever seam is not configured")
        payload: dict[str, Any] = {
            "query": str(query or "").strip(),
            "top_k": max(1, min(8, int(top_k or 1))),
        }
        if isinstance(metadata_filter, dict) and metadata_filter:
            payload["metadata_filter"] = dict(metadata_filter)
        return await self._retriever(payload)

    def evaluate_retrieval(
        self,
        query: str,
        context: GroundingDecisionContext,
        retrieval_payload: dict[str, Any],
    ) -> RetrievalGroundingDecision:
        """Evaluate generation permission from an already executed retrieval."""
        return evaluate_retrieval_grounding_decision(
            query=str(query or "").strip(),
            effective_policy=context.effective_policy,
            retrieval_payload=retrieval_payload,
        )

    def build_instruction_overlay(
        self,
        mode: str,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return build_answerability_instruction_overlay(mode, diagnostics)

    def build_blocked_response(self, diagnostics: dict[str, Any] | None) -> str:
        return build_blocked_response_from_answerability(diagnostics)

    def extract_diagnostics(
        self,
        retrieval_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        return extract_answerability_diagnostics(retrieval_payload)

    def apply_output_guard(
        self,
        response_text: str,
        diagnostics: dict[str, Any] | None,
    ) -> str:
        return apply_answerability_output_guard(response_text, diagnostics)
