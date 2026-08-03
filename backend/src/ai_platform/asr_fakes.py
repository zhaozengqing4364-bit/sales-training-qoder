"""Deterministic ASR adapter sharing the governed provider response contract."""

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
class ASRScenario:
    kind: str
    payload: dict[str, Any] | None = None
    cost_minor_units: int = 0
    partial: bool = False

    @classmethod
    def success(
        cls,
        *,
        transcript: str,
        confidence: float = 0.95,
        cost_minor_units: int = 0,
        partial: bool = False,
    ) -> ASRScenario:
        return cls(
            kind="success",
            payload={"transcript": transcript, "confidence": confidence},
            cost_minor_units=cost_minor_units,
            partial=partial,
        )

    @classmethod
    def low_confidence(cls, *, transcript: str) -> ASRScenario:
        return cls.success(transcript=transcript, confidence=0.2, partial=True)

    @classmethod
    def invalid_schema(cls) -> ASRScenario:
        return cls(kind="success", payload={"unexpected": "shape"})

    @classmethod
    def empty(cls) -> ASRScenario:
        return cls(kind="success", payload={})

    @classmethod
    def timeout(cls) -> ASRScenario:
        return cls(kind="timeout")

    @classmethod
    def rate_limited(cls) -> ASRScenario:
        return cls(kind="rate_limited")

    @classmethod
    def unavailable(cls) -> ASRScenario:
        return cls(kind="unavailable")

    @classmethod
    def cancelled(cls) -> ASRScenario:
        return cls(kind="cancelled")


class DeterministicASRProvider:
    def __init__(self, *, scenarios: list[ASRScenario]) -> None:
        if not scenarios:
            raise ValueError("at least one ASR scenario is required")
        self._scenarios = deque(scenarios)
        self._results: dict[str, ProviderResponse] = {}
        self.requests: list[ASRProviderRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        return self._results.get(idempotency_key)

    async def invoke(
        self, request: ProviderRequest | ASRProviderRequest
    ) -> ProviderResponse:
        if not isinstance(request, ASRProviderRequest):
            raise ProviderWorkloadMismatchError()
        cached = self._results.get(request.idempotency_key)
        if cached is not None:
            return cached
        self.requests.append(request)
        if not self._scenarios:
            raise AssertionError("deterministic ASR provider exhausted its scenarios")
        scenario = self._scenarios.popleft()
        if scenario.kind == "timeout":
            raise ProviderTimeoutError()
        if scenario.kind == "rate_limited":
            raise ProviderRateLimitError()
        if scenario.kind == "unavailable":
            raise ProviderUnavailableError()
        if scenario.kind == "cancelled":
            raise ProviderCancelledError()
        if scenario.kind != "success" or scenario.payload is None:
            raise AssertionError(
                f"unsupported deterministic ASR scenario: {scenario.kind}"
            )
        response = ProviderResponse(
            payload=scenario.payload,
            provider_request_id=f"deterministic-asr-{len(self.requests)}",
            usage=AIUsageSummary(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_minor_units=scenario.cost_minor_units,
                currency="CNY",
            ),
            latency_ms=1,
            finish_reason="completed",
            partial=scenario.partial,
        )
        self._results[request.idempotency_key] = response
        return response
