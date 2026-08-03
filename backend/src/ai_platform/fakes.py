"""Deterministic provider fakes for tests and local contract verification."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from ai_platform.contracts import AIUsageSummary
from ai_platform.errors import (
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderWorkloadMismatchError,
)
from ai_platform.providers import ASRProviderRequest, ProviderRequest, ProviderResponse


@dataclass(frozen=True, slots=True)
class ProviderScenario:
    kind: str
    payload: dict[str, Any] | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_minor_units: int = 0
    partial: bool = False
    status_code: int | None = None

    @classmethod
    def success(
        cls,
        *,
        payload: dict[str, Any],
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_minor_units: int = 0,
        partial: bool = False,
    ) -> ProviderScenario:
        return cls(
            kind="success",
            payload=payload,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_minor_units=cost_minor_units,
            partial=partial,
        )

    @classmethod
    def timeout(cls) -> ProviderScenario:
        return cls(kind="timeout")

    @classmethod
    def rate_limited(cls) -> ProviderScenario:
        return cls(kind="rate_limited")

    @classmethod
    def unavailable(cls, status_code: int = 503) -> ProviderScenario:
        return cls(kind="unavailable", status_code=status_code)

    @classmethod
    def cancelled(cls) -> ProviderScenario:
        return cls(kind="cancelled")

    @classmethod
    def invalid_schema(cls, *, payload: dict[str, Any]) -> ProviderScenario:
        return cls(kind="success", payload=payload)

    @classmethod
    def empty(cls) -> ProviderScenario:
        return cls(kind="success", payload={})


class DeterministicAIProvider:
    def __init__(self, *, scenarios: list[ProviderScenario]) -> None:
        if not scenarios:
            raise ValueError("at least one provider scenario is required")
        self._scenarios = deque(scenarios)
        self._results: dict[str, ProviderResponse] = {}
        self.requests: list[ProviderRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        return self._results.get(idempotency_key)

    async def invoke(
        self, request: ProviderRequest | ASRProviderRequest
    ) -> ProviderResponse:
        if not isinstance(request, ProviderRequest):
            raise ProviderWorkloadMismatchError()
        cached = self._results.get(request.idempotency_key)
        if cached is not None:
            return cached
        self.requests.append(request)
        if not self._scenarios:
            raise AssertionError("deterministic provider exhausted its scenarios")
        scenario = self._scenarios.popleft()
        if scenario.kind == "timeout":
            raise ProviderTimeoutError()
        if scenario.kind == "rate_limited":
            raise ProviderRateLimitError()
        if scenario.kind == "unavailable":
            raise ProviderUnavailableError(status_code=scenario.status_code or 503)
        if scenario.kind == "cancelled":
            raise ProviderCancelledError()
        if scenario.kind != "success" or scenario.payload is None:
            raise AssertionError(f"unsupported deterministic scenario: {scenario.kind}")
        response = ProviderResponse(
            payload=scenario.payload,
            provider_request_id=f"deterministic-{len(self.requests)}",
            usage=AIUsageSummary(
                input_tokens=scenario.input_tokens,
                output_tokens=scenario.output_tokens,
                total_tokens=scenario.input_tokens + scenario.output_tokens,
                cost_minor_units=scenario.cost_minor_units,
                currency="CNY",
            ),
            latency_ms=1,
            finish_reason="stop",
            partial=scenario.partial,
        )
        self._results[request.idempotency_key] = response
        return response
