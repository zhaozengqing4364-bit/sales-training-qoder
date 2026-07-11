"""Contract tests for the provider-neutral realtime boundary."""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import math
from collections import deque
from collections.abc import Mapping
from pathlib import Path

import pytest

from training_runtime.realtime.provider import (
    FrozenJsonMapping,
    ProviderBackpressureResult,
    ProviderCapability,
    ProviderCommand,
    ProviderCommandKind,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEvent,
    ProviderEventKind,
    ProviderHealthResult,
    ProviderSendResult,
    RealtimeProviderCapabilities,
    RealtimeProviderError,
    RealtimeProviderPort,
    RealtimeProviderSessionConfig,
    validate_provider_capabilities,
)

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "realtime" / "provider_contract_v1.json"
)


def _inventory() -> dict[str, object]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _rows(payload: dict[str, object], field_name: str) -> list[dict[str, object]]:
    value = payload[field_name]
    assert isinstance(value, list)
    assert all(isinstance(row, dict) for row in value)
    return value


def _session_config(
    *,
    modalities: tuple[str, ...] = ("text", "audio"),
    tools: tuple[Mapping[str, object], ...] = (),
) -> RealtimeProviderSessionConfig:
    return RealtimeProviderSessionConfig(
        model="step-audio-2",
        voice="qingchunshaonv",
        temperature=0.4,
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        modalities=modalities,
        turn_detection={"type": "server_vad"},
        input_transcription_enabled=True,
        input_transcription_language="zh",
        input_transcription_model="step-asr",
        instructions="Only the adapter may read this prompt.",
        tools=tools,
    )


def test_inventory_should_cover_exact_provider_vocabulary() -> None:
    inventory = _inventory()

    assert type(inventory["schema_version"]) is int
    assert inventory["schema_version"] == 1
    assert inventory["provider"] == "stepfun"
    assert set(inventory["capabilities"]) == {
        capability.value for capability in ProviderCapability
    }

    commands = _rows(inventory, "commands")
    events = _rows(inventory, "events")
    assert {row["canonical_kind"] for row in commands} == {
        kind.value for kind in ProviderCommandKind
    }
    assert {row["canonical_kind"] for row in events} == {
        kind.value
        for kind in ProviderEventKind
        if kind is not ProviderEventKind.UNKNOWN
    }
    assert set(inventory["error_categories"]) == {
        category.value for category in ProviderErrorCategory
    }
    assert set(inventory["error_reasons"]) == {
        reason.value for reason in ProviderErrorReason
    }

    raw_identities: list[tuple[str, tuple[str, str] | None]] = []
    current_module = inspect.getmodule(
        test_inventory_should_cover_exact_provider_vocabulary
    )
    assert current_module is not None
    for row in (*commands, *events):
        assert set(row) in (
            {
                "raw_type",
                "canonical_kind",
                "required_fields",
                "optional_fields",
                "production_consumers",
                "exact_tests",
            },
            {
                "raw_type",
                "discriminator",
                "canonical_kind",
                "required_fields",
                "optional_fields",
                "production_consumers",
                "exact_tests",
            },
        )
        raw_type = row["raw_type"]
        assert type(raw_type) is str and raw_type
        discriminator = row.get("discriminator")
        discriminator_identity: tuple[str, str] | None = None
        if discriminator is not None:
            assert isinstance(discriminator, dict)
            assert set(discriminator) == {"field", "value"}
            assert type(discriminator["field"]) is str and discriminator["field"]
            assert type(discriminator["value"]) is str and discriminator["value"]
            discriminator_identity = (
                discriminator["field"],
                discriminator["value"],
            )
        raw_identities.append((raw_type, discriminator_identity))
        for field_name in (
            "required_fields",
            "optional_fields",
            "production_consumers",
            "exact_tests",
        ):
            values = row[field_name]
            assert isinstance(values, list)
            assert all(type(value) is str and value for value in values)
        assert row["production_consumers"]
        assert row["exact_tests"]
        for test_node in row["exact_tests"]:
            test_path, separator, test_name = test_node.partition("::")
            assert separator == "::"
            assert test_path == "tests/unit/test_realtime_provider_contract.py"
            assert (Path(__file__).parents[2] / test_path).is_file()
            assert callable(getattr(current_module, test_name, None))
    assert len(raw_identities) == len(set(raw_identities))


