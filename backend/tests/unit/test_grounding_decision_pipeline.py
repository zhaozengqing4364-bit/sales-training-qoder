"""Unit tests for the StepFun grounding decision pipeline."""

from __future__ import annotations

# pyright: reportMissingImports=false
from typing import Any

import pytest

from common.knowledge.kb_lock_guard import KbLockDecision
from sales_bot.websocket.grounding_decision_pipeline import (
    GroundingDecisionContext,
    GroundingDecisionPipeline,
)


@pytest.mark.asyncio
async def test_evaluate_returns_skip_when_kb_lock_not_required():
    async def fake_evaluator(**kwargs: Any) -> KbLockDecision:
        return KbLockDecision(
            lock_required=False,
            allow_generation=True,
            status="pass",
            grounding_context="",
            user_message="",
            decision_id=str(kwargs["decision_id"]),
        )

    pipeline = GroundingDecisionPipeline(kb_lock_evaluator=fake_evaluator)

    decision = await pipeline.evaluate(
        "产品价格",
        GroundingDecisionContext(effective_policy={}),
        decision_id="decision-1",
    )

    assert decision.lock_required is False
    assert decision.allow_generation is True
    assert decision.status == "pass"
    assert decision.decision_id == "decision-1"


@pytest.mark.asyncio
async def test_evaluate_returns_block_when_answerability_low():
    async def fake_evaluator(**_kwargs: Any) -> KbLockDecision:
        return KbLockDecision(
            lock_required=True,
            allow_generation=False,
            status="blocked_empty",
            grounding_context="",
            user_message="知识库未命中，请补充关键词",
            error_detail="[KB_LOCK_LOW_CONFIDENCE]",
        )

    pipeline = GroundingDecisionPipeline(kb_lock_evaluator=fake_evaluator)

    decision = await pipeline.evaluate(
        "产品价格",
        GroundingDecisionContext(
            effective_policy={
                "knowledge_base_ids": ["kb-1"],
                "tool_policy": {"require_kb_grounding": True},
            },
        ),
    )

    assert decision.allow_generation is False
    assert decision.status == "blocked_empty"
    assert decision.user_message == "知识库未命中，请补充关键词"
    assert decision.error_detail == "[KB_LOCK_LOW_CONFIDENCE]"


@pytest.mark.asyncio
async def test_retrieve_fetches_from_injected_search_seam():
    calls: list[dict[str, Any]] = []

    async def fake_retriever(arguments_obj: dict[str, Any]) -> dict[str, Any]:
        calls.append(arguments_obj)
        return {
            "count": 1,
            "results": [{"snippet": "标准版支持按年付费。"}],
        }

    pipeline = GroundingDecisionPipeline(retriever=fake_retriever)

    payload = await pipeline.retrieve(" 标准版价格 ", top_k=3)

    assert calls == [{"query": "标准版价格", "top_k": 3}]
    assert payload["count"] == 1
    assert payload["results"][0]["snippet"] == "标准版支持按年付费。"


@pytest.mark.asyncio
async def test_retrieve_caches_successful_result_and_hits_on_second_call():
    now = 100.0
    calls: list[dict[str, Any]] = []

    async def fake_retriever(arguments_obj: dict[str, Any]) -> dict[str, Any]:
        calls.append(arguments_obj)
        return {"count": 1, "results": [{"snippet": f"命中 {len(calls)}"}]}

    pipeline = GroundingDecisionPipeline(
        retriever=fake_retriever,
        cache_ttl_seconds=30.0,
        clock=lambda: now,
    )

    first = await pipeline.retrieve(" 标准版价格 ", top_k=3)
    second = await pipeline.retrieve("标准版价格", top_k=3)

    assert first == second
    assert calls == [{"query": "标准版价格", "top_k": 3}]
    stats = pipeline.get_cache_stats()
    assert stats.hit_count == 1
    assert stats.miss_count == 1
    assert stats.hit_rate == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_retrieve_expires_cached_result_after_ttl():
    now = 100.0
    calls = 0

    async def fake_retriever(_arguments_obj: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"count": 1, "results": [{"snippet": f"命中 {calls}"}]}

    pipeline = GroundingDecisionPipeline(
        retriever=fake_retriever,
        cache_ttl_seconds=5.0,
        clock=lambda: now,
    )

    first = await pipeline.retrieve("标准版价格", top_k=3)
    now = 106.0
    second = await pipeline.retrieve("标准版价格", top_k=3)

    assert first != second
    assert calls == 2
    stats = pipeline.get_cache_stats()
    assert stats.hit_count == 0
    assert stats.miss_count == 2


@pytest.mark.asyncio
async def test_warmup_preloads_kb_index_through_injected_seam():
    calls: list[list[str]] = []

    async def fake_warmup(kb_ids: list[str]) -> None:
        calls.append(kb_ids)

    pipeline = GroundingDecisionPipeline(warmup_callable=fake_warmup)

    result = await pipeline.warmup([" kb-1 ", "", "kb-2"])

    assert calls == [["kb-1", "kb-2"]]
    assert result.status == "completed"
    assert result.kb_count == 2
    assert result.skipped is False


@pytest.mark.asyncio
async def test_warmup_returns_skipped_result_when_no_warmup_seam_configured():
    pipeline = GroundingDecisionPipeline()

    result = await pipeline.warmup(["kb-1"])

    assert result.status == "skipped"
    assert result.kb_count == 1
    assert result.skipped is True


def test_build_instruction_overlay_uses_existing_answerability_semantics():
    pipeline = GroundingDecisionPipeline()

    overlay = pipeline.build_instruction_overlay(
        "partial",
        {
            "answerability": "partial",
            "citations": [{"snippet": "标准版支持按年付费。"}],
            "rewritten_queries": ["标准版价格"],
        },
    )

    assert "当前仅有部分内部证据可用" in overlay
    assert "标准版价格" in overlay
    assert "可引用片段数：1" in overlay


def test_build_blocked_response_uses_existing_answerability_semantics():
    pipeline = GroundingDecisionPipeline()

    blocked = pipeline.build_blocked_response({"source_status": "search_failed"})

    assert blocked == "当前内部知识检索失败，暂时无法基于内部资料安全回答。请稍后重试。"


def test_extract_diagnostics_preserves_answerability_shape():
    pipeline = GroundingDecisionPipeline()

    diagnostics = pipeline.extract_diagnostics(
        {
            "count": 1,
            "_answerability": {
                "answerability": "sufficient",
                "source_status": "hit",
                "citations": [{"snippet": "企业版支持私有化部署。"}],
            },
        }
    )

    assert diagnostics == {
        "answerability": "sufficient",
        "source_status": "hit",
        "citations": [{"snippet": "企业版支持私有化部署。"}],
    }


def test_evaluate_retrieval_end_to_end_retrieve_and_ground():
    pipeline = GroundingDecisionPipeline()

    decision = pipeline.evaluate_retrieval(
        "企业版部署方式",
        GroundingDecisionContext(
            effective_policy={
                "knowledge_base_ids": ["kb-1"],
                "tool_policy": {"require_kb_grounding": False},
            },
        ),
        {
            "count": 1,
            "results": [{"snippet": "企业版支持私有化部署。", "score": 0.91}],
            "_answerability": {
                "answerability": "sufficient",
                "source_status": "hit",
                "citations": [{"snippet": "企业版支持私有化部署。"}],
            },
        },
    )

    assert decision.allow_generation is True
    assert decision.status == "grounded"
    assert decision.answerability_mode == "grounded"
    assert "用户问题：企业版部署方式" in decision.grounding_context
    assert "企业版支持私有化部署" in decision.grounding_context
