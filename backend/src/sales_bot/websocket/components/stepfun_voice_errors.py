from __future__ import annotations

from collections.abc import Mapping

VOICE_ERROR_KEYWORDS = (
    "voice",
    "voice_id",
    "speaker",
    "not found",
    "unavailable",
    "invalid voice",
)


def is_voice_unavailable_error(event: Mapping[str, object]) -> bool:
    text = _flatten_error_text(event).lower()
    return bool(text) and any(keyword in text for keyword in VOICE_ERROR_KEYWORDS)


def _flatten_error_text(value: object) -> str:
    if isinstance(value, Mapping):
        return " ".join(_flatten_error_text(item) for item in value.values())
    if isinstance(value, list | tuple):
        return " ".join(_flatten_error_text(item) for item in value)
    if value is None:
        return ""
    return str(value)
