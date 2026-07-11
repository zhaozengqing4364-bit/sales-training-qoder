"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from common.db.model_registry.base import Base


class KnowledgeConfigVersion(Base):
    """Versioned control-plane snapshot for the knowledge answering engine."""

    __tablename__ = "knowledge_config_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version_name = Column(String(120), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    notes = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_knowledge_config_version_status",
        ),
        Index("idx_knowledge_config_versions_status", "status"),
    )


class KnowledgeQueryProfile(Base):
    """Configures query rewrite behavior for one knowledge intent/profile."""

    __tablename__ = "knowledge_query_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rewrite_strategy = Column(String(50), nullable=False)
    max_rewrite_queries = Column(Integer, nullable=False, default=1)
    stop_after_first_success = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_query_profile_version_key",
        ),
        Index("idx_knowledge_query_profiles_profile_key", "profile_key"),
    )


class KnowledgeIntentRule(Base):
    """Maps user-query patterns to knowledge query profiles."""

    __tablename__ = "knowledge_intent_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent_key = Column(String(100), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    match_type = Column(String(50), nullable=False)
    pattern = Column(Text, nullable=False)
    profile_key = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_knowledge_intent_rules_priority", "priority"),
        Index("idx_knowledge_intent_rules_intent_key", "intent_key"),
    )


class KnowledgeEntityAlias(Base):
    """Deterministic alias mapping used before retrieval planning."""

    __tablename__ = "knowledge_entity_aliases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_entity = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_knowledge_entity_alias_confidence",
        ),
        UniqueConstraint(
            "config_version_id", "alias", name="uq_knowledge_entity_alias_version_alias"
        ),
        Index("idx_knowledge_entity_aliases_canonical_entity", "canonical_entity"),
    )


class KnowledgeRankingProfile(Base):
    """Business-owned reranking weights for retrieved candidates."""

    __tablename__ = "knowledge_ranking_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    title_exact_boost = Column(Float, nullable=False, default=0.0)
    entity_match_boost = Column(Float, nullable=False, default=0.0)
    doc_type_weights_json = Column(JSON, nullable=False, default=dict)
    section_weights_json = Column(JSON, nullable=False, default=dict)
    min_pass_score = Column(Float, nullable=False, default=0.0)
    min_pass_score_keyword = Column(Float, nullable=False, default=0.0)
    # Unified scoring weights (elevated from hardcoded values in _rerank_results)
    base_weight = Column(Float, nullable=False, default=0.50)
    coverage_weight = Column(Float, nullable=False, default=0.20)
    phrase_bonus = Column(Float, nullable=False, default=0.15)
    title_bonus_max = Column(Float, nullable=False, default=0.10)
    ratio_bonus_max = Column(Float, nullable=False, default=0.05)
    cross_encoder_weight = Column(Float, nullable=False, default=0.0)
    diversity_penalty = Column(Float, nullable=False, default=0.12)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_ranking_profile_version_key",
        ),
        Index("idx_knowledge_ranking_profiles_profile_key", "profile_key"),
    )


class KnowledgeChunkingPreset(Base):
    """Named chunking configuration that belongs to a config version."""

    __tablename__ = "knowledge_chunking_presets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    chunking_strategy = Column(String(50), nullable=False, default="element_boundary")
    chunk_size = Column(Integer, nullable=False, default=500)
    chunk_overlap = Column(Integer, nullable=False, default=50)
    is_default = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id", "profile_key", name="uq_chunking_preset_version_key"
        ),
        Index("idx_knowledge_chunking_presets_profile_key", "profile_key"),
    )


class KnowledgeAnswerabilityProfile(Base):
    """Thresholds for deciding whether evidence is sufficient to answer."""

    __tablename__ = "knowledge_answerability_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_key = Column(String(100), nullable=False)
    required_slots_json = Column(JSON, nullable=False, default=list)
    optional_slots_json = Column(JSON, nullable=False, default=list)
    sufficient_threshold = Column(Float, nullable=False, default=1.0)
    partial_threshold = Column(Float, nullable=False, default=0.0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_answerability_profile_version_key",
        ),
        Index("idx_knowledge_answerability_profiles_profile_key", "profile_key"),
    )


class KnowledgeAnswerRun(Base):
    """Top-level audit row for one knowledge-answering attempt."""

    __tablename__ = "knowledge_answer_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_version_id = Column(
        String(36),
        ForeignKey("knowledge_config_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entrypoint = Column(String(100), nullable=False)
    query_text = Column(Text, nullable=False)
    answerability = Column(String(20), nullable=False, default="insufficient")
    final_status = Column(String(20), nullable=False, default="completed")
    blocked_reason = Column(String(100), nullable=True)
    citations_json = Column(JSON, nullable=False, default=list)
    retrieval_summary_json = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "answerability IN ('sufficient', 'partial', 'insufficient', 'blocked')",
            name="ck_knowledge_answer_run_answerability",
        ),
        CheckConstraint(
            "final_status IN ('completed', 'blocked', 'failed')",
            name="ck_knowledge_answer_run_final_status",
        ),
        Index("idx_knowledge_answer_runs_session_created", "session_id", "created_at"),
    )


class KnowledgeAnswerRunStep(Base):
    """Step-level payload audit for one knowledge-answer run."""

    __tablename__ = "knowledge_answer_run_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    answer_run_id = Column(
        String(36),
        ForeignKey("knowledge_answer_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    input_payload = Column(JSON, nullable=False, default=dict)
    output_payload = Column(JSON, nullable=False, default=dict)
    duration_ms = Column(Integer, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed', 'skipped')",
            name="ck_knowledge_answer_run_step_status",
        ),
        UniqueConstraint(
            "answer_run_id", "step_order", name="uq_knowledge_answer_run_steps_order"
        ),
        Index("idx_knowledge_answer_run_steps_run", "answer_run_id"),
    )


__all__ = [
    "KnowledgeConfigVersion",
    "KnowledgeQueryProfile",
    "KnowledgeIntentRule",
    "KnowledgeEntityAlias",
    "KnowledgeRankingProfile",
    "KnowledgeChunkingPreset",
    "KnowledgeAnswerabilityProfile",
    "KnowledgeAnswerRun",
    "KnowledgeAnswerRunStep",
]
