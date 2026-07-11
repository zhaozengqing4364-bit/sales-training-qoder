from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from training_runtime.realtime.grounding import (
    GroundingCacheDisposition,
    GroundingCitation,
    GroundingDecisionResult,
    GroundingDiagnostics,
    GroundingEvidence,
    GroundingMode,
    GroundingOutcome,
    GroundingRequest,
    GroundingRetrievalResult,
    RealtimeGroundingModule,
)
from training_runtime.realtime.grounding_cache import GroundingRetrievalCache
from training_runtime.realtime.provider import FrozenJsonMapping


def _request(
    query: str = "产品能力",
    *,
    policy_hash: str = "policy-v1",
    kb_ids: tuple[str, ...] = ("kb-1",),
    top_k: int = 3,
) -> GroundingRequest:
    return GroundingRequest(
        decision_id=f"decision-{query}",
        query=query,
        frozen_policy_hash=policy_hash,
        knowledge_base_ids=kb_ids,
        top_k=top_k,
        metadata_filter={"channel": "sales", "nested": {"enabled": True}},
    )


def _result(
    *,
    status: str = "success",
    count: int = 1,
    answerability: str = "sufficient",
    source_status: str = "hit",
    error_reason: str | None = None,
) -> GroundingRetrievalResult:
    citations = (
        (
            GroundingCitation(
                knowledge_base_id="kb-1",
                knowledge_base_name="产品库",
                document_title="产品说明",
                snippet="支持实时训练",
                claim="产品支持实时训练。",
                score=0.95,
            ),
        )
        if count
        else ()
    )
    evidence = GroundingEvidence(
        citations=citations,
        rewritten_queries=("产品能力",),
        answerability=answerability,
        source_status=source_status,
        retrieval_mode="vector",
    )
    return GroundingRetrievalResult(
        status=status,
        result_count=count,
        retrieval_mode="vector",
        evidence=evidence,
        diagnostics=GroundingDiagnostics(
            schema_version=1,
            status=status,
            reason_code=error_reason or "none",
            source="knowledge",
            mode="grounded" if count else "degraded",
            degraded=bool(error_reason),
            blocked=False,
            cache_disposition=GroundingCacheDisposition.BYPASS,
            result_count=count,
            duration_ms=2.5,
        ),
        error_reason=error_reason,
    )


def test_grounding_request_is_strict_and_recursively_frozen() -> None:
    request = _request()

    assert request.knowledge_base_ids == ("kb-1",)
    assert request.metadata_filter["channel"] == "sales"
    nested = request.metadata_filter["nested"]
    assert nested["enabled"] is True  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        request.top_k = 4  # type: ignore[misc]
    with pytest.raises(TypeError):
        request.metadata_filter["channel"] = "other"  # type: ignore[index]

    with pytest.raises(ValueError, match="frozen_policy_hash"):
        _request(policy_hash="")
    with pytest.raises(ValueError, match="top_k"):
        _request(top_k=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="knowledge_base_id"):
        _request(kb_ids=("",))


@pytest.mark.asyncio
async def test_cache_hash_scope_hit_deep_copy_ttl_and_lru() -> None:
    now = [10.0]
    calls: list[GroundingRequest] = []

    async def retrieve(request: GroundingRequest) -> GroundingRetrievalResult:
        calls.append(request)
        return _result()

    cache = GroundingRetrievalCache(
        ttl_seconds=5.0,
        max_entries=2,
        timeout_seconds=1.0,
        clock=lambda: now[0],
    )
    first = await cache.get_or_retrieve(_request("a"), retrieve)
    second = await cache.get_or_retrieve(_request("a"), retrieve)

    assert first.diagnostics.cache_disposition is GroundingCacheDisposition.MISS
    assert second.diagnostics.cache_disposition is GroundingCacheDisposition.HIT
    assert first is not second
    assert len(calls) == 1

    await cache.get_or_retrieve(_request("b"), retrieve)
    await cache.get_or_retrieve(_request("c"), retrieve)
    stats = cache.stats()
    assert stats.eviction_count == 1
    assert stats.cache_size == 2

    await cache.get_or_retrieve(_request("a", policy_hash="policy-v2"), retrieve)
    await cache.get_or_retrieve(_request("a", kb_ids=("kb-2",)), retrieve)
    assert len(calls) == 5

    now[0] = 20.0
    await cache.get_or_retrieve(_request("c"), retrieve)
    assert len(calls) == 6


