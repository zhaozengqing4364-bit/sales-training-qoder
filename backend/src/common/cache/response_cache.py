"""
Response Cache Service - Caches API responses to improve performance

Implements Constitution Principles:
- II. Real-time priority - <50ms cache hits
- V. Cost control - Reduce redundant API calls
"""

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import ParamSpec, TypedDict, TypeVar, cast

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CacheEntry(TypedDict):
    value: object
    expires: datetime


class ResponseCache:
    """
    Simple in-memory response cache

    For production, use Redis or Memcached
    """

    def __init__(self, default_ttl: int = 300) -> None:
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._cache: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, prefix: str, **kwargs: object) -> str:
        """Generate cache key from arguments"""
        key_data = f"{prefix}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, prefix: str, **kwargs: object) -> object | None:
        """
        Get cached value

        Args:
            prefix: Cache key prefix
            **kwargs: Arguments that form the unique key

        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(prefix, **kwargs)

        if key not in self._cache:
            return None

        entry = self._cache[key]

        # Check if expired
        expires = cast(datetime, entry["expires"])
        if datetime.now(UTC) > expires:
            del self._cache[key]
            return None

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def set(
        self, prefix: str, value: object, ttl: int | None = None, **kwargs: object
    ) -> None:
        """
        Set cached value

        Args:
            prefix: Cache key prefix
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            **kwargs: Arguments that form the unique key
        """
        key = self._generate_key(prefix, **kwargs)
        expires = datetime.now(UTC) + timedelta(seconds=ttl or self.default_ttl)

        self._cache[key] = {
            "value": value,
            "expires": expires,
        }

        logger.debug(f"Cache set: {key} (expires: {expires})")

    def invalidate(self, prefix: str, **kwargs: object) -> None:
        """Invalidate cache entry"""
        key = self._generate_key(prefix, **kwargs)
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache invalidated: {key}")

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        logger.debug("Cache cleared")

    def cleanup_expired(self) -> int:
        """Remove expired entries, returns count removed"""
        now = datetime.now(UTC)
        expired_keys = [
            key for key, entry in self._cache.items() if now > entry["expires"]
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)


# Global cache instance
response_cache = ResponseCache()


def cached(
    prefix: str, ttl: int | None = None
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for caching async function results

    Args:
        prefix: Cache key prefix
        ttl: Time-to-live in seconds

    Example:
        @cached("leaderboard", ttl=60)
        async def get_leaderboard(scenario_type: str):
            ...
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Try cache first
            cached_value = response_cache.get(prefix, **kwargs)
            if cached_value is not None:
                return cast(T, cached_value)

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            response_cache.set(prefix, result, ttl=ttl, **kwargs)

            return result

        return wrapper

    return decorator
