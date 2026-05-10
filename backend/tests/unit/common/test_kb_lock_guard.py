"""Unit tests for KB lock guard."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import common.knowledge.kb_lock_guard as guard_module
from common.knowledge.kb_lock_guard import (
    evaluate_kb_lock_decision,
    evaluate_retrieval_grounding_decision,
)


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


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_blocks_partial_answerability_in_strict_audit(
    monkeypatch,
):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 1,
                "retrieval_mode": "hybrid",
                "results": [
                    {
                        "snippet": "实习专家是一款企业内部智能演练平台。",
                        "score": 0.91,
                    }
                ],
                "_answerability": {
                    "answerability": "partial",
                    "source_status": "hit",
                },
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="你知道实习科技是什么吗？帮我介绍一下实习科技。",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "kb_lock_mode": "strict_audit",
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is False
    assert decision.status == "blocked_empty"
    assert "[KB_LOCK_ANSWERABILITY_PARTIAL]" in decision.error_detail


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_allows_partial_answerability_in_coach_mode(
    monkeypatch,
):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 1,
                "retrieval_mode": "hybrid",
                "results": [
                    {
                        "snippet": "实习专家是一款企业内部智能演练平台。",
                        "score": 0.91,
                    }
                ],
                "_answerability": {
                    "answerability": "partial",
                    "source_status": "hit",
                },
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="我这轮介绍话术该怎么收窄？",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "kb_lock_mode": "coach_mode",
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is True
    assert decision.status == "pass"
    assert "实习专家是一款企业内部智能演练平台" in decision.grounding_context


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_auto_enables_lock_for_legacy_snapshot(
    monkeypatch,
):
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 1,
                "retrieval_mode": "hybrid",
                "results": [{"snippet": "合同条款以企业采购协议为准"}],
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="合同条款按什么执行",
        effective_policy={
            # Legacy snapshot: no explicit require_kb_grounding key.
            "tool_policy": {"retrieval_top_k": 3},
            "knowledge_base_ids": ["kb-legacy-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is True
    assert decision.status == "pass"
    assert "合同条款以企业采购协议为准" in decision.grounding_context


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_auto_enables_lock_for_legacy_false_snapshot(
    monkeypatch,
):
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 1,
                "retrieval_mode": "hybrid",
                "results": [{"snippet": "企业版报价需按采购清单审批"}],
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="企业版报价审批流程是什么",
        effective_policy={
            # Legacy snapshot persisted profile default `false` without persona intent.
            "tool_policy": {
                "require_kb_grounding": False,
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-legacy-2"],
            "persona_policy": {"tool_policy": {}},
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is True
    assert decision.status == "pass"
    assert "企业版报价需按采购清单审批" in decision.grounding_context


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_respects_explicit_persona_disable(
    monkeypatch,
):
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    decision = await evaluate_kb_lock_decision(
        query="介绍产品",
        effective_policy={
            "tool_policy": {"require_kb_grounding": False},
            "knowledge_base_ids": ["kb-explicit-disable-1"],
            "persona_policy": {
                "tool_policy": {
                    "require_kb_grounding": False,
                }
            },
        },
    )

    assert decision.lock_required is False
    assert decision.allow_generation is True
    assert decision.status == "pass"


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_blocks_empty_retrieval_even_in_coach_mode(
    monkeypatch,
):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 0,
                "results": [],
                "message": "未命中",
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="我这轮话术应该怎么讲更清楚",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "kb_lock_mode": "coach_mode",
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is False
    assert decision.status == "blocked_empty"
    assert decision.grounding_context == ""
    assert decision.user_message


@pytest.mark.asyncio
async def test_evaluate_kb_lock_decision_coach_mode_blocks_product_overview_on_empty_retrieval(
    monkeypatch,
):
    monkeypatch.setattr(
        guard_module,
        "search_internal_knowledge",
        AsyncMock(
            return_value={
                "count": 0,
                "results": [],
                "message": "未命中",
            }
        ),
    )

    decision = await evaluate_kb_lock_decision(
        query="请介绍石犀产品的技术原理",
        effective_policy={
            "tool_policy": {
                "require_kb_grounding": True,
                "kb_lock_mode": "coach_mode",
                "retrieval_top_k": 3,
            },
            "knowledge_base_ids": ["kb-1"],
        },
    )

    assert decision.lock_required is True
    assert decision.allow_generation is False
    assert decision.status == "blocked_empty"
    assert decision.user_message


def test_evaluate_retrieval_grounding_decision_blocks_bound_kb_query_without_evidence():
    decision = evaluate_retrieval_grounding_decision(
        query="我这轮话术应该怎么讲更清楚？",
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": False,
            },
        },
        retrieval_payload={
            "count": 0,
            "results": [],
            "message": "未命中",
            "_answerability": {
                "answerability": "insufficient",
                "source_status": "miss",
            },
        },
    )

    assert decision.allow_generation is False
    assert decision.status == "blocked_empty"
    assert "没有足够依据" in decision.user_message
    assert decision.grounding_context == ""


def test_evaluate_retrieval_grounding_decision_allows_sufficient_grounded_payload():
    decision = evaluate_retrieval_grounding_decision(
        query="实习专家支持什么训练？",
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": False,
            },
        },
        retrieval_payload={
            "count": 1,
            "results": [
                {
                    "snippet": "实习专家支持销售话术演练和实时反馈。",
                    "score": 0.92,
                }
            ],
            "_answerability": {
                "answerability": "sufficient",
                "source_status": "hit",
                "citations": [{"snippet": "实习专家支持销售话术演练和实时反馈。"}],
            },
        },
    )

    assert decision.allow_generation is True
    assert decision.status == "grounded"
    assert decision.answerability_mode == "grounded"
    assert "实习专家支持销售话术演练" in decision.grounding_context
    assert "以命中片段为准" in decision.grounding_context
