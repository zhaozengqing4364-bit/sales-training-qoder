from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from ai_platform import AIErrorClassification, AIUsageSummary
from ai_platform.errors import (
    ProviderCancelledError,
    ProviderRateLimitError,
    ProviderResponseInvalidError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from ai_platform.openai_provider import (
    OpenAICompatibleProvider,
    OpenAICompatibleProviderSettings,
)
from ai_platform.providers import ProviderRequest


class _Completions:
    def __init__(self, response) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


class _Client:
    def __init__(self, response) -> None:
        self.chat = SimpleNamespace(completions=_Completions(response))


class _FailingCompletions:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def create(self, **kwargs):
        del kwargs
        raise self.error


class _FailingClient:
    def __init__(self, error: BaseException) -> None:
        self.chat = SimpleNamespace(completions=_FailingCompletions(error))


def _request() -> ProviderRequest:
    return ProviderRequest(
        idempotency_key="ai:invocation-1:attempt:1",
        invocation_id="invocation-1",
        attempt_no=1,
        prompt="生成结构化结果",
        provider="openai",
        model="governed-model",
        temperature=0.1,
        max_output_tokens=512,
        timeout_seconds=30,
        output_schema_version="question-generation-output-v1",
        trace_id="trace-1",
    )


def _settings() -> OpenAICompatibleProviderSettings:
    return OpenAICompatibleProviderSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="secret-must-not-be-rendered",
        input_cost_minor_units_per_million=1_000,
        output_cost_minor_units_per_million=2_000,
    )


@pytest.mark.asyncio
async def test_openai_compatible_provider_returns_strict_json_and_usage() -> None:
    response = SimpleNamespace(
        id="provider-request-1",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"answer": "ok"}'),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1_000, completion_tokens=500),
    )
    client = _Client(response)
    provider = OpenAICompatibleProvider(_settings(), client=client)

    result = await provider.invoke(_request())

    assert result.payload == {"answer": "ok"}
    assert result.provider_request_id == "provider-request-1"
    assert result.usage == AIUsageSummary(
        input_tokens=1_000,
        output_tokens=500,
        total_tokens=1_500,
        cost_minor_units=2,
        currency="CNY",
    )
    sent = client.chat.completions.requests[0]
    assert sent["model"] == "governed-model"
    assert sent["messages"] == [
        {"role": "user", "content": "生成结构化结果"}
    ]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["extra_headers"] == {
        "Idempotency-Key": "ai:invocation-1:attempt:1",
        "X-Trace-Id": "trace-1",
    }
    assert "secret-must-not-be-rendered" not in repr(_settings())


@pytest.mark.asyncio
async def test_openai_compatible_provider_rejects_non_json_output() -> None:
    response = SimpleNamespace(
        id="provider-request-invalid",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="not-json"),
                finish_reason="stop",
            )
        ],
        usage=None,
    )
    provider = OpenAICompatibleProvider(_settings(), client=_Client(response))

    with pytest.raises(ProviderResponseInvalidError) as invalid:
        await provider.invoke(_request())

    assert (
        invalid.value.classification
        is AIErrorClassification.OUTPUT_SCHEMA_INVALID
    )
    assert invalid.value.retryable is True


def _request_for_error() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _response_for_error(status_code: int) -> httpx.Response:
    request = _request_for_error()
    return httpx.Response(status_code, request=request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_error", "classification", "retryable"),
    [
        (
            APITimeoutError(_request_for_error()),
            ProviderTimeoutError,
            AIErrorClassification.TIMEOUT,
            True,
        ),
        (
            RateLimitError(
                "rate limited",
                response=_response_for_error(429),
                body=None,
            ),
            ProviderRateLimitError,
            AIErrorClassification.RATE_LIMITED,
            True,
        ),
        (
            APIConnectionError(request=_request_for_error()),
            ProviderUnavailableError,
            AIErrorClassification.PROVIDER_UNAVAILABLE,
            True,
        ),
        (
            APIStatusError(
                "provider unavailable",
                response=_response_for_error(503),
                body=None,
            ),
            ProviderUnavailableError,
            AIErrorClassification.PROVIDER_UNAVAILABLE,
            True,
        ),
        (
            asyncio.CancelledError(),
            ProviderCancelledError,
            AIErrorClassification.CANCELLED,
            False,
        ),
    ],
)
async def test_openai_compatible_provider_classifies_provider_failures(
    provider_error: BaseException,
    expected_error: type[Exception],
    classification: AIErrorClassification,
    retryable: bool,
) -> None:
    provider = OpenAICompatibleProvider(
        _settings(),
        client=_FailingClient(provider_error),
    )

    with pytest.raises(expected_error) as caught:
        await provider.invoke(_request())

    assert caught.value.classification is classification
    assert caught.value.retryable is retryable
