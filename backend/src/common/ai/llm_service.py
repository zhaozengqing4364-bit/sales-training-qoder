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
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from openai import AsyncOpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelProvider, ModelType
from common.error_handling.result import Result
from common.knowledge_engine.runtime_events import build_runtime_event
from common.monitoring.logger import get_logger
from common.monitoring.metrics import track_llm_request
from prompt_templates.compiled_contract import CompiledPromptContract

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMStreamChunk:
    text: str = ""
    reasoning_text: str = ""


LEGACY_PROMPT_ENTRYPOINTS: dict[str, dict[str, Any]] = {
    "evaluate": {
        "prompt_contract_mode": "compiled_prompt_contract",
        "consumes_template_text": True,
        "template_lookup_context": "StagedEvaluationService now compiles PromptTemplateService output into a concrete runtime contract before calling evaluate(). Raw dict input remains a compatibility fallback only.",
        "runtime_consumer": "evaluation.services.staged_evaluation.StagedEvaluationService.evaluate_stage",
    },
    "generate_report": {
        "prompt_contract_mode": "compiled_prompt_contract",
        "consumes_template_text": True,
        "template_lookup_context": "ComprehensiveReportService now compiles PromptTemplateService output into a concrete runtime contract before calling generate_report(). Raw context dict input remains a compatibility fallback only.",
        "runtime_consumer": "evaluation.services.comprehensive_report.ComprehensiveReportService._generate_detailed_feedback",
    },
}

# T01 inventory for M021/S04: these are the shipped compatibility/default paths that
# currently hide runtime quality/cost/failure state and therefore need explicit
# eventization in the next task instead of being inferred from user-facing copy.
LLM_RUNTIME_EVENT_INVENTORY: tuple[dict[str, Any], ...] = (
    {
        "event_id": "llm_fallback_response",
        "phase": "generate",
        "trigger": "LLMService.generate() returns Result.fail(fallback_response) when the provider is unavailable or the service is not configured and allow_fallback_response=True.",
        "current_surface": "_get_fallback_response() produces plausible assistant copy instead of an explicit failure token.",
        "hidden_risk": "provider/config/runtime failure is translated into conversational text, so downstream readers must infer degradation from context instead of a first-class quality event.",
    },
    {
        "event_id": "llm_evaluation_default_scores",
        "phase": "evaluate",
        "trigger": "LLMService.evaluate() returns Result.ok(...) with hardcoded 60 scores when json.loads() fails after the model answered.",
        "current_surface": "communication/product_knowledge/problem_solving/customer_focus/professionalism all default to 60 with generic strengths/weaknesses/summary text.",
        "hidden_risk": "evaluation parse failure currently looks like a successful low-score evaluation instead of an explicit degraded/failure event.",
    },
    {
        "event_id": "llm_report_generation_failed",
        "phase": "generate_report",
        "trigger": "CompiledPromptContract/base_url/provider/report generation failures surface through Result.fail(result.fallback or [REPORT_GENERATION_FAILED]).",
        "current_surface": "callers usually receive only the propagated fallback string or [REPORT_GENERATION_FAILED], without a normalized phase-specific quality event.",
        "hidden_risk": "operators can see that report generation failed, but cannot reliably distinguish prompt compile failure, provider rejection, or fallback narrative without reading logs.",
    },
    {
        "event_id": "llm_cost_tracking_coarse_session_total",
        "phase": "cost",
        "trigger": "Successful agenerate() calls only update cost_per_1k_tokens * total_tokens into session_costs[session_id].",
        "current_surface": "CostTrackingHandler stores prompt/completion/total tokens in memory and emits a budget warning around ¥0.8, but there is no persisted per-call/provider/contract cost event line.",
        "hidden_risk": "future support/runtime readers cannot inspect where cost came from or whether a degraded/failure path still consumed tokens without re-reading logs.",
    },
)


