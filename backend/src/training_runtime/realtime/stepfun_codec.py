"""StepFun wire codec for the provider-neutral realtime boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from re import compile as compile_pattern
from typing import TypeAlias, Union, cast

from .provider import (
    JsonValue,
    ProviderCommand,
    ProviderCommandKind,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEvent,
    ProviderEventKind,
)

_RawJsonScalar: TypeAlias = str | int | float | bool | None
_RawJsonValue: TypeAlias = Union[  # noqa: UP007
    _RawJsonScalar,
    dict[str, "_RawJsonValue"],
    list["_RawJsonValue"],
]
_SAFE_RAW_TYPE_PATTERN = compile_pattern(r"[a-z0-9][a-z0-9._:-]{0,127}")
_MAX_RAW_JSON_DEPTH = 64


@dataclass(frozen=True, slots=True)
class _CommonEventFields:
    request_id: int | None
    response_id: str | None
    stream_id: str | None
    call_id: str | None
    event_id: str | None
    turn_id: str | None
    timestamp_ms: float | None
    duration_ms: float | None


_TRANSCRIPTION_DELTA_TYPES = frozenset(
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
_TRANSCRIPTION_FINAL_TYPES = frozenset(
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


class StepFunEventCodec:
    """Own all translation between StepFun raw JSON and canonical DTOs."""

    def encode_command(self, command: ProviderCommand) -> dict[str, JsonValue]:
        data = command.data
        raw: dict[str, _RawJsonValue]
        if command.kind is ProviderCommandKind.APPEND_AUDIO:
            raw = {
                "type": "input_audio_buffer.append",
                "audio": _to_raw_json(data["audio"]),
            }
        elif command.kind is ProviderCommandKind.COMMIT_AUDIO:
            raw = {"type": "input_audio_buffer.commit"}
        elif command.kind is ProviderCommandKind.CLEAR_AUDIO:
            raw = {"type": "input_audio_buffer.clear"}
        elif command.kind is ProviderCommandKind.CREATE_RESPONSE:
            response: dict[str, _RawJsonValue] = {
                "modalities": _to_raw_json(data["modalities"])
            }
            if "instructions" in data:
                response["instructions"] = _to_raw_json(data["instructions"])
            raw = {"type": "response.create", "response": response}
        elif command.kind is ProviderCommandKind.CANCEL_RESPONSE:
            raw = {"type": "response.cancel"}
            if "response_id" in data:
                raw["response_id"] = _to_raw_json(data["response_id"])
        elif command.kind is ProviderCommandKind.CREATE_CONVERSATION_ITEM:
            item: dict[str, _RawJsonValue] = {
                "type": "message",
                "role": _to_raw_json(data["role"]),
                "content": _to_raw_json(data["content"]),
            }
            if "item_id" in data:
                item["id"] = _to_raw_json(data["item_id"])
            raw = {"type": "conversation.item.create", "item": item}
        else:
            raw = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": _to_raw_json(data["call_id"]),
                    "output": _to_raw_json(data["output"]),
                },
            }
        return cast(dict[str, JsonValue], raw)

    def decode_event(
        self,
        raw: str | bytes,
        *,
        connection_epoch: int,
    ) -> ProviderEvent:
        try:
            payload = _decode_raw_object(raw)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
            ValueError,
            TypeError,
        ):
            return _protocol_error(connection_epoch=connection_epoch)

        event_type = payload.get("type")
        if type(event_type) is not str or not event_type:
            return _protocol_error(connection_epoch=connection_epoch)
        safe_event_type = _safe_raw_type(event_type)
        if safe_event_type == "unknown":
            return ProviderEvent(
                kind=ProviderEventKind.UNKNOWN,
                provider_event_type="unknown",
                connection_epoch=connection_epoch,
            )
        try:
            return self._decode_known(
                payload,
                event_type=safe_event_type,
                connection_epoch=connection_epoch,
            )
        except (KeyError, RecursionError, TypeError, ValueError):
            return _protocol_error(
                connection_epoch=connection_epoch,
                provider_event_type=safe_event_type,
            )

    def _decode_known(
        self,
        payload: Mapping[str, _RawJsonValue],
        *,
        event_type: str,
        connection_epoch: int,
    ) -> ProviderEvent:
        if event_type == "error":
            category, reason = _classify_error(payload)
            return ProviderEvent(
                kind=ProviderEventKind.ERROR,
                provider_event_type=event_type,
                connection_epoch=connection_epoch,
                error_category=category,
                error_reason=reason,
            )
        common = _common_event_fields(payload)
        if event_type in {"session.created", "session.updated"}:
            return _event(
                ProviderEventKind.SESSION_READY,
                event_type,
                connection_epoch,
                common=common,
            )
        if event_type == "input_audio_buffer.committed":
            return _event(
                ProviderEventKind.INPUT_AUDIO_COMMITTED,
                event_type,
                connection_epoch,
                common=common,
            )
        if event_type == "conversation.item.created":
            return _decode_conversation_item(payload, event_type, connection_epoch)
        if event_type in _TRANSCRIPTION_DELTA_TYPES:
            text = _extract_transcription_text(cast(dict[str, _RawJsonValue], payload))
            if text is None:
                raise ValueError("stepfun_transcription_delta_text_missing")
            return _event(
                ProviderEventKind.TRANSCRIPTION_DELTA,
                event_type,
                connection_epoch,
                common=common,
                data={"text": text},
            )
        if event_type in _TRANSCRIPTION_FINAL_TYPES:
            text = _extract_transcription_text(cast(dict[str, _RawJsonValue], payload))
            return _event(
                ProviderEventKind.TRANSCRIPTION_FINAL,
                event_type,
                connection_epoch,
                common=common,
                data={} if text is None else {"text": text},
            )
        if event_type == "input_audio_buffer.speech_started":
            return _event(
                ProviderEventKind.SPEECH_STARTED,
                event_type,
                connection_epoch,
                common=common,
            )
        if event_type == "input_audio_buffer.speech_stopped":
            return _event(
                ProviderEventKind.SPEECH_STOPPED,
                event_type,
                connection_epoch,
                common=common,
            )
        if event_type == "response.created":
            return _event(
                ProviderEventKind.RESPONSE_CREATED,
                event_type,
                connection_epoch,
                common=common,
            )
        if event_type == "response.text.delta":
            return _text_event(
                ProviderEventKind.RESPONSE_TEXT_DELTA,
                payload,
                event_type,
                connection_epoch,
                common,
            )
        if event_type == "response.audio_transcript.delta":
            return _text_event(
                ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
                payload,
                event_type,
                connection_epoch,
                common,
            )
        if event_type == "response.audio_transcript.done":
            text = _extract_text(payload)
            return _event(
                ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
                event_type,
                connection_epoch,
                common=common,
                data={} if text is None else {"text": text},
            )
        if event_type == "response.audio.delta":
            audio = _string_value(payload.get("delta"))
            if audio is None:
                raise ValueError("stepfun_response_audio_delta_missing")
            return _event(
                ProviderEventKind.RESPONSE_AUDIO_DELTA,
                event_type,
                connection_epoch,
                common=common,
                data={"audio": audio},
            )
        if event_type == "response.thinking.delta":
            return _text_event(
                ProviderEventKind.THINKING_DELTA,
                payload,
                event_type,
                connection_epoch,
                common,
            )
        if event_type == "response.thinking.done":
            text = _extract_thinking(payload)
            return _event(
                ProviderEventKind.THINKING_DONE,
                event_type,
                connection_epoch,
                common=common,
                data={} if text is None else {"text": text},
            )
        if event_type in {
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
        }:
            return _decode_function_arguments(
                payload,
                event_type=event_type,
                connection_epoch=connection_epoch,
                common=common,
            )
        if event_type == "response.done":
            outputs = _extract_function_outputs(payload)
            return _event(
                ProviderEventKind.RESPONSE_DONE,
                event_type,
                connection_epoch,
                common=common,
                data={} if not outputs else {"function_outputs": outputs},
            )
        return ProviderEvent(
            kind=ProviderEventKind.UNKNOWN,
            provider_event_type="unknown",
            connection_epoch=connection_epoch,
        )


def _to_raw_json(value: JsonValue) -> _RawJsonValue:
    if type(value) is float:
        if not isfinite(value):
            raise ValueError("stepfun_json_number_must_be_finite")
        return value
    if value is None or type(value) in {str, bool, int}:
        return cast(_RawJsonScalar, value)
    if isinstance(value, Mapping):
        return {key: _to_raw_json(item) for key, item in value.items()}
    sequence = cast(tuple[JsonValue, ...], value)
    return [_to_raw_json(item) for item in sequence]


def _decode_raw_object(raw: str | bytes) -> dict[str, _RawJsonValue]:
    text = raw.decode("utf-8") if type(raw) is bytes else raw
    if type(text) is not str:
        raise TypeError("stepfun_raw_event_must_be_text_or_bytes")
    decoded = cast(
        object,
        json.loads(text, parse_constant=_reject_json_constant),
    )
    if not isinstance(decoded, dict):
        raise ValueError("stepfun_raw_event_must_be_object")
    typed = cast(dict[str, _RawJsonValue], decoded)
    _validate_raw_json_depth(typed)
    return typed


def _validate_raw_json_depth(value: _RawJsonValue) -> None:
    pending: list[tuple[_RawJsonValue, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > _MAX_RAW_JSON_DEPTH:
            raise ValueError("stepfun_raw_event_depth_exceeded")
        if isinstance(current, dict):
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
        elif type(current) is float and not isfinite(current):
            raise ValueError("stepfun_raw_event_number_must_be_finite")


def _reject_json_constant(value: str) -> None:
    del value
    raise ValueError("stepfun_raw_event_constant_invalid")


def _safe_raw_type(value: str) -> str:
    return value if _SAFE_RAW_TYPE_PATTERN.fullmatch(value) is not None else "unknown"


def _protocol_error(
    *,
    connection_epoch: int,
    provider_event_type: str = "invalid",
) -> ProviderEvent:
    return ProviderEvent(
        kind=ProviderEventKind.ERROR,
        provider_event_type=_safe_raw_type(provider_event_type),
        connection_epoch=connection_epoch,
        error_category=ProviderErrorCategory.PROTOCOL,
        error_reason=ProviderErrorReason.INVALID_EVENT,
    )


def _event(
    kind: ProviderEventKind,
    provider_event_type: str,
    connection_epoch: int,
    *,
    common: _CommonEventFields,
    data: Mapping[str, object] | None = None,
) -> ProviderEvent:
    return ProviderEvent(
        kind=kind,
        provider_event_type=provider_event_type,
        connection_epoch=connection_epoch,
        request_id=common.request_id,
        response_id=common.response_id,
        stream_id=common.stream_id,
        call_id=common.call_id,
        event_id=common.event_id,
        turn_id=common.turn_id,
        timestamp_ms=common.timestamp_ms,
        duration_ms=common.duration_ms,
        data=cast(Mapping[str, JsonValue], data or {}),
    )


def _common_event_fields(
    payload: Mapping[str, _RawJsonValue],
) -> _CommonEventFields:
    response = _mapping(payload.get("response"))
    item = _mapping(payload.get("item"))
    timestamp = _optional_number(payload, "timestamp_ms")
    if timestamp is None:
        timestamp = _optional_number(payload, "created_at_ms")
    duration = _optional_number(payload, "duration_ms")
    if duration is None:
        duration = _optional_number(payload, "audio_duration_ms")
    if duration is None:
        start = _optional_number(payload, "speech_started_at_ms")
        stop = _optional_number(payload, "speech_stopped_at_ms")
        if start is not None and stop is not None:
            duration = max(0.0, stop - start)
    return _CommonEventFields(
        request_id=_optional_integer(payload, "request_id"),
        response_id=_first_identifier(
            payload.get("response_id"),
            response.get("id"),
        ),
        stream_id=_optional_identifier(payload, "stream_id"),
        call_id=_first_identifier(payload.get("call_id"), item.get("call_id")),
        event_id=_first_identifier(payload.get("event_id"), payload.get("id")),
        turn_id=_first_identifier(payload.get("turn_id"), payload.get("item_id")),
        timestamp_ms=timestamp,
        duration_ms=duration,
    )


def _optional_identifier(
    payload: Mapping[str, _RawJsonValue],
    key: str,
) -> str | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if type(value) is not str or not value.strip():
        raise ValueError(f"stepfun_{key}_must_be_non_empty_string")
    return value


def _first_identifier(*values: _RawJsonValue | None) -> str | None:
    for value in values:
        if value is None:
            continue
        if type(value) is not str or not value.strip():
            raise ValueError("stepfun_identifier_must_be_non_empty_string")
        return value
    return None


def _optional_integer(
    payload: Mapping[str, _RawJsonValue],
    key: str,
) -> int | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if type(value) is not int or value < 0:
        raise ValueError(f"stepfun_{key}_must_be_non_negative_integer")
    return value


def _optional_number(
    payload: Mapping[str, _RawJsonValue],
    key: str,
) -> int | float | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if type(value) not in {int, float}:
        raise ValueError(f"stepfun_{key}_must_be_non_negative_number")
    number = cast(int | float, value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"stepfun_{key}_must_be_non_negative_number")
    return number


def _mapping(value: _RawJsonValue | None) -> dict[str, _RawJsonValue]:
    return value if isinstance(value, dict) else {}


def _string_value(value: _RawJsonValue | None) -> str | None:
    if type(value) is str:
        return value
    if isinstance(value, dict):
        nested = value.get("text")
        return nested if type(nested) is str else None
    return None


def _extract_text(
    payload: Mapping[str, _RawJsonValue],
    *,
    prefer_delta: bool = False,
) -> str | None:
    keys = (
        ("delta", "text", "transcript")
        if prefer_delta
        else (
            "transcript",
            "text",
            "delta",
        )
    )
    for key in keys:
        if key in payload:
            value = _string_value(payload[key])
            if value is not None:
                return value
    for container_key in ("item", "content"):
        text = _extract_text_from_container(payload.get(container_key))
        if text is not None:
            return text
    return _extract_text_from_response(payload.get("response"))


def _extract_transcription_text(payload: _RawJsonValue) -> str | None:
    """Match the legacy StepFun/OpenAI-style nested ASR extractor."""

    return _extract_text_from_keys(
        payload,
        text_keys=("transcript", "text", "audio_transcript", "stash", "delta"),
        container_keys=(
            "item",
            "content",
            "parts",
            "part",
            "transcription",
            "input_audio_transcription",
            "audio",
        ),
        max_depth=5,
    )


def _extract_text_from_keys(
    payload: _RawJsonValue,
    *,
    text_keys: tuple[str, ...],
    container_keys: tuple[str, ...],
    max_depth: int,
) -> str | None:
    if max_depth < 0:
        return None
    if type(payload) is str:
        return payload if payload.strip() else None
    if isinstance(payload, list):
        for item in payload:
            extracted = _extract_text_from_keys(
                item,
                text_keys=text_keys,
                container_keys=container_keys,
                max_depth=max_depth - 1,
            )
            if extracted is not None and extracted.strip():
                return extracted
        return None
    if not isinstance(payload, dict):
        return None
    for key in text_keys:
        candidate = payload.get(key)
        if type(candidate) is str and candidate.strip():
            return candidate
        if isinstance(candidate, (dict, list)):
            extracted = _extract_text_from_keys(
                candidate,
                text_keys=text_keys,
                container_keys=container_keys,
                max_depth=max_depth - 1,
            )
            if extracted is not None and extracted.strip():
                return extracted
    for key in container_keys:
        if key not in payload:
            continue
        extracted = _extract_text_from_keys(
            payload[key],
            text_keys=text_keys,
            container_keys=container_keys,
            max_depth=max_depth - 1,
        )
        if extracted is not None and extracted.strip():
            return extracted
    return None


def _extract_text_from_container(value: _RawJsonValue | None) -> str | None:
    if isinstance(value, dict):
        for key in ("transcript", "text"):
            if key in value:
                text = _string_value(value[key])
                if text is not None:
                    return text
        return _extract_text_from_container(value.get("content"))
    if isinstance(value, list):
        parts: list[str] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            text = _extract_text_from_container(entry)
            if text is None:
                audio = entry.get("audio")
                text = _extract_text_from_container(audio)
            if text is not None:
                parts.append(text)
        return "".join(parts) if parts else None
    return None


def _extract_text_from_response(value: _RawJsonValue | None) -> str | None:
    if not isinstance(value, dict):
        return None
    direct = _extract_text_from_container(value)
    if direct is not None:
        return direct
    output = value.get("output")
    if not isinstance(output, list):
        return None
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        text = _extract_text_from_container(item.get("content"))
        if text is not None:
            parts.append(text)
    return "".join(parts).strip() if parts else None


def _extract_thinking(payload: Mapping[str, _RawJsonValue]) -> str | None:
    thinking = _string_value(payload.get("thinking"))
    if thinking is not None:
        return thinking
    response = _mapping(payload.get("response"))
    return _string_value(response.get("thinking"))


def _text_event(
    kind: ProviderEventKind,
    payload: Mapping[str, _RawJsonValue],
    event_type: str,
    connection_epoch: int,
    common: _CommonEventFields,
) -> ProviderEvent:
    text = _extract_text(payload, prefer_delta=True)
    if text is None:
        raise ValueError("stepfun_text_delta_missing")
    return _event(
        kind,
        event_type,
        connection_epoch,
        common=common,
        data={"text": text},
    )


def _decode_conversation_item(
    payload: Mapping[str, _RawJsonValue],
    event_type: str,
    connection_epoch: int,
) -> ProviderEvent:
    item = _mapping(payload.get("item"))
    item_type = _string_value(item.get("type"))
    if item_type is None or not item_type:
        raise ValueError("stepfun_conversation_item_type_missing")
    data: dict[str, object] = {"item_type": item_type}
    for key in ("role", "name", "arguments", "transcript"):
        value = _string_value(item.get(key))
        if value is not None:
            data[key] = value
    content = item.get("content")
    if isinstance(content, list):
        normalized: list[dict[str, object]] = []
        for entry in content:
            if not isinstance(entry, dict):
                continue
            entry_type = _string_value(entry.get("type"))
            if entry_type is None or not entry_type:
                continue
            normalized_entry: dict[str, object] = {"type": entry_type}
            for key in ("text", "transcript", "audio"):
                value = _string_value(entry.get(key))
                if value is not None:
                    normalized_entry[key] = value
            if "transcript" not in normalized_entry:
                nested_transcript = _extract_text_from_container(entry.get("audio"))
                if nested_transcript is not None:
                    normalized_entry["transcript"] = nested_transcript
            normalized.append(normalized_entry)
        data["content"] = normalized
    transcript = _extract_text_from_container(item)
    if transcript is not None and "transcript" not in data:
        data["transcript"] = transcript
    return _event(
        ProviderEventKind.CONVERSATION_ITEM,
        event_type,
        connection_epoch,
        common=_common_event_fields(payload),
        data=data,
    )


def _decode_function_arguments(
    payload: Mapping[str, _RawJsonValue],
    *,
    event_type: str,
    connection_epoch: int,
    common: _CommonEventFields,
) -> ProviderEvent:
    value = (
        payload.get("delta")
        if event_type.endswith(".delta")
        else payload.get("arguments")
    )
    if isinstance(value, dict):
        arguments = json.dumps(value, ensure_ascii=False, allow_nan=False)
    elif type(value) is str:
        arguments = value
    elif value is None:
        arguments = ""
    else:
        raise ValueError("stepfun_function_arguments_invalid")
    data: dict[str, object] = {"arguments": arguments}
    name = _string_value(payload.get("name"))
    if name is not None:
        data["name"] = name
    kind = (
        ProviderEventKind.FUNCTION_ARGUMENTS_DELTA
        if event_type.endswith(".delta")
        else ProviderEventKind.FUNCTION_ARGUMENTS_DONE
    )
    return _event(
        kind,
        event_type,
        connection_epoch,
        common=common,
        data=data,
    )


def _extract_function_outputs(
    payload: Mapping[str, _RawJsonValue],
) -> list[dict[str, object]]:
    response = _mapping(payload.get("response"))
    output = response.get("output")
    if not isinstance(output, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        call_id = _string_value(item.get("call_id"))
        if call_id is None or not call_id:
            continue
        name = _string_value(item.get("name")) or "unknown"
        arguments_value = item.get("arguments")
        if isinstance(arguments_value, dict):
            arguments = json.dumps(
                arguments_value,
                ensure_ascii=False,
                allow_nan=False,
            )
        elif type(arguments_value) is str:
            arguments = arguments_value
        else:
            arguments = "{}"
        normalized.append({"call_id": call_id, "name": name, "arguments": arguments})
    return normalized


def _classify_error(
    payload: Mapping[str, _RawJsonValue],
) -> tuple[ProviderErrorCategory, ProviderErrorReason]:
    error = _mapping(payload.get("error"))
    status = _first_integer(
        error.get("status"),
        error.get("status_code"),
        error.get("code"),
        payload.get("status"),
        payload.get("status_code"),
    )
    if status == 401:
        return (
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.INVALID_CREDENTIALS,
        )
    if status == 402:
        return ProviderErrorCategory.QUOTA, ProviderErrorReason.QUOTA_EXHAUSTED
    if status == 403:
        return ProviderErrorCategory.AUTHENTICATION, ProviderErrorReason.FORBIDDEN
    if status == 429:
        return ProviderErrorCategory.RATE_LIMIT, ProviderErrorReason.RATE_LIMITED
    code = _first_code(error.get("code"), payload.get("code"))
    reason_map = {
        "invalid_credentials": (
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.INVALID_CREDENTIALS,
        ),
        "forbidden": (
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.FORBIDDEN,
        ),
        "quota_exhausted": (
            ProviderErrorCategory.QUOTA,
            ProviderErrorReason.QUOTA_EXHAUSTED,
        ),
        "rate_limited": (
            ProviderErrorCategory.RATE_LIMIT,
            ProviderErrorReason.RATE_LIMITED,
        ),
        "asr_unavailable": (
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.ASR_UNAVAILABLE,
        ),
        "voice_unavailable": (
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.VOICE_UNAVAILABLE,
        ),
        "idle_timeout": (
            ProviderErrorCategory.TIMEOUT,
            ProviderErrorReason.IDLE_TIMEOUT,
        ),
        "upstream_unavailable": (
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.UPSTREAM_UNAVAILABLE,
        ),
        "connection_closed": (
            ProviderErrorCategory.DISCONNECTED,
            ProviderErrorReason.CONNECTION_CLOSED,
        ),
        "invalid_event": (
            ProviderErrorCategory.PROTOCOL,
            ProviderErrorReason.INVALID_EVENT,
        ),
    }
    return reason_map.get(
        code,
        (ProviderErrorCategory.UNAVAILABLE, ProviderErrorReason.UNKNOWN),
    )


def _first_integer(*values: _RawJsonValue | None) -> int | None:
    for value in values:
        if type(value) is int:
            return value
    return None


def _first_code(*values: _RawJsonValue | None) -> str:
    for value in values:
        if type(value) is str:
            return value.strip().lower().replace("-", "_").replace(".", "_")
    return ""


__all__ = ["StepFunEventCodec"]
