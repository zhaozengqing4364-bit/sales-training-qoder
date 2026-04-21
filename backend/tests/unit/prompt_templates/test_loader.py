"""
Tests for Prompt Template Loader with Caching

TDD Tests for Task B5: Implement PromptTemplateLoader
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prompt_templates.loader import (
    CachedTemplate,
    PromptTemplateLoader,
    get_loader,
)
from prompt_templates.models import PromptTemplate, PromptType


class TestCachedTemplate:
    """Test the CachedTemplate dataclass"""

    def test_creation(self):
        """Test creating a cached template entry"""
        template = MagicMock(spec=PromptTemplate)
        cached = CachedTemplate(template=template)
        assert cached.template == template
        assert cached.access_count == 0
        assert cached.scenario_overrides == {}

    def test_expiration_check(self):
        """Test TTL expiration logic"""
        template = MagicMock(spec=PromptTemplate)
        cached = CachedTemplate(template=template)

        # Should not be expired immediately
        assert cached.is_expired(300) is False

        # Simulate old cache by manipulating cached_at
        cached.cached_at = datetime.now(UTC).timestamp() - 400
        assert cached.is_expired(300) is True


class TestPromptTemplateLoader:
    """Test the PromptTemplateLoader class"""

    @pytest.fixture
    def loader(self):
        """Create a fresh loader with small cache for testing"""
        return PromptTemplateLoader(cache_size=5, ttl_seconds=60)

    @pytest.fixture
    def sample_template(self):
        """Create a sample template for testing"""
        return PromptTemplate(
            id=uuid4(),
            name="Test Template",
            prompt_type=PromptType.SUMMARY,
            category="test",
            template="Hello {{ name }}",
            variables=["name"],
            is_active=True,
            is_default=True,
            is_system=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def test_initialization(self):
        """Test loader initialization with custom params"""
        loader = PromptTemplateLoader(cache_size=100, ttl_seconds=300)
        assert loader.cache_size == 100
        assert loader.ttl_seconds == 300
        assert loader._cache == {}

    def test_cache_stats_empty(self, loader):
        """Test cache stats for empty cache"""
        stats = loader.get_cache_stats()
        assert stats["total_entries"] == 0
        assert stats["active_entries"] == 0
        assert stats["cache_size_limit"] == 5

    def test_cache_stats_with_entries(self, loader, sample_template):
        """Test cache stats with cached entries"""
        cached = CachedTemplate(template=sample_template)
        loader._cache[sample_template.id] = cached

        stats = loader.get_cache_stats()
        assert stats["total_entries"] == 1
        assert stats["active_entries"] == 1

    @pytest.mark.asyncio
    async def test_get_from_cache_hit(self, loader, sample_template):
        """Test cache hit"""
        cached = CachedTemplate(template=sample_template)
        loader._cache[sample_template.id] = cached

        result = loader._get_from_cache(sample_template.id)
        assert result == sample_template
        assert cached.access_count == 1

    @pytest.mark.asyncio
    async def test_get_from_cache_miss(self, loader):
        """Test cache miss"""
        result = loader._get_from_cache(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_from_cache_expired(self, loader, sample_template):
        """Test that expired entries are removed"""
        cached = CachedTemplate(template=sample_template)
        cached.cached_at = datetime.now(UTC).timestamp() - 100  # Expired
        loader._cache[sample_template.id] = cached

        result = loader._get_from_cache(sample_template.id)
        assert result is None
        assert sample_template.id not in loader._cache

    @pytest.mark.asyncio
    async def test_add_to_cache(self, loader, sample_template):
        """Test adding to cache"""
        await loader._add_to_cache(sample_template)
        assert sample_template.id in loader._cache

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, loader):
        """Test LRU eviction when cache is full"""
        # Fill cache to capacity
        templates = []
        for i in range(5):
            template = PromptTemplate(
                id=uuid4(),
                name=f"Template {i}",
                prompt_type=PromptType.SUMMARY,
                category="test",
                template=f"Content {i}",
                variables=[],
                is_active=True,
                is_default=False,
                is_system=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            templates.append(template)
            await loader._add_to_cache(template)
            await asyncio.sleep(0.01)  # Ensure different timestamps

        # All 5 should be in cache
        assert len(loader._cache) == 5

        # Add one more - should evict oldest
        new_template = PromptTemplate(
            id=uuid4(),
            name="New Template",
            prompt_type=PromptType.SUMMARY,
            category="test",
            template="New content",
            variables=[],
            is_active=True,
            is_default=False,
            is_system=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await loader._add_to_cache(new_template)

        # Should still be at capacity, oldest removed
        assert len(loader._cache) == 5
        assert templates[0].id not in loader._cache  # Oldest evicted
        assert new_template.id in loader._cache

    @pytest.mark.asyncio
    async def test_invalidate_single(self, loader, sample_template):
        """Test invalidating single cache entry"""
        cached = CachedTemplate(template=sample_template)
        loader._cache[sample_template.id] = cached

        await loader.invalidate_cache(sample_template.id)
        assert sample_template.id not in loader._cache

    @pytest.mark.asyncio
    async def test_invalidate_all(self, loader, sample_template):
        """Test invalidating all cache entries"""
        cached = CachedTemplate(template=sample_template)
        loader._cache[sample_template.id] = cached

        await loader.invalidate_cache()
        assert loader._cache == {}

    @pytest.mark.asyncio
    async def test_preload_templates(self, loader):
        """Test preloading multiple templates"""
        # Mock the _load_from_db method
        loader._load_from_db = AsyncMock(return_value=None)

        ids = [uuid4() for _ in range(3)]
        mock_session = MagicMock()

        await loader.preload_templates(ids, mock_session)

        # Should have attempted to load each
        assert loader._load_from_db.call_count == 3

    @pytest.mark.asyncio
    async def test_preload_skips_cached(self, loader, sample_template):
        """Test that preloading skips already cached templates"""
        # Add one to cache
        await loader._add_to_cache(sample_template)

        # Mock _load_from_db
        loader._load_from_db = AsyncMock(return_value=None)

        ids = [sample_template.id, uuid4()]
        mock_session = MagicMock()

        await loader.preload_templates(ids, mock_session)

        # Should only load the uncached one
        assert loader._load_from_db.call_count == 1


class TestGetLoader:
    """Test the get_loader singleton function"""

    def test_singleton(self):
        """Test that get_loader returns same instance"""
        loader1 = get_loader()
        loader2 = get_loader()
        assert loader1 is loader2

    def test_singleton_creates_default(self):
        """Test that singleton creates loader with defaults"""
        loader = get_loader()
        assert loader.cache_size == 100
        assert loader.ttl_seconds == 300
