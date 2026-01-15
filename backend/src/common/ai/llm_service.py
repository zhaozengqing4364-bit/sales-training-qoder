"""
LLM Service - LangChain AI orchestration with ConfigManager integration

Refactored to load configuration from ConfigManager with environment variable fallback.
Supports multiple providers: OpenAI, Azure, Anthropic.

References:
- Requirements: R6.1 (Service Layer Abstraction)
- Design: model-config-management/design.md
- Constitution Principle IV: Fault Tolerance & Cost Control
"""
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class CostTrackingHandler(AsyncCallbackHandler):
    """Track LLM token usage for cost control"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def on_llm_end(self, response, **kwargs):
        """Track token usage"""
        if hasattr(response, 'llm_output') and response.llm_output:
            if 'token_usage' in response.llm_output:
                usage = response.llm_output['token_usage']
                self.total_tokens = usage.get('total_tokens', 0)
                self.prompt_tokens = usage.get('prompt_tokens', 0)
                self.completion_tokens = usage.get('completion_tokens', 0)

                logger.info(
                    f"LLM tokens used - Session: {self.session_id}, "
                    f"Prompt: {self.prompt_tokens}, "
                    f"Completion: {self.completion_tokens}, "
                    f"Total: {self.total_tokens}"
                )


class LLMService:
    """
    LLM service with ConfigManager integration.

    Features:
    - Loads configuration from ConfigManager (database)
    - Falls back to environment variables if no database config
    - Supports multiple providers: OpenAI, Azure, Anthropic
    - Timeout, retry, and cost tracking

    Requirements: R6.1 (LLM Service loads from ConfigManager)
    """

    def __init__(self, config: ModelConfig | None = None):
        """
        Initialize LLM service.

        Args:
            config: Optional ModelConfig. If not provided, uses default from ConfigManager.
        """
        self._config_manager = get_config_manager()
        self._config = config
        self._effective_config: dict[str, Any] | None = None

        # Cost tracking (¥0.05/1K tokens default)
        self.cost_per_1k_tokens = 0.00005
        self.session_costs: dict[str, float] = {}

        # Initialize LLM client
        self._llm = None
        self._init_client()

    def _init_client(self) -> None:
        """
        Initialize LLM client based on configuration.

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
            self._effective_config = self._config_manager.get_effective_config(ModelType.LLM)

        if not self._effective_config:
            logger.warning("No LLM configuration available")
            return

        # Extract config values
        provider = self._effective_config.get("provider", "openai")
        base_url = self._effective_config.get("base_url", "")
        api_key = self._effective_config.get("api_key", "")
        model_name = self._effective_config.get("model_name", "gpt-4o")
        extra_config = self._effective_config.get("extra_config", {})

        # Get parameters from extra_config
        temperature = extra_config.get("temperature", 0.7)
        timeout = extra_config.get("timeout", 10.0)
        max_retries = extra_config.get("max_retries", 2)

        # Update cost tracking from config
        if "cost_per_1k_tokens" in extra_config:
            self.cost_per_1k_tokens = extra_config["cost_per_1k_tokens"]

        # Initialize based on provider
        if provider == ModelProvider.AZURE.value or provider == "azure":
            self._init_azure_client(api_key, base_url, model_name, temperature, timeout, max_retries, extra_config)
        elif provider == ModelProvider.ANTHROPIC.value or provider == "anthropic":
            self._init_anthropic_client(api_key, base_url, model_name, temperature, timeout, max_retries)
        else:
            # Default to OpenAI-compatible
            self._init_openai_client(api_key, base_url, model_name, temperature, timeout, max_retries)

        logger.info(f"LLM service initialized with provider: {provider}, model: {model_name}")

    def _init_openai_client(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        timeout: float,
        max_retries: int
    ) -> None:
        """Initialize OpenAI-compatible client"""
        self._llm = ChatOpenAI(
            openai_api_key=api_key,
            openai_api_base=base_url if base_url else None,
            model=model_name,
            temperature=temperature,
            max_retries=max_retries,
            request_timeout=timeout,
        )

    def _init_azure_client(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        timeout: float,
        max_retries: int,
        extra_config: dict
    ) -> None:
        """Initialize Azure OpenAI client"""
        api_version = extra_config.get("api_version", "2024-02-15-preview")
        deployment_name = extra_config.get("deployment_name", model_name)

        self._llm = AzureChatOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
            azure_deployment=deployment_name,
            temperature=temperature,
            max_retries=max_retries,
            request_timeout=timeout,
        )

    def _init_anthropic_client(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        timeout: float,
        max_retries: int
    ) -> None:
        """Initialize Anthropic client (via OpenAI-compatible interface)"""
        # Anthropic can be used via OpenAI-compatible interface
        # or via langchain_anthropic if installed
        try:
            from langchain_anthropic import ChatAnthropic
            self._llm = ChatAnthropic(
                anthropic_api_key=api_key,
                model=model_name,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout,
            )
        except ImportError:
            logger.warning("langchain_anthropic not installed, using OpenAI-compatible interface")
            self._init_openai_client(api_key, base_url, model_name, temperature, timeout, max_retries)

    @property
    def is_configured(self) -> bool:
        """Check if LLM service is properly configured"""
        return self._llm is not None

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

    def reload_config(self, config: ModelConfig | None = None) -> None:
        """
        Reload configuration and reinitialize client.

        Args:
            config: Optional new config. If not provided, reloads from ConfigManager.
        """
        self._config = config
        self._init_client()

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        session_id: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None
    ) -> Result[str]:
        """
        Generate LLM response with timeout and retry.

        Args:
            prompt: User prompt
            session_id: Session ID for cost tracking
            system_message: Optional system message
            context: Optional context (conversation history, etc.)

        Returns:
            Result with response text or fallback
        """
        if not self.is_configured:
            logger.error("LLM service not configured")
            return Result.fail(self._get_fallback_response(prompt, context))

        try:
            messages = []

            # Add system message if provided
            if system_message:
                messages.append(SystemMessage(content=system_message))

            # Add context if provided
            if context and "history" in context:
                for msg in context["history"]:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            # Add current prompt
            messages.append(HumanMessage(content=prompt))

            # Generate with cost tracking
            cost_handler = CostTrackingHandler(session_id)
            result = await self._llm.agenerate(
                [messages],
                callbacks=[cost_handler]
            )

            # Extract response text
            generation = result.generations[0][0]
            response_text = getattr(generation, 'text', None) or getattr(generation, 'content', str(generation))

            # Track cost
            cost = (cost_handler.total_tokens / 1000) * self.cost_per_1k_tokens
            self.session_costs[session_id] = self.session_costs.get(session_id, 0) + cost

            # Alert if approaching budget (<¥1 per session)
            if self.session_costs[session_id] > 0.8:
                logger.warning(
                    f"Session {session_id} approaching budget: "
                    f"¥{self.session_costs[session_id]:.2f}"
                )

            return Result.ok(response_text)

        except Exception as e:
            logger.error(f"LLM generation error: {str(e)}")
            # Return predefined fallback response
            fallback_response = self._get_fallback_response(prompt, context)
            return Result.fail(fallback_response)

    def _get_fallback_response(
        self,
        prompt: str,
        context: dict[str, Any] | None
    ) -> str:
        """
        Get predefined fallback response based on context.
        These are "filler" phrases when LLM times out.
        """
        # Context-aware fallbacks
        if context and "scenario" in context:
            scenario = context["scenario"]

            if scenario == "presentation":
                return "Hmm, let me think about that... Can you continue?"

            elif scenario == "sales":
                return "That's interesting. Tell me more about your product."

        # Generic fallbacks
        fallbacks = [
            "Could you elaborate on that?",
            "I see. Please go on.",
            "That's a good point. What else?",
            "Can you provide more details?",
        ]

        # Simple hash-based selection for consistency
        fallback_index = hash(prompt) % len(fallbacks)
        return fallbacks[fallback_index]

    def get_session_cost(self, session_id: str) -> float:
        """Get cost for a specific session"""
        return self.session_costs.get(session_id, 0.0)

    def reset_session_cost(self, session_id: str) -> None:
        """Reset cost tracking for a session"""
        if session_id in self.session_costs:
            del self.session_costs[session_id]


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """
    Get singleton LLM service instance.

    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def create_llm_service(config: ModelConfig) -> LLMService:
    """
    Create a new LLM service with specific configuration.

    Use this when you need a non-default configuration.

    Args:
        config: ModelConfig to use

    Returns:
        New LLMService instance
    """
    return LLMService(config=config)


async def reload_llm_service() -> None:
    """
    Reload the singleton LLM service with fresh configuration.

    Call this after ConfigManager cache is refreshed.
    """
    global _llm_service
    if _llm_service is not None:
        _llm_service.reload_config()
        logger.info("LLM service reloaded with fresh configuration")
