"""Unit tests for StepFun internal knowledge search orchestration helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
from sales_bot.websocket.components.stepfun_internal_knowledge_searcher import (
    search_internal_knowledge,
)


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
    record_metric.assert_awaited_once_with(
        query="",
        result_count=0,
        status="missing_query",
        knowledge_base_ids=["kb-1"],
    )


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
    record_metric.assert_awaited_once_with(
        query="产品定价",
        result_count=0,
        status="no_kb_bound",
        knowledge_base_ids=[],
    )


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


@pytest.mark.asyncio
async def test_search_internal_knowledge_passes_hybrid_and_metadata_filter():
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
                        "content": "命中内容",
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
