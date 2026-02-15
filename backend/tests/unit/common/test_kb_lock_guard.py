"""Unit tests for KB lock guard."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import common.knowledge.kb_lock_guard as guard_module
from common.knowledge.kb_lock_guard import evaluate_kb_lock_decision


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_returns_pass_when_lock_disabled():
    decision = await evaluate_kb_lock_decision(
        query="介绍产品",
        effective_policy={"tool_policy": {"require_kb_grounding": False}},
    )

    assert decision.lock_required is False
    assert decision.allow_generation is True
    assert decision.status == "pass"


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_blocks_when_no_kb_bound():
    decision = await evaluate_kb_lock_decision(
        query="介绍产品",
        effective_policy={
            "tool_policy": {"require_kb_grounding": True},
            "knowledge_base_ids": [],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is False
    assert decision.status == "blocked_no_kb"


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_blocks_when_retrieval_not_ready(monkeypatch):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 0,
                "results": [],
                "message": "内部知识库文档尚未处理完成，请稍后重试",
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="介绍产品",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is False
    assert decision.status == "blocked_not_ready"


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_passes_with_grounding_context(monkeypatch):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 1,
                "retrieval_mode": "hybrid",
                "results": [{"snippet": "企业版支持按席位扩容"}],
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="企业版支持扩容吗",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is True
    assert decision.status == "pass"
    assert "企业版支持按席位扩容" in decision.grounding_context
    assert decision.retrieval_mode == "hybrid"
