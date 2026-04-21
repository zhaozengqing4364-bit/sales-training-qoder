"""Tests for Redis cache memory fallback behavior."""

from __future__ import annotations

import pytest

from common.cache.redis_cache import CacheManager


@pytest.mark.asyncio
async def test_memory_fallback_evicts_lru_entries_over_limit() -> None:
    cache = CacheManager(default_ttl=60, memory_max_entries=2)
    cache._redis = None

    await cache.set("a", "A")
    await cache.set("b", "B")
    assert await cache.get("a") == "A"  # a becomes most recently used
    await cache.set("c", "C")

    assert await cache.get("a") == "A"
    assert await cache.get("b") is None
    assert await cache.get("c") == "C"


@pytest.mark.asyncio
async def test_memory_fallback_delete_pattern_uses_glob_semantics() -> None:
    cache = CacheManager(default_ttl=60, memory_max_entries=10)
    cache._redis = None

    await cache.set("sem_search:kb-1:query", 1)
    await cache.set("sem_search:kb-2:query", 2)
    await cache.set("other:kb-1:query", 3)

    await cache.delete_pattern("sem_search:kb-1:*")

    assert await cache.get("sem_search:kb-1:query") is None
    assert await cache.get("sem_search:kb-2:query") == 2
    assert await cache.get("other:kb-1:query") == 3