def test_inventory_should_lock_exact_wire_type_and_discriminator_pairs() -> None:
    inventory = _inventory()
    commands = _rows(inventory, "commands")
    events = _rows(inventory, "events")

    def identity(row: dict[str, object]) -> tuple[str, tuple[str, str] | None]:
        raw_type = row["raw_type"]
        assert isinstance(raw_type, str)
        discriminator = row.get("discriminator")
        if discriminator is None:
            return raw_type, None
        assert isinstance(discriminator, dict)
        return raw_type, (
            str(discriminator["field"]),
            str(discriminator["value"]),
        )

    assert {identity(row) for row in commands} == {
        ("input_audio_buffer.append", None),
        ("input_audio_buffer.commit", None),
        ("input_audio_buffer.clear", None),
        ("response.create", None),
        ("response.cancel", None),
        ("conversation.item.create", ("item.type", "message")),
        ("conversation.item.create", ("item.type", "function_call_output")),
    }
    assert {identity(row) for row in events} == {
        (raw_type, None)
        for raw_type in {
            "session.created",
            "session.updated",
            "input_audio_buffer.committed",
            "conversation.item.created",
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.input_audio_transcription.text",
            "conversation.item.input_audio_transcript.delta",
            "conversation.item.input_audio_transcript.text",
            "input_audio_buffer.transcription.delta",
            "input_audio_buffer.transcription.text",
            "input_audio_buffer.transcript.delta",
            "input_audio_buffer.transcript.text",
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
            "input_audio_buffer.speech_started",
            "input_audio_buffer.speech_stopped",
            "response.created",
            "response.text.delta",
            "response.audio_transcript.delta",
            "response.audio_transcript.done",
            "response.audio.delta",
            "response.thinking.delta",
            "response.thinking.done",
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
            "response.done",
            "error",
        }
    }


def test_inventory_should_include_high_risk_event_semantics() -> None:
    inventory = _inventory()
    event_by_type = {row["raw_type"]: row for row in _rows(inventory, "events")}

    assert event_by_type["input_audio_buffer.committed"]["canonical_kind"] == (
        "input_audio_committed"
    )
    assert event_by_type["response.audio_transcript.done"]["canonical_kind"] == (
        "response_transcript_final"
    )
    assert event_by_type["response.thinking.delta"]["canonical_kind"] == (
        "thinking_delta"
    )
    assert event_by_type["response.thinking.done"]["canonical_kind"] == (
        "thinking_done"
    )
    assert "data.function_outputs" in event_by_type["response.done"]["optional_fields"]
    assert event_by_type["response.done"]["required_fields"] == []
    assert "response_id" in event_by_type["response.done"]["optional_fields"]
    assert event_by_type["response.thinking.done"]["required_fields"] == ["response_id"]
    assert "data.text" in event_by_type["response.thinking.done"]["optional_fields"]
    assert event_by_type["response.audio_transcript.done"]["required_fields"] == []
    assert {"response_id", "data.text"} <= set(
        event_by_type["response.audio_transcript.done"]["optional_fields"]
    )

    transcript_fields = set(
        event_by_type["response.audio_transcript.done"]["optional_fields"]
    )
    speech_start_fields = set(
        event_by_type["input_audio_buffer.speech_started"]["optional_fields"]
    )
    assert {"turn_id", "event_id", "duration_ms"} <= transcript_fields
    assert {"turn_id", "event_id", "timestamp_ms"} <= speech_start_fields
    assert {
        "asr_unavailable",
        "voice_unavailable",
        "idle_timeout",
    } <= set(inventory["error_reasons"])


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        (ProviderCommandKind.APPEND_AUDIO, {}),
        (ProviderCommandKind.APPEND_AUDIO, {"audio": 1}),
        (ProviderCommandKind.COMMIT_AUDIO, {"unexpected": True}),
        (ProviderCommandKind.CLEAR_AUDIO, {"audio": "forbidden"}),
        (ProviderCommandKind.CREATE_RESPONSE, {"modalities": "audio"}),
        (
            ProviderCommandKind.CREATE_RESPONSE,
            {"modalities": ("audio",), "raw_prompt": "must not cross"},
        ),
        (ProviderCommandKind.CANCEL_RESPONSE, {"response_id": 1}),
        (
            ProviderCommandKind.CREATE_CONVERSATION_ITEM,
            {"role": "user", "content": "must be an array"},
        ),
        (ProviderCommandKind.TOOL_OUTPUT, {"call_id": "call-1"}),
    ],
)
def test_command_should_validate_closed_fields_by_kind(
    kind: ProviderCommandKind,
    data: Mapping[str, object],
) -> None:
    with pytest.raises(ValueError):
        ProviderCommand(kind=kind, data=data)

    with pytest.raises(ValueError, match="provider_command_kind_must_be_enum"):
        ProviderCommand(kind="append_audio", data={"audio": "AAE="})  # type: ignore[arg-type]

    assert ProviderCommand(
        kind=ProviderCommandKind.APPEND_AUDIO,
        data={"audio": "AAE="},
    ).data == {"audio": "AAE="}
    assert ProviderCommand(
        kind=ProviderCommandKind.CREATE_RESPONSE,
        data={"modalities": ("audio", "text"), "instructions": "grounded"},
    ).data["modalities"] == ("audio", "text")
    assert (
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_CONVERSATION_ITEM,
            data={
                "role": "user",
                "content": ({"type": "input_text", "text": "hello"},),
            },
        ).data["role"]
        == "user"
    )
    assert (
        ProviderCommand(
            kind=ProviderCommandKind.TOOL_OUTPUT,
            data={"call_id": "call-1", "output": "{}"},
        ).data["output"]
        == "{}"
    )


