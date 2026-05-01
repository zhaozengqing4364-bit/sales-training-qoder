"""
Vector Store - ChromaDB integration for knowledge base

Provides vector storage and retrieval for knowledge base documents.
Supports embedding generation via EmbeddingService.

Constitution Principle: Fallback to empty results on failure

References:
- Requirements: R5 (Knowledge Base management)
- Design: Section 27 (Vector Store)
"""

import asyncio
import os
from typing import Any

import chromadb
from chromadb.config import Settings

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
CHROMADB_PERSIST_DIR = os.getenv("CHROMADB_PERSIST_DIR", "./data/chromadb")


class KnowledgeVectorStore:
    """
    ChromaDB vector store for knowledge base documents.

    Features:
    - Per-knowledge-base collections
    - Metadata filtering by document_id
    - Similarity search with threshold
    - Graceful degradation on failure
    - Thread-safe write operations
    """

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or CHROMADB_PERSIST_DIR
        self.client: chromadb.PersistentClient | None = None
        self._initialized = False
        self._write_lock = asyncio.Lock()  # 写入锁，防止并发写入冲突

    def _ensure_initialized(self) -> bool:
        """Ensure ChromaDB client is initialized."""
        if self._initialized and self.client:
            return True

        try:
            os.makedirs(self.persist_dir, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            self._initialized = True
            logger.info(f"ChromaDB initialized at {self.persist_dir}")
            return True

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"ChromaDB initialization error: {e}")
            return False

    def _get_collection(self, collection_name: str) -> chromadb.Collection | None:
        """Get or create a collection."""
        if not self._ensure_initialized():
            return None

        try:
            return self.client.get_or_create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 200,
                    "hnsw:M": 16,
                },
            )
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"Failed to get collection {collection_name}: {e}")
            return None

    async def add_chunks(
        self,
        collection_name: str,
        chunks: list[dict[str, Any]],
        embeddings: list[list[float]],
        document_id: str,
        document_title: str,
    ) -> Result[int]:
        """
        Add document chunks to vector store.

        Supports two chunk types via ``chunk_type`` metadata field:

        * ``"child"``  (default) – normal embedded chunk for retrieval.
        * ``"parent"`` – context chunk stored with a zero-vector placeholder
          embedding; it is **not** used for retrieval, only returned when a
          child hit maps back to its parent.

        Parent-child linkage is maintained via ``parent_id`` / ``child_ids``
        metadata keys.

        Args:
            collection_name: ChromaDB collection name (from KnowledgeBase.vector_collection)
            chunks: List of chunk dicts with 'index', 'content', 'metadata'
            embeddings: List of embedding vectors (one per chunk; parent chunks
                may use an empty/zero vector as placeholder)
            document_id: Document UUID
            document_title: Document title for metadata

        Returns:
            Result with number of chunks added
        """
        if not chunks or not embeddings:
            return Result.ok(0)

        if len(chunks) != len(embeddings):
            return Result.fail("[CHUNK_EMBEDDING_MISMATCH]")

        collection = self._get_collection(collection_name)
        if not collection:
            return Result.fail("[VECTOR_STORE_UNAVAILABLE]")

        # 使用写入锁防止并发写入冲突
        async with self._write_lock:
            try:
                ids = []
                documents = []
                metadatas = []

                for chunk in chunks:
                    chunk_type = (chunk.get("metadata") or {}).get(
                        "chunk_type", "child"
                    )
                    chunk_id = f"{document_id}_{chunk['index']}"
                    ids.append(chunk_id)
                    documents.append(chunk["content"])
                    metadatas.append(
                        {
                            "document_id": document_id,
                            "document_title": document_title,
                            "chunk_index": chunk["index"],
                            "chunk_type": chunk_type,
                            **chunk.get("metadata", {}),
                        }
                    )

                # Best-effort pre-cleanup for idempotent retries.
                try:
                    collection.delete(where={"document_id": document_id})
                except Exception as cleanup_error:
                    logger.warning(
                        f"Pre-cleanup before vector add failed: {cleanup_error}",
                        document_id=document_id,
                    )

                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )

                logger.info(
                    f"Added {len(chunks)} chunks to collection {collection_name}",
                    document_id=document_id,
                )
                return Result.ok(len(chunks))

            except Exception as e:
                try:
                    # Chroma has no transaction; compensate partial writes by document_id.
                    collection.delete(where={"document_id": document_id})
                except Exception as cleanup_error:
                    logger.error(
                        f"Failed vector compensation cleanup: {cleanup_error}",
                        document_id=document_id,
                    )
                logger.error(f"Failed to add chunks: {e}")
                return Result.fail(f"[VECTOR_ADD_FAILED] {str(e)}")

    async def search(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 3,
        similarity_threshold: float = 0.7,
        document_ids: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> Result[list[dict[str, Any]]]:
        """
        Search for similar chunks.

        Args:
            collection_name: ChromaDB collection name
            query_embedding: Query embedding vector
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1, cosine)
            document_ids: Optional filter by document IDs

        Returns:
            Result with list of search results
        """
        collection = self._get_collection(collection_name)
        if not collection:
            return Result.ok([])  # Graceful degradation

        try:
            # Build where clause
            where_clauses: list[dict[str, Any]] = []
            if document_ids:
                if len(document_ids) == 1:
                    where_clauses.append({"document_id": document_ids[0]})
                else:
                    where_clauses.append({"document_id": {"$in": document_ids}})

            if isinstance(metadata_filter, dict):
                for key, expected in metadata_filter.items():
                    if isinstance(expected, list):
                        where_clauses.append(
                            {key: {"$in": [item for item in expected]}}
                        )
                    else:
                        where_clauses.append({key: expected})

            where = None
            if len(where_clauses) == 1:
                where = where_clauses[0]
            elif len(where_clauses) > 1:
                where = {"$and": where_clauses}

            # Query
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            # Format results
            formatted = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    # ChromaDB returns distance, convert to similarity
                    # For cosine distance: similarity = 1 - distance
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance

                    if similarity >= similarity_threshold:
                        metadata = (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        )
                        formatted.append(
                            {
                                "content": doc,
                                "score": round(similarity, 4),
                                "source": metadata.get("document_title", "未知来源"),
                                "metadata": {
                                    "document_id": metadata.get("document_id"),
                                    "document_title": metadata.get("document_title"),
                                    "chunk_index": metadata.get("chunk_index"),
                                },
                            }
                        )

            logger.debug(
                f"Search in {collection_name}: {len(formatted)} results above threshold"
            )
            return Result.ok(formatted)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Vector search error: {e}")
            return Result.ok([])  # Graceful degradation

    async def get_parent_chunks(
        self,
        collection_name: str,
        parent_ids: list[str],
    ) -> Result[list[dict[str, Any]]]:
        """
        Fetch parent chunks by their IDs.

        Parent chunks are stored with ``chunk_type == "parent"`` metadata.
        They carry full section context but are **not** used for vector
        retrieval – they are only fetched when a child hit needs to expand
        into its parent's content.

        Args:
            collection_name: ChromaDB collection name
            parent_ids: List of parent chunk IDs (``{doc_id}_{chunk_index}``)

        Returns:
            Result with list of parent chunk dicts
        """
        if not parent_ids:
            return Result.ok([])

        collection = self._get_collection(collection_name)
        if not collection:
            return Result.ok([])

        try:
            results = collection.get(
                ids=parent_ids,
                include=["documents", "metadatas"],
            )

            parents: list[dict[str, Any]] = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"]):
                    metadata = results["metadatas"][i] if results["metadatas"] else {}
                    parents.append(
                        {
                            "content": doc,
                            "metadata": metadata,
                            "id": results["ids"][i],
                        }
                    )

            return Result.ok(parents)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch parent chunks: {e}")
            return Result.ok([])

    async def delete_document_chunks(
        self,
        collection_name: str,
        document_id: str,
    ) -> Result[bool]:
        """
        Delete all chunks for a document.

        Args:
            collection_name: ChromaDB collection name
            document_id: Document UUID

        Returns:
            Result indicating success
        """
        collection = self._get_collection(collection_name)
        if not collection:
            return Result.ok(True)  # Nothing to delete

        # 使用写入锁防止并发操作冲突
        async with self._write_lock:
            try:
                # Get all chunk IDs for this document
                results = collection.get(where={"document_id": document_id}, include=[])

                if results and results["ids"]:
                    collection.delete(ids=results["ids"])
                    logger.info(
                        f"Deleted {len(results['ids'])} chunks for document {document_id}"
                    )

                return Result.ok(True)

            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Failed to delete document chunks: {e}")
                return Result.fail(f"[VECTOR_DELETE_FAILED] {str(e)}")

    async def delete_collection(self, collection_name: str) -> Result[bool]:
        """
        Delete entire collection (when deleting knowledge base).

        Args:
            collection_name: ChromaDB collection name

        Returns:
            Result indicating success
        """
        if not self._ensure_initialized():
            return Result.ok(True)

        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection {collection_name}")
            return Result.ok(True)

        except Exception as e:
            # Collection might not exist
            if "does not exist" in str(e).lower():
                return Result.ok(True)
            logger.error(f"Failed to delete collection: {e}")
            return Result.fail(f"[COLLECTION_DELETE_FAILED] {str(e)}")

    async def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Get statistics for a collection."""
        collection = self._get_collection(collection_name)
        if not collection:
            return {"count": 0, "error": "Collection unavailable"}

        try:
            return {
                "count": collection.count(),
                "name": collection_name,
            }
        except (RuntimeError, ValueError, OSError) as e:
            return {"count": 0, "error": str(e)}


# Singleton instance
_knowledge_vector_store: KnowledgeVectorStore | None = None


def get_knowledge_vector_store() -> KnowledgeVectorStore:
    """Get singleton KnowledgeVectorStore instance."""
    global _knowledge_vector_store
    if _knowledge_vector_store is None:
        _knowledge_vector_store = KnowledgeVectorStore()
    return _knowledge_vector_store


# =============================================================================
# Legacy VectorStore for PPT Presentations (backward compatibility)
# =============================================================================


class VectorStore:
    """
    Legacy vector store for PPT presentations.

    Provides backward-compatible API for ingestion_service.py
    """

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or CHROMADB_PERSIST_DIR
        self.collection_name = "ppt_knowledge"
        self.client: chromadb.PersistentClient | None = None
        self.collection: chromadb.Collection | None = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Ensure ChromaDB client is initialized."""
        if self._initialized and self.client:
            return True

        try:
            os.makedirs(self.persist_dir, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            self._initialized = True
            logger.info(f"VectorStore initialized at {self.persist_dir}")
            return True

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"VectorStore initialization error: {e}")
            return False

    def _get_legacy_collection(self) -> chromadb.Collection | None:
        """Get collection for legacy API, allowing test-time mock injection."""
        if self.collection is not None:
            return self.collection

        if not self._ensure_initialized():
            return None

        return self.collection

    async def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> Result[bool]:
        """Add documents to vector store."""
        collection = self._get_legacy_collection()
        if not collection:
            return Result.fail("[USE_KEYWORD_SEARCH]")

        try:
            collection.add(documents=texts, metadatas=metadatas, ids=ids)
            return Result.ok(True)
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def update_document(
        self,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: dict[str, Any],
    ) -> Result[bool]:
        """Update a document in vector store."""
        collection = self._get_legacy_collection()
        if not collection:
            return Result.fail("[USE_KEYWORD_SEARCH]")

        try:
            collection.update(ids=[doc_id], documents=[text], metadatas=[metadata])
            return Result.ok(True)
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def query(
        self,
        query_text: str,
        presentation_id: str,
        page_number: int | None = None,
        n_results: int = 3,
        **kwargs,
    ) -> Result[list[dict[str, Any]]]:
        """Query vector store for similar documents."""
        collection = self._get_legacy_collection()
        if not collection:
            return Result.fail("[USE_KEYWORD_SEARCH]")

        try:
            where: dict[str, Any] = {"presentation_id": presentation_id}
            if page_number is not None:
                where = {
                    "$and": [
                        {"presentation_id": presentation_id},
                        {"page_number": page_number},
                    ]
                }

            results = collection.query(
                query_texts=[query_text], where=where, n_results=n_results
            )

            formatted = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = (
                        results["metadatas"][0][i] if results["metadatas"] else {}
                    )
                    distance = results["distances"][0][i] if results["distances"] else 0
                    formatted.append(
                        {"content": doc, "metadata": metadata, "distance": distance}
                    )

            return Result.ok(formatted)
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def delete_by_metadata(
        self,
        collection_name: str,
        metadata_filter: dict[str, Any],
    ) -> Result[bool]:
        """Delete documents by metadata filter."""
        collection = self._get_legacy_collection()
        if not collection:
            return Result.fail("[USE_KEYWORD_SEARCH]")

        try:
            results = collection.get(where=metadata_filter)
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
            return Result.ok(True)
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return Result.fail("[USE_KEYWORD_SEARCH]")

    async def delete_presentation(self, presentation_id: str) -> Result[bool]:
        """Delete all documents for a presentation."""
        return await self.delete_by_metadata(
            self.collection_name, {"presentation_id": presentation_id}
        )

    async def search_by_keyword(
        self,
        keyword: str,
        presentation_id: str,
        page_number: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fallback keyword search."""
        collection = self._get_legacy_collection()
        if not collection:
            return []

        try:
            where = {"presentation_id": presentation_id}
            results = collection.get(where=where)

            matches = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"]):
                    if keyword.lower() in doc.lower():
                        metadata = (
                            results["metadatas"][i] if results["metadatas"] else {}
                        )
                        matches.append({"content": doc, "metadata": metadata})

            return matches
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []


# Singleton for legacy VectorStore
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get singleton VectorStore instance (legacy API)."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
