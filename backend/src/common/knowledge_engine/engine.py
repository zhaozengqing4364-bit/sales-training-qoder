from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, cast

from common.db.models import KnowledgeAnswerRun
from common.knowledge_engine.answerability import (
    KnowledgeAnswerabilityEvaluator,
    KnowledgeAnswerabilityResult,
)
from common.knowledge_engine.assembler import KnowledgeAnswerAssembler
from common.knowledge_engine.audit_repo import KnowledgeAnswerAuditRepository
from common.knowledge_engine.config_repo import (
    KnowledgeAnswerConfigRepository,
    KnowledgeAnswerConfigSnapshot,
    KnowledgeEntityAliasConfig,
)
from common.knowledge_engine.entity_resolver import (
    KnowledgeEntityResolution,
    KnowledgeEntityResolver,
)
from common.knowledge_engine.haystack_adapter import (
    KnowledgeHaystackAdapter,
    KnowledgeHaystackExecutionResult,
)
from common.knowledge_engine.intent_classifier import (
    KnowledgeIntentClassification,
    KnowledgeIntentClassifier,
)
from common.knowledge_engine.reranker import KnowledgeReranker
from common.knowledge_engine.retrieval_planner import (
    KnowledgeRetrievalPlan,
    KnowledgeRetrievalPlanner,
)
from common.knowledge_engine.schemas import (
    KnowledgeAnswerRequest,
    KnowledgeAnswerResult,
    KnowledgeAuditStep,
)

HaystackPipelineFactory = Callable[[], Any | None]