def test_event_should_validate_closed_fields_and_normalized_function_outputs() -> None:
    original_outputs = [
        {
            "call_id": "call-1",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"产品"}',
        }
    ]
    event = ProviderEvent(
        kind=ProviderEventKind.RESPONSE_DONE,
        provider_event_type="response.done",
        connection_epoch=2,
        request_id=4,
        response_id="response-1",
        stream_id="stream-1",
        turn_id="turn-1",
        event_id="event-1",
        timestamp_ms=1000.5,
        duration_ms=250.0,
        data={"function_outputs": original_outputs},
    )

    outputs = event.data["function_outputs"]
    assert isinstance(outputs, tuple)
    assert outputs[0] == {
        "call_id": "call-1",
        "name": "search_internal_knowledge",
        "arguments": '{"query":"产品"}',
    }
    original_outputs[0]["arguments"] = "mutated"
    assert outputs[0]["arguments"] == '{"query":"产品"}'

    with pytest.raises(ValueError, match="provider_event_data_field_unknown"):
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=1,
            response_id="response-1",
            data={"raw_response": {}},
        )
    with pytest.raises(ValueError, match="provider_function_output_fields_invalid"):
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=1,
            response_id="response-1",
            data={"function_outputs": [{"call_id": "call-1", "name": "tool"}]},
        )
    with pytest.raises(ValueError, match="provider_event_response_id_required"):
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_AUDIO_DELTA,
            provider_event_type="response.audio.delta",
            connection_epoch=1,
            data={"audio": "AAE="},
        )
    with pytest.raises(ValueError, match="provider_event_call_id_required"):
        ProviderEvent(
            kind=ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
            provider_event_type="response.function_call_arguments.done",
            connection_epoch=1,
            data={"arguments": "{}"},
        )


def test_terminal_events_should_accept_existing_sparse_wire_shapes() -> None:
    response_done = ProviderEvent(
        kind=ProviderEventKind.RESPONSE_DONE,
        provider_event_type="response.done",
        connection_epoch=2,
        data={},
    )
    assert response_done.response_id is None

    thinking_done_without_text = ProviderEvent(
        kind=ProviderEventKind.THINKING_DONE,
        provider_event_type="response.thinking.done",
        connection_epoch=2,
        response_id="response-1",
        data={},
    )
    thinking_done_with_empty_text = ProviderEvent(
        kind=ProviderEventKind.THINKING_DONE,
        provider_event_type="response.thinking.done",
        connection_epoch=2,
        response_id="response-1",
        data={"text": ""},
    )
    assert thinking_done_without_text.data == {}
    assert thinking_done_with_empty_text.data["text"] == ""

    transcript_final = ProviderEvent(
        kind=ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
        provider_event_type="response.audio_transcript.done",
        connection_epoch=2,
        data={},
    )
    transcript_final_with_empty_text = ProviderEvent(
        kind=ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
        provider_event_type="response.audio_transcript.done",
        connection_epoch=2,
        data={"text": ""},
    )
    assert transcript_final.response_id is None
    assert transcript_final_with_empty_text.data["text"] == ""


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("connection_epoch", True),
        ("connection_epoch", 1.0),
        ("connection_epoch", "1"),
        ("request_id", False),
        ("request_id", 1.0),
        ("timestamp_ms", True),
        ("timestamp_ms", math.inf),
        ("duration_ms", -0.1),
    ],
)
def test_event_should_reject_numeric_coercion_and_invalid_numbers(
    field_name: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        "kind": ProviderEventKind.SESSION_READY,
        "provider_event_type": "session.created",
        "connection_epoch": 1,
    }
    kwargs[field_name] = value
    with pytest.raises(ValueError):
        ProviderEvent(**kwargs)  # type: ignore[arg-type]


