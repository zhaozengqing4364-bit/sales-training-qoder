"""Utilities for extracting and formatting W3C trace context headers."""

from __future__ import annotations

import re
import secrets
from collections.abc import Mapping

TRACEPARENT_RE = re.compile(
    r"^(?P<version>[a-f0-9]{2})-(?P<trace_id>[a-f0-9]{32})-(?P<span_id>[a-f0-9]{16})-(?P<flags>[a-f0-9]{2})$"
)


def generate_trace_id() -> str:
    """Generate a W3C-compatible trace id."""

    return secrets.token_hex(16)


def normalize_trace_id(value: str | None) -> str | None:
    """Normalize UUID-like or hex trace ids into 32 lowercase hex chars."""

    if not value:
        return None

    normalized = value.strip().lower().replace("-", "")
    if len(normalized) != 32:
        return None
    if normalized == "0" * 32:
        return None
    if not re.fullmatch(r"[a-f0-9]{32}", normalized):
        return None
    return normalized


def extract_trace_id_from_traceparent(traceparent: str | None) -> str | None:
    """Return the trace id from a valid W3C traceparent header."""

    if not traceparent:
        return None

    match = TRACEPARENT_RE.fullmatch(traceparent.strip().lower())
    if not match:
        return None

    trace_id = match.group("trace_id")
    return None if trace_id == "0" * 32 else trace_id


def build_traceparent(trace_id: str | None) -> str | None:
    """Build a traceparent header when the trace id is valid."""

    normalized_trace_id = normalize_trace_id(trace_id)
    if not normalized_trace_id:
        return None

    span_id = secrets.token_hex(8)
    return f"00-{normalized_trace_id}-{span_id}-01"


def get_header_value(headers: Mapping[str, str], key: str) -> str | None:
    """Read a header from a case-insensitive header mapping."""

    for candidate, value in headers.items():
        if candidate.lower() == key.lower():
            return value
    return None


def resolve_trace_headers(
    headers: Mapping[str, str],
) -> tuple[str | None, str | None, str | None]:
    """Resolve trace id, response traceparent and tracestate from request headers."""

    incoming_traceparent = get_header_value(headers, "traceparent")
    trace_id = extract_trace_id_from_traceparent(incoming_traceparent)
    if not trace_id:
        trace_id = normalize_trace_id(get_header_value(headers, "x-trace-id"))

    tracestate = get_header_value(headers, "tracestate")
    response_traceparent = incoming_traceparent or build_traceparent(trace_id)
    return trace_id, response_traceparent, tracestate