@pytest.mark.asyncio
async def test_cache_does_not_negative_cache_empty_error_or_timeout() -> None:
    calls = 0

    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        nonlocal calls
        calls += 1
        if calls <= 2:
            return _result(count=0, status="empty")
        if calls <= 4:
            return _result(status="error", count=0, error_reason="retrieval_failed")
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    cache = GroundingRetrievalCache(
        ttl_seconds=60.0,
        max_entries=8,
        timeout_seconds=0.01,
    )
    await cache.get_or_retrieve(_request("empty"), retrieve)
    await cache.get_or_retrieve(_request("empty"), retrieve)
    await cache.get_or_retrieve(_request("error"), retrieve)
    await cache.get_or_retrieve(_request("error"), retrieve)
    with pytest.raises(TimeoutError):
        await cache.get_or_retrieve(_request("timeout"), retrieve)
    with pytest.raises(TimeoutError):
        await cache.get_or_retrieve(_request("timeout"), retrieve)

    assert calls == 6
    assert cache.stats().cache_size == 0
    assert cache.stats().bypass_count == 6


@pytest.mark.asyncio
async def test_cache_singleflight_shields_waiter_cancellation_and_runs_keys_in_parallel() -> (
    None
):
    started: dict[str, asyncio.Event] = {}
    releases: dict[str, asyncio.Event] = {}
    calls: list[str] = []

    async def retrieve(request: GroundingRequest) -> GroundingRetrievalResult:
        calls.append(request.query)
        started.setdefault(request.query, asyncio.Event()).set()
        await releases.setdefault(request.query, asyncio.Event()).wait()
        return _result()

    cache = GroundingRetrievalCache(
        ttl_seconds=60.0,
        max_entries=8,
        timeout_seconds=1.0,
    )
    owner = asyncio.create_task(cache.get_or_retrieve(_request("same"), retrieve))
    await started.setdefault("same", asyncio.Event()).wait()
    waiter = asyncio.create_task(cache.get_or_retrieve(_request("same"), retrieve))
    other = asyncio.create_task(cache.get_or_retrieve(_request("other"), retrieve))
    await started.setdefault("other", asyncio.Event()).wait()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    releases["same"].set()
    releases["other"].set()

    owner_result, other_result = await asyncio.gather(owner, other)
    hit = await cache.get_or_retrieve(_request("same"), retrieve)
    assert owner_result.diagnostics.cache_disposition is GroundingCacheDisposition.MISS
    assert other_result.diagnostics.cache_disposition is GroundingCacheDisposition.MISS
    assert hit.diagnostics.cache_disposition is GroundingCacheDisposition.HIT
    assert calls.count("same") == 1
    assert calls.count("other") == 1
    assert cache.stats().shared_count == 1

    shared_owner = asyncio.create_task(
        cache.get_or_retrieve(_request("shared"), retrieve)
    )
    await started.setdefault("shared", asyncio.Event()).wait()
    shared_waiter = asyncio.create_task(
        cache.get_or_retrieve(_request("shared"), retrieve)
    )
    await asyncio.sleep(0)
    releases["shared"].set()
    owner_value, waiter_value = await asyncio.gather(shared_owner, shared_waiter)
    assert owner_value.diagnostics.cache_disposition is GroundingCacheDisposition.MISS
    assert (
        waiter_value.diagnostics.cache_disposition is GroundingCacheDisposition.SHARED
    )


@pytest.mark.asyncio
async def test_cache_close_cancels_and_awaits_owner_without_late_store() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        raise AssertionError("unreachable")

    cache = GroundingRetrievalCache(
        ttl_seconds=60.0,
        max_entries=8,
        timeout_seconds=30.0,
    )
    pending = asyncio.create_task(cache.get_or_retrieve(_request(), retrieve))
    await started.wait()
    await cache.close()

    await cancelled.wait()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert cache.stats().inflight_count == 0
    assert cache.stats().cache_size == 0
    with pytest.raises(RuntimeError, match="closed"):
        await cache.get_or_retrieve(_request(), retrieve)


