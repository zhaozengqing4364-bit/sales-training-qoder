"""
AI Model Configuration Manager

Singleton service for managing AI model configurations.
Provides in-memory caching with database persistence.

References:
- Requirements: R4 (Dynamic Model Switching)
- Design: model-config-management/design.md
"""

import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from common.ai.encryption import decrypt_api_key
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.db.session import AsyncSessionLocal
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """
    Singleton service for managing AI model configurations.

    Features:
    - In-memory cache for fast access
    - Database persistence
    - Environment variable fallback
    - Automatic cache refresh on config changes
    """

    _instance: "ConfigManager | None" = None
    _initialized: bool = False

    @staticmethod
    def _api_key_required(model_type: ModelType, provider: str) -> bool:
        """Check whether a provider requires API key decryption."""
        if model_type == ModelType.TTS:
            # Edge/local TTS can run without API key
            return provider not in {ModelProvider.LOCAL.value}
        if model_type == ModelType.ASR:
            return provider not in {
                ModelProvider.LOCAL.value,
                ModelProvider.LOCAL_STREAMING.value,
            }
        return True

    @staticmethod
    def _base_url_required(model_type: ModelType, provider: str) -> bool:
        """Mirror the runtime base_url policy used by remote model providers."""
        if model_type == ModelType.TTS:
            return False
        if model_type == ModelType.ASR and provider in {
            ModelProvider.LOCAL.value,
            ModelProvider.LOCAL_STREAMING.value,
        }:
            return False
        return True

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ConfigManager._initialized:
            return

        # In-memory cache
        self._cache: dict[str, ModelConfig] = {}  # id -> config
        self._defaults: dict[ModelType, ModelConfig] = {}  # type -> default config
        self._by_type: dict[ModelType, list[ModelConfig]] = {}  # type -> all configs

        ConfigManager._initialized = True
        logger.info("ConfigManager initialized")

    async def initialize(self) -> None:
        """
        Load all configurations from database on startup.
        Should be called during application startup.
        """
        await self.refresh_cache()
        logger.info(
            f"ConfigManager loaded {len(self._cache)} configs, "
            f"defaults: {list(self._defaults.keys())}"
        )

    async def refresh_cache(self) -> None:
        """
        Refresh in-memory cache from database.
        Called on startup and after config changes.
        """
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True))
                result = await db.execute(stmt)
                configs = result.scalars().all()

                # Clear and rebuild cache
                self._cache.clear()
                self._defaults.clear()
                self._by_type.clear()

                for config in configs:
                    self._cache[config.id] = config

                    # Group by type
                    model_type = ModelType(config.model_type)
                    if model_type not in self._by_type:
                        self._by_type[model_type] = []
                    self._by_type[model_type].append(config)

                    # Track defaults
                    if config.is_default:
                        if model_type in self._defaults:
                            logger.warning(
                                "Multiple default configs detected for model type",
                                extra={
                                    "model_type": model_type.value,
                                    "kept_default_id": self._defaults[model_type].id,
                                    "overridden_default_id": config.id,
                                },
                            )
                        self._defaults[model_type] = config

                logger.debug(f"Cache refreshed: {len(self._cache)} configs")

        except (SQLAlchemyError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to refresh config cache: {e}")

    def get_config(
        self,
        model_type: ModelType,
        provider: ModelProvider | None = None,
        model_name: str | None = None,
    ) -> ModelConfig | None:
        """
        Get a model configuration.

        Args:
            model_type: Type of model (llm, embedding, asr, tts)
            provider: Optional provider filter
            model_name: Optional model name filter

        Returns:
            ModelConfig if found, None otherwise
        """
        configs = self._by_type.get(model_type, [])

        if not configs:
            return None

        # Filter by provider and model_name if specified
        for config in configs:
            if provider and config.provider != provider.value:
                continue
            if model_name and config.model_name != model_name:
                continue
            return config

        # Return default if no specific match
        return self._defaults.get(model_type)

    def get_default_config(self, model_type: ModelType) -> ModelConfig | None:
        """
        Get the default configuration for a model type.

        Args:
            model_type: Type of model

        Returns:
            Default ModelConfig or None
        """
        return self._defaults.get(model_type)

    def get_all_configs(self, model_type: ModelType | None = None) -> list[ModelConfig]:
        """
        Get all configurations, optionally filtered by type.

        Args:
            model_type: Optional type filter

        Returns:
            List of ModelConfig
        """
        if model_type:
            return self._by_type.get(model_type, [])
        return list(self._cache.values())

    def get_config_by_id(self, config_id: str) -> ModelConfig | None:
        """
        Get configuration by ID.

        Args:
            config_id: Configuration UUID

        Returns:
            ModelConfig or None
        """
        return self._cache.get(config_id)

    def get_decrypted_api_key(self, config: ModelConfig) -> Result[str]:
        """
        Get decrypted API key for a configuration.

        Args:
            config: ModelConfig instance

        Returns:
            Result with decrypted key or error
        """
        return decrypt_api_key(config.api_key_encrypted)

    def get_env_fallback(self, model_type: ModelType) -> dict[str, Any] | None:
        """
        Get configuration from environment variables as fallback.

        Args:
            model_type: Type of model

        Returns:
            Dict with config values or None
        """
        if model_type == ModelType.LLM:
            # Support both LLM_API_KEY (new) and OPENAI_API_KEY (legacy) for backward compatibility
            api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if api_key:
                return {
                    "provider": os.getenv("LLM_PROVIDER", "openai"),
                    "base_url": os.getenv("LLM_BASE_URL")
                    or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    "api_key": api_key,
                    "model_name": os.getenv("LLM_MODEL")
                    or os.getenv("OPENAI_MODEL", "gpt-4o"),
                    "extra_config": {
                        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
                        "timeout": float(os.getenv("LLM_TIMEOUT", "10.0")),
                    },
                }

        elif model_type == ModelType.EMBEDDING:
            embedding_api_key = os.getenv("EMBEDDING_API_KEY")
            dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
            legacy_openai_api_key = os.getenv("OPENAI_API_KEY")

            if embedding_api_key or dashscope_api_key:
                return {
                    "provider": os.getenv(
                        "EMBEDDING_PROVIDER", ModelProvider.OPENAI.value
                    ),
                    "base_url": os.getenv(
                        "EMBEDDING_BASE_URL",
                        "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    ),
                    "api_key": embedding_api_key or dashscope_api_key,
                    "model_name": os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
                    "extra_config": {},
                }

            if legacy_openai_api_key:
                return {
                    "provider": os.getenv(
                        "EMBEDDING_PROVIDER", ModelProvider.OPENAI.value
                    ),
                    "base_url": os.getenv("EMBEDDING_BASE_URL")
                    or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                    "api_key": legacy_openai_api_key,
                    "model_name": os.getenv(
                        "EMBEDDING_MODEL", "text-embedding-3-small"
                    ),
                    "extra_config": {},
                }

        elif model_type == ModelType.ASR:
            # Check if local_streaming is explicitly requested
            asr_provider = os.getenv("ASR_PROVIDER", "").lower()
            if asr_provider == "local_streaming":
                # Use local streaming Paraformer model
                return {
                    "provider": "local_streaming",
                    "base_url": "",
                    "api_key": "",
                    "model_name": "paraformer-zh-streaming",
                    "extra_config": {
                        "device": os.getenv("ASR_DEVICE", "cpu"),
                        "chunk_size_ms": int(os.getenv("ASR_CHUNK_SIZE_MS", "600")),
                    },
                }
            # 使用实际的环境变量名 ASR_API_KEY (qwen3-asr-flash)
            api_key = os.getenv("ASR_API_KEY")
            if api_key:
                return {
                    "provider": "alibaba",
                    "base_url": os.getenv(
                        "ASR_API_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
                    ),
                    "api_key": api_key,
                    "model_name": os.getenv("ASR_MODEL", "qwen3-asr-flash-realtime"),
                    "extra_config": {},
                }
            # Default to local_streaming when no API key is configured
            return {
                "provider": "local_streaming",
                "base_url": "",
                "api_key": "",
                "model_name": "paraformer-zh-streaming",
                "extra_config": {
                    "device": os.getenv("ASR_DEVICE", "cpu"),
                    "chunk_size_ms": int(os.getenv("ASR_CHUNK_SIZE_MS", "600")),
                },
            }

        elif model_type == ModelType.TTS:
            # Edge TTS doesn't need API key
            return {
                "provider": "local",
                "base_url": "",
                "api_key": "",
                "model_name": os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural"),
                "extra_config": {},
            }

        return None

    def describe_runtime_policy(
        self,
        model_type: ModelType,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Describe provider/base_url policy for the effective runtime config."""
        effective = (
            config if config is not None else self.get_effective_config(model_type)
        )
        effective = effective or {}

        provider = str(effective.get("provider") or "").strip().lower()
        model_name = str(effective.get("model_name") or "").strip()
        base_url = str(effective.get("base_url") or "").strip()
        base_url_required = self._base_url_required(model_type, provider)
        if base_url:
            base_url_status = "configured"
        elif base_url_required:
            base_url_status = "missing"
        else:
            base_url_status = "not_required"

        return {
            "provider": provider,
            "model_name": model_name,
            "base_url": base_url,
            "base_url_required": base_url_required,
            "base_url_status": base_url_status,
            "config_present": bool(effective),
        }

    def get_effective_config(self, model_type: ModelType) -> dict[str, Any] | None:
        """
        Get effective configuration, with database taking precedence over env vars.

        Args:
            model_type: Type of model

        Returns:
            Dict with config values or None
        """
        # Try database config first
        db_config = self.get_default_config(model_type)
        if db_config:
            provider = db_config.provider
            if not self._api_key_required(model_type, provider):
                return {
                    "provider": provider,
                    "base_url": db_config.base_url,
                    "api_key": "",
                    "model_name": db_config.model_name,
                    "extra_config": db_config.extra_config or {},
                }

            if not db_config.api_key_encrypted:
                logger.warning(
                    f"Database config missing API key for {model_type.value}/{provider}, "
                    f"falling back to environment variables"
                )
            else:
                key_result = self.get_decrypted_api_key(db_config)
                # If decryption succeeds and we have a valid key, use database config
                if key_result.is_success and key_result.value:
                    return {
                        "provider": provider,
                        "base_url": db_config.base_url,
                        "api_key": key_result.value,
                        "model_name": db_config.model_name,
                        "extra_config": db_config.extra_config or {},
                    }

                # Decryption failed, log warning and fall back to env vars
                logger.warning(
                    f"Database config decryption failed for {model_type.value}, "
                    f"falling back to environment variables"
                )

        # Fallback to environment variables
        return self.get_env_fallback(model_type)


# Singleton instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """
    Get singleton ConfigManager instance.

    Returns:
        ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


async def initialize_config_manager() -> None:
    """
    Initialize ConfigManager on application startup.
    Should be called in FastAPI lifespan.
    """
    manager = get_config_manager()
    await manager.initialize()