def test_error_contract_should_be_closed_and_safe() -> None:
    error = RealtimeProviderError(
        category=ProviderErrorCategory.UNAVAILABLE,
        reason=ProviderErrorReason.ASR_UNAVAILABLE,
        retryable=True,
    )
    rendered = repr(error)
    assert "unavailable" in rendered
    assert "asr_unavailable" in rendered
    assert "credential" not in rendered
    assert "endpoint" not in rendered
    assert "raw" not in rendered
    assert str(error) == "realtime_provider_error:unavailable:asr_unavailable"

    with pytest.raises(ValueError, match="provider_error_category_reason_mismatch"):
        RealtimeProviderError(
            category=ProviderErrorCategory.AUTHENTICATION,
            reason=ProviderErrorReason.IDLE_TIMEOUT,
            retryable=False,
        )
    with pytest.raises(ValueError, match="provider_error_retryable_must_be_boolean"):
        RealtimeProviderError(
            category=ProviderErrorCategory.TIMEOUT,
            reason=ProviderErrorReason.IDLE_TIMEOUT,
            retryable=1,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="provider_event_error_fields_required"):
        ProviderEvent(
            kind=ProviderEventKind.ERROR,
            provider_event_type="error",
            connection_epoch=1,
        )
    with pytest.raises(ValueError, match="provider_event_error_fields_forbidden"):
        ProviderEvent(
            kind=ProviderEventKind.UNKNOWN,
            provider_event_type="provider.future.event",
            connection_epoch=1,
            error_category=ProviderErrorCategory.PROTOCOL,
            error_reason=ProviderErrorReason.INVALID_EVENT,
        )
    with pytest.raises(ValueError, match="provider_event_type_invalid"):
        ProviderEvent(
            kind=ProviderEventKind.UNKNOWN,
            provider_event_type="wss://provider.example/realtime?token=secret",
            connection_epoch=1,
        )

    assert (
        ProviderSendResult(
            accepted=False,
            error_category=ProviderErrorCategory.BACKPRESSURE,
            error_reason=ProviderErrorReason.BACKPRESSURE_LIMIT,
        ).accepted
        is False
    )
    assert (
        ProviderHealthResult(
            healthy=False,
            error_category=ProviderErrorCategory.DISCONNECTED,
            error_reason=ProviderErrorReason.CONNECTION_CLOSED,
        ).healthy
        is False
    )
    assert (
        ProviderBackpressureResult(
            accepted=False,
            error_reason=ProviderErrorReason.BACKPRESSURE_LIMIT,
        ).accepted
        is False
    )

    with pytest.raises(ValueError):
        ProviderSendResult(accepted=True, error_reason=ProviderErrorReason.UNKNOWN)
    with pytest.raises(ValueError):
        ProviderHealthResult(
            healthy=False,
            error_category=ProviderErrorCategory.DISCONNECTED,
        )
    with pytest.raises(ValueError):
        ProviderBackpressureResult(
            accepted=True, error_reason=ProviderErrorReason.UNKNOWN
        )


