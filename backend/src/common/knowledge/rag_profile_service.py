"""
RAG Profile Resolution Service

Resolves the effective RAG profile for a knowledge base:
1. If KB has rag_profile_id → use that profile
2. Otherwise → use system default profile
3. If neither exists → return None (hardcoded defaults apply)

References:
- Plan: unified RAG configuration management
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResolvedRagProfile:
    """Resolved RAG profile settings ready for consumption."""

    chunking_strategy: str = "element_boundary"
    chunk_size: int = 500
    chunk_overlap: int = 50
    semantic_cache_enabled: bool = True
    semantic_cache_similarity_threshold: float = 0.95
    semantic_cache_ttl_seconds: int = 300
    cross_encoder_backend: str | None = None
    cross_encoder_model: str | None = None
    cross_encoder_device: str | None = None
    cross_encoder_api_key: str | None = None


async def resolve_rag_profile(
    db: AsyncSession,
    kb: Any,
) -> ResolvedRagProfile | None:
    """Resolve the effective RAG profile for a knowledge base.

    Args:
        db: Database session.
        kb: KnowledgeBase ORM object (must have rag_profile_id attribute).

    Returns:
        ResolvedRagProfile or None if no profile found.
    """
    from common.knowledge.rag_profile_models import RagProfile

    profile_id = getattr(kb, "rag_profile_id", None)

    # Try explicit profile first
    if profile_id:
        result = await db.execute(
            select(RagProfile).where(RagProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            return _profile_to_resolved(profile)

    # Fall back to system default
    result = await db.execute(
        select(RagProfile).where(RagProfile.is_system_default == 1)
    )
    profile = result.scalar_one_or_none()
    if profile:
        return _profile_to_resolved(profile)

    return None


async def resolve_rag_profile_for_search(
    db: AsyncSession,
    kb_contexts: dict[str, Any],
) -> ResolvedRagProfile | None:
    """Resolve a single RAG profile across multiple KB contexts.

    When searching across multiple KBs, use the first non-null profile found.
    If all agree, great. If they disagree, we use the first one found.

    Args:
        db: Database session.
        kb_contexts: Dict mapping kb_id to context objects with rag_profile_id.

    Returns:
        Merged ResolvedRagProfile or None.
    """
    from common.knowledge.rag_profile_models import RagProfile

    seen_profile_ids: set[str] = set()
    profiles: list[Any] = []

    # Collect distinct profile IDs
    for kb_id, ctx in kb_contexts.items():
        pid = getattr(ctx, "rag_profile_id", None) if hasattr(ctx, "rag_profile_id") else None
        if pid and pid not in seen_profile_ids:
            seen_profile_ids.add(pid)

    # Also include system default
    if not seen_profile_ids:
        result = await db.execute(
            select(RagProfile).where(RagProfile.is_system_default == 1)
        )
        default_profile = result.scalar_one_or_none()
        if default_profile:
            return _profile_to_resolved(default_profile)
        return None

    # Batch fetch all referenced profiles
    result = await db.execute(
        select(RagProfile).where(RagProfile.id.in_(seen_profile_ids))
    )
    profiles = result.scalars().all()

    if not profiles:
        return None

    # Use first profile (could merge later)
    return _profile_to_resolved(profiles[0])


def _profile_to_resolved(profile: Any) -> ResolvedRagProfile:
    """Convert an ORM RagProfile to a ResolvedRagProfile dataclass."""
    return ResolvedRagProfile(
        chunking_strategy=profile.chunking_strategy,
        chunk_size=profile.chunk_size,
        chunk_overlap=profile.chunk_overlap,
        semantic_cache_enabled=bool(profile.semantic_cache_enabled),
        semantic_cache_similarity_threshold=(
            profile.semantic_cache_similarity_threshold
        ),
        semantic_cache_ttl_seconds=profile.semantic_cache_ttl_seconds,
        cross_encoder_backend=profile.cross_encoder_backend,
        cross_encoder_model=profile.cross_encoder_model,
        cross_encoder_device=profile.cross_encoder_device,
        cross_encoder_api_key=profile.cross_encoder_api_key,
    )