class KnowledgeAnswerEngine:
    """Project-owned grounded-answer orchestration seam."""

    def __init__(
        self,
        *,
        haystack_pipeline_factory: HaystackPipelineFactory | None = None,
        config_repository: KnowledgeAnswerConfigRepository | None = None,
        entity_resolver: KnowledgeEntityResolver | None = None,
        intent_classifier_factory: type[
            KnowledgeIntentClassifier
        ] = KnowledgeIntentClassifier,
        retrieval_planner_factory: type[
            KnowledgeRetrievalPlanner
        ] = KnowledgeRetrievalPlanner,
        haystack_adapter: KnowledgeHaystackAdapter | None = None,
        reranker: KnowledgeReranker | None = None,
        answerability_evaluator_factory: type[
            KnowledgeAnswerabilityEvaluator
        ] = KnowledgeAnswerabilityEvaluator,
        assembler: KnowledgeAnswerAssembler | None = None,
        audit_repository: KnowledgeAnswerAuditRepository | None = None,
    ) -> None:
        self._haystack_pipeline_factory = (
            haystack_pipeline_factory or default_haystack_pipeline_factory
        )
        self._config_repository = config_repository
        self._entity_resolver = entity_resolver or KnowledgeEntityResolver()
        self._intent_classifier_factory = intent_classifier_factory
        self._retrieval_planner_factory = retrieval_planner_factory
        self._haystack_adapter = haystack_adapter
        self._reranker = reranker or KnowledgeReranker()
        self._answerability_evaluator_factory = answerability_evaluator_factory
        self._assembler = assembler or KnowledgeAnswerAssembler()
        self._audit_repository = audit_repository

    @property
    def haystack_pipeline_factory(self) -> HaystackPipelineFactory:
        return self._haystack_pipeline_factory

    def answer(self, request: KnowledgeAnswerRequest) -> KnowledgeAnswerResult:
        config_snapshot = (
            self._config_repository.get_active_config()
            if self._config_repository
            else None
        )
        if (
            config_snapshot is None
            or not config_snapshot.query_profiles
            or self._haystack_adapter is None
        ):
            return KnowledgeAnswerResult()

        audit_steps: list[KnowledgeAuditStep] = []

        entity_resolution = self._record_step(
            audit_steps,
            step_name="resolve",
            input_payload={"query": request.query},
            output_builder=lambda: self._resolve_query(
                request.query,
                config_snapshot=config_snapshot,
                runtime_options=request.runtime_options,
            ),
        )
        classifier = self._intent_classifier_factory(
            query_profiles=config_snapshot.query_profiles,
            intent_rules=config_snapshot.intent_rules,
        )
        classification = self._record_step(
            audit_steps,
            step_name="classify",
            input_payload={
                "query": request.query,
                "normalized_query": entity_resolution.normalized_query,
            },
            output_builder=lambda: classifier.classify(
                request.query,
                entity_resolution=entity_resolution,
            ),
        )
        profile_key = classification.profile_key
        if not profile_key or profile_key not in config_snapshot.query_profiles:
            return KnowledgeAnswerResult()

        planner = self._retrieval_planner_factory(
            query_profiles=config_snapshot.query_profiles
        )
        retrieval_plan = self._record_step(
            audit_steps,
            step_name="plan",
            input_payload={
                "profile_key": profile_key,
                "intent_key": classification.intent_key,
            },
            output_builder=lambda: planner.build_plan(classification),
        )
        execution_result = self._record_step(
            audit_steps,
            step_name="retrieve",
            input_payload={
                "knowledge_base_ids": list(request.knowledge_base_ids),
                "plan_query_count": len(retrieval_plan.steps),
                "runtime_options": dict(request.runtime_options),
            },
            output_builder=lambda: self._execute_plan(request, retrieval_plan),
        )
        reranked_rows = self._record_step(
            audit_steps,
            step_name="rank",
            input_payload={
                "candidate_count": len(execution_result.rows),
                "profile_key": retrieval_plan.profile_key,
            },
            output_builder=lambda: self._reranker.rerank(
                rows=execution_result.rows,
                profile_key=retrieval_plan.profile_key,
                query=request.query,
                normalized_query=entity_resolution.normalized_query,
                resolved_entities=classification.resolved_entities,
                top_k=max(1, int(request.runtime_options.get("top_k") or 5)),
            ),
        )
        evaluator = self._answerability_evaluator_factory(
            answerability_profiles=config_snapshot.answerability_profiles
        )
        answerability_result = self._record_step(
            audit_steps,
            step_name="answerability",
            input_payload={
                "profile_key": retrieval_plan.profile_key,
                "row_count": len(reranked_rows),
            },
            output_builder=lambda: evaluator.evaluate(
                profile_key=retrieval_plan.profile_key,
                rows=reranked_rows,
                execution_result=execution_result,
            ),
        )
        assembled = self._record_step(
            audit_steps,
            step_name="assemble",
            input_payload={
                "query": entity_resolution.normalized_query or request.query,
                "row_count": len(reranked_rows),
                "answerability": answerability_result.answerability,
            },
            output_builder=lambda: self._assembler.assemble(
                query=entity_resolution.normalized_query or request.query,
                rows=reranked_rows,
                answerability_result=answerability_result,
                execution_result=execution_result,
            ),
        )

        retrieval_summary = dict(assembled.retrieval_summary)
        retrieval_summary.update(
            {
                "config_version_id": config_snapshot.config_version_id,
                "config_version_name": config_snapshot.config_version_name,
                "resolved_query": entity_resolution.normalized_query or request.query,
                "profile_key": retrieval_plan.profile_key,
                "intent_key": classification.intent_key,
                "entity_resolution": _entity_resolution_payload(entity_resolution),
                "intent": _classification_payload(classification),
                "retrieval_plan": _retrieval_plan_payload(retrieval_plan),
                "execution_trace": _execution_trace_payload(execution_result),
                "search_failures": list(execution_result.search_failures),
                "compat_source_status": _compat_source_status(
                    answerability_result, execution_result
                ),
                "retrieval_mode": _retrieval_mode_from_rows(reranked_rows),
            }
        )

        result = cast(
            KnowledgeAnswerResult,
            assembled.model_copy(update={"retrieval_summary": retrieval_summary}),
        )
        persisted = self._persist_audit(
            request=request,
            config_version_id=config_snapshot.config_version_id,
            result=result,
            answerability=answerability_result.answerability,
            blocked_reason=answerability_result.audit.get("blocked_reason"),
            audit_steps=audit_steps,
        )
        if persisted is not None:
            result = cast(
                KnowledgeAnswerResult,
                result.model_copy(update={"audit_run_id": persisted.id}),
            )
        return result

    def _resolve_query(
        self,
        query: str,
        *,
        config_snapshot: KnowledgeAnswerConfigSnapshot | None = None,
        runtime_options: dict[str, Any] | None = None,
    ) -> KnowledgeEntityResolution:
        entity_aliases = list(
            config_snapshot.entity_aliases
            if config_snapshot is not None
            and getattr(config_snapshot, "entity_aliases", None)
            else []
        )
        entity_aliases.extend(_runtime_lexicon_entity_aliases(runtime_options or {}))
        if entity_aliases:
            resolver = KnowledgeEntityResolver(entity_aliases=entity_aliases)
            return resolver.resolve_query(query)
        return self._entity_resolver.resolve_query(query)

    def _execute_plan(
        self,
        request: KnowledgeAnswerRequest,
        retrieval_plan: KnowledgeRetrievalPlan,
    ) -> KnowledgeHaystackExecutionResult:
        adapter = self._haystack_adapter
        if adapter is None:
            return KnowledgeHaystackExecutionResult()

        runtime_options = dict(request.runtime_options)
        raw_metadata_filter = runtime_options.get("metadata_filter")
        metadata_filter = (
            dict(raw_metadata_filter) if isinstance(raw_metadata_filter, dict) else None
        )
        return _run_async(
            adapter.execute_plan(
                plan=retrieval_plan,
                knowledge_base_ids=list(request.knowledge_base_ids),
                top_k=max(1, int(runtime_options.get("top_k") or 5)),
                similarity_threshold=float(
                    runtime_options.get("similarity_threshold") or 0.58
                ),
                metadata_filter=metadata_filter,
                enable_hybrid=bool(runtime_options.get("enable_hybrid", True)),
                keyword_candidate_limit=max(
                    1, int(runtime_options.get("keyword_candidate_limit") or 32)
                ),
                embedding_timeout_ms=max(
                    0, int(runtime_options.get("embedding_timeout_ms") or 0)
                ),
                enable_rerank=bool(runtime_options.get("enable_rerank", True)),
                rerank_top_k=max(1, int(runtime_options.get("rerank_top_k") or 8)),
            )
        )

    def _persist_audit(
        self,
        *,
        request: KnowledgeAnswerRequest,
        config_version_id: str | None,
        result: KnowledgeAnswerResult,
        answerability: str,
        blocked_reason: Any,
        audit_steps: list[KnowledgeAuditStep],
    ) -> KnowledgeAnswerRun | None:
        if self._audit_repository is None or not request.session_id:
            return None
        final_status = (
            "blocked" if answerability in {"blocked", "insufficient"} else "completed"
        )
        return self._audit_repository.create_run(
            session_id=request.session_id,
            config_version_id=config_version_id,
            entrypoint=str(request.entrypoint or "unknown"),
            query_text=str(
                result.retrieval_summary.get("resolved_query") or request.query
            ),
            answerability=answerability,
            final_status=final_status,
            blocked_reason=str(blocked_reason).strip() or None
            if blocked_reason is not None
            else None,
            citations=[citation.model_dump() for citation in result.citations],
            retrieval_summary=dict(result.retrieval_summary),
            steps=audit_steps,
        )

    @staticmethod
    def _record_step(
        audit_steps: list[KnowledgeAuditStep],
        *,
        step_name: str,
        input_payload: dict[str, Any],
        output_builder: Callable[[], Any],
    ) -> Any:
        started_at = time.monotonic()
        output = output_builder()
        audit_steps.append(
            KnowledgeAuditStep(
                step_name=step_name,
                input_payload=_normalize_payload(input_payload),
                output_payload=_normalize_payload(_audit_output_payload(output)),
                duration_ms=max(0, int((time.monotonic() - started_at) * 1000)),
                status="completed",
            )
        )
        return output


