"""
Unit tests for KnowledgeService document preview fallback path.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import common.knowledge.service as knowledge_service_module
from common.error_handling.result import Result
from common.knowledge.service import KnowledgeService


@pytest.mark.asyncio
async def test_get_document_chunks_falls_back_when_collection_unavailable(monkeypatch):
    service = KnowledgeService(MagicMock())

    doc = SimpleNamespace(
        id="doc-1",
        file_url="data/documents/test.docx",
        file_type="docx",
    )
    kb = SimpleNamespace(vector_collection="kb_collection_1")

    service.get_document = AsyncMock(return_value=Result.ok(doc))
    service.get_by_id = AsyncMock(return_value=Result.ok(kb))

    vector_store = MagicMock()
    vector_store._get_collection.return_value = None
    monkeypatch.setattr(knowledge_service_module, "get_knowledge_vector_store", lambda: vector_store)
    storage = MagicMock()
    storage.load_parse_artifact = MagicMock(return_value=None)
    monkeypatch.setattr(
        knowledge_service_module,
        "get_document_storage_service",
        lambda: storage,
    )

    processor = MagicMock()
    processor._parse_document = AsyncMock(
        return_value=SimpleNamespace(content="第一段内容。第二段内容。第三段内容。")
    )
    processor._build_chunks_from_parse_result.return_value = [
        {"index": 0, "content": "第一段内容。", "metadata": {"start_char": 0, "end_char": 5}},
        {"index": 1, "content": "第二段内容。", "metadata": {"start_char": 6, "end_char": 11}},
        {"index": 2, "content": "第三段内容。", "metadata": {"start_char": 12, "end_char": 17}},
    ]
    monkeypatch.setattr(knowledge_service_module, "get_document_processor", lambda: processor)

    result = await service.get_document_chunks("kb-1", "doc-1", page=1, page_size=2)

    assert result.is_success is True
    chunks, total = result.value
    assert total == 3
    assert len(chunks) == 2
    assert chunks[0]["content"] == "第一段内容。"
    assert chunks[1]["content"] == "第二段内容。"


@pytest.mark.asyncio
async def test_get_document_chunks_falls_back_when_vector_result_empty(monkeypatch):
    service = KnowledgeService(MagicMock())

    doc = SimpleNamespace(
        id="doc-2",
        file_url="data/documents/test2.docx",
        file_type="docx",
    )
    kb = SimpleNamespace(vector_collection="kb_collection_2")

    service.get_document = AsyncMock(return_value=Result.ok(doc))
    service.get_by_id = AsyncMock(return_value=Result.ok(kb))

    class DummyCollection:
        def get(self, where=None, include=None):  # noqa: ANN001
            return {"documents": [], "metadatas": []}

    vector_store = MagicMock()
    vector_store._get_collection.return_value = DummyCollection()
    monkeypatch.setattr(knowledge_service_module, "get_knowledge_vector_store", lambda: vector_store)
    storage = MagicMock()
    storage.load_parse_artifact = MagicMock(return_value=None)
    monkeypatch.setattr(
        knowledge_service_module,
        "get_document_storage_service",
        lambda: storage,
    )

    processor = MagicMock()
    processor._parse_document = AsyncMock(return_value=SimpleNamespace(content="A段。B段。"))
    processor._build_chunks_from_parse_result.return_value = [
        {"index": 0, "content": "A段。", "metadata": {"start_char": 0, "end_char": 2}},
        {"index": 1, "content": "B段。", "metadata": {"start_char": 3, "end_char": 5}},
    ]
    monkeypatch.setattr(knowledge_service_module, "get_document_processor", lambda: processor)

    result = await service.get_document_chunks("kb-2", "doc-2", page=1, page_size=10)

    assert result.is_success is True
    chunks, total = result.value
    assert total == 2
    assert len(chunks) == 2
    assert chunks[0]["index"] == 0
    assert chunks[1]["index"] == 1


@pytest.mark.asyncio
async def test_get_document_chunks_prefers_parse_artifact(monkeypatch):
    service = KnowledgeService(MagicMock())

    doc = SimpleNamespace(
        id="doc-3",
        file_url="data/documents/test3.docx",
        file_type="docx",
    )
    kb = SimpleNamespace(vector_collection="kb_collection_3")

    service.get_document = AsyncMock(return_value=Result.ok(doc))
    service.get_by_id = AsyncMock(return_value=Result.ok(kb))

    storage = MagicMock()
    storage.load_parse_artifact = MagicMock(
        return_value={
            "chunks": [
                {
                    "index": 0,
                    "content": "结构化块A",
                    "metadata": {"element_types": ["heading"], "source_mode": "artifact"},
                },
                {
                    "index": 1,
                    "content": "结构化块B",
                    "metadata": {"element_types": ["table_row"], "source_mode": "artifact"},
                },
            ]
        }
    )
    monkeypatch.setattr(
        knowledge_service_module,
        "get_document_storage_service",
        lambda: storage,
    )

    vector_store = MagicMock()
    monkeypatch.setattr(
        knowledge_service_module,
        "get_knowledge_vector_store",
        lambda: vector_store,
    )

    processor = MagicMock()
    monkeypatch.setattr(knowledge_service_module, "get_document_processor", lambda: processor)

    result = await service.get_document_chunks("kb-3", "doc-3", page=1, page_size=10)

    assert result.is_success is True
    chunks, total = result.value
    assert total == 2
    assert [chunk["content"] for chunk in chunks] == ["结构化块A", "结构化块B"]
    processor._read_document.assert_not_called()
    vector_store._get_collection.assert_not_called()