@pytest.mark.asyncio
async def test_cache_close_finishes_owner_cleanup_before_propagating_cancellation() -> (
    None
):
    started = asyncio.Event()
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup_started.set()
            await release_cleanup.wait()
        raise AssertionError("unreachable")

    cache = GroundingRetrievalCache(
        ttl_seconds=60.0,
        max_entries=8,
        timeout_seconds=30.0,
    )
    pending = asyncio.create_task(cache.get_or_retrieve(_request(), retrieve))
    await started.wait()
    closing = asyncio.create_task(cache.close())
    await cleanup_started.wait()
    closing.cancel("first-cache-close-cancel")
    closing.cancel("second-cache-close-cancel")
    await asyncio.sleep(0)
    assert closing.done() is False
    release_cleanup.set()

    with pytest.raises(asyncio.CancelledError) as captured:
        await closing
    assert captured.value.args == ("first-cache-close-cancel",)
    await asyncio.gather(pending, return_exceptions=True)
    assert cache.stats().inflight_count == 0


@pytest.mark.asyncio
async def test_grounding_module_preserves_strict_kb_and_unrestricted_modes() -> None:
    calls = 0

    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        nonlocal calls
        calls += 1
        return _result()

    module = RealtimeGroundingModule(
        retriever=retrieve,
        cache=GroundingRetrievalCache(
            ttl_seconds=60.0,
            max_entries=8,
            timeout_seconds=1.0,
        ),
    )
    strict = await module.prepare(
        _request(),
        policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"require_kb_grounding": True, "retrieval_top_k": 3},
        },
    )
    unrestricted = await module.prepare(
        _request("general", kb_ids=()),
        policy={"tool_policy": {"require_kb_grounding": False}},
    )

    assert strict.outcome is GroundingOutcome.READY
    assert strict.mode is GroundingMode.KB_LOCK
    assert strict.allow_generation is True
    assert strict.evidence.citations[0].claim == "产品支持实时训练。"
    assert calls == 1
    assert unrestricted.outcome is GroundingOutcome.SKIPPED
    assert unrestricted.mode is GroundingMode.UNRESTRICTED
    assert unrestricted.allow_generation is True


@pytest.mark.asyncio
async def test_grounding_module_blocks_unbound_strict_policy_without_retrieval() -> (
    None
):
    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        raise AssertionError("unbound strict policy must not retrieve")

    module = RealtimeGroundingModule(
        retriever=retrieve,
        cache=GroundingRetrievalCache(
            ttl_seconds=60.0,
            max_entries=8,
            timeout_seconds=1.0,
        ),
    )
    result = await module.prepare(
        _request(kb_ids=()),
        policy={"tool_policy": {"require_kb_grounding": True}},
    )

    assert result.outcome is GroundingOutcome.BLOCKED
    assert result.mode is GroundingMode.BLOCKED
    assert result.allow_generation is False
    assert "未绑定" in result.blocked_response


@pytest.mark.asyncio
async def test_grounding_module_thaws_frozen_policy_and_fails_closed_on_scope_drift() -> (
    None
):
    calls = 0

    async def retrieve(_request: GroundingRequest) -> GroundingRetrievalResult:
        nonlocal calls
        calls += 1
        return _result()

    module = RealtimeGroundingModule(
        retriever=retrieve,
        cache=GroundingRetrievalCache(
            ttl_seconds=60.0,
            max_entries=8,
            timeout_seconds=1.0,
        ),
    )
    frozen_policy = FrozenJsonMapping(
        {
            "instruction_contract_hash": "policy-v1",
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"require_kb_grounding": True},
        }
    )

    ready = await module.prepare(_request(), policy=frozen_policy)
    blocked = await module.prepare(
        _request("drift", kb_ids=("kb-other",)),
        policy=frozen_policy,
    )

    assert ready.outcome is GroundingOutcome.READY
    assert blocked.outcome is GroundingOutcome.BLOCKED
    assert blocked.diagnostics.reason_code == "policy_scope_mismatch"
    assert calls == 1


def test_grounding_decision_partial_output_guard_uses_immutable_evidence() -> None:
    module = RealtimeGroundingModule(
        retriever=pytest.fail,  # type: ignore[arg-type]
        cache=GroundingRetrievalCache(
            ttl_seconds=60.0,
            max_entries=8,
            timeout_seconds=1.0,
        ),
    )
    retrieval = _result(answerability="partial")
    decision = module.decide(
        _request(),
        retrieval,
        policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"require_kb_grounding": False},
        },
    )

    assert isinstance(decision, GroundingDecisionResult)
    assert decision.output_guard_required is True
    assert module.build_overlay(decision)
    assert (
        module.apply_output_guard(
            "产品支持实时训练。另有未经支持的承诺。",
            decision,
        )
        == "产品支持实时训练。"
    )