def default_haystack_pipeline_factory() -> Any | None:
    try:
        from haystack import Pipeline  # type: ignore[import-not-found]
    except ImportError:
        return None

    return Pipeline()


def _run_async(
    awaitable: Coroutine[Any, Any, KnowledgeHaystackExecutionResult],
) -> KnowledgeHaystackExecutionResult:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        raise RuntimeError(
            "KnowledgeAnswerEngine.answer cannot be called from a running event loop"
        )
    return asyncio.run(awaitable)


def _normalize_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _runtime_lexicon_entity_aliases(
    runtime_options: dict[str, Any],
) -> list[KnowledgeEntityAliasConfig]:
    tool_policy = runtime_options.get("tool_policy")
    if not isinstance(tool_policy, dict):
        return []
    entries = tool_policy.get("transcript_normalization_lexicon")
    if not isinstance(entries, list):
        return []

    aliases: list[KnowledgeEntityAliasConfig] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        canonical_term = str(entry.get("canonical_term") or "").strip()
        raw_aliases = entry.get("aliases")
        if not canonical_term or not isinstance(raw_aliases, list):
            continue
        entity_type = str(entry.get("entity_type") or "asr_lexicon").strip()
        try:
            confidence = float(entry.get("confidence") or 0.95)
        except (TypeError, ValueError):
            confidence = 0.95
        for raw_alias in raw_aliases:
            alias = str(raw_alias or "").strip()
            if not alias or alias == canonical_term:
                continue
            dedupe_key = (canonical_term, alias)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            aliases.append(
                KnowledgeEntityAliasConfig(
                    canonical_entity=canonical_term,
                    alias=alias,
                    entity_type=entity_type,
                    confidence=confidence,
                    profile_source="runtime_tool_policy",
                )
            )
    return aliases


