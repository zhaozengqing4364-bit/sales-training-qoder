import socket
from types import SimpleNamespace
from typing import cast

import pytest

from admin.api import model_configs
from common.ai.models import ModelConfig, ModelProvider, ModelType


def _addrinfo(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.is_redirect = status_code in {301, 302, 303, 307, 308}

    def json(self):
        return {"data": [{"embedding": [0.1, 0.2]}]}


class FakeAsyncClient:
    calls = []
    init_kwargs = []
    response = FakeResponse()

    def __init__(self, **kwargs):
        self.init_kwargs.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json})
        return self.response


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    import httpx

    FakeAsyncClient.calls = []
    FakeAsyncClient.init_kwargs = []
    FakeAsyncClient.response = FakeResponse()
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)


@pytest.mark.asyncio
async def test_llm_test_rejects_private_dns_before_authorization_call(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: _addrinfo("127.0.0.1")
    )
    config = cast(
        ModelConfig,
        SimpleNamespace(
            provider=ModelProvider.OPENAI.value,
            base_url="https://api.openai.com/v1",
            model_name="gpt-test",
        ),
    )

    result = await model_configs._test_llm(config, "sk-realistic-secret-value")

    assert result.success is False
    assert "non-public" in result.message
    assert FakeAsyncClient.calls == []


@pytest.mark.asyncio
async def test_llm_test_allows_public_provider_with_no_redirect_follow(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: _addrinfo("93.184.216.34")
    )
    config = cast(
        ModelConfig,
        SimpleNamespace(
            provider=ModelProvider.OPENAI.value,
            base_url="https://api.openai.com/v1/",
            model_name="gpt-test",
        ),
    )

    result = await model_configs._test_llm(config, "sk-realistic-secret-value")

    assert result.success is True
    assert FakeAsyncClient.init_kwargs == [{"timeout": 10.0, "follow_redirects": False}]
    assert FakeAsyncClient.calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
    assert FakeAsyncClient.calls[0]["headers"]["Authorization"] == "Bearer sk-realistic-secret-value"


@pytest.mark.asyncio
async def test_llm_test_redacts_upstream_error_body(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: _addrinfo("93.184.216.34")
    )
    FakeAsyncClient.response = FakeResponse(
        status_code=401, text="secret body sk-leaked"
    )
    config = cast(
        ModelConfig,
        SimpleNamespace(
            provider=ModelProvider.OPENAI.value,
            base_url="https://api.openai.com/v1",
            model_name="gpt-test",
        ),
    )

    result = await model_configs._test_llm(config, "sk-realistic-secret-value")

    assert result.success is False
    assert result.details == {"status_code": 401, "response_redacted": True}
    assert "sk-leaked" not in str(result.model_dump())


def test_request_boundary_rejects_localhost_base_url():
    error = model_configs._validate_config_fields(
        ModelType.LLM,
        ModelProvider.OPENAI,
        "https://localhost/v1",
        "sk-realistic-secret-value",
    )

    assert error is not None
    assert error.error_code == "[MODEL_CONFIG_ENDPOINT_POLICY_VIOLATION]"
