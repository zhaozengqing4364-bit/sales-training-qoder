import socket

import pytest

from common.ai.endpoint_policy import (
    EndpointPolicyError,
    validate_provider_base_url,
    validate_redirect_location,
)
from common.ai.models import ModelProvider


def _addrinfo(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]


@pytest.mark.parametrize(
    "url",
    [
        "http://api.openai.com/v1",
        "https://user:pass@api.openai.com/v1",
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://[::1]/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://api.openai.com:8443/v1",
        "https://api.openai.com/v1?token=secret",
    ],
)
def test_provider_base_url_rejects_unsafe_static_inputs(url):
    with pytest.raises(EndpointPolicyError):
        validate_provider_base_url(ModelProvider.OPENAI, url)


def test_provider_base_url_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: _addrinfo("10.0.0.8")
    )

    with pytest.raises(EndpointPolicyError, match="non-public"):
        validate_provider_base_url(
            ModelProvider.OPENAI,
            "https://api.openai.com/v1",
            resolve_dns=True,
        )


def test_provider_base_url_allows_known_public_provider(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args, **kwargs: _addrinfo("93.184.216.34")
    )

    endpoint = validate_provider_base_url(
        ModelProvider.OPENAI,
        "https://api.openai.com/v1/",
        resolve_dns=True,
    )

    assert endpoint.base_url == "https://api.openai.com/v1"
    assert (
        endpoint.child_url("chat/completions")
        == "https://api.openai.com/v1/chat/completions"
    )


def test_redirect_location_reuses_provider_policy():
    with pytest.raises(EndpointPolicyError):
        validate_redirect_location(
            ModelProvider.OPENAI,
            "https://api.openai.com/v1",
            "http://169.254.169.254/latest/meta-data",
        )
