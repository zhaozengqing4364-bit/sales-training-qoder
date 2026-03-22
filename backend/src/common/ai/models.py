"""
AI Model Configuration SQLAlchemy Models

Unified configuration management for LLM, Embedding, ASR, TTS services.
Supports dynamic configuration without server restart.

References:
- Requirements: R1-R7 (Model Config Management)
- Design: model-config-management/design.md
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)

from common.db.models import Base


class ModelType(str, enum.Enum):
    """AI model types"""

    LLM = "llm"
    EMBEDDING = "embedding"
    ASR = "asr"
    TTS = "tts"


class ModelProvider(str, enum.Enum):
    """AI model providers"""

    OPENAI = "openai"
    AZURE = "azure"
    ALIBABA = "alibaba"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    LOCAL_STREAMING = "local_streaming"  # Paraformer-zh-streaming for real-time ASR


class ModelConfig(Base):
    """
    ModelConfig - AI service configuration entity

    Stores configuration for various AI services (LLM, Embedding, ASR, TTS).
    API keys are encrypted using AES-256 before storage.

    Requirements: R1 (Model Config Data Model)
    """

    __tablename__ = "model_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Display name for admin UI
    name = Column(String(100), nullable=False)

    # Model classification
    model_type = Column(String(20), nullable=False)  # llm/embedding/asr/tts
    provider = Column(String(20), nullable=False)  # openai/azure/alibaba/local

    # Connection settings
    base_url = Column(String(500), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)  # AES-256 encrypted
    model_name = Column(String(100), nullable=False)  # e.g., "gpt-4o"

    # Provider-specific configuration (JSON)
    # For LLM: temperature, max_tokens, etc.
    # For ASR: language, sample_rate, etc.
    extra_config = Column(JSON, default=dict)

    # Status flags
    is_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Validation status
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_status = Column(String(20), nullable=True)  # success/failed

    # Audit
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Ensure unique combination of type + provider + model
        UniqueConstraint(
            "model_type",
            "provider",
            "model_name",
            name="uq_model_config_type_provider_model",
        ),
        # Validate model_type values
        CheckConstraint(
            "model_type IN ('llm', 'embedding', 'asr', 'tts')",
            name="ck_model_config_type",
        ),
        # Validate provider values
        CheckConstraint(
            "provider IN ('openai', 'azure', 'alibaba', 'anthropic', 'local', 'local_streaming')",
            name="ck_model_config_provider",
        ),
        # Validate test status values
        CheckConstraint(
            "last_test_status IS NULL OR last_test_status IN ('success', 'failed')",
            name="ck_model_config_test_status",
        ),
        # Indexes for common queries
        Index("idx_model_configs_type", "model_type"),
        Index("idx_model_configs_type_default", "model_type", "is_default"),
        Index("idx_model_configs_active", "is_active"),
        Index(
            "uq_model_configs_default_per_type",
            "model_type",
            unique=True,
            postgresql_where=text("is_default = true"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ModelConfig {self.name} ({self.model_type}/{self.provider})>"
