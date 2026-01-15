"""
AI Services Module

Unified AI service layer with ConfigManager integration.
Provides LLM, Embedding, ASR, and TTS services with dynamic configuration.

Usage:
    from common.ai import get_llm_service, get_embedding_service
    
    llm = get_llm_service()
    result = await llm.generate("Hello", session_id="123")
    
    embedding = get_embedding_service()
    result = await embedding.embed("Hello world")
"""

from common.ai.config_manager import (
    ConfigManager,
    get_config_manager,
    initialize_config_manager,
)
from common.ai.embedding_service import (
    EmbeddingService,
    create_embedding_service,
    get_embedding_service,
    reload_embedding_service,
)
from common.ai.encryption import (
    decrypt_api_key,
    encrypt_api_key,
    get_encryption,
    mask_api_key,
)
from common.ai.llm_service import (
    LLMService,
    create_llm_service,
    get_llm_service,
    reload_llm_service,
)
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.ai.schemas import (
    CreateModelConfigRequest,
    ModelConfigListResponse,
    ModelConfigResponse,
    TestConfigResponse,
    UpdateModelConfigRequest,
)

__all__ = [
    # Config Manager
    "ConfigManager",
    "get_config_manager",
    "initialize_config_manager",
    # LLM Service
    "LLMService",
    "get_llm_service",
    "create_llm_service",
    "reload_llm_service",
    # Embedding Service
    "EmbeddingService",
    "get_embedding_service",
    "create_embedding_service",
    "reload_embedding_service",
    # Encryption
    "encrypt_api_key",
    "decrypt_api_key",
    "mask_api_key",
    "get_encryption",
    # Models
    "ModelConfig",
    "ModelType",
    "ModelProvider",
    # Schemas
    "CreateModelConfigRequest",
    "UpdateModelConfigRequest",
    "ModelConfigResponse",
    "ModelConfigListResponse",
    "TestConfigResponse",
]
