"""
Response Cache Service - Caches API responses to improve performance

Implements Constitution Principles:
- II. Real-time priority - <50ms cache hits
- V. Cost control - Reduce redundant API calls
"""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Simple in-memory response cache

    For production, use Redis or Memcached
    """

    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._cache: dict[str, dict] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = f"{prefix}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, prefix: str, **kwargs) -> object | None:
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
        if datetime.now(UTC) > entry["expires"]:
            del self._cache[key]
            return None

        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def set(self, prefix: str, value: object, ttl: int | None = None, **kwargs) -> None:
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

    def invalidate(self, prefix: str, **kwargs) -> None:
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


def cached(prefix: str, ttl: int | None = None):
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

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try cache first
            cached_value = response_cache.get(prefix, **kwargs)
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            response_cache.set(prefix, result, ttl=ttl, **kwargs)

            return result

        return wrapper

    return decorator