def test_dtos_should_freeze_nested_json_and_redact_repr() -> None:
    original_content: list[dict[str, object]] = [
        {"type": "input_text", "text": "secret transcript"}
    ]
    command = ProviderCommand(
        kind=ProviderCommandKind.CREATE_CONVERSATION_ITEM,
        data={"role": "user", "content": original_content},
    )
    original_content[0]["text"] = "mutated"

    assert isinstance(command.data, FrozenJsonMapping)
    assert command.data["content"][0]["text"] == "secret transcript"
    assert copy.deepcopy(command.data) is command.data
    assert copy.deepcopy(command) is command
    assert "secret transcript" not in repr(command)

    config = _session_config(
        tools=(
            {
                "type": "function",
                "name": "search_internal_knowledge",
                "parameters": {"type": "object", "required": ("query",)},
            },
        )
    )
    assert isinstance(config.turn_detection, FrozenJsonMapping)
    assert isinstance(config.tools[0], FrozenJsonMapping)
    assert copy.deepcopy(config) is config
    assert "Only the adapter" not in repr(config)
    assert "search_internal_knowledge" not in repr(config)

    with pytest.raises(TypeError):
        command.data["role"] = "assistant"  # type: ignore[index]
    with pytest.raises(AttributeError):
        command.data._items = ()  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="json_mapping_key_must_be_string"):
        FrozenJsonMapping({1: "invalid"})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="json_value_type_invalid"):
        FrozenJsonMapping({"invalid": {"set"}})


def test_config_should_derive_required_capabilities_without_invented_formats() -> None:
    config = _session_config(
        tools=(
            {
                "type": "function",
                "name": "search_internal_knowledge",
                "parameters": {"type": "object"},
            },
        )
    )
    assert config.required_capabilities() == frozenset(
        {
            ProviderCapability.TEXT,
            ProviderCapability.AUDIO_INPUT,
            ProviderCapability.AUDIO_OUTPUT,
            ProviderCapability.INPUT_TRANSCRIPTION,
            ProviderCapability.FUNCTION_TOOLS,
            ProviderCapability.SERVER_VAD,
        }
    )

    capabilities = RealtimeProviderCapabilities(
        supported=frozenset(ProviderCapability),
        input_audio_formats=None,
        output_audio_formats=None,
    )
    assert capabilities.input_audio_formats is None
    assert capabilities.output_audio_formats is None

    with pytest.raises(ValueError, match="provider_temperature_must_be_number"):
        RealtimeProviderSessionConfig(
            model="step-audio-2",
            voice="voice",
            temperature="0.4",  # type: ignore[arg-type]
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            modalities=("text",),
            turn_detection=None,
            input_transcription_enabled=False,
            input_transcription_language="",
            input_transcription_model="",
            instructions="",
            tools=(),
        )
    with pytest.raises(ValueError, match="provider_supported_capability_must_be_enum"):
        RealtimeProviderCapabilities(
            supported=frozenset({"text"}),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="provider_input_audio_formats_must_be_tuple"):
        RealtimeProviderCapabilities(
            supported=frozenset({ProviderCapability.TEXT}),
            input_audio_formats=["pcm16"],  # type: ignore[arg-type]
        )


def test_capability_validation_should_fail_closed_on_declared_mismatch() -> None:
    config = _session_config()
    required = config.required_capabilities()

    validate_provider_capabilities(
        capabilities=RealtimeProviderCapabilities(
            supported=required,
            input_audio_formats=None,
            output_audio_formats=None,
        ),
        config=config,
    )
    validate_provider_capabilities(
        capabilities=RealtimeProviderCapabilities(
            supported=required,
            input_audio_formats=("pcm16",),
            output_audio_formats=("pcm16",),
        ),
        config=config,
    )

    for capabilities in (
        RealtimeProviderCapabilities(
            supported=required - {ProviderCapability.SERVER_VAD},
        ),
        RealtimeProviderCapabilities(
            supported=required,
            input_audio_formats=("g711_ulaw",),
            output_audio_formats=("pcm16",),
        ),
        RealtimeProviderCapabilities(
            supported=required,
            input_audio_formats=("pcm16",),
            output_audio_formats=("mp3",),
        ),
    ):
        with pytest.raises(RealtimeProviderError) as captured:
            validate_provider_capabilities(capabilities=capabilities, config=config)
        assert captured.value.category is ProviderErrorCategory.PROTOCOL
        assert captured.value.reason is ProviderErrorReason.INVALID_EVENT


