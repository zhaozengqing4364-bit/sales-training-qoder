"""
Prompt Template Loader with Caching

Requirements: B5 - Implement PromptTemplateLoader

Features:
- In-memory LRU cache for templates
- TTL-based cache expiration
- Cache warming/preloading
- Cache statistics
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from prompt_templates.models import PromptTemplate


@dataclass
class CachedTemplate:
    """Cached template entry with metadata."""

    template: PromptTemplate
    cached_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    scenario_overrides: dict[str, UUID] = field(default_factory=dict)

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.cached_at > ttl_seconds

    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()


class PromptTemplateLoader:
    """Template loader with LRU caching.

    Features:
    - In-memory cache with TTL
    - LRU eviction when cache is full
    - Cache warming/preloading
    - Cache statistics
    """

    def __init__(self, cache_size: int = 100, ttl_seconds: float = 300):
        """Initialize loader.

        Args:
            cache_size: Maximum number of cached templates
            ttl_seconds: Time-to-live for cache entries
        """
        self.cache_size = cache_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[UUID, CachedTemplate] = {}

    async def get_template(
        self,
        template_id: UUID,
        db_session: AsyncSession | None = None,
    ) -> PromptTemplate | None:
        """Get template by ID (from cache or database).

        Args:
            template_id: Template UUID
            db_session: Optional database session

        Returns:
            PromptTemplate or None if not found
        """
        # Try cache first
        cached = self._get_from_cache(template_id)
        if cached:
            return cached

        # Load from database if session provided
        if db_session:
            template = await self._load_from_db(template_id, db_session)
            if template:
                await self._add_to_cache(template)
                return template

        return None

    def _get_from_cache(self, template_id: UUID) -> PromptTemplate | None:
        """Get template from cache if available and not expired.

        Args:
            template_id: Template UUID

        Returns:
            PromptTemplate or None
        """
        cached = self._cache.get(template_id)
        if not cached:
            return None

        # Check expiration
        if cached.is_expired(self.ttl_seconds):
            del self._cache[template_id]
            return None

        # Update access metadata
        cached.touch()
        return cached.template

    async def _load_from_db(
        self,
        template_id: UUID,
        db_session: AsyncSession,
    ) -> PromptTemplate | None:
        """Load template from database.

        Args:
            template_id: Template UUID
            db_session: Database session

        Returns:
            PromptTemplate or None
        """
        from sqlalchemy import select

        from common.db.models import PromptTemplate as PromptTemplateDB

        result = await db_session.execute(
            select(PromptTemplateDB).where(PromptTemplateDB.id == template_id)
        )
        db_template = result.scalar_one_or_none()

        if db_template:
            return PromptTemplate.model_validate(db_template)
        return None

    async def _add_to_cache(self, template: PromptTemplate) -> None:
        """Add template to cache with LRU eviction.

        Args:
            template: Template to cache
        """
        # Evict if cache is full
        if len(self._cache) >= self.cache_size:
            # Find oldest entry (by last_accessed)
            oldest_id = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed,
            )
            del self._cache[oldest_id]

        # Add to cache
        self._cache[template.id] = CachedTemplate(template=template)

    async def preload_templates(
        self,
        template_ids: list[UUID],
        db_session: AsyncSession,
    ) -> int:
        """Preload multiple templates into cache.

        Args:
            template_ids: List of template IDs to preload
            db_session: Database session

        Returns:
            Number of templates loaded
        """
        loaded = 0
        for template_id in template_ids:
            # Skip if already cached
            if template_id in self._cache:
                continue

            template = await self._load_from_db(template_id, db_session)
            if template:
                await self._add_to_cache(template)
                loaded += 1

        return loaded

    async def invalidate_cache(self, template_id: UUID | None = None) -> None:
        """Invalidate cache entries.

        Args:
            template_id: Specific template to invalidate, or None for all
        """
        if template_id:
            self._cache.pop(template_id, None)
        else:
            self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total = len(self._cache)
        expired = sum(1 for c in self._cache.values() if c.is_expired(self.ttl_seconds))

        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
            "cache_size_limit": self.cache_size,
            "ttl_seconds": self.ttl_seconds,
        }


# Singleton instance
_loader: PromptTemplateLoader | None = None


def get_loader() -> PromptTemplateLoader:
    """Get singleton PromptTemplateLoader instance."""
    global _loader
    if _loader is None:
        _loader = PromptTemplateLoader()
    return _loader
