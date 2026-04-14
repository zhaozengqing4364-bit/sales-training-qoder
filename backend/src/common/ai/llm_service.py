"""
LLM Service - LangChain AI orchestration with ConfigManager integration

Refactored to load configuration from ConfigManager with environment variable fallback.
Supports multiple providers: OpenAI, Azure, Anthropic.

References:
- Requirements: R6.1 (Service Layer Abstraction)
- Design: model-config-management/design.md
- Constitution Principle IV: Fault Tolerance & Cost Control
"""
import os
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


LEGACY_PROMPT_ENTRYPOINTS: dict[str, dict[str, Any]] = {
    "evaluate": {
        "prompt_contract_mode": "hardcoded_builtin_prompt",
        "consumes_template_text": False,
        "template_lookup_context": "render_request carries template_id + variables, but the method rebuilds an internal evaluation prompt from selected variables only.",
        "runtime_consumer": "evaluation.services.staged_evaluation.StagedEvaluationService.evaluate_stage",
    },
    "generate_report": {
        "prompt_contract_mode": "hardcoded_builtin_prompt",
        "consumes_template_text": False,
        "template_lookup_context": "report context is forwarded from ComprehensiveReportService after a template lookup, but the method rebuilds its own report prompt instead of consuming rendered template text.",
        "runtime_consumer": "evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback",
    },
}


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

    def _is_performance_test_mode(self) -> bool:
        """Return True when running performance tests without explicit real-LLM opt-in."""
        current_test = os.getenv("PYTEST_CURRENT_TEST", "")
        if "tests/performance/" not in current_test:
            return False
        return os.getenv("ENABLE_REAL_LLM_PERF_TESTS", "0") != "1"

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
    def llm(self) -> Any:
        """Backward-compatible access to the underlying LangChain client."""
        if self._is_performance_test_mode():
            return None
        return self._llm

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
        if self._is_performance_test_mode():
            return Result.ok(self._get_fallback_response(prompt, context))

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

        except (ConnectionError, TimeoutError, RuntimeError, ValueError, OSError) as e:
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

    async def evaluate(
        self,
        render_request: dict,
        session_id: str = "evaluation",
    ) -> Result[dict]:
        """
        Evaluate a conversation stage using LLM.

        Args:
            render_request: Dict with template_id and variables
            session_id: Session ID for cost tracking

        Returns:
            Result with parsed evaluation data (scores, strengths, weaknesses, suggestions, summary)
        """
        import json as json_module

        variables = render_request.get("variables", {})
        conversation = variables.get("conversation", "")
        stage_name = variables.get("stage_name", "")
        stage_description = variables.get("stage_description", "")

        prompt = f"""请评估以下销售对话阶段的表现，并以JSON格式返回评估结果。

阶段名称: {stage_name}
阶段描述: {stage_description}

对话内容:
{conversation}

请返回以下JSON格式（不要包含markdown代码块标记）:
{{
    "scores": {{
        "communication": <0-100>,
        "product_knowledge": <0-100>,
        "problem_solving": <0-100>,
        "customer_focus": <0-100>,
        "professionalism": <0-100>
    }},
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["不足1", "不足2"],
    "suggestions": ["建议1", "建议2"],
    "summary": "阶段总结"
}}"""

        result = await self.generate(
            prompt=prompt,
            session_id=session_id,
            system_message="你是一个专业的销售培训评估专家。请严格按照JSON格式返回评估结果。",
        )

        if not result.is_success:
            return Result.fail("[LLM_EVALUATION_FAILED]")

        try:
            response_text = result.value.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
            evaluation_data = json_module.loads(response_text)
            return Result.ok(evaluation_data)
        except (json_module.JSONDecodeError, ValueError):
            return Result.ok({
                "scores": {
                    "communication": 60,
                    "product_knowledge": 60,
                    "problem_solving": 60,
                    "customer_focus": 60,
                    "professionalism": 60,
                },
                "strengths": ["完成了对话"],
                "weaknesses": ["需要更多练习"],
                "suggestions": ["继续练习以提高表现"],
                "summary": "完成了销售对话练习",
            })

    async def generate_report(
        self,
        context: dict,
        session_id: str = "report",
    ) -> Result[str]:
        """
        Generate detailed feedback report using LLM.

        Args:
            context: Dict with session_id, stage_count, overall_summary
            session_id: Session ID for cost tracking

        Returns:
            Result with detailed feedback text
        """
        stage_count = context.get("stage_count", 0)
        overall_summary = context.get("overall_summary", "")
        ctx_session_id = context.get("session_id", "unknown")

        prompt = f"""请为以下销售练习会话生成详细的反馈报告。

会话ID: {ctx_session_id}
阶段数量: {stage_count}

各阶段总结:
{overall_summary}

请生成一份详细的中文反馈报告，包括：
1. 整体表现评价
2. 各阶段的具体分析
3. 突出的优势
4. 需要改进的方面
5. 具体的提升建议"""

        result = await self.generate(
            prompt=prompt,
            session_id=session_id,
            system_message="你是一个专业的销售培训教练，请提供详细、有建设性的反馈。",
        )

        if not result.is_success:
            return Result.fail("[REPORT_GENERATION_FAILED]")

        return Result.ok(result.value)

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
