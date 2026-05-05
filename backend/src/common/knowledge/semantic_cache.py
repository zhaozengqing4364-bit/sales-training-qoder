"""
Semantic Search Cache — cache search results by query embedding similarity.

Intercepts search_multiple() after embedding computation but before vector search.
On cache hit (cosine similarity > threshold to a previous query), returns cached results.

Uses the existing CacheManager (Redis with in-memory fallback) for storage.

References:
    - Intercepts: service.py search_multiple() between embedding and vector search
    - Storage: common/cache/redis_cache.py CacheManager
"""

from __future__ import annotations

import math
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _kb_cache_key_prefix(kb_ids: list[str]) -> str:
    """Build Redis key prefix for a set of KB IDs."""
    sorted_ids = ",".join(sorted(kb_ids))
    return f"sem_search:{sorted_ids}"


class SemanticSearchCache:
    """Cache search results keyed by query embedding similarity.

    Thread-safe via Redis (or in-memory dict). Each cache entry stores:
    - query_embedding: the original query vector
    - results: the search results
    - top_k: the original top_k used (only return cache if stored top_k >= requested)
    - created_at: for debugging
    """

    def __init__(
        self,
        similarity_threshold: float = 0.95,
        default_ttl: int = 300,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    async def get(
        self,
        cache_manager: Any,
        kb_ids: list[str],
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]] | None:
        """Check if a semantically similar query was recently cached.

        Returns cached results if found and compatible, else None.
        """
        prefix = _kb_cache_key_prefix(kb_ids)

        # Get the index of cached queries for this KB set
        index_key = f"{prefix}:_index"
        index_data = await cache_manager.get(index_key)
        if not index_data or not isinstance(index_data, dict):
            self._misses += 1
            return None

        # Check each cached query for similarity
        cached_queries: list[dict[str, Any]] = index_data.get("entries", [])
        best_match: dict[str, Any] | None = None
        best_similarity = 0.0

        for entry in cached_queries:
            cached_embedding = entry.get("embedding")
            cached_top_k = entry.get("top_k", 0)
            if not cached_embedding or cached_top_k < top_k:
                continue

            similarity = _cosine_similarity(query_embedding, cached_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        if best_match is None or best_similarity < self.similarity_threshold:
            self._misses += 1
            return None

        # Fetch the actual cached results
        result_key = best_match.get("result_key", "")
        if not result_key:
            self._misses += 1
            return None

        cached = await cache_manager.get(result_key)
        if not isinstance(cached, list) or any(
            not isinstance(item, dict) for item in cached
        ):
            self._misses += 1
            return None

        results = [dict(item) for item in cached]
        self._hits += 1
        logger.debug(
            "Semantic cache hit",
            kb_count=len(kb_ids),
            similarity=round(best_similarity, 4),
            top_k=top_k,
            cached_results=len(results),
        )
        return results

    async def put(
        self,
        cache_manager: Any,
        kb_ids: list[str],
        query_embedding: list[float],
        top_k: int,
        results: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> None:
        """Cache search results for a query."""
        if not results:
            return

        effective_ttl = ttl or self.default_ttl
        prefix = _kb_cache_key_prefix(kb_ids)

        # Store results
        result_hash = str(hash(tuple(round(x, 6) for x in query_embedding[:8])))
        result_key = f"{prefix}:result:{result_hash}"
        await cache_manager.set(result_key, results, ttl=effective_ttl)

        # Update index
        index_key = f"{prefix}:_index"
        index_data = await cache_manager.get(index_key)
        if not isinstance(index_data, dict):
            index_data = {"entries": []}

        entries: list[dict[str, Any]] = index_data.get("entries", [])

        # Add new entry
        entries.append(
            {
                "embedding": query_embedding,
                "top_k": top_k,
                "result_key": result_key,
                "created_at": time.time(),
            }
        )

        # Keep only last 50 entries per KB set to avoid unbounded growth
        if len(entries) > 50:
            entries = entries[-50:]

        index_data["entries"] = entries
        await cache_manager.set(index_key, index_data, ttl=effective_ttl)

    async def invalidate_kb(
        self,
        cache_manager: Any,
        kb_id: str,
    ) -> None:
        """Invalidate all cache entries that include this KB."""
        # Delete patterns that contain this kb_id
        pattern = f"sem_search:*{kb_id}*"
        await cache_manager.delete_pattern(pattern)
        logger.debug("Semantic cache invalidated", kb_id=kb_id)

    async def invalidate_all(self, cache_manager: Any) -> None:
        """Invalidate all semantic cache entries."""
        await cache_manager.delete_pattern("sem_search:*")

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}


# ── Singleton ──

_semantic_cache: SemanticSearchCache | None = None


def get_semantic_search_cache() -> SemanticSearchCache:
    """Get the global semantic search cache singleton."""
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticSearchCache()
    return _semantic_cache
