from __future__ import annotations

import ipaddress
import socket

import pytest

from common.ai.endpoint_policy import (
    EndpointPolicyError,
    validate_provider_base_url,
    validate_redirect_location,
)
from common.ai.models import ModelProvider


def _public_getaddrinfo(*args, **kwargs):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("203.0.113.10", 443),
        )
    ]


def _private_getaddrinfo(*args, **kwargs):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("127.0.0.1", 443),
        )
    ]


def test_validate_provider_base_url_normalizes_allowed_public_endpoint(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _public_getaddrinfo)

    endpoint = validate_provider_base_url(
        ModelProvider.OPENAI,
        "https://api.openai.com/v1/",
        resolve_dns=True,
    )

    assert endpoint.base_url == "https://api.openai.com/v1"
    assert endpoint.host == "api.openai.com"
    assert endpoint.timeout_seconds == 10.0


def test_validate_provider_base_url_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _private_getaddrinfo)

    with pytest.raises(EndpointPolicyError, match="non-public network address"):
        validate_provider_base_url(
            ModelProvider.OPENAI,
            "https://api.openai.com/v1",
            resolve_dns=True,
        )


def test_validate_provider_base_url_rejects_credentials_and_query():
    with pytest.raises(EndpointPolicyError, match="must not contain credentials"):
        validate_provider_base_url(
            ModelProvider.OPENAI,
            "https://user:pass@api.openai.com/v1",
            resolve_dns=False,
        )

    with pytest.raises(EndpointPolicyError, match="must not contain query or fragment"):
        validate_provider_base_url(
            ModelProvider.OPENAI,
            "https://api.openai.com/v1?token=secret",
            resolve_dns=False,
        )


def test_validate_redirect_location_rejects_private_redirect(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _private_getaddrinfo)

    with pytest.raises(EndpointPolicyError, match="non-public network address"):
        validate_redirect_location(
            ModelProvider.OPENAI,
            "https://api.openai.com/v1",
            "https://api.openai.com/v1/chat/completions",
            resolve_dns=True,
        )
