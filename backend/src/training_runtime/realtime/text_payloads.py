"""Scenario-neutral extraction of text from realtime provider payloads."""

from __future__ import annotations

from typing import Any


def extract_text_payload(data: dict[str, Any]) -> str:
    """Extract text payload with legacy fallback support."""

    text = data.get("text")
    if isinstance(text, str) and text.strip():
        return text
    legacy_text = data.get("content")
    if isinstance(legacy_text, str) and legacy_text.strip():
        return legacy_text
    return ""


def extract_response_text(response_done_event: dict[str, Any]) -> str:
    """Extract assistant text from a response.done provider payload."""

    response = response_done_event.get("response")
    if not isinstance(response, dict):
        return ""
    output = response.get("output", [])
    if not isinstance(output, list):
        return ""
    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("text"), str):
                text_parts.append(part["text"])
            elif isinstance(part.get("transcript"), str):
                text_parts.append(part["transcript"])
    return "".join(text_parts).strip()
