"""
BM25 Sparse Retrieval Index — replaces brute-force keyword scan.

Uses rank_bm25 for in-memory BM25 scoring with Chinese character n-gram tokenization.
Indexes are lazily built on first search and auto-invalidated when documents change.

References:
    - Replaces: service.py _search_multiple_by_keywords() full-collection scan
    - Library: rank_bm25 (pure Python, zero external dependencies)
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

import structlog
from rank_bm25 import BM25Okapi

logger = structlog.get_logger(__name__)

# ── Chinese tokenization helpers ──

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
_WORD_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25: CJK bigrams + word-boundary tokens.

    Chinese text uses character bigrams for reasonable BM25 scoring
    without external segmentation libraries. English uses whitespace tokens.
    """
    if not text:
        return []

    tokens: list[str] = []

    # CJK bigrams
    for cjk_match in _CJK_PATTERN.finditer(text):
        segment = cjk_match.group()
        for i in range(len(segment)):
            tokens.append(segment[i])  # unigram for short matches
            if i + 1 < len(segment):
                tokens.append(segment[i] + segment[i + 1])  # bigram

    # Word-boundary tokens (English, numbers)
    for word_match in _WORD_PATTERN.finditer(text.lower()):
        word = word_match.group()
        if len(word) >= 2:
            tokens.append(word)

    return tokens


# ── Per-collection index ──


class _CollectionIndex:
    """BM25 index for a single ChromaDB collection."""

    __slots__ = ("bm25", "ids", "metadatas", "chunk_count_at_build", "built_at")

    def __init__(
        self,
        bm25: BM25Okapi,
        ids: list[str],
        metadatas: list[dict[str, Any]],
        chunk_count: int,
    ) -> None:
        self.bm25 = bm25
        self.ids = ids
        self.metadatas = metadatas
        self.chunk_count_at_build = chunk_count
        self.built_at = time.monotonic()


# ── Manager ──


class BM25IndexManager:
    """Singleton that owns per-collection BM25 indices.

    Thread-safe via a per-collection lock. Indices are lazily built on first
    search and auto-rebuilt when the underlying ChromaDB collection changes
    (detected via chunk count mismatch).
    """

    def __init__(self) -> None:
        self._indices: dict[str, _CollectionIndex] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_lock(self, collection_name: str) -> threading.Lock:
        with self._global_lock:
            if collection_name not in self._locks:
                self._locks[collection_name] = threading.Lock()
            return self._locks[collection_name]

    def build_index(
        self,
        collection_name: str,
        corpus: list[str],
        ids: list[str],
        metadatas: list[dict[str, Any]],
        chunk_count: int,
    ) -> None:
        """Build (or rebuild) the BM25 index for a collection."""
        tokenized_corpus = [_tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        self._indices[collection_name] = _CollectionIndex(
            bm25=bm25,
            ids=ids,
            metadatas=metadatas,
            chunk_count=chunk_count,
        )

        logger.debug(
            "BM25 index built",
            collection=collection_name,
            documents=len(corpus),
            chunk_count=chunk_count,
        )

    def ensure_index(
        self,
        collection_name: str,
        get_all_chunks: Any,  # callable: () -> dict with ids, documents, metadatas
        get_chunk_count: Any,  # callable: () -> int
    ) -> _CollectionIndex:
        """Ensure the index exists and is fresh, building if needed.

        Args:
            collection_name: ChromaDB collection name
            get_all_chunks: Sync callable returning {ids, documents, metadatas}
            get_chunk_count: Sync callable returning collection.count()
        """
        lock = self._get_lock(collection_name)
        with lock:
            current_count = get_chunk_count()
            existing = self._indices.get(collection_name)

            # Index is fresh if chunk count matches
            if existing is not None and existing.chunk_count_at_build == current_count:
                return existing

            # Build or rebuild
            raw = get_all_chunks()
            raw_ids = raw.get("ids", []) or []
            raw_docs = raw.get("documents", []) or []
            raw_metas = raw.get("metadatas", []) or []

            if not raw_ids:
                # Empty collection — create empty index
                self.build_index(collection_name, [], [], [], current_count)
                return self._indices[collection_name]

            # Filter out entries with None documents
            corpus: list[str] = []
            ids: list[str] = []
            metas: list[dict[str, Any]] = []
            for i, doc in enumerate(raw_docs):
                if isinstance(doc, str) and doc.strip():
                    corpus.append(doc)
                    ids.append(raw_ids[i] if i < len(raw_ids) else "")
                    metas.append(
                        raw_metas[i]
                        if i < len(raw_metas) and isinstance(raw_metas[i], dict)
                        else {}
                    )

            self.build_index(collection_name, corpus, ids, metas, current_count)
            return self._indices[collection_name]

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Search the BM25 index.

        Returns:
            List of (chunk_id, bm25_score) tuples sorted by score descending.
        """
        index = self._indices.get(collection_name)
        if index is None or not index.ids:
            return []

        tokenized_query = _tokenize(query)
        if not tokenized_query:
            return []

        scores = index.bm25.get_scores(tokenized_query)

        # Pair (id, score) and sort descending
        results: list[tuple[str, float]] = [
            (index.ids[i], float(scores[i]))
            for i in range(len(scores))
            if scores[i] > 0
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_metadatas(
        self, collection_name: str, chunk_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Get metadata for specific chunk IDs from the cached index."""
        index = self._indices.get(collection_name)
        if index is None:
            return {}

        id_to_meta: dict[str, dict[str, Any]] = {}
        for i, cid in enumerate(index.ids):
            if cid in chunk_ids and i < len(index.metadatas):
                id_to_meta[cid] = index.metadatas[i]
        return id_to_meta

    def invalidate_collection(self, collection_name: str) -> None:
        """Mark the index as stale so it rebuilds on next search."""
        self._indices.pop(collection_name, None)
        logger.debug("BM25 index invalidated", collection=collection_name)

    def is_index_ready(self, collection_name: str) -> bool:
        return collection_name in self._indices


# ── Singleton ──

_bm25_manager: BM25IndexManager | None = None


def get_bm25_index_manager() -> BM25IndexManager:
    """Get the global BM25 index manager singleton."""
    global _bm25_manager
    if _bm25_manager is None:
        _bm25_manager = BM25IndexManager()
    return _bm25_manager
