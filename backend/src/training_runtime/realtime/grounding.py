"""Provider-neutral grounding decisions and immutable evidence contracts."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING, Any, Protocol

from common.knowledge.kb_lock_guard import (
    KbLockDecision,
    apply_answerability_output_guard,
    build_answerability_instruction_overlay,
    evaluate_kb_lock_decision,
    evaluate_retrieval_grounding_decision,
)
from training_runtime.realtime.provider import FrozenJsonMapping, JsonValue

if TYPE_CHECKING:
    from training_runtime.realtime.grounding_cache import GroundingRetrievalCache


def _required_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"grounding_{field_name}_must_be_non_empty_string")
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _non_negative_int(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"grounding_{field_name}_must_be_non_negative_integer")
    return value


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(item) for item in value]
    return copy.deepcopy(value)


class GroundingOutcome(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class GroundingMode(StrEnum):
    GROUNDED = "grounded"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    SKIPPED = "skipped"
    UNRESTRICTED = "unrestricted"
    KB_LOCK = "kb_lock"
    NOT_APPLICABLE = "not_applicable"


class GroundingCacheDisposition(StrEnum):
    HIT = "hit"
    MISS = "miss"
    SHARED = "shared"
    BYPASS = "bypass"


@dataclass(frozen=True, slots=True)
class GroundingRequest:
    decision_id: str
    query: str
    frozen_policy_hash: str
    knowledge_base_ids: tuple[str, ...]
    top_k: int
    metadata_filter: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id", _required_text(self.decision_id, "decision_id")
        )
        object.__setattr__(self, "query", _required_text(self.query, "query"))
        object.__setattr__(
            self,
            "frozen_policy_hash",
            _required_text(self.frozen_policy_hash, "frozen_policy_hash"),
        )
        if type(self.knowledge_base_ids) is not tuple:
            raise ValueError("grounding_knowledge_base_ids_must_be_tuple")
        normalized_ids = tuple(
            _required_text(item, "knowledge_base_id")
            for item in self.knowledge_base_ids
        )
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("grounding_knowledge_base_ids_must_be_unique")
        object.__setattr__(self, "knowledge_base_ids", normalized_ids)
        if type(self.top_k) is not int or not 1 <= self.top_k <= 8:
            raise ValueError("grounding_top_k_must_be_integer_between_1_and_8")
        if not isinstance(self.metadata_filter, Mapping):
            raise ValueError("grounding_metadata_filter_must_be_mapping")
        object.__setattr__(
            self, "metadata_filter", FrozenJsonMapping(self.metadata_filter)
        )


@dataclass(frozen=True, slots=True)
class GroundingCacheStats:
    hit_count: int
    miss_count: int
    shared_count: int
    bypass_count: int
    eviction_count: int
    cache_size: int
    inflight_count: int

    def __post_init__(self) -> None:
        for field_name in (
            "hit_count",
            "miss_count",
            "shared_count",
            "bypass_count",
            "eviction_count",
            "cache_size",
            "inflight_count",
        ):
            _non_negative_int(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class GroundingDiagnostics:
    schema_version: int
    status: str
    reason_code: str
    source: str
    mode: str
    degraded: bool
    blocked: bool
    cache_disposition: GroundingCacheDisposition
    result_count: int
    duration_ms: float

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("grounding_diagnostics_schema_version_unsupported")
        for field_name in ("status", "reason_code", "source", "mode"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )
        if self.mode not in {item.value for item in GroundingMode}:
            raise ValueError("grounding_diagnostics_mode_invalid")
        if type(self.degraded) is not bool or type(self.blocked) is not bool:
            raise ValueError("grounding_diagnostics_flags_must_be_boolean")
        if not isinstance(self.cache_disposition, GroundingCacheDisposition):
            raise ValueError("grounding_cache_disposition_invalid")
        _non_negative_int(self.result_count, "result_count")
        if (
            type(self.duration_ms) not in {int, float}
            or not isfinite(float(self.duration_ms))
            or float(self.duration_ms) < 0
        ):
            raise ValueError("grounding_duration_ms_must_be_non_negative_finite")
        object.__setattr__(self, "duration_ms", float(self.duration_ms))


@dataclass(frozen=True, slots=True)
class GroundingCitation:
    knowledge_base_id: str
    knowledge_base_name: str
    document_title: str
    snippet: str
    claim: str
    score: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "knowledge_base_id",
            "knowledge_base_name",
            "document_title",
            "snippet",
            "claim",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )
        if self.score is not None:
            if type(self.score) not in {int, float} or not isfinite(float(self.score)):
                raise ValueError("grounding_citation_score_must_be_finite")
            object.__setattr__(self, "score", float(self.score))


@dataclass(frozen=True, slots=True)
class GroundingEvidence:
    citations: tuple[GroundingCitation, ...]
    rewritten_queries: tuple[str, ...]
    answerability: str
    source_status: str
    retrieval_mode: str

    def __post_init__(self) -> None:
        if type(self.citations) is not tuple or not all(
            isinstance(item, GroundingCitation) for item in self.citations
        ):
            raise ValueError("grounding_citations_must_be_tuple")
        if type(self.rewritten_queries) is not tuple:
            raise ValueError("grounding_rewritten_queries_must_be_tuple")
        object.__setattr__(
            self,
            "rewritten_queries",
            tuple(
                _required_text(item, "rewritten_query")
                for item in self.rewritten_queries
            ),
        )
        for field_name in ("answerability", "source_status", "retrieval_mode"):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True, slots=True)
class GroundingRetrievalResult:
    status: str
    result_count: int
    retrieval_mode: str
    evidence: GroundingEvidence
    diagnostics: GroundingDiagnostics
    error_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _required_text(self.status, "status"))
        _non_negative_int(self.result_count, "result_count")
        object.__setattr__(
            self,
            "retrieval_mode",
            _required_text(self.retrieval_mode, "retrieval_mode"),
        )
        if not isinstance(self.evidence, GroundingEvidence):
            raise ValueError("grounding_evidence_invalid")
        if not isinstance(self.diagnostics, GroundingDiagnostics):
            raise ValueError("grounding_diagnostics_invalid")
        if self.diagnostics.result_count != self.result_count:
            raise ValueError("grounding_result_count_mismatch")
        object.__setattr__(
            self,
            "error_reason",
            _optional_text(self.error_reason, "error_reason"),
        )


@dataclass(frozen=True, slots=True)
class GroundingDecisionResult:
    decision_id: str
    frozen_policy_hash: str
    outcome: GroundingOutcome
    mode: GroundingMode
    allow_generation: bool
    grounding_context: str
    blocked_response: str
    output_guard_required: bool
    evidence: GroundingEvidence
    cache_disposition: GroundingCacheDisposition
    diagnostics: GroundingDiagnostics

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id", _required_text(self.decision_id, "decision_id")
        )
        object.__setattr__(
            self,
            "frozen_policy_hash",
            _required_text(self.frozen_policy_hash, "frozen_policy_hash"),
        )
        if not isinstance(self.outcome, GroundingOutcome):
            raise ValueError("grounding_outcome_invalid")
        if not isinstance(self.mode, GroundingMode):
            raise ValueError("grounding_mode_invalid")
        if (
            type(self.allow_generation) is not bool
            or type(self.output_guard_required) is not bool
        ):
            raise ValueError("grounding_decision_flags_must_be_boolean")
        if (
            type(self.grounding_context) is not str
            or type(self.blocked_response) is not str
        ):
            raise ValueError("grounding_decision_text_must_be_string")
        if not isinstance(self.evidence, GroundingEvidence):
            raise ValueError("grounding_evidence_invalid")
        if not isinstance(self.cache_disposition, GroundingCacheDisposition):
            raise ValueError("grounding_cache_disposition_invalid")
        if not isinstance(self.diagnostics, GroundingDiagnostics):
            raise ValueError("grounding_diagnostics_invalid")
        if self.outcome is GroundingOutcome.BLOCKED:
            if self.allow_generation or not self.blocked_response.strip():
                raise ValueError("grounding_blocked_decision_invariant")
        elif not self.allow_generation:
            raise ValueError("grounding_non_blocked_decision_must_allow_generation")
        if self.output_guard_required and not self.allow_generation:
            raise ValueError("grounding_output_guard_requires_generation")


class GroundingRetrieverPort(Protocol):
    async def __call__(self, request: GroundingRequest) -> GroundingRetrievalResult: ...


class RealtimeGroundingRuntime(Protocol):
    async def prepare(
        self,
        request: GroundingRequest,
        *,
        policy: Mapping[str, JsonValue],
    ) -> GroundingDecisionResult: ...

    async def close(self) -> None: ...


KbLockEvaluator = Callable[..., Awaitable[KbLockDecision]]


def _empty_evidence() -> GroundingEvidence:
    return GroundingEvidence(
        citations=(),
        rewritten_queries=(),
        answerability="not_applicable",
        source_status="not_applicable",
        retrieval_mode="not_applicable",
    )


def _answerability_diagnostics(evidence: GroundingEvidence) -> dict[str, Any]:
    return {
        "answerability": evidence.answerability,
        "source_status": evidence.source_status,
        "rewritten_queries": list(evidence.rewritten_queries),
        "citations": [
            {
                "knowledge_base_id": citation.knowledge_base_id,
                "knowledge_base_name": citation.knowledge_base_name,
                "document_title": citation.document_title,
                "snippet": citation.snippet,
                "claim": citation.claim,
                "score": citation.score,
            }
            for citation in evidence.citations
        ],
    }


def _legacy_retrieval_payload(result: GroundingRetrievalResult) -> dict[str, Any]:
    rows = [
        {
            "knowledge_base_id": citation.knowledge_base_id,
            "knowledge_base_name": citation.knowledge_base_name,
            "document_title": citation.document_title,
            "title": citation.document_title,
            "snippet": citation.snippet,
            "content": citation.snippet,
            "claim": citation.claim,
            "score": citation.score,
        }
        for citation in result.evidence.citations
    ]
    payload: dict[str, Any] = {
        "count": result.result_count,
        "retrieval_mode": result.retrieval_mode,
        "results": rows,
        "_answerability": _answerability_diagnostics(result.evidence),
    }
    if result.error_reason:
        payload["error"] = result.error_reason
    return payload


class RealtimeGroundingModule:
    """Single decision surface over strict KB-lock and retrieval grounding."""

    def __init__(
        self,
        *,
        retriever: GroundingRetrieverPort,
        cache: GroundingRetrievalCache,
        kb_lock_evaluator: KbLockEvaluator = evaluate_kb_lock_decision,
    ) -> None:
        self._retriever = retriever
        self._cache = cache
        self._kb_lock_evaluator = kb_lock_evaluator

    async def prepare(
        self,
        request: GroundingRequest,
        *,
        policy: Mapping[str, JsonValue],
    ) -> GroundingDecisionResult:
        if not isinstance(policy, Mapping):
            raise ValueError("grounding_policy_must_be_mapping")
        effective_policy = _thaw_json(policy)
        if not isinstance(effective_policy, dict):
            raise ValueError("grounding_policy_must_be_mapping")
        scope_failure = self._scope_failure(request, effective_policy)
        if scope_failure is not None:
            return self._blocked_scope_result(request, scope_failure)
        retrieval_result: GroundingRetrievalResult | None = None

        async def cache_backed_retriever(**_kwargs: Any) -> dict[str, Any]:
            nonlocal retrieval_result
            retrieval_result = await self.retrieve(request)
            return _legacy_retrieval_payload(retrieval_result)

        decision = await self._kb_lock_evaluator(
            query=request.query,
            effective_policy=effective_policy,
            record_metric=None,
            decision_id=request.decision_id,
            retriever=cache_backed_retriever,
        )
        return self._from_kb_lock_decision(request, decision, retrieval_result)

    async def retrieve(self, request: GroundingRequest) -> GroundingRetrievalResult:
        try:
            return await self._cache.get_or_retrieve(request, self._retriever)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            return self._degraded_retrieval("timeout")
        except Exception:  # noqa: BLE001
            return self._degraded_retrieval("retrieval_failed")

    def decide(
        self,
        request: GroundingRequest,
        retrieval: GroundingRetrievalResult,
        *,
        policy: Mapping[str, JsonValue],
    ) -> GroundingDecisionResult:
        if not isinstance(policy, Mapping):
            raise ValueError("grounding_policy_must_be_mapping")
        effective_policy = _thaw_json(policy)
        if not isinstance(effective_policy, dict):
            raise ValueError("grounding_policy_must_be_mapping")
        scope_failure = self._scope_failure(request, effective_policy)
        if scope_failure is not None:
            return self._blocked_scope_result(request, scope_failure)
        decision = evaluate_retrieval_grounding_decision(
            query=request.query,
            effective_policy=effective_policy,
            retrieval_payload=_legacy_retrieval_payload(retrieval),
        )
        if not decision.allow_generation:
            outcome = GroundingOutcome.BLOCKED
            mode = GroundingMode.BLOCKED
        elif retrieval.error_reason:
            outcome = GroundingOutcome.DEGRADED
            mode = GroundingMode.DEGRADED
        elif decision.status == "grounded":
            outcome = GroundingOutcome.READY
            mode = GroundingMode.GROUNDED
        else:
            outcome = GroundingOutcome.SKIPPED
            mode = GroundingMode.UNRESTRICTED
        diagnostics = self._decision_diagnostics(
            status=decision.status,
            reason_code=retrieval.error_reason or decision.status,
            source="retrieval",
            mode=mode,
            blocked=not decision.allow_generation,
            degraded=outcome is GroundingOutcome.DEGRADED,
            retrieval=retrieval,
        )
        return GroundingDecisionResult(
            decision_id=request.decision_id,
            frozen_policy_hash=request.frozen_policy_hash,
            outcome=outcome,
            mode=mode,
            allow_generation=decision.allow_generation,
            grounding_context=decision.grounding_context,
            blocked_response=decision.user_message,
            output_guard_required=decision.should_apply_output_guard,
            evidence=retrieval.evidence,
            cache_disposition=retrieval.diagnostics.cache_disposition,
            diagnostics=diagnostics,
        )

    def build_overlay(self, result: GroundingDecisionResult) -> str:
        diagnostics = _answerability_diagnostics(result.evidence)
        if result.output_guard_required:
            mode = "partial"
        elif result.mode in {GroundingMode.GROUNDED, GroundingMode.KB_LOCK}:
            mode = "grounded"
        elif result.mode is GroundingMode.DEGRADED:
            mode = "ungrounded"
        else:
            mode = "default"
        return build_answerability_instruction_overlay(mode, diagnostics)

    def build_blocked_response(self, result: GroundingDecisionResult) -> str:
        return result.blocked_response

    def apply_output_guard(self, text: str, result: GroundingDecisionResult) -> str:
        if not result.output_guard_required:
            return text
        return apply_answerability_output_guard(
            text,
            _answerability_diagnostics(result.evidence),
        )

    async def close(self) -> None:
        await self._cache.close()

    @staticmethod
    def _scope_failure(
        request: GroundingRequest,
        effective_policy: dict[str, Any],
    ) -> str | None:
        raw_ids = effective_policy.get("knowledge_base_ids", [])
        if not isinstance(raw_ids, list) or any(
            type(item) is not str for item in raw_ids
        ):
            return "policy_scope_invalid"
        policy_ids = tuple(sorted(item.strip() for item in raw_ids if item.strip()))
        if policy_ids != tuple(sorted(request.knowledge_base_ids)):
            return "policy_scope_mismatch"
        policy_hash = effective_policy.get("instruction_contract_hash")
        if policy_hash is not None:
            if type(policy_hash) is not str or not policy_hash.strip():
                return "policy_hash_invalid"
            if policy_hash.strip() != request.frozen_policy_hash:
                return "policy_hash_mismatch"
        return None

    @staticmethod
    def _blocked_scope_result(
        request: GroundingRequest,
        reason: str,
    ) -> GroundingDecisionResult:
        evidence = _empty_evidence()
        diagnostics = GroundingDiagnostics(
            schema_version=1,
            status="blocked_configuration",
            reason_code=reason,
            source="policy",
            mode=GroundingMode.BLOCKED.value,
            degraded=False,
            blocked=True,
            cache_disposition=GroundingCacheDisposition.BYPASS,
            result_count=0,
            duration_ms=0.0,
        )
        return GroundingDecisionResult(
            decision_id=request.decision_id,
            frozen_policy_hash=request.frozen_policy_hash,
            outcome=GroundingOutcome.BLOCKED,
            mode=GroundingMode.BLOCKED,
            allow_generation=False,
            grounding_context="",
            blocked_response="当前会话的知识范围与冻结配置不一致，请重新建立会话后再试。",
            output_guard_required=False,
            evidence=evidence,
            cache_disposition=GroundingCacheDisposition.BYPASS,
            diagnostics=diagnostics,
        )

    def _from_kb_lock_decision(
        self,
        request: GroundingRequest,
        decision: KbLockDecision,
        retrieval: GroundingRetrievalResult | None,
    ) -> GroundingDecisionResult:
        evidence = retrieval.evidence if retrieval is not None else _empty_evidence()
        disposition = (
            retrieval.diagnostics.cache_disposition
            if retrieval is not None
            else GroundingCacheDisposition.BYPASS
        )
        if not decision.lock_required:
            outcome = GroundingOutcome.SKIPPED
            mode = GroundingMode.UNRESTRICTED
        elif decision.allow_generation:
            outcome = GroundingOutcome.READY
            mode = GroundingMode.KB_LOCK
        else:
            outcome = GroundingOutcome.BLOCKED
            mode = GroundingMode.BLOCKED
        diagnostics = GroundingDiagnostics(
            schema_version=1,
            status=decision.status,
            reason_code=decision.status,
            source="kb_lock",
            mode=mode.value,
            degraded=False,
            blocked=not decision.allow_generation,
            cache_disposition=disposition,
            result_count=decision.result_count,
            duration_ms=decision.duration_ms,
        )
        return GroundingDecisionResult(
            decision_id=request.decision_id,
            frozen_policy_hash=request.frozen_policy_hash,
            outcome=outcome,
            mode=mode,
            allow_generation=decision.allow_generation,
            grounding_context=decision.grounding_context,
            blocked_response=decision.user_message,
            output_guard_required=False,
            evidence=evidence,
            cache_disposition=disposition,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _decision_diagnostics(
        *,
        status: str,
        reason_code: str,
        source: str,
        mode: GroundingMode,
        blocked: bool,
        degraded: bool,
        retrieval: GroundingRetrievalResult,
    ) -> GroundingDiagnostics:
        return GroundingDiagnostics(
            schema_version=1,
            status=status,
            reason_code=reason_code,
            source=source,
            mode=mode.value,
            degraded=degraded,
            blocked=blocked,
            cache_disposition=retrieval.diagnostics.cache_disposition,
            result_count=retrieval.result_count,
            duration_ms=retrieval.diagnostics.duration_ms,
        )

    @staticmethod
    def _degraded_retrieval(reason: str) -> GroundingRetrievalResult:
        evidence = GroundingEvidence(
            citations=(),
            rewritten_queries=(),
            answerability="insufficient",
            source_status=reason,
            retrieval_mode="unavailable",
        )
        return GroundingRetrievalResult(
            status="degraded",
            result_count=0,
            retrieval_mode="unavailable",
            evidence=evidence,
            diagnostics=GroundingDiagnostics(
                schema_version=1,
                status="degraded",
                reason_code=reason,
                source="retrieval",
                mode=GroundingMode.DEGRADED.value,
                degraded=True,
                blocked=False,
                cache_disposition=GroundingCacheDisposition.BYPASS,
                result_count=0,
                duration_ms=0.0,
            ),
            error_reason=reason,
        )
