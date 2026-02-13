"""
Unit tests for KnowledgeService keyword fallback retrieval.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import common.knowledge.service as knowledge_service_module
from common.error_handling.result import Result
from common.knowledge.service import KnowledgeService


@pytest.mark.asyncio
async def test_search_multiple_falls_back_to_keywords_when_embedding_fails(monkeypatch):
    service = KnowledgeService(MagicMock())
    service.get_by_id = AsyncMock(
        return_value=Result.ok(
            SimpleNamespace(
                id="kb-1",
                name="产品知识库",
                vector_collection="kb_collection_1",
            )
        )
    )

    embedding_service = MagicMock()
    embedding_service.is_configured = True
    embedding_service.embed = AsyncMock(
        return_value=Result.fail("[EMBEDDING_API_ERROR] 402 Payment Required")
    )
    monkeypatch.setattr(knowledge_service_module, "get_embedding_service", lambda: embedding_service)

    class DummyCollection:
        def get(self, include=None):
            return {
                "documents": [
                    "十七科技的实习产品支持销售训练和话术演练。",
                    "这是无关的资料。",
                ],
                "metadatas": [
                    {"document_id": "doc-1", "document_title": "产品手册", "chunk_index": 1},
                    {"document_id": "doc-2", "document_title": "其他资料", "chunk_index": 1},
                ],
            }

    vector_store = MagicMock()
    vector_store._get_collection.return_value = DummyCollection()
    monkeypatch.setattr(knowledge_service_module, "get_knowledge_vector_store", lambda: vector_store)

    result = await service.search_multiple(
        kb_ids=["kb-1"],
        query="十七科技实习产品是什么",
        top_k=3,
        similarity_threshold=0.7,
    )

    assert result.is_success is True
    assert isinstance(result.value, list)
    assert len(result.value) == 1
    assert result.value[0]["knowledge_base_id"] == "kb-1"
    assert result.value[0]["retrieval_mode"] == "keyword_fallback"
    assert "十七科技的实习产品" in result.value[0]["content"]


@pytest.mark.asyncio
async def test_search_multiple_returns_error_when_embedding_fails_and_no_keyword_hit(monkeypatch):
    service = KnowledgeService(MagicMock())
    service.get_by_id = AsyncMock(
        return_value=Result.ok(
            SimpleNamespace(
                id="kb-1",
                name="产品知识库",
                vector_collection="kb_collection_1",
            )
        )
    )

    embedding_service = MagicMock()
    embedding_service.is_configured = True
    embedding_service.embed = AsyncMock(
        return_value=Result.fail("[EMBEDDING_API_ERROR] 402 Payment Required")
    )
    monkeypatch.setattr(knowledge_service_module, "get_embedding_service", lambda: embedding_service)

    class DummyCollection:
        def get(self, include=None):
            return {
                "documents": ["完全不相关的内容"],
                "metadatas": [{"document_id": "doc-3", "document_title": "其他资料", "chunk_index": 1}],
            }

    vector_store = MagicMock()
    vector_store._get_collection.return_value = DummyCollection()
    monkeypatch.setattr(knowledge_service_module, "get_knowledge_vector_store", lambda: vector_store)

    result = await service.search_multiple(
        kb_ids=["kb-1"],
        query="十七科技实习产品是什么",
        top_k=3,
        similarity_threshold=0.7,
    )

    assert result.is_success is False
    assert result.fallback is not None
    assert "[KNOWLEDGE_SEARCH_UNAVAILABLE]" in result.fallback
    assert "[EMBEDDING_API_ERROR]" in result.fallback