class FakeRealtimeProvider:
    def __init__(
        self,
        *,
        supported: frozenset[ProviderCapability],
        events: tuple[ProviderEvent, ...] = (),
    ) -> None:
        self._capabilities = RealtimeProviderCapabilities(supported=supported)
        self._events = deque(events)
        self.connected = False
        self.closed = False

    @property
    def capabilities(self) -> RealtimeProviderCapabilities:
        return self._capabilities

    async def connect(self, config: RealtimeProviderSessionConfig) -> None:
        validate_provider_capabilities(
            capabilities=self.capabilities,
            config=config,
        )
        self.connected = True

    async def send(self, command: ProviderCommand) -> ProviderSendResult:
        if not self.connected:
            return ProviderSendResult(
                accepted=False,
                error_category=ProviderErrorCategory.DISCONNECTED,
                error_reason=ProviderErrorReason.CONNECTION_CLOSED,
            )
        assert isinstance(command, ProviderCommand)
        return ProviderSendResult(accepted=True)

    async def receive(self, *, connection_epoch: int) -> ProviderEvent:
        if type(connection_epoch) is not int or connection_epoch < 0:
            raise ValueError("connection_epoch_invalid")
        event = self._events.popleft()
        if event.connection_epoch != connection_epoch:
            raise RealtimeProviderError(
                category=ProviderErrorCategory.PROTOCOL,
                reason=ProviderErrorReason.INVALID_EVENT,
                retryable=False,
            )
        return event

    async def check_health(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> ProviderHealthResult:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds_invalid")
        return ProviderHealthResult(
            healthy=self.connected and not self.closed,
            error_category=(
                None
                if self.connected and not self.closed
                else ProviderErrorCategory.DISCONNECTED
            ),
            error_reason=(
                None
                if self.connected and not self.closed
                else ProviderErrorReason.CONNECTION_CLOSED
            ),
        )

    def decide_backpressure(
        self,
        command: ProviderCommand,
        *,
        pending_bytes: int,
    ) -> ProviderBackpressureResult:
        assert isinstance(command, ProviderCommand)
        if type(pending_bytes) is not int or pending_bytes < 0:
            raise ValueError("pending_bytes_invalid")
        if pending_bytes > 1024:
            return ProviderBackpressureResult(
                accepted=False,
                error_reason=ProviderErrorReason.BACKPRESSURE_LIMIT,
            )
        return ProviderBackpressureResult(accepted=True)

    async def close(self) -> None:
        self.closed = True


def test_port_protocol_should_support_fake_and_fail_closed_on_capability_mismatch() -> (
    None
):
    event = ProviderEvent(
        kind=ProviderEventKind.SESSION_READY,
        provider_event_type="session.created",
        connection_epoch=1,
    )
    provider = FakeRealtimeProvider(
        supported=frozenset(ProviderCapability),
        events=(event,),
    )
    assert isinstance(provider, RealtimeProviderPort)

    async def exercise_port() -> None:
        await provider.connect(_session_config())
        assert provider.connected is True
        command = ProviderCommand(
            kind=ProviderCommandKind.APPEND_AUDIO,
            data={"audio": "AAE="},
        )
        assert (await provider.send(command)).accepted is True
        assert (await provider.receive(connection_epoch=1)) == event
        assert (await provider.check_health(timeout_seconds=0.5)).healthy is True
        assert (
            provider.decide_backpressure(command, pending_bytes=1024).accepted is True
        )
        assert (
            provider.decide_backpressure(command, pending_bytes=1025).error_reason
            is ProviderErrorReason.BACKPRESSURE_LIMIT
        )
        await provider.close()
        assert (await provider.check_health()).healthy is False

    asyncio.run(exercise_port())

    missing_tool_provider = FakeRealtimeProvider(
        supported=frozenset(
            {
                ProviderCapability.TEXT,
                ProviderCapability.AUDIO_INPUT,
                ProviderCapability.AUDIO_OUTPUT,
                ProviderCapability.INPUT_TRANSCRIPTION,
                ProviderCapability.SERVER_VAD,
            }
        )
    )

    async def connect_without_required_capability() -> None:
        with pytest.raises(RealtimeProviderError) as captured:
            await missing_tool_provider.connect(
                _session_config(
                    tools=(
                        {
                            "type": "function",
                            "name": "search_internal_knowledge",
                        },
                    )
                )
            )
        assert captured.value.category is ProviderErrorCategory.PROTOCOL
        assert captured.value.reason is ProviderErrorReason.INVALID_EVENT

    asyncio.run(connect_without_required_capability())
