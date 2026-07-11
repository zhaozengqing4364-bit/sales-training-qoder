"""Closed provider-neutral contracts for realtime session I/O."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from re import compile as compile_pattern
from typing import Protocol, Self, TypeAlias, Union, cast, runtime_checkable

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = Union[  # noqa: UP007
    JsonScalar,
    "FrozenJsonMapping",
    tuple["JsonValue", ...],
]
_JsonInputValue: TypeAlias = (
    JsonScalar
    | Mapping[str, "_JsonInputValue"]
    | list["_JsonInputValue"]
    | tuple["_JsonInputValue", ...]
)
_PROVIDER_EVENT_TYPE_PATTERN = compile_pattern(r"[a-z0-9][a-z0-9._:-]{0,127}")


class FrozenJsonMapping(Mapping[str, JsonValue]):
    """Recursively frozen JSON object with normal ``Mapping`` semantics."""

    __slots__ = ("_items",)
    _items: tuple[tuple[str, JsonValue], ...]

    def __init__(self, source: Mapping[str, _JsonInputValue] | None = None) -> None:
        items: list[tuple[str, JsonValue]] = []
        for key, value in (source or {}).items():
            if type(key) is not str:
                raise ValueError("json_mapping_key_must_be_string")
            items.append((key, _freeze_json_value(value)))
        object.__setattr__(self, "_items", tuple(items))

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("FrozenJsonMapping is immutable")

    def __getitem__(self, key: str) -> JsonValue:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _value in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        return dict(self.items()) == dict(other.items())

    def __repr__(self) -> str:
        return f"FrozenJsonMapping(keys={tuple(self)!r})"

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        del memo
        return self


def _freeze_json_value(value: object) -> JsonValue:
    if value is None or type(value) in {str, bool, int}:
        return value  # type: ignore[return-value]
    if type(value) is float:
        if not isfinite(value):
            raise ValueError("json_number_must_be_finite")
        return value
    if isinstance(value, Mapping):
        return FrozenJsonMapping(value)
    if type(value) in {list, tuple}:
        sequence = cast(list[object] | tuple[object, ...], value)
        return tuple(_freeze_json_value(item) for item in sequence)
    raise ValueError("json_value_type_invalid")


class _ImmutableValue:
    __slots__ = ()

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        del memo
        return self


class ProviderCapability(StrEnum):
    TEXT = "text"
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"
    INPUT_TRANSCRIPTION = "input_transcription"
    FUNCTION_TOOLS = "function_tools"
    SERVER_VAD = "server_vad"
    HEALTH_CHECK = "health_check"
    RECONNECT = "reconnect"


class ProviderCommandKind(StrEnum):
    APPEND_AUDIO = "append_audio"
    COMMIT_AUDIO = "commit_audio"
    CLEAR_AUDIO = "clear_audio"
    CREATE_RESPONSE = "create_response"
    CANCEL_RESPONSE = "cancel_response"
    CREATE_CONVERSATION_ITEM = "create_conversation_item"
    TOOL_OUTPUT = "tool_output"


class ProviderEventKind(StrEnum):
    SESSION_READY = "session_ready"
    INPUT_AUDIO_COMMITTED = "input_audio_committed"
    CONVERSATION_ITEM = "conversation_item"
    TRANSCRIPTION_DELTA = "transcription_delta"
    TRANSCRIPTION_FINAL = "transcription_final"
    SPEECH_STARTED = "speech_started"
    SPEECH_STOPPED = "speech_stopped"
    RESPONSE_CREATED = "response_created"
    RESPONSE_TEXT_DELTA = "response_text_delta"
    RESPONSE_TRANSCRIPT_DELTA = "response_transcript_delta"
    RESPONSE_TRANSCRIPT_FINAL = "response_transcript_final"
    RESPONSE_AUDIO_DELTA = "response_audio_delta"
    THINKING_DELTA = "thinking_delta"
    THINKING_DONE = "thinking_done"
    FUNCTION_ARGUMENTS_DELTA = "function_arguments_delta"
    FUNCTION_ARGUMENTS_DONE = "function_arguments_done"
    RESPONSE_DONE = "response_done"
    ERROR = "error"
    UNKNOWN = "unknown"


class ProviderErrorCategory(StrEnum):
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    PROTOCOL = "protocol"
    BACKPRESSURE = "backpressure"
    DISCONNECTED = "disconnected"


class ProviderErrorReason(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    FORBIDDEN = "forbidden"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    ASR_UNAVAILABLE = "asr_unavailable"
    VOICE_UNAVAILABLE = "voice_unavailable"
    IDLE_TIMEOUT = "idle_timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INVALID_EVENT = "invalid_event"
    CONNECTION_CLOSED = "connection_closed"
    BACKPRESSURE_LIMIT = "backpressure_limit"
    UNKNOWN = "unknown"


_REASON_CATEGORIES: dict[ProviderErrorReason, frozenset[ProviderErrorCategory]] = {
    ProviderErrorReason.INVALID_CREDENTIALS: frozenset(
        {ProviderErrorCategory.AUTHENTICATION}
    ),
    ProviderErrorReason.FORBIDDEN: frozenset({ProviderErrorCategory.AUTHENTICATION}),
    ProviderErrorReason.QUOTA_EXHAUSTED: frozenset({ProviderErrorCategory.QUOTA}),
    ProviderErrorReason.RATE_LIMITED: frozenset({ProviderErrorCategory.RATE_LIMIT}),
    ProviderErrorReason.ASR_UNAVAILABLE: frozenset({ProviderErrorCategory.UNAVAILABLE}),
    ProviderErrorReason.VOICE_UNAVAILABLE: frozenset(
        {ProviderErrorCategory.UNAVAILABLE}
    ),
    ProviderErrorReason.IDLE_TIMEOUT: frozenset({ProviderErrorCategory.TIMEOUT}),
    ProviderErrorReason.UPSTREAM_UNAVAILABLE: frozenset(
        {ProviderErrorCategory.UNAVAILABLE}
    ),
    ProviderErrorReason.INVALID_EVENT: frozenset({ProviderErrorCategory.PROTOCOL}),
    ProviderErrorReason.CONNECTION_CLOSED: frozenset(
        {ProviderErrorCategory.DISCONNECTED}
    ),
    ProviderErrorReason.BACKPRESSURE_LIMIT: frozenset(
        {ProviderErrorCategory.BACKPRESSURE}
    ),
    ProviderErrorReason.UNKNOWN: frozenset(ProviderErrorCategory),
}


def _require_enum(value: object, enum_type: type[StrEnum], field_name: str) -> None:
    if type(value) is not enum_type:
        raise ValueError(f"{field_name}_must_be_enum")


def _require_string(
    value: object, field_name: str, *, allow_empty: bool = False
) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name}_must_be_string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{field_name}_must_be_non_empty")
    return value


def _require_optional_string(value: object, field_name: str) -> None:
    if value is not None:
        _require_string(value, field_name)


def _require_boolean(value: object, field_name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field_name}_must_be_boolean")


def _require_non_negative_integer(
    value: object,
    field_name: str,
    *,
    optional: bool = False,
) -> None:
    if optional and value is None:
        return
    if type(value) is not int:
        raise ValueError(f"{field_name}_must_be_integer")
    if value < 0:
        raise ValueError(f"{field_name}_must_be_non_negative")


def _require_non_negative_number(
    value: object,
    field_name: str,
    *,
    optional: bool = False,
) -> None:
    if optional and value is None:
        return
    if type(value) not in {int, float}:
        raise ValueError(f"{field_name}_must_be_number")
    number = cast(int | float, value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field_name}_must_be_non_negative_finite")


def _validate_error_pair(
    category: ProviderErrorCategory,
    reason: ProviderErrorReason,
) -> None:
    _require_enum(category, ProviderErrorCategory, "provider_error_category")
    _require_enum(reason, ProviderErrorReason, "provider_error_reason")
    if category not in _REASON_CATEGORIES[reason]:
        raise ValueError("provider_error_category_reason_mismatch")


def _validate_result_error_fields(
    *,
    successful: bool,
    category: ProviderErrorCategory | None,
    reason: ProviderErrorReason | None,
    prefix: str,
) -> None:
    _require_boolean(successful, f"{prefix}_successful")
    if successful:
        if category is not None or reason is not None:
            raise ValueError(f"{prefix}_success_error_fields_forbidden")
        return
    if category is None or reason is None:
        raise ValueError(f"{prefix}_failure_error_fields_required")
    _validate_error_pair(category, reason)


def _freeze_mapping(value: object, field_name: str) -> FrozenJsonMapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_must_be_mapping")
    return FrozenJsonMapping(value)


def _require_tuple_of_strings(
    value: object,
    field_name: str,
    *,
    allowed: frozenset[str] | None = None,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field_name}_must_be_tuple")
    if not allow_empty and not value:
        raise ValueError(f"{field_name}_must_be_non_empty")
    validated: list[str] = []
    for item in value:
        validated_item = _require_string(item, f"{field_name}_item")
        if allowed is not None and validated_item not in allowed:
            raise ValueError(f"{field_name}_item_unsupported")
        validated.append(validated_item)
    if len(validated) != len(set(validated)):
        raise ValueError(f"{field_name}_items_must_be_unique")
    return tuple(validated)


@dataclass(frozen=True, slots=True)
class RealtimeProviderCapabilities(_ImmutableValue):
    supported: frozenset[ProviderCapability]
    input_audio_formats: tuple[str, ...] | None = None
    output_audio_formats: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if type(self.supported) is not frozenset:
            raise ValueError("provider_supported_capabilities_must_be_frozenset")
        for capability in self.supported:
            _require_enum(
                capability,
                ProviderCapability,
                "provider_supported_capability",
            )
        for field_name in ("input_audio_formats", "output_audio_formats"):
            formats = getattr(self, field_name)
            if formats is None:
                continue
            object.__setattr__(
                self,
                field_name,
                _require_tuple_of_strings(
                    formats,
                    f"provider_{field_name}",
                ),
            )


@dataclass(frozen=True, slots=True, repr=False)
class RealtimeProviderSessionConfig(_ImmutableValue):
    model: str
    voice: str
    temperature: float
    input_audio_format: str
    output_audio_format: str
    modalities: tuple[str, ...]
    turn_detection: Mapping[str, JsonValue] | None
    input_transcription_enabled: bool
    input_transcription_language: str
    input_transcription_model: str
    instructions: str
    tools: tuple[Mapping[str, JsonValue], ...]

    def __post_init__(self) -> None:
        _require_string(self.model, "provider_model")
        _require_string(self.voice, "provider_voice")
        if type(self.temperature) not in {int, float}:
            raise ValueError("provider_temperature_must_be_number")
        if not isfinite(self.temperature) or self.temperature < 0:
            raise ValueError("provider_temperature_must_be_non_negative_finite")
        _require_string(self.input_audio_format, "provider_input_audio_format")
        _require_string(self.output_audio_format, "provider_output_audio_format")
        object.__setattr__(
            self,
            "modalities",
            _require_tuple_of_strings(
                self.modalities,
                "provider_modalities",
                allowed=frozenset({"text", "audio"}),
            ),
        )
        if self.turn_detection is not None:
            frozen_turn_detection = _freeze_mapping(
                self.turn_detection,
                "provider_turn_detection",
            )
            if "type" in frozen_turn_detection:
                _require_string(
                    frozen_turn_detection["type"],
                    "provider_turn_detection_type",
                )
            object.__setattr__(self, "turn_detection", frozen_turn_detection)
        _require_boolean(
            self.input_transcription_enabled,
            "provider_input_transcription_enabled",
        )
        _require_string(
            self.input_transcription_language,
            "provider_input_transcription_language",
            allow_empty=not self.input_transcription_enabled,
        )
        _require_string(
            self.input_transcription_model,
            "provider_input_transcription_model",
            allow_empty=not self.input_transcription_enabled,
        )
        _require_string(self.instructions, "provider_instructions", allow_empty=True)
        if type(self.tools) is not tuple:
            raise ValueError("provider_tools_must_be_tuple")
        object.__setattr__(
            self,
            "tools",
            tuple(_freeze_mapping(tool, "provider_tool") for tool in self.tools),
        )

    def required_capabilities(self) -> frozenset[ProviderCapability]:
        required = {ProviderCapability.AUDIO_INPUT}
        if "text" in self.modalities:
            required.add(ProviderCapability.TEXT)
        if "audio" in self.modalities:
            required.add(ProviderCapability.AUDIO_OUTPUT)
        if self.input_transcription_enabled:
            required.add(ProviderCapability.INPUT_TRANSCRIPTION)
        if self.tools:
            required.add(ProviderCapability.FUNCTION_TOOLS)
        if (
            self.turn_detection is not None
            and self.turn_detection.get("type") == "server_vad"
        ):
            required.add(ProviderCapability.SERVER_VAD)
        return frozenset(required)

    def __repr__(self) -> str:
        return (
            "RealtimeProviderSessionConfig("
            f"model={self.model!r}, voice={self.voice!r}, "
            f"temperature={self.temperature!r}, "
            f"input_audio_format={self.input_audio_format!r}, "
            f"output_audio_format={self.output_audio_format!r}, "
            f"modalities={self.modalities!r}, "
            f"turn_detection={self.turn_detection!r}, "
            f"input_transcription_enabled={self.input_transcription_enabled!r}, "
            f"input_transcription_language={self.input_transcription_language!r}, "
            f"input_transcription_model={self.input_transcription_model!r}, "
            "instructions='<redacted>', "
            f"tools='<redacted:{len(self.tools)}>'"
            ")"
        )


def validate_provider_capabilities(
    *,
    capabilities: RealtimeProviderCapabilities,
    config: RealtimeProviderSessionConfig,
) -> None:
    """Fail closed when a provider cannot satisfy one frozen session config."""

    missing = config.required_capabilities() - capabilities.supported
    input_format_mismatch = (
        capabilities.input_audio_formats is not None
        and config.input_audio_format not in capabilities.input_audio_formats
    )
    output_format_mismatch = (
        capabilities.output_audio_formats is not None
        and config.output_audio_format not in capabilities.output_audio_formats
    )
    if missing or input_format_mismatch or output_format_mismatch:
        raise RealtimeProviderError(
            category=ProviderErrorCategory.PROTOCOL,
            reason=ProviderErrorReason.INVALID_EVENT,
            retryable=False,
        )


@dataclass(frozen=True, slots=True)
class ProviderSendResult(_ImmutableValue):
    accepted: bool
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

    def __post_init__(self) -> None:
        _validate_result_error_fields(
            successful=self.accepted,
            category=self.error_category,
            reason=self.error_reason,
            prefix="provider_send",
        )


@dataclass(frozen=True, slots=True)
class ProviderHealthResult(_ImmutableValue):
    healthy: bool
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

    def __post_init__(self) -> None:
        _validate_result_error_fields(
            successful=self.healthy,
            category=self.error_category,
            reason=self.error_reason,
            prefix="provider_health",
        )


@dataclass(frozen=True, slots=True)
class ProviderBackpressureResult(_ImmutableValue):
    accepted: bool
    error_reason: ProviderErrorReason | None = None

    def __post_init__(self) -> None:
        _require_boolean(self.accepted, "provider_backpressure_accepted")
        if self.accepted:
            if self.error_reason is not None:
                raise ValueError("provider_backpressure_success_error_reason_forbidden")
            return
        if self.error_reason is not ProviderErrorReason.BACKPRESSURE_LIMIT:
            raise ValueError("provider_backpressure_failure_reason_invalid")


class RealtimeProviderError(RuntimeError):
    category: ProviderErrorCategory
    reason: ProviderErrorReason
    retryable: bool

    def __init__(
        self,
        *,
        category: ProviderErrorCategory,
        reason: ProviderErrorReason,
        retryable: bool,
    ) -> None:
        _validate_error_pair(category, reason)
        if type(retryable) is not bool:
            raise ValueError("provider_error_retryable_must_be_boolean")
        self.category = category
        self.reason = reason
        self.retryable = retryable
        super().__init__(f"realtime_provider_error:{category.value}:{reason.value}")

    def __repr__(self) -> str:
        return (
            "RealtimeProviderError("
            f"category={self.category.value!r}, "
            f"reason={self.reason.value!r}, "
            f"retryable={self.retryable!r}"
            ")"
        )


_COMMAND_FIELDS: dict[
    ProviderCommandKind,
    tuple[frozenset[str], frozenset[str]],
] = {
    ProviderCommandKind.APPEND_AUDIO: (frozenset({"audio"}), frozenset()),
    ProviderCommandKind.COMMIT_AUDIO: (frozenset(), frozenset()),
    ProviderCommandKind.CLEAR_AUDIO: (frozenset(), frozenset()),
    ProviderCommandKind.CREATE_RESPONSE: (
        frozenset({"modalities"}),
        frozenset({"instructions"}),
    ),
    ProviderCommandKind.CANCEL_RESPONSE: (
        frozenset(),
        frozenset({"response_id"}),
    ),
    ProviderCommandKind.CREATE_CONVERSATION_ITEM: (
        frozenset({"role", "content"}),
        frozenset({"item_id"}),
    ),
    ProviderCommandKind.TOOL_OUTPUT: (
        frozenset({"call_id", "output"}),
        frozenset(),
    ),
}


def _validate_closed_fields(
    value: Mapping[str, JsonValue],
    *,
    required: frozenset[str],
    optional: frozenset[str],
    prefix: str,
) -> None:
    keys = frozenset(value)
    missing = required - keys
    if missing:
        raise ValueError(f"{prefix}_field_required:{sorted(missing)[0]}")
    unknown = keys - required - optional
    if unknown:
        raise ValueError(f"{prefix}_field_unknown:{sorted(unknown)[0]}")


def _validate_command_data(
    kind: ProviderCommandKind,
    data: FrozenJsonMapping,
) -> None:
    required, optional = _COMMAND_FIELDS[kind]
    _validate_closed_fields(
        data,
        required=required,
        optional=optional,
        prefix="provider_command_data",
    )
    if kind is ProviderCommandKind.APPEND_AUDIO:
        _require_string(data["audio"], "provider_command_audio")
    elif kind is ProviderCommandKind.CREATE_RESPONSE:
        _require_tuple_of_strings(
            data["modalities"],
            "provider_command_modalities",
            allowed=frozenset({"text", "audio"}),
        )
        if "instructions" in data:
            _require_string(
                data["instructions"],
                "provider_command_instructions",
                allow_empty=True,
            )
    elif kind is ProviderCommandKind.CANCEL_RESPONSE:
        if "response_id" in data:
            _require_string(data["response_id"], "provider_command_response_id")
    elif kind is ProviderCommandKind.CREATE_CONVERSATION_ITEM:
        role = _require_string(data["role"], "provider_command_role")
        if role not in {"user", "assistant", "system"}:
            raise ValueError("provider_command_role_unsupported")
        content = data["content"]
        if type(content) is not tuple or not content:
            raise ValueError("provider_command_content_must_be_non_empty_tuple")
        for item in content:
            if not isinstance(item, FrozenJsonMapping):
                raise ValueError("provider_command_content_item_must_be_mapping")
            _validate_closed_fields(
                item,
                required=frozenset({"type", "text"}),
                optional=frozenset(),
                prefix="provider_command_content_item",
            )
            if (
                _require_string(item["type"], "provider_command_content_item_type")
                != "input_text"
            ):
                raise ValueError("provider_command_content_item_type_unsupported")
            _require_string(item["text"], "provider_command_content_item_text")
        if "item_id" in data:
            _require_string(data["item_id"], "provider_command_item_id")
    elif kind is ProviderCommandKind.TOOL_OUTPUT:
        _require_string(data["call_id"], "provider_command_call_id")
        _require_string(
            data["output"],
            "provider_command_output",
            allow_empty=True,
        )


@dataclass(frozen=True, slots=True, repr=False)
class ProviderCommand(_ImmutableValue):
    kind: ProviderCommandKind
    data: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        _require_enum(self.kind, ProviderCommandKind, "provider_command_kind")
        frozen_data = _freeze_mapping(self.data, "provider_command_data")
        _validate_command_data(self.kind, frozen_data)
        object.__setattr__(self, "data", frozen_data)

    def __repr__(self) -> str:
        return (
            f"ProviderCommand(kind={self.kind.value!r}, "
            f"data_fields={tuple(self.data)!r})"
        )


_NO_EVENT_DATA: tuple[frozenset[str], frozenset[str]] = (
    frozenset(),
    frozenset(),
)
_EVENT_FIELDS: dict[
    ProviderEventKind,
    tuple[frozenset[str], frozenset[str]],
] = {
    ProviderEventKind.SESSION_READY: _NO_EVENT_DATA,
    ProviderEventKind.INPUT_AUDIO_COMMITTED: _NO_EVENT_DATA,
    ProviderEventKind.CONVERSATION_ITEM: (
        frozenset({"item_type"}),
        frozenset({"role", "name", "arguments", "content", "transcript"}),
    ),
    ProviderEventKind.TRANSCRIPTION_DELTA: (
        frozenset({"text"}),
        frozenset(),
    ),
    ProviderEventKind.TRANSCRIPTION_FINAL: (
        frozenset({"text"}),
        frozenset(),
    ),
    ProviderEventKind.SPEECH_STARTED: _NO_EVENT_DATA,
    ProviderEventKind.SPEECH_STOPPED: _NO_EVENT_DATA,
    ProviderEventKind.RESPONSE_CREATED: _NO_EVENT_DATA,
    ProviderEventKind.RESPONSE_TEXT_DELTA: (
        frozenset({"text"}),
        frozenset(),
    ),
    ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA: (
        frozenset({"text"}),
        frozenset(),
    ),
    ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL: (
        frozenset(),
        frozenset({"text"}),
    ),
    ProviderEventKind.RESPONSE_AUDIO_DELTA: (
        frozenset({"audio"}),
        frozenset(),
    ),
    ProviderEventKind.THINKING_DELTA: (
        frozenset({"text"}),
        frozenset(),
    ),
    ProviderEventKind.THINKING_DONE: (
        frozenset(),
        frozenset({"text"}),
    ),
    ProviderEventKind.FUNCTION_ARGUMENTS_DELTA: (
        frozenset({"arguments"}),
        frozenset({"name"}),
    ),
    ProviderEventKind.FUNCTION_ARGUMENTS_DONE: (
        frozenset({"arguments"}),
        frozenset({"name"}),
    ),
    ProviderEventKind.RESPONSE_DONE: (
        frozenset(),
        frozenset({"function_outputs"}),
    ),
    ProviderEventKind.ERROR: _NO_EVENT_DATA,
    ProviderEventKind.UNKNOWN: _NO_EVENT_DATA,
}

_RESPONSE_EVENT_KINDS = frozenset(
    {
        ProviderEventKind.RESPONSE_CREATED,
        ProviderEventKind.RESPONSE_TEXT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
        ProviderEventKind.RESPONSE_AUDIO_DELTA,
        ProviderEventKind.THINKING_DELTA,
        ProviderEventKind.THINKING_DONE,
    }
)
_FUNCTION_EVENT_KINDS = frozenset(
    {
        ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
        ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
    }
)


def _validate_conversation_item(data: FrozenJsonMapping) -> None:
    _require_string(data["item_type"], "provider_event_item_type")
    for field_name in ("role", "name", "arguments", "transcript"):
        if field_name in data:
            _require_string(
                data[field_name],
                f"provider_event_item_{field_name}",
                allow_empty=field_name == "arguments",
            )
    if "content" not in data:
        return
    content = data["content"]
    if type(content) is not tuple:
        raise ValueError("provider_event_item_content_must_be_tuple")
    for item in content:
        if not isinstance(item, FrozenJsonMapping):
            raise ValueError("provider_event_item_content_entry_must_be_mapping")
        _validate_closed_fields(
            item,
            required=frozenset({"type"}),
            optional=frozenset({"text", "transcript", "audio"}),
            prefix="provider_event_item_content_entry",
        )
        _require_string(item["type"], "provider_event_item_content_type")
        for field_name in ("text", "transcript", "audio"):
            if field_name in item:
                _require_string(
                    item[field_name],
                    f"provider_event_item_content_{field_name}",
                    allow_empty=True,
                )


def _validate_function_outputs(data: FrozenJsonMapping) -> None:
    if "function_outputs" not in data:
        return
    outputs = data["function_outputs"]
    if type(outputs) is not tuple:
        raise ValueError("provider_function_outputs_must_be_tuple")
    for output in outputs:
        if not isinstance(output, FrozenJsonMapping):
            raise ValueError("provider_function_output_must_be_mapping")
        if frozenset(output) != {"call_id", "name", "arguments"}:
            raise ValueError("provider_function_output_fields_invalid")
        _require_string(output["call_id"], "provider_function_output_call_id")
        _require_string(output["name"], "provider_function_output_name")
        _require_string(
            output["arguments"],
            "provider_function_output_arguments",
            allow_empty=True,
        )


def _validate_event_data(kind: ProviderEventKind, data: FrozenJsonMapping) -> None:
    required, optional = _EVENT_FIELDS[kind]
    _validate_closed_fields(
        data,
        required=required,
        optional=optional,
        prefix="provider_event_data",
    )
    if kind is ProviderEventKind.CONVERSATION_ITEM:
        _validate_conversation_item(data)
    elif kind in {
        ProviderEventKind.TRANSCRIPTION_DELTA,
        ProviderEventKind.TRANSCRIPTION_FINAL,
        ProviderEventKind.RESPONSE_TEXT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
        ProviderEventKind.THINKING_DELTA,
    }:
        _require_string(data["text"], "provider_event_text", allow_empty=False)
    elif kind in {
        ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
        ProviderEventKind.THINKING_DONE,
    }:
        if "text" in data:
            _require_string(data["text"], "provider_event_text", allow_empty=True)
    elif kind is ProviderEventKind.RESPONSE_AUDIO_DELTA:
        _require_string(data["audio"], "provider_event_audio")
    elif kind in _FUNCTION_EVENT_KINDS:
        _require_string(
            data["arguments"],
            "provider_event_function_arguments",
            allow_empty=True,
        )
        if "name" in data:
            _require_string(data["name"], "provider_event_function_name")
    elif kind is ProviderEventKind.RESPONSE_DONE:
        _validate_function_outputs(data)


@dataclass(frozen=True, slots=True, repr=False)
class ProviderEvent(_ImmutableValue):
    kind: ProviderEventKind
    provider_event_type: str
    connection_epoch: int
    request_id: int | None = None
    response_id: str | None = None
    stream_id: str | None = None
    call_id: str | None = None
    event_id: str | None = None
    turn_id: str | None = None
    timestamp_ms: float | None = None
    duration_ms: float | None = None
    data: Mapping[str, JsonValue] = field(default_factory=FrozenJsonMapping)
    error_category: ProviderErrorCategory | None = None
    error_reason: ProviderErrorReason | None = None

    def __post_init__(self) -> None:
        _require_enum(self.kind, ProviderEventKind, "provider_event_kind")
        _require_string(self.provider_event_type, "provider_event_type")
        if _PROVIDER_EVENT_TYPE_PATTERN.fullmatch(self.provider_event_type) is None:
            raise ValueError("provider_event_type_invalid")
        _require_non_negative_integer(
            self.connection_epoch,
            "provider_event_connection_epoch",
        )
        _require_non_negative_integer(
            self.request_id,
            "provider_event_request_id",
            optional=True,
        )
        for field_name in (
            "response_id",
            "stream_id",
            "call_id",
            "event_id",
            "turn_id",
        ):
            _require_optional_string(
                getattr(self, field_name),
                f"provider_event_{field_name}",
            )
        _require_non_negative_number(
            self.timestamp_ms,
            "provider_event_timestamp_ms",
            optional=True,
        )
        _require_non_negative_number(
            self.duration_ms,
            "provider_event_duration_ms",
            optional=True,
        )
        frozen_data = _freeze_mapping(self.data, "provider_event_data")
        _validate_event_data(self.kind, frozen_data)
        object.__setattr__(self, "data", frozen_data)

        if self.kind in _RESPONSE_EVENT_KINDS and self.response_id is None:
            raise ValueError("provider_event_response_id_required")
        if self.kind in _FUNCTION_EVENT_KINDS and self.call_id is None:
            raise ValueError("provider_event_call_id_required")
        if self.kind is ProviderEventKind.ERROR:
            if self.error_category is None or self.error_reason is None:
                raise ValueError("provider_event_error_fields_required")
            _validate_error_pair(self.error_category, self.error_reason)
        elif self.error_category is not None or self.error_reason is not None:
            raise ValueError("provider_event_error_fields_forbidden")

    def __repr__(self) -> str:
        return (
            "ProviderEvent("
            f"kind={self.kind.value!r}, "
            f"provider_event_type={self.provider_event_type!r}, "
            f"connection_epoch={self.connection_epoch!r}, "
            f"request_id={self.request_id!r}, response_id={self.response_id!r}, "
            f"stream_id={self.stream_id!r}, call_id={self.call_id!r}, "
            f"event_id={self.event_id!r}, turn_id={self.turn_id!r}, "
            f"timestamp_ms={self.timestamp_ms!r}, duration_ms={self.duration_ms!r}, "
            f"data_fields={tuple(self.data)!r}, "
            f"error_category={self.error_category!r}, "
            f"error_reason={self.error_reason!r}"
            ")"
        )


@runtime_checkable
class RealtimeProviderPort(Protocol):
    @property
    def capabilities(self) -> RealtimeProviderCapabilities: ...

    async def connect(self, config: RealtimeProviderSessionConfig) -> None: ...

    async def send(self, command: ProviderCommand) -> ProviderSendResult: ...

    async def receive(self, *, connection_epoch: int) -> ProviderEvent: ...

    async def check_health(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> ProviderHealthResult: ...

    def decide_backpressure(
        self,
        command: ProviderCommand,
        *,
        pending_bytes: int,
    ) -> ProviderBackpressureResult: ...

    async def close(self) -> None: ...


__all__ = [
    "FrozenJsonMapping",
    "JsonValue",
    "ProviderBackpressureResult",
    "ProviderCapability",
    "ProviderCommand",
    "ProviderCommandKind",
    "ProviderErrorCategory",
    "ProviderErrorReason",
    "ProviderEvent",
    "ProviderEventKind",
    "ProviderHealthResult",
    "ProviderSendResult",
    "RealtimeProviderCapabilities",
    "RealtimeProviderError",
    "RealtimeProviderPort",
    "RealtimeProviderSessionConfig",
    "validate_provider_capabilities",
]
