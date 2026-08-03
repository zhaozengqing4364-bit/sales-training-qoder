"""OpenAI-compatible LLM adapter behind the provider-neutral AI contract."""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)

from ai_platform.contracts import AIErrorClassification, AIUsageSummary
from ai_platform.errors import (
    AIPlatformError,
    EmptyProviderResponseError,
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderResponseInvalidError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderWorkloadMismatchError,
)
from ai_platform.providers import (
    ASRProviderRequest,
    ProviderRequest,
    ProviderResponse,
)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProviderSettings:
    provider: str
    base_url: str
    api_key: str = field(repr=False)
    currency: str = "CNY"
    input_cost_minor_units_per_million: int = 0
    output_cost_minor_units_per_million: int = 0

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.base_url.strip():
            raise ValueError("base_url is required")
        if not self.api_key.strip():
            raise ValueError("api_key is required")
        if len(self.currency) != 3:
            raise ValueError("currency must be a three-letter code")
        if (
            self.input_cost_minor_units_per_million < 0
            or self.output_cost_minor_units_per_million < 0
        ):
            raise ValueError("token costs cannot be negative")


class OpenAICompatibleProvider:
    """Strict JSON Chat Completions adapter; platform policy owns retries."""

    def __init__(
        self,
        settings: OpenAICompatibleProviderSettings,
        *,
        client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url.rstrip("/"),
            max_retries=0,
        )

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        # Chat Completions has no portable lookup endpoint. The request still
        # carries a provider idempotency key for providers that support it.
        del idempotency_key
        return None

    async def invoke(
        self,
        request: ProviderRequest | ASRProviderRequest,
    ) -> ProviderResponse:
        if isinstance(request, ASRProviderRequest):
            raise ProviderWorkloadMismatchError()
        if request.provider != self._settings.provider:
            raise AIPlatformError(
                code="AI_PROVIDER_CONFIGURATION_MISMATCH",
                classification=AIErrorClassification.MODEL_ROUTE_NOT_PUBLISHED,
                message="模型路由与 Provider 连接配置不一致。",
            )

        started = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=[
                    {"role": "user", "content": request.prompt},
                ],
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                response_format={"type": "json_object"},
                timeout=request.timeout_seconds,
                extra_headers={
                    "Idempotency-Key": request.idempotency_key,
                    "X-Trace-Id": request.trace_id,
                },
            )
        except asyncio.CancelledError as exc:
            raise ProviderCancelledError() from exc
        except APITimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except RateLimitError as exc:
            raise ProviderRateLimitError() from exc
        except APIStatusError as exc:
            if exc.status_code == 429:
                raise ProviderRateLimitError() from exc
            raise ProviderUnavailableError(status_code=exc.status_code) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailableError() from exc
        except OpenAIError as exc:
            raise ProviderUnavailableError() from exc

        choices = getattr(response, "choices", None) or []
        if not choices:
            raise EmptyProviderResponseError()
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if not isinstance(content, str) or not content.strip():
            raise EmptyProviderResponseError()
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderResponseInvalidError() from exc
        if not isinstance(payload, dict) or not payload:
            raise ProviderResponseInvalidError()

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = self._cost_minor_units(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return ProviderResponse(
            payload=payload,
            provider_request_id=str(getattr(response, "id", "") or request.invocation_id),
            usage=AIUsageSummary(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_minor_units=cost,
                currency=self._settings.currency,
            ),
            latency_ms=max(0, int((time.perf_counter() - started) * 1_000)),
            finish_reason=str(getattr(choice, "finish_reason", "") or "unknown"),
        )

    def _cost_minor_units(self, *, input_tokens: int, output_tokens: int) -> int:
        raw = (
            input_tokens * self._settings.input_cost_minor_units_per_million
            + output_tokens * self._settings.output_cost_minor_units_per_million
        ) / 1_000_000
        return math.ceil(raw) if raw > 0 else 0


__all__ = [
    "OpenAICompatibleProvider",
    "OpenAICompatibleProviderSettings",
]
