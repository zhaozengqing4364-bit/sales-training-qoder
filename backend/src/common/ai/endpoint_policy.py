"""Provider endpoint validation for admin model configuration tests.

This module enforces the code-owned SSRF baseline for admin-triggered provider
connectivity probes. Provider allowlists are intentionally narrow defaults that
can be wired to a managed settings surface later; the network invariants here
must remain fail-closed.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

from common.ai.models import ModelProvider


class EndpointPolicyError(ValueError):
    """Raised when an endpoint violates provider endpoint policy."""


@dataclass(frozen=True, slots=True)
class EndpointPolicy:
    provider: ModelProvider
    allowed_hosts: tuple[str, ...]
    allowed_host_suffixes: tuple[str, ...] = ()
    allowed_schemes: tuple[str, ...] = ("https",)
    timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class ValidatedEndpoint:
    """A normalized provider endpoint that passed static and DNS checks."""

    provider: ModelProvider
    base_url: str
    host: str
    timeout_seconds: float

    def child_url(self, relative_path: str) -> str:
        """Build a provider child URL without losing the configured base path."""
        return urljoin(f"{self.base_url.rstrip('/')}/", relative_path.lstrip("/"))


_PROVIDER_POLICIES: dict[ModelProvider, EndpointPolicy] = {
    ModelProvider.OPENAI: EndpointPolicy(
        provider=ModelProvider.OPENAI,
        allowed_hosts=("api.openai.com",),
    ),
    ModelProvider.AZURE: EndpointPolicy(
        provider=ModelProvider.AZURE,
        allowed_hosts=(),
        allowed_host_suffixes=(".openai.azure.com",),
    ),
    ModelProvider.ALIBABA: EndpointPolicy(
        provider=ModelProvider.ALIBABA,
        allowed_hosts=("dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"),
        allowed_schemes=("https", "wss"),
    ),
    ModelProvider.ANTHROPIC: EndpointPolicy(
        provider=ModelProvider.ANTHROPIC,
        allowed_hosts=("api.anthropic.com",),
    ),
}

_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}


def validate_provider_base_url(
    provider: ModelProvider,
    base_url: str,
    *,
    resolve_dns: bool = False,
) -> ValidatedEndpoint:
    """Validate and normalize a provider base URL.

    The validation is deliberately safe for error reporting: exceptions never
    contain API keys, userinfo, full URLs, or upstream response bodies.
    """
    policy = _policy_for(provider)
    raw_url = (base_url or "").strip()
    if not raw_url:
        raise EndpointPolicyError("Provider endpoint is required.")

    parts = urlsplit(raw_url)
    scheme = parts.scheme.lower()
    if scheme not in policy.allowed_schemes:
        raise EndpointPolicyError("Provider endpoint must use an allowed secure scheme.")

    if parts.username or parts.password:
        raise EndpointPolicyError("Provider endpoint must not contain credentials.")

    if parts.query or parts.fragment:
        raise EndpointPolicyError("Provider endpoint must not contain query or fragment.")

    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise EndpointPolicyError("Provider endpoint host is required.")

    if not _host_allowed(host, policy):
        raise EndpointPolicyError(
            f"Provider endpoint host is not allowed for provider '{provider.value}'."
        )

    if parts.port not in (None, 443):
        raise EndpointPolicyError("Provider endpoint must use the default secure port.")

    normalized_netloc = host if parts.port is None else f"{host}:{parts.port}"
    normalized = urlunsplit(
        (scheme, normalized_netloc, parts.path.rstrip("/") or "", "", "")
    )

    if resolve_dns:
        _assert_public_dns_resolution(host, parts.port or 443)

    return ValidatedEndpoint(
        provider=provider,
        base_url=normalized,
        host=host,
        timeout_seconds=policy.timeout_seconds,
    )


def validate_redirect_location(
    provider: ModelProvider,
    base_url: str,
    location: str,
    *,
    resolve_dns: bool = False,
) -> None:
    """Validate a redirect target while keeping redirects disabled by default."""
    if not location:
        raise EndpointPolicyError("Provider redirect target is empty.")
    absolute_location = urljoin(f"{base_url.rstrip('/')}/", location)
    validate_provider_base_url(
        provider,
        absolute_location,
        resolve_dns=resolve_dns,
    )


def _policy_for(provider: ModelProvider) -> EndpointPolicy:
    policy = _PROVIDER_POLICIES.get(provider)
    if policy is None:
        raise EndpointPolicyError(
            f"Provider endpoint policy is not configured for provider '{provider.value}'."
        )
    return policy


def _host_allowed(host: str, policy: EndpointPolicy) -> bool:
    if host in policy.allowed_hosts:
        return True
    return any(host.endswith(suffix) for suffix in policy.allowed_host_suffixes)


def _assert_public_dns_resolution(host: str, port: int) -> None:
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise EndpointPolicyError("Provider endpoint DNS resolution failed.") from exc

    if not records:
        raise EndpointPolicyError("Provider endpoint DNS resolution returned no records.")

    for record in records:
        sockaddr = record[4]
        ip_text = sockaddr[0]
        ip = ipaddress.ip_address(ip_text)
        if not _is_public_provider_ip(ip):
            raise EndpointPolicyError(
                "Provider endpoint resolves to a non-public network address."
            )


def _is_public_provider_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip in _METADATA_IPS:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