def _audit_output_payload(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        payload: dict[str, Any] = {}
        for key, raw in vars(value).items():
            payload[key] = _audit_value(raw)
        return payload
    if isinstance(value, list):
        return {"items": [_audit_value(item) for item in value]}
    if isinstance(value, dict):
        return {key: _audit_value(raw) for key, raw in value.items()}
    return {"value": _audit_value(value)}


def _audit_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return {key: _audit_value(raw) for key, raw in vars(value).items()}
    if isinstance(value, list):
        return [_audit_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _audit_value(raw) for key, raw in value.items()}
    return value


def _entity_resolution_payload(
    entity_resolution: KnowledgeEntityResolution,
) -> dict[str, Any]:
    return {
        "resolved": entity_resolution.resolved,
        "normalized_query": entity_resolution.normalized_query,
        "canonical_entities": list(entity_resolution.canonical_entities),
        "matches": [
            {
                "canonical_entity": match.canonical_entity,
                "matched_text": match.matched_text,
                "entity_type": match.entity_type,
                "confidence": match.confidence,
                "match_source": match.match_source,
                "start_index": match.start_index,
                "end_index": match.end_index,
            }
            for match in entity_resolution.matches
        ],
    }


def _classification_payload(
    classification: KnowledgeIntentClassification,
) -> dict[str, Any]:
    return {
        "intent_key": classification.intent_key,
        "profile_key": classification.profile_key,
        "matched": classification.matched,
        "matched_terms": list(classification.matched_terms),
        "resolved_entities": list(classification.resolved_entities),
        "fallback_reason": classification.fallback_reason,
    }


def _retrieval_plan_payload(retrieval_plan: KnowledgeRetrievalPlan) -> dict[str, Any]:
    return {
        "profile_key": retrieval_plan.profile_key,
        "intent_key": retrieval_plan.intent_key,
        "strategy": retrieval_plan.strategy,
        "stop_after_first_success": retrieval_plan.stop_after_first_success,
        "resolved_entities": list(retrieval_plan.resolved_entities),
        "steps": [
            {
                "query": step.query,
                "stage": step.stage,
                "profile_key": step.profile_key,
            }
            for step in retrieval_plan.steps
        ],
        "audit": dict(retrieval_plan.audit),
    }


def _execution_trace_payload(
    execution_result: KnowledgeHaystackExecutionResult,
) -> dict[str, Any]:
    return {
        "stopped_early": execution_result.stopped_early,
        "search_failures": list(execution_result.search_failures),
        "executed_steps": [
            {
                "query": step.query,
                "stage": step.stage,
                "profile_key": step.profile_key,
                "status": step.status,
                "hit_count": step.hit_count,
                "retrieval_modes": list(step.retrieval_modes),
                "error": step.error,
                "early_stopped": step.early_stopped,
            }
            for step in execution_result.executed_steps
        ],
    }


def _compat_source_status(
    answerability_result: KnowledgeAnswerabilityResult,
    execution_result: KnowledgeHaystackExecutionResult,
) -> str:
    if answerability_result.answerability == "blocked":
        if execution_result.search_failures:
            return "search_failed"
        return "blocked"
    if execution_result.executed_steps and not execution_result.rows:
        return "miss"
    if execution_result.rows:
        return "hit"
    return str(answerability_result.source_status)


def _retrieval_mode_from_rows(rows: list[dict[str, Any]]) -> str:
    modes = {
        str(row.get("retrieval_mode") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("retrieval_mode") or "").strip()
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
