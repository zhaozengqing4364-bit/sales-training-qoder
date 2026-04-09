"""
RAG Profile SQLAlchemy Models

Named, reusable configuration bundles for RAG pipelines.
Each profile contains chunking, semantic cache, and cross-encoder settings.
Knowledge bases reference a single profile (or fall back to system default).

References:
- Plan: unified RAG configuration management
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from common.db.models import Base


class RagProfile(Base):
    """Reusable RAG configuration profile."""

    __tablename__ = "rag_profiles"

    id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)

    # Only one profile can be the system default
    is_system_default = Column(Integer, default=0, nullable=False)

    # ── Chunking configuration ──
    chunking_strategy = Column(
        String(50), nullable=False, default="element_boundary"
    )
    chunk_size = Column(Integer, nullable=False, default=500)
    chunk_overlap = Column(Integer, nullable=False, default=50)

    # ── Semantic cache configuration ──
    semantic_cache_enabled = Column(Integer, nullable=False, default=1)
    semantic_cache_similarity_threshold = Column(
        Float, nullable=False, default=0.95
    )
    semantic_cache_ttl_seconds = Column(
        Integer, nullable=False, default=300
    )

    # ── Cross-encoder reranker configuration ──
    cross_encoder_backend = Column(String(20), nullable=True)
    cross_encoder_model = Column(String(200), nullable=True)
    cross_encoder_device = Column(String(20), nullable=True)
    cross_encoder_api_key = Column(Text, nullable=True)

    # ── Audit ──
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_rag_profiles_name", "name"),
        Index(
            "idx_rag_profiles_system_default",
            "is_system_default",
        ),
    )

    # Relationships
    knowledge_bases = relationship(
        "KnowledgeBase",
        back_populates="rag_profile",
        passive_deletes=True,
    )
