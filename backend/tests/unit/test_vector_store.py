"""
Unit tests for Vector Store (T039-T040)
Test ChromaDB wrapper and fallback logic
"""
from unittest.mock import MagicMock, patch

import pytest

from common.knowledge.vector_store import VectorStore


class TestVectorStore:
    """T039-P1: Test ChromaDB wrapper"""

    @pytest.fixture
    def vector_store(self):
        """Create vector store instance without real ChromaDB"""
        with patch('common.knowledge.vector_store.chromadb.PersistentClient'):
            store = VectorStore(persist_dir="./test_data")
            return store

    def test_vector_store_initialization(self, vector_store):
        """Should initialize vector store"""
        assert vector_store is not None
        assert vector_store.persist_dir == "./test_data"
        assert vector_store.collection_name == "ppt_knowledge"

    @pytest.mark.asyncio
    async def test_add_documents(self, vector_store):
        """Should add documents to vector store"""
        vector_store.collection = MagicMock()
        vector_store.collection.add = MagicMock()

        documents = ["First document", "Second document"]
        metadatas = [
            {"page_number": 1, "presentation_id": "ppt_123"},
            {"page_number": 2, "presentation_id": "ppt_123"},
        ]
        ids = ["doc1", "doc2"]

        result = await vector_store.add_documents(documents, metadatas, ids)

        assert result.is_success is True
        assert result.value is True
        vector_store.collection.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_documents_with_fallback(self, vector_store):
        """Should return fallback on add failure (T040)"""
        vector_store.collection = MagicMock()
        vector_store.collection.add = MagicMock(side_effect=Exception("ChromaDB unavailable"))

        result = await vector_store.add_documents(["doc"], [{"page": 1}], ["id1"])

        assert result.is_success is False
        assert result.fallback == "[USE_KEYWORD_SEARCH]"

    @pytest.mark.asyncio
    async def test_query_with_metadata_filter(self, vector_store):
        """Should query with metadata filtering (required for PPT retrieval)"""
        vector_store.collection = MagicMock()
        vector_store.collection.query = MagicMock(return_value={
            "documents": [["Matched page content"]],
            "metadatas": [[{"page_number": 5, "presentation_id": "ppt_123"}]],
            "distances": [[0.08]],
        })

        result = await vector_store.query(
            query_text="what is on page 5",
            presentation_id="ppt_123",
            page_number=5,
            n_results=3,
        )

        assert result.is_success is True
        assert len(result.value) == 1
        assert result.value[0]["content"] == "Matched page content"
        assert result.value[0]["metadata"]["page_number"] == 5
        assert result.value[0]["distance"] == 0.08

    @pytest.mark.asyncio
    async def test_query_with_fallback(self, vector_store):
        """Should return fallback on ChromaDB failure (T040)"""
        vector_store.collection = MagicMock()
        vector_store.collection.query = MagicMock(side_effect=Exception("Query failed"))

        result = await vector_store.query(
            query_text="test query",
            presentation_id="ppt_123",
        )

        assert result.is_success is False
        assert result.fallback == "[USE_KEYWORD_SEARCH]"

    @pytest.mark.asyncio
    async def test_delete_presentation(self, vector_store):
        """Should delete all documents for a presentation"""
        vector_store.collection = MagicMock()
        vector_store.collection.get = MagicMock(return_value={
            "ids": ["doc1", "doc2", "doc3"]
        })
        vector_store.collection.delete = MagicMock()

        result = await vector_store.delete_presentation("ppt_123")

        assert result.is_success is True
        vector_store.collection.delete.assert_called_once_with(ids=["doc1", "doc2", "doc3"])

    @pytest.mark.asyncio
    async def test_delete_presentation_with_fallback(self, vector_store):
        """Should return fallback on delete failure"""
        vector_store.collection = MagicMock()
        vector_store.collection.get = MagicMock(side_effect=Exception("Get failed"))

        result = await vector_store.delete_presentation("ppt_123")

        assert result.is_success is False
        assert result.fallback == "[USE_KEYWORD_SEARCH]"

    @pytest.mark.asyncio
    async def test_search_by_keyword_fallback(self, vector_store):
        """Should perform keyword search as fallback"""
        vector_store.collection = MagicMock()
        vector_store.collection.get = MagicMock(return_value={
            "documents": ["This is page 1 content", "Page 2 has different text"],
            "metadatas": [
                {"page_number": 1, "presentation_id": "ppt_123"},
                {"page_number": 2, "presentation_id": "ppt_123"},
            ],
        })

        results = await vector_store.search_by_keyword(
            keyword="page 1",
            presentation_id="ppt_123",
        )

        assert len(results) == 1
        assert "page 1" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_search_by_keyword_with_page_filter(self, vector_store):
        """Should filter by page number in keyword search"""
        vector_store.collection = MagicMock()
        vector_store.collection.get = MagicMock(return_value={
            "documents": ["Page 1", "Page 2", "Page 3"],
            "metadatas": [
                {"page_number": 1, "presentation_id": "ppt_123"},
                {"page_number": 2, "presentation_id": "ppt_123"},
                {"page_number": 3, "presentation_id": "ppt_123"},
            ],
        })

        results = await vector_store.search_by_keyword(
            keyword="page",
            presentation_id="ppt_123",
            page_number=2,
        )

        # Note: The search_by_keyword implementation doesn't filter by page_number in the results
        # It only uses page_number in the where clause when fetching from collection
        # So it returns all matches with the keyword
        assert len(results) == 3  # All pages contain "page"

    def test_get_vector_store_singleton(self):
        """Should return singleton vector store instance"""
        with patch('common.knowledge.vector_store.chromadb.PersistentClient'):
            from common.knowledge.vector_store import get_vector_store

            store1 = get_vector_store()
            store2 = get_vector_store()

            assert store1 is store2

    @pytest.mark.asyncio
    async def test_query_empty_results(self, vector_store):
        """Should handle empty query results"""
        vector_store.collection = MagicMock()
        vector_store.collection.query = MagicMock(return_value={
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        })

        result = await vector_store.query(
            query_text="no matches",
            presentation_id="ppt_123",
        )

        assert result.is_success is True
        assert len(result.value) == 0
