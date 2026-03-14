"""Routing helpers for StepFun upstream websocket events."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class UpstreamEventRoute(StrEnum):
    """Normalized route key for upstream event handling."""

    IGNORE = "ignore"
    CONVERSATION_ITEM_CREATED = "conversation_item_created"
    TRANSCRIPTION_DELTA = "transcription_delta"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    RESPONSE_CREATED = "response_created"
    RESPONSE_TEXT_DELTA = "response_text_delta"
    FUNCTION_ARGUMENTS_DELTA = "function_arguments_delta"
    FUNCTION_ARGUMENTS_DONE = "function_arguments_done"
    RESPONSE_AUDIO_DELTA = "response_audio_delta"
    RESPONSE_DONE = "response_done"
    ERROR = "error"
    UNHANDLED = "unhandled"


_IGNORED_EVENT_TYPES = frozenset({"session.created", "session.updated"})
_TRANSCRIPTION_DELTA_EVENT_TYPES = frozenset(
    {
        "conversation.item.input_audio_transcription.delta",
        "conversation.item.input_audio_transcription.text",
        "conversation.item.input_audio_transcript.delta",
        "conversation.item.input_audio_transcript.text",
        "input_audio_buffer.transcription.delta",
        "input_audio_buffer.transcription.text",
        "input_audio_buffer.transcript.delta",
        "input_audio_buffer.transcript.text",
    }
)
_TRANSCRIPTION_COMPLETED_EVENT_TYPES = frozenset(
    {
        "conversation.item.input_audio_transcription.completed",
        "conversation.item.input_audio_transcription.done",
        "conversation.item.input_audio_transcription.final",
        "conversation.item.input_audio_transcript.completed",
        "conversation.item.input_audio_transcript.done",
        "conversation.item.input_audio_transcript.final",
        "input_audio_buffer.transcription.completed",
        "input_audio_buffer.transcription.done",
        "input_audio_buffer.transcription.final",
        "input_audio_buffer.transcript.completed",
        "input_audio_buffer.transcript.done",
        "input_audio_buffer.transcript.final",
    }
)
_RESPONSE_TEXT_DELTA_EVENT_TYPES = frozenset(
    {"response.text.delta", "response.audio_transcript.delta"}
)


def classify_upstream_event(event_type: str) -> UpstreamEventRoute:
    """Map raw upstream event type to a stable handling route."""
    if event_type in _IGNORED_EVENT_TYPES:
        return UpstreamEventRoute.IGNORE
    if event_type == "conversation.item.created":
        return UpstreamEventRoute.CONVERSATION_ITEM_CREATED
    if event_type in _TRANSCRIPTION_DELTA_EVENT_TYPES:
        return UpstreamEventRoute.TRANSCRIPTION_DELTA
    if event_type in _TRANSCRIPTION_COMPLETED_EVENT_TYPES:
        return UpstreamEventRoute.TRANSCRIPTION_COMPLETED
    if event_type == "response.created":
        return UpstreamEventRoute.RESPONSE_CREATED
    if event_type in _RESPONSE_TEXT_DELTA_EVENT_TYPES:
        return UpstreamEventRoute.RESPONSE_TEXT_DELTA
    if event_type == "response.function_call_arguments.delta":
        return UpstreamEventRoute.FUNCTION_ARGUMENTS_DELTA
    if event_type == "response.function_call_arguments.done":
        return UpstreamEventRoute.FUNCTION_ARGUMENTS_DONE
    if event_type == "response.audio.delta":
        return UpstreamEventRoute.RESPONSE_AUDIO_DELTA
    if event_type == "response.done":
        return UpstreamEventRoute.RESPONSE_DONE
    if event_type == "error":
        return UpstreamEventRoute.ERROR
    return UpstreamEventRoute.UNHANDLED


def extract_function_call_from_item_created(
    event: dict[str, Any],
) -> tuple[str, str] | None:
    """Extract function-call identifiers from conversation.item.created event."""
    item = event.get("item", {}) if isinstance(event.get("item"), dict) else {}
    if item.get("type") != "function_call":
        return None

    call_id = str(item.get("call_id") or "")
    name = str(item.get("name") or "")
    if not call_id or not name:
        return None
    return call_id, name


def extract_response_done_function_calls(
    response_done_event: dict[str, Any],
) -> list[dict[str, str]]:
    """Extract function-call outputs from `response.done` payload."""
    response = response_done_event.get("response")
    if not isinstance(response, dict):
        return []

    output_items = response.get("output", [])
    if not isinstance(output_items, list):
        return []

    function_calls: list[dict[str, str]] = []
    for output in output_items:
        if not isinstance(output, dict):
            continue
        if output.get("type") != "function_call":
            continue
        function_calls.append(
            {
                "call_id": str(output.get("call_id") or ""),
                "name": str(output.get("name") or "unknown"),
                "arguments": str(output.get("arguments") or "{}"),
            }
        )

    return function_calls


def extract_error_message(event: dict[str, Any]) -> str:
    """Extract fallback-safe error message from upstream error event."""
    error_obj = event.get("error")
    if isinstance(error_obj, dict):
        nested_detail = error_obj.get("message")
        if isinstance(nested_detail, str) and nested_detail.strip():
            return nested_detail
    detail = event.get("message")
    if isinstance(detail, str) and detail.strip():
        return detail
    return "Realtime 服务返回错误"
