from __future__ import annotations

import pytest

from common.error_handling.result import Result
from common.knowledge_engine.haystack_adapter import KnowledgeHaystackAdapter
from common.knowledge_engine.retrieval_planner import (
    KnowledgeRetrievalPlan,
    KnowledgeRetrievalStep,
)


@pytest.mark.asyncio
async def test_adapter_executes_plan_dedupes_rows_and_early_stops_after_first_hit():
    captured_queries: list[str] = []

    async def fake_search_multiple(**kwargs):
        captured_queries.append(str(kwargs["query"]))
        if kwargs["query"] == "石犀科技 产品介绍":
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "石犀科技产品介绍",
                        "content": "石犀科技是一家销售训练平台。",
                        "score": 0.61,
                        "retrieval_mode": "hybrid",
                    },
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "石犀科技产品介绍",
                        "content": "石犀科技是一家销售训练平台。",
                        "score": 0.58,
                        "retrieval_mode": "hybrid",
                    },
                ]
            )
        return Result.ok([])

    adapter = KnowledgeHaystackAdapter(search_multiple=fake_search_multiple)
    plan = KnowledgeRetrievalPlan(
        profile_key="product_overview",
        intent_key="company_intro",
        strategy="multi_query",
        stop_after_first_success=True,
        resolved_entities=["石犀科技"],
        steps=[
            KnowledgeRetrievalStep(
                query="请介绍一下石犀科技",
                stage="primary",
                profile_key="product_overview",
            ),
            KnowledgeRetrievalStep(
                query="石犀科技 产品介绍",
                stage="expansion",
                profile_key="product_overview",
            ),
            KnowledgeRetrievalStep(
                query="石犀科技 核心能力",
                stage="expansion",
                profile_key="product_overview",
            ),
        ],
        audit={},
    )

    result = await adapter.execute_plan(
        plan=plan,
        knowledge_base_ids=["kb-1"],
        top_k=5,
        similarity_threshold=0.58,
        metadata_filter=None,
        enable_hybrid=True,
        keyword_candidate_limit=32,
        embedding_timeout_ms=0,
        enable_rerank=True,
        rerank_top_k=8,
    )

    assert captured_queries == ["请介绍一下石犀科技", "石犀科技 产品介绍"]
    assert result.stopped_early is True
    assert len(result.rows) == 1
    assert result.rows[0]["document_title"] == "石犀科技产品介绍"
    assert [step.status for step in result.executed_steps] == ["miss", "hit"]
    assert result.executed_steps[1].hit_count == 1
    assert result.executed_steps[1].early_stopped is True


@pytest.mark.asyncio
async def test_adapter_records_failed_steps_and_returns_first_failure_when_no_hits():
    async def fake_search_multiple(**kwargs):
        if kwargs["query"] == "石犀科技 产品介绍":
            return Result.fail("[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout")
        return Result.ok([])

    adapter = KnowledgeHaystackAdapter(search_multiple=fake_search_multiple)
    plan = KnowledgeRetrievalPlan(
        profile_key="product_overview",
        intent_key="company_intro",
        strategy="multi_query",
        stop_after_first_success=True,
        resolved_entities=["石犀科技"],
        steps=[
            KnowledgeRetrievalStep(
                query="请介绍一下石犀科技",
                stage="primary",
                profile_key="product_overview",
            ),
            KnowledgeRetrievalStep(
                query="石犀科技 产品介绍",
                stage="expansion",
                profile_key="product_overview",
            ),
        ],
        audit={},
    )

    result = await adapter.execute_plan(
        plan=plan,
        knowledge_base_ids=["kb-1"],
        top_k=5,
        similarity_threshold=0.58,
        metadata_filter=None,
        enable_hybrid=True,
        keyword_candidate_limit=32,
        embedding_timeout_ms=0,
        enable_rerank=True,
        rerank_top_k=8,
    )

    assert result.rows == []
    assert result.search_failures == ["[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout"]
    assert [step.status for step in result.executed_steps] == ["miss", "failed"]
    assert result.executed_steps[1].error == "[KNOWLEDGE_SEARCH_UNAVAILABLE] timeout"
    assert result.stopped_early is False
