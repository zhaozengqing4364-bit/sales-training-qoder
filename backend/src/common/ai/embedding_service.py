"""
Embedding Service - Unified embedding interface with ConfigManager integration

Provides a consistent interface for generating text embeddings across different providers.
Supports OpenAI, Azure OpenAI, and local models.

References:
- Requirements: R6.2 (Embedding Service Abstraction)
- Design: model-config-management/design.md
"""
from typing import Any

import httpx

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Embedding service with ConfigManager integration.

    Features:
    - Loads configuration from ConfigManager (database)
    - Falls back to environment variables if no database config
    - Supports multiple providers: OpenAI, Azure
    - Batch embedding support for efficiency

    Requirements: R6.2 (Embedding Service with same abstraction pattern)
    """

    def __init__(self, config: ModelConfig | None = None):
        """
        Initialize Embedding service.

        Args:
            config: Optional ModelConfig. If not provided, uses default from ConfigManager.
        """
        self._config_manager = get_config_manager()
        self._config = config
        self._effective_config: dict[str, Any] | None = None
        self._http_client: httpx.AsyncClient | None = None

        # Initialize configuration
        self._init_config()

    def _init_config(self) -> None:
        """
        Initialize configuration from ConfigManager or environment.

        Priority:
        1. Explicit config passed to constructor
        2. Default config from ConfigManager (database)
        3. Environment variable fallback
        """
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
            self._effective_config = self._config_manager.get_effective_config(ModelType.EMBEDDING)

        if self._effective_config:
            provider = self._effective_config.get("provider", "openai")
            model_name = self._effective_config.get("model_name", "text-embedding-3-small")
            logger.info(f"Embedding service initialized with provider: {provider}, model: {model_name}")
        else:
            logger.warning("No Embedding configuration available")

    @property
    def is_configured(self) -> bool:
        """Check if Embedding service is properly configured"""
        return self._effective_config is not None and bool(self._effective_config.get("api_key"))

    @property
    def provider(self) -> str:
        """Get current provider name"""
        if self._effective_config:
            return self._effective_config.get("provider", "unknown")
        return "unknown"

    @property
    def model_name(self) -> str:
        """Get current model name"""
        if self._effective_config:
            return self._effective_config.get("model_name", "unknown")
        return "unknown"

    @property
    def dimensions(self) -> int | None:
        """Get embedding dimensions if configured"""
        if self._effective_config:
            return self._effective_config.get("extra_config", {}).get("dimensions")
        return None

    def reload_config(self, config: ModelConfig | None = None) -> None:
        """
        Reload configuration and reinitialize.

        Args:
            config: Optional new config. If not provided, reloads from ConfigManager.
        """
        self._config = config
        self._init_config()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def embed(self, text: str) -> Result[list[float]]:
        """
        Generate embedding vector for a single text.

        Args:
            text: Text to embed

        Returns:
            Result with embedding vector or error
        """
        result = await self.embed_batch([text])
        if result.is_success and result.value:
            return Result.ok(result.value[0])
        return Result.fail(result.error if hasattr(result, 'error') else "[EMBEDDING_FAILED]")

    async def embed_batch(self, texts: list[str]) -> Result[list[list[float]]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            Result with list of embedding vectors or error
        """
        if not self.is_configured:
            logger.error("Embedding service not configured")
            return Result.fail("[EMBEDDING_NOT_CONFIGURED]")

        if not texts:
            return Result.ok([])

        provider = self._effective_config.get("provider", "openai")

        if provider == ModelProvider.AZURE.value or provider == "azure":
            return await self._embed_azure(texts)
        else:
            # Default to OpenAI-compatible API
            return await self._embed_openai(texts)

    async def _embed_openai(self, texts: list[str]) -> Result[list[list[float]]]:
        """Generate embeddings using OpenAI-compatible API"""
        try:
            base_url = self._effective_config.get("base_url", "https://api.openai.com/v1")
            api_key = self._effective_config.get("api_key", "")
            model_name = self._effective_config.get("model_name", "text-embedding-3-small")
            extra_config = self._effective_config.get("extra_config", {})

            # Build request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model_name,
                "input": texts,
            }

            # Add dimensions if specified (for text-embedding-3 models)
            if "dimensions" in extra_config:
                payload["dimensions"] = extra_config["dimensions"]

            # Make request
            client = await self._get_client()
            response = await client.post(
                f"{base_url.rstrip('/')}/embeddings",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_msg = f"OpenAI API error: {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                return Result.fail(f"[EMBEDDING_API_ERROR] {error_msg}")

            data = response.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]

            logger.debug(f"Generated {len(embeddings)} embeddings, dim={len(embeddings[0]) if embeddings else 0}")
            return Result.ok(embeddings)

        except httpx.TimeoutException:
            logger.error("Embedding request timeout")
            return Result.fail("[EMBEDDING_TIMEOUT]")
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}")
            return Result.fail(f"[EMBEDDING_ERROR] {str(e)}")

    async def _embed_azure(self, texts: list[str]) -> Result[list[list[float]]]:
        """Generate embeddings using Azure OpenAI API"""
        try:
            base_url = self._effective_config.get("base_url", "")
            api_key = self._effective_config.get("api_key", "")
            model_name = self._effective_config.get("model_name", "text-embedding-ada-002")
            extra_config = self._effective_config.get("extra_config", {})

            api_version = extra_config.get("api_version", "2024-02-15-preview")
            deployment_name = extra_config.get("deployment_name", model_name)

            # Build Azure endpoint
            endpoint = f"{base_url.rstrip('/')}/openai/deployments/{deployment_name}/embeddings?api-version={api_version}"

            headers = {
                "api-key": api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "input": texts,
            }

            # Add dimensions if specified
            if "dimensions" in extra_config:
                payload["dimensions"] = extra_config["dimensions"]

            # Make request
            client = await self._get_client()
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_msg = f"Azure API error: {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                return Result.fail(f"[EMBEDDING_API_ERROR] {error_msg}")

            data = response.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]

            logger.debug(f"Generated {len(embeddings)} embeddings via Azure")
            return Result.ok(embeddings)

        except httpx.TimeoutException:
            logger.error("Azure embedding request timeout")
            return Result.fail("[EMBEDDING_TIMEOUT]")
        except Exception as e:
            logger.error(f"Azure embedding error: {str(e)}")
            return Result.fail(f"[EMBEDDING_ERROR] {str(e)}")

    async def close(self) -> None:
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Singleton instance
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """
    Get singleton Embedding service instance.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def create_embedding_service(config: ModelConfig) -> EmbeddingService:
    """
    Create a new Embedding service with specific configuration.

    Use this when you need a non-default configuration.

    Args:
        config: ModelConfig to use

    Returns:
        New EmbeddingService instance
    """
    return EmbeddingService(config=config)


async def reload_embedding_service() -> None:
    """
    Reload the singleton Embedding service with fresh configuration.

    Call this after ConfigManager cache is refreshed.
    """
    global _embedding_service
    if _embedding_service is not None:
        _embedding_service.reload_config()
        logger.info("Embedding service reloaded with fresh configuration")
