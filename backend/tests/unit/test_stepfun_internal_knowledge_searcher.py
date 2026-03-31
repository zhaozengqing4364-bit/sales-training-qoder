"""Unit tests for StepFun internal knowledge search orchestration helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)


class DummySearchHealthMixin:
    async def get_search_health(self, **kwargs):
        return {
            "knowledge_base_count": 1,
            "ready_document_count": 1,
            "ready_chunk_count": 4,
            "vector_chunk_count": 4,
        }


@pytest.mark.asyncio
async def test_search_internal_knowledge_returns_missing_query_payload():
    record_metric = AsyncMock()

    payload = await search_internal_knowledge(
        arguments_obj={"query": "   "},
        effective_policy={"knowledge_base_ids": ["kb-1"]},
        session_factory=lambda: MagicMock(),
        knowledge_service_cls=MagicMock,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "缺少 query 参数"
    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["query"] == ""
    assert kwargs["result_count"] == 0
    assert kwargs["status"] == "missing_query"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert kwargs["ledger_event"]["status"] == "missing_query"
    assert kwargs["ledger_event"]["query"] == ""
    assert kwargs["ledger_event"]["error_summary"] == "缺少 query 参数"
    assert kwargs["ledger_event"]["result_summaries"] == []


@pytest.mark.asyncio
async def test_search_internal_knowledge_returns_no_kb_payload_when_unbound():
    record_metric = AsyncMock()

    payload = await search_internal_knowledge(
        arguments_obj={"query": "产品定价"},
        effective_policy={"knowledge_base_ids": []},
        session_factory=lambda: MagicMock(),
        knowledge_service_cls=MagicMock,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "当前会话未关联内部知识库"
    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["query"] == "产品定价"
    assert kwargs["result_count"] == 0
    assert kwargs["status"] == "no_kb_bound"
    assert kwargs["knowledge_base_ids"] == []
    assert kwargs["ledger_event"]["status"] == "no_kb_bound"
    assert kwargs["ledger_event"]["query"] == "产品定价"
    assert kwargs["ledger_event"]["error_summary"] == "当前会话未关联内部知识库"
    assert kwargs["ledger_event"]["result_summaries"] == []


@pytest.mark.asyncio
async def test_search_internal_knowledge_records_search_failed_detail():
    record_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            return Result.fail("[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR]")

    payload = await search_internal_knowledge(
        arguments_obj={"query": "十七科技实习产品", "top_k": 3},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"retrieval_similarity_threshold": 0.65},
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "知识检索失败"
    assert "[EMBEDDING_API_ERROR]" in payload["error"]

    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "search_failed"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert kwargs["top_k"] == 3
    assert kwargs["similarity_threshold"] == 0.57
    assert kwargs["ledger_event"]["status"] == "search_failed"
    assert kwargs["ledger_event"]["query"] == "十七科技实习产品"
    assert kwargs["ledger_event"]["error_summary"] == "[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR]"
    assert kwargs["ledger_event"]["result_summaries"] == []


@pytest.mark.asyncio
async def test_search_internal_knowledge_handles_unexpected_exception():
    record_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class ExplodingKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            raise RuntimeError("network down")

    payload = await search_internal_knowledge(
        arguments_obj={"query": "实习产品", "top_k": 2},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"retrieval_similarity_threshold": 0.7},
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=ExplodingKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "知识检索失败"
    assert "[KNOWLEDGE_SEARCH_EXCEPTION]" in payload["error"]
    assert "RuntimeError" in payload["error"]

    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "search_failed"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert kwargs["top_k"] == 2
    assert kwargs["similarity_threshold"] == 0.62
    assert kwargs["ledger_event"]["status"] == "search_failed"
    assert kwargs["ledger_event"]["query"] == "实习产品"
    assert "RuntimeError" in kwargs["ledger_event"]["error_summary"]


@pytest.mark.asyncio
async def test_search_internal_knowledge_returns_kb_not_ready_payload_when_no_ready_docs():
    record_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def get_search_health(self, **kwargs):
            return {
                "knowledge_base_count": 1,
                "ready_document_count": 0,
                "ready_chunk_count": 0,
            }

        async def search_multiple(self, **kwargs):
            raise AssertionError(
                "search_multiple should not be called when KB not ready"
            )

    payload = await search_internal_knowledge(
        arguments_obj={"query": "公司产品有哪些"},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"retrieval_similarity_threshold": 0.65},
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "内部知识库文档尚未处理完成，请稍后重试"

    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "kb_not_ready"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert kwargs["ledger_event"]["status"] == "kb_not_ready"
    assert kwargs["ledger_event"]["query"] == "公司产品有哪些"
    assert kwargs["ledger_event"]["error_summary"] == "内部知识库文档尚未处理完成，请稍后重试"


@pytest.mark.asyncio
async def test_search_internal_knowledge_returns_kb_not_ready_payload_when_health_not_ready_flagged():
    record_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def get_search_health(self, **kwargs):
            return {
                "knowledge_base_count": 1,
                "ready_document_count": 2,
                "ready_chunk_count": 24,
                "vector_chunk_count": 0,
                "is_ready": False,
            }

        async def search_multiple(self, **kwargs):
            raise AssertionError(
                "search_multiple should not be called when KB health is not ready"
            )

    payload = await search_internal_knowledge(
        arguments_obj={"query": "公司产品有哪些"},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"retrieval_similarity_threshold": 0.65},
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert payload["message"] == "内部知识库文档尚未处理完成，请稍后重试"

    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "kb_not_ready"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert "vector_chunks=0" in str(kwargs["error_message"])
    assert kwargs["ledger_event"]["status"] == "kb_not_ready"
    assert kwargs["ledger_event"]["query"] == "公司产品有哪些"
    assert kwargs["ledger_event"]["error_summary"] == "内部知识库文档尚未处理完成，请稍后重试"


@pytest.mark.asyncio
async def test_search_internal_knowledge_stops_rewritten_queries_after_first_success_for_product_overview():
    effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "retrieval_top_k": 5,
        },
    }
    record_metric = AsyncMock()
    captured_queries: list[str] = []

    class FakeKnowledgeService:
        def __init__(self, _db):
            pass

        def get_search_health(self, kb_ids):
            return {
                "is_ready": True,
                "ready_document_count": 1,
                "ready_chunk_count": 1,
                "vector_chunk_count": 1,
            }

        async def search_multiple(
            self,
            *,
            kb_ids,
            query,
            top_k,
            similarity_threshold,
            metadata_filter,
            enable_hybrid,
            keyword_candidate_limit,
            embedding_timeout_ms,
            enable_rerank,
            rerank_top_k,
        ):
            captured_queries.append(query)
            if query.endswith("产品介绍"):
                return Result.ok([
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "世袭科技产品手册",
                        "content": "世袭科技是一家面向企业训练场景的智能销售训练平台。",
                        "score": 0.93,
                        "retrieval_mode": "keyword_fallback",
                    }
                ])
            return Result.ok([])

        def get_last_search_timing(self):
            return {
                "phase_vector_ms": 1200.0,
                "phase_keyword_ms": 20.0,
                "cache_hit_ready_docs": False,
            }

    class FakeSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    payload = await search_internal_knowledge(
        arguments_obj={
            "query": "请你介绍一下世袭科技",
            "top_k": 5,
            "embedding_timeout_ms": 1200,
        },
        effective_policy=effective_policy,
        session_factory=lambda: FakeSession(),
        knowledge_service_cls=FakeKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 1
    assert payload["results"][0]["document_title"] == "世袭科技产品手册"
    assert captured_queries == ["请你介绍一下世袭科技", "请你介绍一下世袭科技 产品介绍"]
    assert payload["_answerability"]["source_status"] in {"hit", "hit_keyword_fallback"}


@pytest.mark.asyncio
async def test_search_internal_knowledge_rewrites_product_overview_query_and_aggregates_results():
    record_metric = AsyncMock()
    captured_queries: list[str] = []

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService(DummySearchHealthMixin):
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            captured_queries.append(str(kwargs["query"]))
            query = str(kwargs["query"])
            if "产品介绍" in query:
                return Result.ok([
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "实习专家是一款面向企业内部训练的智能演练平台。",
                        "score": 0.92,
                        "retrieval_mode": "hybrid",
                    }
                ])
            if "核心能力" in query:
                return Result.ok([
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "它支持销售对练、报告复盘、回放与知识库约束问答。",
                        "score": 0.89,
                        "retrieval_mode": "hybrid",
                    }
                ])
            return Result.ok([])

    payload = await search_internal_knowledge(
        arguments_obj={"query": "请你讲一下实习，介绍一下实习这个产品。", "top_k": 3},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "retrieval_similarity_threshold": 0.65,
                "retrieval_enable_hybrid": True,
                "retrieval_enable_rerank": True,
                "retrieval_rerank_top_k": 8,
            },
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 1
    assert any("产品介绍" in query for query in captured_queries)
    assert not any("核心能力" in query for query in captured_queries)
    assert payload["results"][0]["knowledge_base_name"] == "产品知识库"
    assert record_metric.await_args is not None
    assert record_metric.await_args.kwargs["status"] == "hit"


@pytest.mark.asyncio
async def test_search_internal_knowledge_records_hit_ledger_event_from_transformed_results():
    record_metric = AsyncMock()
    captured: dict[str, object] = {}

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            captured.update(kwargs)
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "命中内容" * 40,
                        "score": 0.91,
                        "retrieval_mode": "vector",
                    }
                ]
            )

    payload = await search_internal_knowledge(
        arguments_obj={
            "query": "十七科技企业版",
            "top_k": 2,
            "metadata_filter": {
                "product_line": "enterprise",
                "regions": ["cn", "", None, "sg"],
            },
        },
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "retrieval_similarity_threshold": 0.66,
                "retrieval_enable_hybrid": False,
                "retrieval_keyword_candidate_limit": 20,
            },
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 1
    assert captured["enable_hybrid"] is False
    assert captured["keyword_candidate_limit"] == 20
    assert captured["metadata_filter"] == {
        "product_line": "enterprise",
        "regions": ["cn", "sg"],
    }
    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "hit"
    assert kwargs["retrieval_mode"] == "vector"
    assert kwargs["ledger_event"]["status"] == "hit"
    assert kwargs["ledger_event"]["query"] == "十七科技企业版"
    assert kwargs["ledger_event"]["result_count"] == 1
    assert kwargs["ledger_event"]["retrieval_mode"] == "vector"
    assert len(kwargs["ledger_event"]["result_summaries"]) == 1
    assert kwargs["ledger_event"]["result_summaries"][0]["knowledge_base_id"] == "kb-1"


@pytest.mark.asyncio
async def test_search_internal_knowledge_records_miss_ledger_event_with_empty_results():
    record_metric = AsyncMock()
    captured: dict[str, object] = {}

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            captured.update(kwargs)
            return Result.ok([])

    payload = await search_internal_knowledge(
        arguments_obj={"query": "石犀产品"},
        effective_policy={
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {
                "retrieval_enable_rerank": True,
                "retrieval_rerank_top_k": 10,
            },
        },
        session_factory=lambda: DummyDbSessionContext(),
        knowledge_service_cls=DummyKnowledgeService,
        record_metric=record_metric,
    )

    assert payload["count"] == 0
    assert captured["enable_rerank"] is True
    assert captured["rerank_top_k"] == 10
    assert record_metric.await_args is not None
    kwargs = record_metric.await_args.kwargs
    assert kwargs["status"] == "miss"
    assert kwargs["ledger_event"]["status"] == "miss"
    assert kwargs["ledger_event"]["query"] == "石犀产品"
    assert kwargs["ledger_event"]["result_count"] == 0
    assert kwargs["ledger_event"]["result_summaries"] == []
