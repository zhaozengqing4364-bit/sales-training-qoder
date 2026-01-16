"""
ASR Service - Provider Factory with ConfigManager integration

Refactored to load configuration from ConfigManager with environment variable fallback.
Supports multiple providers: Alibaba Cloud, Local model.

References:
- Requirements: R6.3 (ASR Service loads from ConfigManager)
- Design: model-config-management/design.md
- Constitution Principle II: Real-Time Priority - <200ms streaming latency
- Constitution Principle V: Cost Control - ¥0.00033/s (API) vs free (local)
"""
from typing import TYPE_CHECKING, Any

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.audio.asr_alibaba import AlibabaASRProvider
from common.audio.asr_base import ASRProvider
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ASRService:
    """
    ASR Service with ConfigManager integration.

    Features:
    - Loads configuration from ConfigManager (database)
    - Falls back to environment variables if no database config
    - Supports multiple providers: Alibaba Cloud, Local
    - Automatic provider selection based on configuration

    Requirements: R6.3 (ASR Service loads from ConfigManager)
    """

    def __init__(self, config: ModelConfig | None = None, provider: ASRProvider | None = None):
        """
        Initialize ASR service.

        Args:
            config: Optional ModelConfig. If not provided, uses default from ConfigManager.
            provider: Optional pre-created provider (for testing).
        """
        self._config_manager = get_config_manager()
        self._config = config
        self._effective_config: dict[str, Any] | None = None
        self._provider = provider

        if not self._provider:
            self._init_provider()

    def _init_provider(self) -> None:
        """
        Initialize ASR provider based on configuration.

        Priority:
        1. Explicit config passed to constructor
        2. Default config from ConfigManager (database)
        3. Environment variable fallback
        """
        # Get effective configuration
        if self._config:
            # Use explicit config
            key_result = self._config_manager.get_decrypted_api_key(self._config)
            self._effective_config = {
                "provider": self._config.provider,
                "base_url": self._config.base_url,
                "api_key": key_result.value if key_result.is_success else "",
                "model_name": self._config.model_name,
                "extra_config": self._config.extra_config or {},
            }
        else:
            # Get from ConfigManager (database or env fallback)
            self._effective_config = self._config_manager.get_effective_config(ModelType.ASR)

        if not self._effective_config:
            logger.warning("No ASR configuration available, using local fallback")
            from common.audio.asr_local import LocalASRProvider
            self._provider = LocalASRProvider(device="cuda")
            return

        # Create provider based on configuration
        provider_name = self._effective_config.get("provider", "local")
        api_key = self._effective_config.get("api_key", "")

        if provider_name == ModelProvider.ALIBABA.value or provider_name == "alibaba":
            if api_key:
                logger.info("Using Alibaba Cloud ASR API")
                self._provider = AlibabaASRProvider(
                    api_key=api_key,
                    api_url=self._effective_config.get("base_url", ""),
                    app_key=self._effective_config.get("model_name", ""),
                    extra_config=self._effective_config.get("extra_config", {}),
                )
            else:
                logger.warning("Alibaba ASR API key not configured, using local fallback")
                from common.audio.asr_local import LocalASRProvider
                self._provider = LocalASRProvider(device="cuda")
        elif provider_name == ModelProvider.LOCAL_STREAMING.value or provider_name == "local_streaming":
            # Use streaming Paraformer model for real-time scenarios
            logger.info("Using local streaming ASR (Paraformer-zh-streaming)")
            from common.audio.asr_streaming import LocalStreamingASRProvider
            extra_config = self._effective_config.get("extra_config", {})
            device = extra_config.get("device", "cuda")
            chunk_size_ms = extra_config.get("chunk_size_ms", 600)
            self._provider = LocalStreamingASRProvider(
                device=device,
                chunk_size_ms=chunk_size_ms,
            )
        else:
            # Default to local model (non-streaming)
            logger.info("Using local ASR model")
            from common.audio.asr_local import LocalASRProvider
            device = self._effective_config.get("extra_config", {}).get("device", "cuda")
            self._provider = LocalASRProvider(device=device)

        logger.info(f"ASR service initialized with provider: {provider_name}")

    @property
    def provider(self) -> ASRProvider:
        """Get current ASR provider"""
        return self._provider

    @property
    def provider_name(self) -> str:
        """Get current provider name"""
        if self._effective_config:
            return self._effective_config.get("provider", "local")
        return "local"

    @property
    def is_configured(self) -> bool:
        """Check if ASR service is properly configured"""
        return self._provider is not None

    def reload_config(self, config: ModelConfig | None = None) -> None:
        """
        Reload configuration and reinitialize provider.

        Args:
            config: Optional new config. If not provided, reloads from ConfigManager.
        """
        self._config = config
        self._init_provider()

    async def stream_transcribe(self, audio_stream, sample_rate: int = 16000):
        """
        Stream transcribe audio chunks.

        Args:
            audio_stream: Async iterator of audio bytes
            sample_rate: Audio sample rate

        Yields:
            Result with transcribed text
        """
        async for result in self._provider.stream_transcribe(audio_stream, sample_rate):
            yield result

    async def transcribe_file(self, audio_file: str) -> Result[str]:
        """
        Transcribe an audio file.

        Args:
            audio_file: Path to audio file

        Returns:
            Result with transcribed text
        """
        return await self._provider.transcribe_file(audio_file)

    async def health_check(self) -> Result[bool]:
        """
        Check provider health.

        Returns:
            Result indicating if provider is available
        """
        return await self._provider.health_check()


# Singleton instance (lazy loading)
_asr_service: ASRService | None = None


def get_asr_service() -> ASRService:
    """
    Get singleton ASR service (lazy initialization).

    Returns:
        ASRService instance
    """
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService()
        logger.info("ASR service initialized")
    return _asr_service


def create_asr_service(config: ModelConfig) -> ASRService:
    """
    Create a new ASR service with specific configuration.

    Use this when you need a non-default configuration.

    Args:
        config: ModelConfig to use

    Returns:
        New ASRService instance
    """
    return ASRService(config=config)


async def preload_asr_service() -> None:
    """
    Preload ASR service for faster first request.

    Use in lifespan when PRELOAD_SERVICES=true
    """
    global _asr_service
    if _asr_service is None:
        logger.info("Preloading ASR service...")
        _asr_service = get_asr_service()
        health = await _asr_service.health_check()
        if health.is_success:
            logger.info("ASR service preloaded successfully")
        else:
            logger.warning("ASR service preload failed, will use fallback")


async def reload_asr_service() -> None:
    """
    Reload the singleton ASR service with fresh configuration.

    Call this after ConfigManager cache is refreshed.
    """
    global _asr_service
    if _asr_service is not None:
        _asr_service.reload_config()
        logger.info("ASR service reloaded with fresh configuration")