class CostTrackingHandler(AsyncCallbackHandler):
    """Track LLM token usage for cost control"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Track token usage"""
        if hasattr(response, "llm_output") and response.llm_output:
            if "token_usage" in response.llm_output:
                usage = response.llm_output["token_usage"]
                self.total_tokens = usage.get("total_tokens", 0)
                self.prompt_tokens = usage.get("prompt_tokens", 0)
                self.completion_tokens = usage.get("completion_tokens", 0)

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
        self._runtime_policy: dict[str, Any] = (
            self._config_manager.describe_runtime_policy(
                ModelType.LLM,
                None,
            )
        )

        # Cost tracking (¥0.05/1K tokens default)
        self.cost_per_1k_tokens = 0.00005
        self.session_costs: dict[str, float] = {}
        self.session_runtime_events: dict[str, list[dict[str, Any]]] = {}

        # Initialize LLM client
        self._llm: Any = None
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
            self._effective_config = self._config_manager.get_effective_config(
                ModelType.LLM
            )

        self._runtime_policy = self._config_manager.describe_runtime_policy(
            ModelType.LLM,
            self._effective_config,
        )

        if not self._effective_config:
            logger.warning(
                "No LLM configuration available",
                base_url_policy=str(
                    self._runtime_policy.get("base_url_status") or "unknown"
                ),
            )
            return

        # Extract config values
        provider = self._effective_config.get("provider", "openai")
        base_url = self._effective_config.get("base_url", "")
        api_key = self._effective_config.get("api_key", "")
        model_name = self._effective_config.get("model_name", "gpt-4o")
        extra_config = self._effective_config.get("extra_config", {})

        if self._runtime_policy.get("base_url_required") and not str(base_url).strip():
            logger.error(
                "LLM configuration rejected by base_url policy",
                provider=str(provider),
                model_name=str(model_name),
                base_url_policy=(
                    f"required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                ),
            )
            return

        # Get parameters from extra_config
        temperature = extra_config.get("temperature", 0.7)
        timeout = extra_config.get("timeout", 10.0)
        max_retries = extra_config.get("max_retries", 2)

        # Update cost tracking from config
        if "cost_per_1k_tokens" in extra_config:
            self.cost_per_1k_tokens = extra_config["cost_per_1k_tokens"]

        # Initialize based on provider
        if provider == ModelProvider.AZURE.value or provider == "azure":
            self._init_azure_client(
                api_key,
                base_url,
                model_name,
                temperature,
                timeout,
                max_retries,
                extra_config,
            )
        elif provider == ModelProvider.ANTHROPIC.value or provider == "anthropic":
            self._init_anthropic_client(
                api_key, base_url, model_name, temperature, timeout, max_retries
            )
        else:
            # Default to OpenAI-compatible
            self._init_openai_client(
                api_key, base_url, model_name, temperature, timeout, max_retries
            )

        logger.info(
            f"LLM service initialized with provider: {provider}, model: {model_name}"
        )

    def _init_openai_client(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        timeout: float,
        max_retries: int,
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
        extra_config: dict,
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
        max_retries: int,
    ) -> None:
        """Initialize Anthropic client (via OpenAI-compatible interface)"""
        # Anthropic can be used via OpenAI-compatible interface
        # or via langchain_anthropic if installed
        try:
            from langchain_anthropic import (  # type: ignore[import-not-found]
                ChatAnthropic,
            )

            self._llm = ChatAnthropic(
                anthropic_api_key=api_key,
                model=model_name,
                temperature=temperature,
                max_retries=max_retries,
                timeout=timeout,
            )
        except ImportError:
            logger.warning(
                "langchain_anthropic not installed, using OpenAI-compatible interface"
            )
            self._init_openai_client(
                api_key, base_url, model_name, temperature, timeout, max_retries
            )

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
            return cast(str, self._effective_config.get("provider", "unknown"))
        return "unknown"

    @property
    def model_name(self) -> str:
        """Get current model name"""
        if self._effective_config:
            return cast(str, self._effective_config.get("model_name", "unknown"))
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

    def _record_runtime_event(self, session_id: str, event: dict[str, Any]) -> None:
        bucket = self.session_runtime_events.setdefault(session_id, [])
        bucket.append(dict(event))

    def get_session_runtime_events(self, session_id: str) -> list[dict[str, Any]]:
        return [
            dict(event) for event in self.session_runtime_events.get(session_id, [])
        ]

    def _log_compiled_prompt_contract(self, contract: CompiledPromptContract) -> None:
        """Emit explicit diagnostics for compiled prompt consumers."""
        for diagnostic in contract.diagnostics:
            log_kwargs = {
                "runtime_consumer": contract.runtime_consumer,
                "contract_hash": contract.contract_hash,
                "code": diagnostic.code,
                "severity": diagnostic.severity,
                "detail": diagnostic.detail,
                "base_url_policy": contract.base_url_policy,
            }
            if diagnostic.severity == "warning":
                logger.warning("Compiled prompt contract diagnostic", **log_kwargs)
            else:
                logger.info("Compiled prompt contract diagnostic", **log_kwargs)

    @staticmethod
    def _build_messages(
        prompt: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        messages: list[SystemMessage | HumanMessage | AIMessage] = []

        if system_message:
            messages.append(SystemMessage(content=system_message))

        if context and "history" in context:
            for msg in context["history"]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=prompt))
        return messages

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return LLMService._content_to_text(content.get("text", ""))
        if isinstance(content, list):
            pieces: list[str] = []
            for item in content:
                if isinstance(item, str):
                    pieces.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    pieces.append(str(item["text"]))
            return "".join(pieces)
        return ""

    @staticmethod
    def _chunk_reasoning_to_text(chunk: Any) -> str:
        text = LLMService._reasoning_content_to_text(getattr(chunk, "content", ""))
        if text:
            return text
        for key in ("reasoning_content", "reasoning", "reasoning_text"):
            text = LLMService._content_to_text(getattr(chunk, key, ""))
            if text:
                return text
        for container_name in ("additional_kwargs", "response_metadata"):
            container = getattr(chunk, container_name, None)
            if not isinstance(container, dict):
                continue
            text = LLMService._reasoning_mapping_to_text(container)
            if text:
                return text
        return ""

    @staticmethod
    def _reasoning_content_to_text(content: Any) -> str:
        if isinstance(content, dict):
            return LLMService._reasoning_mapping_to_text(content)
        if isinstance(content, list):
            pieces = [LLMService._reasoning_content_to_text(item) for item in content]
            return "".join(piece for piece in pieces if piece)
        return ""

    @staticmethod
    def _reasoning_mapping_to_text(mapping: dict[str, Any]) -> str:
        for key in ("reasoning_content", "reasoning", "reasoning_text"):
            text = LLMService._content_to_text(mapping.get(key, ""))
            if text:
                return text
        item_type = str(mapping.get("type", "")).lower()
        if "reason" in item_type or "thinking" in item_type:
            return LLMService._content_to_text(mapping.get("text", ""))
        for key in ("delta", "message"):
            nested = mapping.get(key)
            if isinstance(nested, dict):
                text = LLMService._reasoning_mapping_to_text(nested)
                if text:
                    return text
        return ""

    def _llm_for_call(self, response_format: dict[str, Any] | None = None) -> Any:
        """Return the runtime client, optionally constrained for this call only."""
        if response_format is None:
            return self._llm
        return self._llm.bind(response_format=response_format)

    def _uses_deepseek_reasoning_stream(self) -> bool:
        if not self._effective_config:
            return False
        provider = str(self._effective_config.get("provider", "")).lower()
        model_name = str(self._effective_config.get("model_name", "")).lower()
        base_url = str(self._effective_config.get("base_url", "")).lower()
        return provider == "openai" and (
            model_name.startswith("deepseek") or "deepseek" in base_url
        )

    @staticmethod
    def _messages_to_openai_payload(
        messages: list[SystemMessage | HumanMessage | AIMessage],
    ) -> list[dict[str, str]]:
        role_by_type = {
            SystemMessage: "system",
            HumanMessage: "user",
            AIMessage: "assistant",
        }
        payload: list[dict[str, str]] = []
        for message in messages:
            role = next(
                value for klass, value in role_by_type.items() if isinstance(message, klass)
            )
            payload.append(
                {
                    "role": role,
                    "content": LLMService._content_to_text(message.content),
                }
            )
        return payload

    @staticmethod
    def _openai_stream_chunk_to_llm_chunk(chunk: Any) -> LLMStreamChunk:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return LLMStreamChunk()
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return LLMStreamChunk()
        content = getattr(delta, "content", "") or ""
        reasoning = getattr(delta, "reasoning_content", "") or ""
        if not reasoning and hasattr(delta, "model_dump"):
            dumped = delta.model_dump(exclude_none=True)
            if isinstance(dumped, dict):
                reasoning = dumped.get("reasoning_content", "") or ""
        return LLMStreamChunk(text=str(content or ""), reasoning_text=str(reasoning or ""))

    async def _stream_deepseek_reasoning_chunks(
        self,
        *,
        prompt: str,
        session_id: str,
        system_message: str | None,
        context: dict[str, Any] | None,
        response_format: dict[str, Any] | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        if not self._effective_config:
            return
        extra_config = self._effective_config.get("extra_config", {}) or {}
        client = AsyncOpenAI(
            api_key=str(self._effective_config.get("api_key", "")),
            base_url=str(self._effective_config.get("base_url", "")).rstrip("/") or None,
            timeout=float(extra_config.get("timeout", 60.0)),
            max_retries=int(extra_config.get("max_retries", 0)),
        )
        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._messages_to_openai_payload(
                self._build_messages(prompt, system_message, context)
            ),
            "stream": True,
            "reasoning_effort": str(extra_config.get("reasoning_effort", "high")),
            "extra_body": {"thinking": {"type": "enabled"}},
        }
        if response_format is not None:
            request["response_format"] = response_format
        stream = await client.chat.completions.create(**request)
        async for raw_chunk in stream:
            chunk = self._openai_stream_chunk_to_llm_chunk(raw_chunk)
            if chunk.text or chunk.reasoning_text:
                yield chunk

    async def stream_generate(
        self,
        prompt: str,
        session_id: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None,
        *,
        allow_fallback_response: bool = True,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Stream LLM response text chunks for callers with their own contracts."""
        async for chunk in self.stream_generate_chunks(
            prompt=prompt,
            session_id=session_id,
            system_message=system_message,
            context=context,
            allow_fallback_response=allow_fallback_response,
            response_format=response_format,
        ):
            if chunk.text:
                yield chunk.text

    async def stream_generate_chunks(
        self,
        prompt: str,
        session_id: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None,
        *,
        allow_fallback_response: bool = True,
        response_format: dict[str, Any] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream LLM text plus provider reasoning chunks when available."""
        if self._is_performance_test_mode():
            track_llm_request("performance_test", "fallback", 0.0, {})
            yield LLMStreamChunk(text=self._get_fallback_response(prompt, context))
            return

        if not self.is_configured:
            track_llm_request(self.provider, "not_configured", 0.0, {})
            logger.error(
                "LLM service not configured for streaming",
                provider=self.provider,
                model_name=self.model_name,
                base_url_policy=(
                    f"required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                    if self._runtime_policy.get("base_url_required")
                    else f"not_required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                ),
            )
            if allow_fallback_response:
                yield LLMStreamChunk(text=self._get_fallback_response(prompt, context))
                return
            raise RuntimeError("[LLM_NOT_CONFIGURED]")

        started_at = time.perf_counter()
        try:
            cost_handler = CostTrackingHandler(session_id)
            chunk_count = 0
            text_length = 0
            reasoning_length = 0
            if self._uses_deepseek_reasoning_stream():
                async for chunk in self._stream_deepseek_reasoning_chunks(
                    prompt=prompt,
                    session_id=session_id,
                    system_message=system_message,
                    context=context,
                    response_format=response_format,
                ):
                    chunk_count += 1
                    text_length += len(chunk.text)
                    reasoning_length += len(chunk.reasoning_text)
                    yield chunk
            else:
                messages = self._build_messages(prompt, system_message, context)
                async for chunk in self._llm_for_call(response_format).astream(
                    messages,
                    config={"callbacks": [cost_handler]},
                ):
                    text = self._content_to_text(getattr(chunk, "content", ""))
                    reasoning_text = self._chunk_reasoning_to_text(chunk)
                    if text or reasoning_text:
                        emitted = LLMStreamChunk(
                            text=text,
                            reasoning_text=reasoning_text,
                        )
                        chunk_count += 1
                        text_length += len(emitted.text)
                        reasoning_length += len(emitted.reasoning_text)
                        yield emitted
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_provider_response_received",
                    category=cast(Any, "runtime"),
                    severity="info",
                    status="received",
                    source="llm.stream_generate",
                    summary="Streaming LLM provider response was received.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "response_format": response_format,
                        "fallback_used": False,
                    },
                    metrics={
                        "latency_ms": latency_ms,
                        "chunk_count": chunk_count,
                        "response_text_length": text_length,
                        "reasoning_text_length": reasoning_length,
                    },
                ),
            )
            cost = (cost_handler.total_tokens / 1000) * self.cost_per_1k_tokens
            self.session_costs[session_id] = (
                self.session_costs.get(session_id, 0) + cost
            )
            track_llm_request(
                self.provider,
                "success",
                latency_ms / 1000,
                {
                    "prompt": cost_handler.prompt_tokens,
                    "completion": cost_handler.completion_tokens,
                    "total": cost_handler.total_tokens,
                },
            )
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_cost_tracking_coarse_session_total",
                    category="cost",
                    severity="info",
                    status="tracked",
                    source="llm.stream_generate",
                    summary="Streaming LLM token usage and coarse session cost were recorded.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "response_format": response_format,
                    },
                    metrics={
                        "prompt_tokens": cost_handler.prompt_tokens,
                        "completion_tokens": cost_handler.completion_tokens,
                        "total_tokens": cost_handler.total_tokens,
                        "request_cost": round(cost, 6),
                        "session_cost": round(self.session_costs[session_id], 6),
                    },
                ),
            )
        except (
            ConnectionError,
            TimeoutError,
            RuntimeError,
            ValueError,
            OSError,
            OpenAIError,
        ) as e:
            logger.error(
                "LLM streaming generation error",
                provider=self.provider,
                model_name=self.model_name,
                error_type=type(e).__name__,
                error=str(e),
                base_url_policy=(
                    f"required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                    if self._runtime_policy.get("base_url_required")
                    else f"not_required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                ),
            )
            track_llm_request(
                self.provider,
                f"error:{type(e).__name__}",
                time.perf_counter() - started_at,
                {},
            )
            if allow_fallback_response:
                yield LLMStreamChunk(text=self._get_fallback_response(prompt, context))
                return
            raise RuntimeError("[LLM_STREAMING_GENERATION_FAILED]") from e

    @retry(
        stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        session_id: str,
        system_message: str | None = None,
        context: dict[str, Any] | None = None,
        *,
        allow_fallback_response: bool = True,
        response_format: dict[str, Any] | None = None,
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
            track_llm_request("performance_test", "fallback", 0.0, {})
            return Result.ok(self._get_fallback_response(prompt, context))

        if not self.is_configured:
            track_llm_request(self.provider, "not_configured", 0.0, {})
            logger.error(
                "LLM service not configured",
                provider=self.provider,
                model_name=self.model_name,
                base_url_policy=(
                    f"required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                    if self._runtime_policy.get("base_url_required")
                    else f"not_required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                ),
            )
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_fallback_response",
                    category="failure",
                    severity="failure",
                    status="not_configured",
                    source="llm.generate",
                    summary="LLM generation fell back because the service was not configured.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "fallback_allowed": allow_fallback_response,
                    },
                ),
            )
            if allow_fallback_response:
                return Result.fail(self._get_fallback_response(prompt, context))
            return Result.fail("[LLM_NOT_CONFIGURED]")

        started_at = time.perf_counter()
        try:
            messages = self._build_messages(prompt, system_message, context)

            # Generate with cost tracking
            cost_handler = CostTrackingHandler(session_id)
            result = await self._llm_for_call(response_format).agenerate(
                [messages], callbacks=[cost_handler]
            )

            # Extract response text
            generation = result.generations[0][0]
            response_text = getattr(generation, "text", None) or getattr(
                generation, "content", str(generation)
            )
            response_metadata = getattr(generation, "response_metadata", None)
            if not isinstance(response_metadata, dict):
                message = getattr(generation, "message", None)
                response_metadata = getattr(message, "response_metadata", None)
            if not isinstance(response_metadata, dict):
                response_metadata = {}
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            track_llm_request(
                self.provider,
                "success",
                latency_ms / 1000,
                {
                    "prompt": cost_handler.prompt_tokens,
                    "completion": cost_handler.completion_tokens,
                    "total": cost_handler.total_tokens,
                },
            )
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_provider_response_received",
                    category=cast(Any, "runtime"),
                    severity="info",
                    status="received",
                    source="llm.generate",
                    summary="LLM provider response was received.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "response_format": response_format,
                        "fallback_used": False,
                        "response_metadata_keys": sorted(response_metadata.keys()),
                    },
                    metrics={
                        "latency_ms": latency_ms,
                        "generation_count": sum(len(items) for items in result.generations),
                        "response_text_length": len(str(response_text or "")),
                    },
                ),
            )

            # Track cost
            cost = (cost_handler.total_tokens / 1000) * self.cost_per_1k_tokens
            self.session_costs[session_id] = (
                self.session_costs.get(session_id, 0) + cost
            )
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_cost_tracking_coarse_session_total",
                    category="cost",
                    severity="info",
                    status="tracked",
                    source="llm.generate",
                    summary="LLM token usage and coarse session cost were recorded.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "response_format": response_format,
                    },
                    metrics={
                        "prompt_tokens": cost_handler.prompt_tokens,
                        "completion_tokens": cost_handler.completion_tokens,
                        "total_tokens": cost_handler.total_tokens,
                        "request_cost": round(cost, 6),
                        "session_cost": round(self.session_costs[session_id], 6),
                    },
                ),
            )

            # Alert if approaching budget (<¥1 per session)
            if self.session_costs[session_id] > 0.8:
                logger.warning(
                    f"Session {session_id} approaching budget: "
                    f"¥{self.session_costs[session_id]:.2f}"
                )
                self._record_runtime_event(
                    session_id,
                    build_runtime_event(
                        event_id="llm_session_cost_budget_warning",
                        category="cost",
                        severity="degraded",
                        status="budget_warning",
                        source="llm.generate",
                        summary="LLM session cost is approaching the configured budget threshold.",
                        details={
                            "provider": self.provider,
                            "model_name": self.model_name,
                        },
                        metrics={
                            "session_cost": round(self.session_costs[session_id], 6),
                            "budget_warning_threshold": 0.8,
                        },
                    ),
                )

            return Result.ok(cast(str, response_text))

        except (
            ConnectionError,
            TimeoutError,
            RuntimeError,
            ValueError,
            OSError,
            OpenAIError,
        ) as e:
            logger.error(
                "LLM generation error",
                provider=self.provider,
                model_name=self.model_name,
                error_type=type(e).__name__,
                error=str(e),
                base_url_policy=(
                    f"required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                    if self._runtime_policy.get("base_url_required")
                    else f"not_required_{self._runtime_policy.get('base_url_status') or 'unknown'}"
                ),
            )
            track_llm_request(
                self.provider,
                f"error:{type(e).__name__}",
                time.perf_counter() - started_at,
                {},
            )
            # Return predefined fallback response
            fallback_response = self._get_fallback_response(prompt, context)
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_fallback_response",
                    category="failure",
                    severity="failure",
                    status=f"generation_error:{type(e).__name__}",
                    source="llm.generate",
                    summary="LLM generation fell back after a provider/runtime error.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "error_type": type(e).__name__,
                        "fallback_allowed": allow_fallback_response,
                    },
                ),
            )
            if allow_fallback_response:
                return Result.fail(fallback_response)
            return Result.fail(f"[LLM_GENERATION_ERROR:{type(e).__name__}]")

    def _get_fallback_response(
        self, prompt: str, context: dict[str, Any] | None
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
        render_request: dict[str, Any] | CompiledPromptContract,
        session_id: str = "evaluation",
    ) -> Result[dict]:
        """
        Evaluate a conversation stage using LLM.

        Args:
            render_request: Dict with template_id and variables, or a compiled prompt contract
            session_id: Session ID for cost tracking

        Returns:
            Result with parsed evaluation data (scores, strengths, weaknesses, suggestions, summary)
        """
        import json as json_module

        if isinstance(render_request, CompiledPromptContract):
            self._log_compiled_prompt_contract(render_request)
            prompt = render_request.rendered_prompt
            system_message = (
                render_request.system_message
                or "你是一个专业的销售培训评估专家。请严格按照JSON格式返回评估结果。"
            )
            result = await self.generate(
                prompt=prompt,
                session_id=session_id,
                system_message=system_message,
                context={
                    "contract_hash": render_request.contract_hash,
                    "runtime_consumer": render_request.runtime_consumer,
                },
                allow_fallback_response=False,
            )
        else:
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
            return Result.fail(result.fallback or "[LLM_EVALUATION_FAILED]")

        try:
            response_text = cast(str, result.value).strip()
            if response_text.startswith("```"):
                response_text = (
                    response_text.split("\n", 1)[1]
                    if "\n" in response_text
                    else response_text
                )
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
            evaluation_data = json_module.loads(response_text)
            return Result.ok(evaluation_data)
        except (json_module.JSONDecodeError, ValueError):
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_evaluation_default_scores",
                    category="quality",
                    severity="degraded",
                    status="default_scores_applied",
                    source="llm.evaluate",
                    summary="Evaluation parsing failed and default scores were returned.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                    },
                ),
            )
            return Result.ok(
                {
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
                }
            )

    async def generate_report(
        self,
        context: dict[str, Any] | CompiledPromptContract,
        session_id: str = "report",
    ) -> Result[str]:
        """
        Generate detailed feedback report using LLM.

        Args:
            context: Dict with session_id/stage_count/overall_summary, or a compiled prompt contract
            session_id: Session ID for cost tracking

        Returns:
            Result with detailed feedback text
        """
        if isinstance(context, CompiledPromptContract):
            self._log_compiled_prompt_contract(context)
            prompt = context.rendered_prompt
            system_message = (
                context.system_message
                or "你是一个专业的销售培训教练，请提供详细、有建设性的反馈。"
            )
            result = await self.generate(
                prompt=prompt,
                session_id=session_id,
                system_message=system_message,
                context={
                    "contract_hash": context.contract_hash,
                    "runtime_consumer": context.runtime_consumer,
                },
                allow_fallback_response=False,
            )
        else:
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
            self._record_runtime_event(
                session_id,
                build_runtime_event(
                    event_id="llm_report_generation_failed",
                    category="failure",
                    severity="failure",
                    status="report_failed",
                    source="llm.generate_report",
                    summary="Detailed report generation failed and surfaced a fallback token.",
                    details={
                        "provider": self.provider,
                        "model_name": self.model_name,
                        "error_token": result.fallback or "[REPORT_GENERATION_FAILED]",
                    },
                ),
            )
            return Result.fail(result.fallback or "[REPORT_GENERATION_FAILED]")

        return Result.ok(cast(str, result.value))

    def get_session_cost(self, session_id: str) -> float:
        """Get cost for a specific session"""
        return self.session_costs.get(session_id, 0.0)

    def reset_session_cost(self, session_id: str) -> None:
        """Reset cost tracking for a session"""
        if session_id in self.session_costs:
            del self.session_costs[session_id]
        self.session_runtime_events.pop(session_id, None)


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
