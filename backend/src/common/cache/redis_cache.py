"""
Redis Cache - High-performance caching layer

Implements caching for:
- Agent/Persona configurations
- User sessions
- API responses
- Prompt templates

Requirements: P2-FIXES.md Issue #24
"""

import fnmatch
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any

from common.config import settings
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """
    Cache manager with Redis backend

    Features:
    - Automatic serialization/deserialization
    - TTL support
    - Pattern-based cache invalidation
    - Fallback to memory cache if Redis unavailable

    Usage:
        cache = CacheManager()
        await cache.connect()

        # Set cache
        await cache.set("user:123", user_data, ttl=3600)

        # Get cache
        user_data = await cache.get("user:123")

        # Delete cache
        await cache.delete("user:123")
    """

    def __init__(self, default_ttl: int = 3600, memory_max_entries: int | None = None):
        self.default_ttl = default_ttl
        self._redis: Any | None = None
        self._memory_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._use_memory_fallback = True
        self._memory_max_entries = (
            memory_max_entries or settings.CACHE_MEMORY_MAX_ENTRIES
        )

    async def connect(self, redis_url: str = "redis://localhost:6379"):
        """Connect to Redis"""
        try:
            import redis.asyncio as redis

            self._redis = await redis.from_url(
                redis_url, encoding="utf-8", decode_responses=True
            )
            logger.info("Redis cache connected")
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning(f"Redis connection failed, using memory fallback: {e}")
            self._redis = None

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        try:
            if self._redis:
                value = await self._redis.get(key)
                if value:
                    return json.loads(value)
            elif self._use_memory_fallback:
                entry = self._memory_cache.get(key)
                if entry and entry["expires"] > time.time():
                    self._memory_cache.move_to_end(key)
                    return entry["value"]
                elif entry:
                    del self._memory_cache[key]
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Cache get error: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None):
        """Set value in cache"""
        try:
            if self._redis:
                await self._redis.set(
                    key, json.dumps(value, default=str), ex=ttl or self.default_ttl
                )
            elif self._use_memory_fallback:
                self._memory_cache[key] = {
                    "value": value,
                    "expires": time.time() + (ttl or self.default_ttl),
                }
                self._memory_cache.move_to_end(key)
                self._enforce_memory_limit()
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Cache set error: {e}")

    async def delete(self, key: str):
        """Delete key from cache"""
        try:
            if self._redis:
                await self._redis.delete(key)
            elif self._use_memory_fallback:
                self._memory_cache.pop(key, None)
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Cache delete error: {e}")

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        try:
            if self._redis:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
            elif self._use_memory_fallback:
                keys_to_delete = [
                    k for k in self._memory_cache.keys() if fnmatch.fnmatch(k, pattern)
                ]
                for k in keys_to_delete:
                    del self._memory_cache[k]
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Cache delete_pattern error: {e}")

    async def clear(self):
        """Clear all cache"""
        try:
            if self._redis:
                await self._redis.flushdb()
            elif self._use_memory_fallback:
                self._memory_cache.clear()
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Cache clear error: {e}")

    def _enforce_memory_limit(self) -> None:
        """Evict least-recently-used memory fallback entries above the cap."""
        while len(self._memory_cache) > self._memory_max_entries:
            self._memory_cache.popitem(last=False)


# Global cache instance
_cache: CacheManager | None = None


def get_cache() -> CacheManager:
    """Get global cache instance"""
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


async def init_cache(redis_url: str = "redis://localhost:6379"):
    """Initialize global cache"""
    cache = get_cache()
    await cache.connect(redis_url)


def cached(key_prefix: str, ttl: int = 3600, key_builder: Callable | None = None):
    """
    Cache decorator for async functions

    Usage:
        @cached(key_prefix="agent", ttl=3600)
        async def get_agent(agent_id: str):
            return await db.get_agent(agent_id)
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key: prefix:func_name:args_hash
                args_str = ":".join(
                    str(a) for a in args if isinstance(a, (str, int, float))
                )
                cache_key = f"{key_prefix}:{func.__name__}:{args_str}"

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss, stored: {cache_key}")

            return result

        return wrapper

    return decorator


def cache_invalidate(key_prefix: str):
    """
    Decorator to invalidate cache after function execution

    Usage:
        @cache_invalidate(key_prefix="agent")
        async def update_agent(agent_id: str, data: dict):
            await db.update_agent(agent_id, data)
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Invalidate cache
            cache = get_cache()
            await cache.delete_pattern(f"{key_prefix}:*")
            logger.debug(f"Cache invalidated: {key_prefix}:*")

            return result

        return wrapper

    return decorator
