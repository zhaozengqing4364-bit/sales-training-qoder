"""Deep module for StepFun grounding and KB-lock decisions."""

from __future__ import annotations

import copy
import json
import time
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
GroundingWarmupCallable = Callable[[list[str]], Awaitable[None]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class GroundingDecisionContext:
    """Runtime policy and metric seams for one grounding decision."""

    effective_policy: dict[str, Any]
    record_metric: RecordMetric | None = None


@dataclass(frozen=True)
class GroundingCacheStats:
    """Retrieve-cache counters owned by the grounding pipeline."""

    hit_count: int
    miss_count: int
    cache_size: int

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        if total <= 0:
            return 0.0
        return self.hit_count / total


@dataclass(frozen=True)
class GroundingWarmupResult:
    """Structured result for explicit grounding warmup."""

    status: str
    kb_count: int
    skipped: bool = False
    error: str = ""


class GroundingDecisionPipeline:
    """Small interface around KB-lock and retrieval grounding semantics."""

    def __init__(
        self,
        *,
        kb_lock_evaluator: KbLockEvaluator = evaluate_kb_lock_decision,
        retriever: KnowledgeRetriever | None = None,
        warmup_callable: GroundingWarmupCallable | None = None,
        cache_ttl_seconds: float = 0.0,
        clock: Clock = time.monotonic,
    ) -> None:
        self._kb_lock_evaluator = kb_lock_evaluator
        self._retriever = retriever
        self._warmup_callable = warmup_callable
        self._cache_ttl_seconds = max(0.0, float(cache_ttl_seconds or 0.0))
        self._clock = clock
        self._retrieve_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cache_hit_count = 0
        self._cache_miss_count = 0

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
        cache_key = self._build_retrieve_cache_key(payload)
        if self._cache_ttl_seconds > 0:
            cached = self._get_cached_retrieval(cache_key)
            if cached is not None:
                self._cache_hit_count += 1
                return cached
        self._cache_miss_count += 1
        result = await self._retriever(payload)
        if self._cache_ttl_seconds > 0 and self._is_successful_retrieval(result):
            self._retrieve_cache[cache_key] = (
                self._clock() + self._cache_ttl_seconds,
                copy.deepcopy(result),
            )
        return result

    def get_cache_stats(self) -> GroundingCacheStats:
        """Expose pipeline-owned retrieval cache counters."""
        self._drop_expired_cache_entries()
        return GroundingCacheStats(
            hit_count=self._cache_hit_count,
            miss_count=self._cache_miss_count,
            cache_size=len(self._retrieve_cache),
        )

    async def warmup(self, kb_ids: list[str]) -> GroundingWarmupResult:
        """Warm the grounding retrieval backend through an optional seam."""
        normalized_kb_ids = [str(item).strip() for item in kb_ids if str(item).strip()]
        if self._warmup_callable is None:
            return GroundingWarmupResult(
                status="skipped",
                kb_count=len(normalized_kb_ids),
                skipped=True,
            )
        try:
            await self._warmup_callable(normalized_kb_ids)
        except Exception as exc:  # noqa: BLE001
            return GroundingWarmupResult(
                status="degraded",
                kb_count=len(normalized_kb_ids),
                error=str(exc),
            )
        return GroundingWarmupResult(
            status="completed",
            kb_count=len(normalized_kb_ids),
        )

    def _get_cached_retrieval(self, cache_key: str) -> dict[str, Any] | None:
        entry = self._retrieve_cache.get(cache_key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= self._clock():
            self._retrieve_cache.pop(cache_key, None)
            return None
        return copy.deepcopy(payload)

    def _drop_expired_cache_entries(self) -> None:
        now = self._clock()
        expired_keys = [
            cache_key
            for cache_key, (expires_at, _payload) in self._retrieve_cache.items()
            if expires_at <= now
        ]
        for cache_key in expired_keys:
            self._retrieve_cache.pop(cache_key, None)

    @staticmethod
    def _build_retrieve_cache_key(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _is_successful_retrieval(result: dict[str, Any]) -> bool:
        return isinstance(result, dict) and not bool(result.get("error"))

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
