"""Golden contracts for the StepFun realtime codec and Provider adapter."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from pathlib import Path

import pytest

from training_runtime.realtime.provider import (
    ProviderBackpressureResult,
    ProviderCommand,
    ProviderCommandKind,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEventKind,
    RealtimeProviderError,
    RealtimeProviderPort,
    RealtimeProviderSessionConfig,
)
from training_runtime.realtime.stepfun_codec import StepFunEventCodec
from training_runtime.realtime.stepfun_provider import StepFunRealtimeProvider
from training_runtime.stepfun_transport import (
    StepFunBackpressureResult,
    StepFunBackpressureStatus,
    StepFunHealthResult,
    StepFunHealthStatus,
    StepFunSendResult,
    StepFunSendStatus,
    StepFunUpstreamConnectError,
)

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "realtime" / "provider_contract_v1.json"
)

TRANSCRIPTION_DELTA_TYPES = (
    "conversation.item.input_audio_transcription.delta",
    "conversation.item.input_audio_transcription.text",
    "conversation.item.input_audio_transcript.delta",
    "conversation.item.input_audio_transcript.text",
    "input_audio_buffer.transcription.delta",
    "input_audio_buffer.transcription.text",
    "input_audio_buffer.transcript.delta",
    "input_audio_buffer.transcript.text",
)
TRANSCRIPTION_FINAL_TYPES = (
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
)


def _session_config() -> RealtimeProviderSessionConfig:
    return RealtimeProviderSessionConfig(
        model="stepaudio-2.5-realtime",
        voice="qingchunshaonv",
        temperature=0.4,
        input_audio_format="pcm16",
        output_audio_format="pcm16",
        modalities=("text", "audio"),
        turn_detection={"type": "server_vad", "silence_duration_ms": 500},
        input_transcription_enabled=True,
        input_transcription_language="zh",
        input_transcription_model="step-asr",
        instructions="grounded instructions",
        tools=(
            {
                "type": "function",
                "name": "search_internal_knowledge",
                "parameters": {"type": "object"},
            },
        ),
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (
            ProviderCommand(
                kind=ProviderCommandKind.APPEND_AUDIO,
                data={"audio": "AAE="},
            ),
            {"type": "input_audio_buffer.append", "audio": "AAE="},
        ),
        (
            ProviderCommand(kind=ProviderCommandKind.COMMIT_AUDIO, data={}),
            {"type": "input_audio_buffer.commit"},
        ),
        (
            ProviderCommand(kind=ProviderCommandKind.CLEAR_AUDIO, data={}),
            {"type": "input_audio_buffer.clear"},
        ),
        (
            ProviderCommand(
                kind=ProviderCommandKind.CREATE_RESPONSE,
                data={"modalities": ("audio", "text"), "instructions": "grounded"},
            ),
            {
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],
                    "instructions": "grounded",
                },
            },
        ),
        (
            ProviderCommand(
                kind=ProviderCommandKind.CANCEL_RESPONSE,
                data={"response_id": "response-1"},
            ),
            {"type": "response.cancel", "response_id": "response-1"},
        ),
        (
            ProviderCommand(
                kind=ProviderCommandKind.CREATE_CONVERSATION_ITEM,
                data={
                    "role": "user",
                    "content": ({"type": "input_text", "text": "hello"},),
                    "item_id": "item-1",
                },
            ),
            {
                "type": "conversation.item.create",
                "item": {
                    "id": "item-1",
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            },
        ),
        (
            ProviderCommand(
                kind=ProviderCommandKind.TOOL_OUTPUT,
                data={"call_id": "call-1", "output": '{"count":1}'},
            ),
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": '{"count":1}',
                },
            },
        ),
    ],
)
def test_codec_should_encode_every_inventory_command(
    command: ProviderCommand,
    expected: dict[str, object],
) -> None:
    assert StepFunEventCodec().encode_command(command) == expected


def test_codec_command_cases_should_match_versioned_inventory() -> None:
    inventory = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert {row["canonical_kind"] for row in inventory["commands"]} == {
        kind.value for kind in ProviderCommandKind
    }


@pytest.mark.parametrize("event_type", TRANSCRIPTION_DELTA_TYPES)
def test_codec_should_decode_all_input_transcription_delta_aliases(
    event_type: str,
) -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": event_type,
                "event_id": "event-1",
                "item_id": "turn-1",
                "delta": "客户语音",
            }
        ),
        connection_epoch=3,
    )

    assert event.kind is ProviderEventKind.TRANSCRIPTION_DELTA
    assert event.provider_event_type == event_type
    assert event.connection_epoch == 3
    assert event.event_id == "event-1"
    assert event.turn_id == "turn-1"
    assert event.data == {"text": "客户语音"}


@pytest.mark.parametrize("event_type", TRANSCRIPTION_FINAL_TYPES)
def test_codec_should_decode_all_input_transcription_final_aliases(
    event_type: str,
) -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": event_type,
                "event_id": "event-final",
                "item_id": "turn-final",
                "transcript": "最终文本",
                "audio_duration_ms": 240.5,
            },
            ensure_ascii=False,
        ),
        connection_epoch=4,
    )

    assert event.kind is ProviderEventKind.TRANSCRIPTION_FINAL
    assert event.data == {"text": "最终文本"}
    assert event.duration_ms == 240.5


@pytest.mark.parametrize(
    ("raw_payload", "expected_text"),
    [
        ({"transcript": {"text": "object transcript"}}, "object transcript"),
        ({"text": "direct text"}, "direct text"),
        ({"audio_transcript": "audio transcript field"}, "audio transcript field"),
        ({"stash": {"text": "stash nested"}}, "stash nested"),
        ({"parts": [{"text": "parts nested"}]}, "parts nested"),
        ({"part": {"transcript": "part nested"}}, "part nested"),
        ({"transcription": {"text": "transcription nested"}}, "transcription nested"),
        (
            {"input_audio_transcription": {"transcript": "input ASR nested"}},
            "input ASR nested",
        ),
        (
            {"item": {"content": [{"type": "input_audio", "transcript": "nested"}]}},
            "nested",
        ),
        (
            {
                "item": {
                    "content": [
                        {
                            "type": "input_audio",
                            "audio": {"transcript": "audio nested"},
                        }
                    ]
                }
            },
            "audio nested",
        ),
    ],
)
def test_codec_should_preserve_existing_alternate_transcript_shapes(
    raw_payload: dict[str, object],
    expected_text: str,
) -> None:
    raw_payload["type"] = "conversation.item.input_audio_transcription.completed"
    event = StepFunEventCodec().decode_event(
        json.dumps(raw_payload, ensure_ascii=False),
        connection_epoch=1,
    )
    assert event.kind is ProviderEventKind.TRANSCRIPTION_FINAL
    assert event.data == {"text": expected_text}


@pytest.mark.parametrize(
    ("raw_payload", "expected_kind", "expected_data"),
    [
        ({"type": "session.created"}, ProviderEventKind.SESSION_READY, {}),
        ({"type": "session.updated"}, ProviderEventKind.SESSION_READY, {}),
        (
            {"type": "input_audio_buffer.committed", "item_id": "turn-1"},
            ProviderEventKind.INPUT_AUDIO_COMMITTED,
            {},
        ),
        (
            {
                "type": "conversation.item.created",
                "item": {
                    "type": "function_call",
                    "call_id": "call-item",
                    "name": "search_internal_knowledge",
                    "arguments": "{}",
                },
            },
            ProviderEventKind.CONVERSATION_ITEM,
            {
                "item_type": "function_call",
                "name": "search_internal_knowledge",
                "arguments": "{}",
            },
        ),
        (
            {"type": "input_audio_buffer.speech_started"},
            ProviderEventKind.SPEECH_STARTED,
            {},
        ),
        (
            {"type": "input_audio_buffer.speech_stopped"},
            ProviderEventKind.SPEECH_STOPPED,
            {},
        ),
        (
            {"type": "response.created", "response": {"id": "response-1"}},
            ProviderEventKind.RESPONSE_CREATED,
            {},
        ),
        (
            {
                "type": "response.text.delta",
                "response_id": "response-1",
                "delta": "text",
            },
            ProviderEventKind.RESPONSE_TEXT_DELTA,
            {"text": "text"},
        ),
        (
            {
                "type": "response.audio_transcript.delta",
                "response_id": "response-1",
                "delta": "spoken",
            },
            ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
            {"text": "spoken"},
        ),
        (
            {
                "type": "response.audio_transcript.done",
                "response_id": "response-1",
                "transcript": "spoken final",
            },
            ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
            {"text": "spoken final"},
        ),
        (
            {
                "type": "response.audio.delta",
                "response_id": "response-1",
                "delta": "AAE=",
            },
            ProviderEventKind.RESPONSE_AUDIO_DELTA,
            {"audio": "AAE="},
        ),
        (
            {
                "type": "response.thinking.delta",
                "response_id": "response-1",
                "delta": "reasoning",
            },
            ProviderEventKind.THINKING_DELTA,
            {"text": "reasoning"},
        ),
        (
            {
                "type": "response.thinking.done",
                "response_id": "response-1",
            },
            ProviderEventKind.THINKING_DONE,
            {},
        ),
        (
            {
                "type": "response.function_call_arguments.delta",
                "response_id": "response-1",
                "call_id": "call-1",
                "name": "search_internal_knowledge",
                "delta": '{"query":',
            },
            ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
            {"arguments": '{"query":', "name": "search_internal_knowledge"},
        ),
        (
            {
                "type": "response.function_call_arguments.done",
                "response_id": "response-1",
                "call_id": "call-1",
                "arguments": {"query": "产品"},
            },
            ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
            {"arguments": '{"query": "产品"}'},
        ),
        (
            {
                "type": "response.done",
                "response": {
                    "id": "response-done",
                    "output": [
                        {"type": "message", "content": []},
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": "search_internal_knowledge",
                            "arguments": '{"query":"产品"}',
                        },
                    ],
                },
            },
            ProviderEventKind.RESPONSE_DONE,
            {
                "function_outputs": (
                    {
                        "call_id": "call-1",
                        "name": "search_internal_knowledge",
                        "arguments": '{"query":"产品"}',
                    },
                )
            },
        ),
    ],
)
def test_codec_should_decode_every_non_error_inventory_event(
    raw_payload: dict[str, object],
    expected_kind: ProviderEventKind,
    expected_data: Mapping[str, object],
) -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(raw_payload, ensure_ascii=False).encode(),
        connection_epoch=5,
    )

    assert event.kind is expected_kind
    assert event.data == expected_data


def test_codec_event_cases_should_match_versioned_inventory() -> None:
    inventory = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    inventory_types = {row["raw_type"] for row in inventory["events"]}
    directly_tested = {
        "session.created",
        "session.updated",
        "input_audio_buffer.committed",
        "conversation.item.created",
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
    assert inventory_types == directly_tested | set(TRANSCRIPTION_DELTA_TYPES) | set(
        TRANSCRIPTION_FINAL_TYPES
    )


def test_codec_should_preserve_ids_and_emotion_timing() -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": "response.audio_transcript.done",
                "request_id": 4,
                "response_id": "response-4",
                "stream_id": "stream-4",
                "call_id": "call-4",
                "event_id": "event-4",
                "turn_id": "turn-4",
                "created_at_ms": 1000,
                "speech_started_at_ms": 1000,
                "speech_stopped_at_ms": 1250.5,
                "transcript": "final",
            }
        ),
        connection_epoch=7,
    )

    assert event.request_id == 4
    assert event.response_id == "response-4"
    assert event.stream_id == "stream-4"
    assert event.call_id == "call-4"
    assert event.event_id == "event-4"
    assert event.turn_id == "turn-4"
    assert event.timestamp_ms == 1000
    assert event.duration_ms == 250.5


@pytest.mark.parametrize(
    ("raw", "expected_kind", "expected_category", "expected_reason"),
    [
        (
            "not-json",
            ProviderEventKind.ERROR,
            ProviderErrorCategory.PROTOCOL,
            ProviderErrorReason.INVALID_EVENT,
        ),
        (
            "[]",
            ProviderEventKind.ERROR,
            ProviderErrorCategory.PROTOCOL,
            ProviderErrorReason.INVALID_EVENT,
        ),
        (
            '{"type":"future.provider.event","token":"must-not-cross"}',
            ProviderEventKind.UNKNOWN,
            None,
            None,
        ),
    ],
)
def test_codec_should_fail_closed_for_invalid_and_unknown_payloads(
    raw: str,
    expected_kind: ProviderEventKind,
    expected_category: ProviderErrorCategory | None,
    expected_reason: ProviderErrorReason | None,
) -> None:
    event = StepFunEventCodec().decode_event(raw, connection_epoch=1)
    assert event.kind is expected_kind
    assert event.error_category is expected_category
    assert event.error_reason is expected_reason
    assert "must-not-cross" not in repr(event)


@pytest.mark.parametrize(
    ("raw_error", "category", "reason"),
    [
        (
            {"status": 401},
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.INVALID_CREDENTIALS,
        ),
        (
            {"status_code": 402},
            ProviderErrorCategory.QUOTA,
            ProviderErrorReason.QUOTA_EXHAUSTED,
        ),
        (
            {"code": 403},
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.FORBIDDEN,
        ),
        (
            {"status": 429},
            ProviderErrorCategory.RATE_LIMIT,
            ProviderErrorReason.RATE_LIMITED,
        ),
        (
            {"code": "asr_unavailable"},
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.ASR_UNAVAILABLE,
        ),
        (
            {"code": "voice_unavailable"},
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.VOICE_UNAVAILABLE,
        ),
        (
            {"code": "idle_timeout"},
            ProviderErrorCategory.TIMEOUT,
            ProviderErrorReason.IDLE_TIMEOUT,
        ),
        (
            {"code": "future_error"},
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.UNKNOWN,
        ),
    ],
)
def test_codec_should_map_safe_closed_error_reasons(
    raw_error: dict[str, object],
    category: ProviderErrorCategory,
    reason: ProviderErrorReason,
) -> None:
    raw_error["message"] = "raw provider body with secret-token"
    event = StepFunEventCodec().decode_event(
        json.dumps({"type": "error", "error": raw_error}),
        connection_epoch=1,
    )
    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is category
    assert event.error_reason is reason
    assert event.data == {}
    assert "raw provider body" not in repr(event)
    assert "secret-token" not in repr(event)


class FakeConnection:
    def __init__(self, events: tuple[str | bytes, ...] = ()) -> None:
        self.events = deque(events)
        self.close_count = 0

    async def recv(self) -> str | bytes:
        return self.events.popleft()

    async def close(self) -> None:
        self.close_count += 1


class FakeTransport:
    def __init__(
        self,
        *,
        connection: FakeConnection | None = None,
        connect_error: StepFunUpstreamConnectError | None = None,
    ) -> None:
        self.connection = connection or FakeConnection()
        self.connect_error = connect_error
        self.connect_calls: list[dict[str, str]] = []
        self.sent: list[dict[str, object]] = []
        self.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
        self.health_result = StepFunHealthResult(status=StepFunHealthStatus.HEALTHY)
        self.close_calls = 0

    async def connect(self, *, api_key: str, url: str, model: str) -> FakeConnection:
        self.connect_calls.append({"api_key": api_key, "url": url, "model": model})
        if self.connect_error is not None:
            raise self.connect_error
        return self.connection

    async def send_json(
        self,
        _connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        self.sent.append(payload)
        return self.send_result

    async def check_health(
        self,
        _connection: object,
        *,
        timeout_seconds: float | None = None,
    ) -> StepFunHealthResult:
        del timeout_seconds
        return self.health_result

    def decide_backpressure(
        self,
        payload: dict[str, object],
        *,
        pending_bytes: int,
        policy: object,
    ) -> StepFunBackpressureResult:
        high_watermark = getattr(policy, "high_watermark_bytes")
        if (
            payload.get("type") == "input_audio_buffer.append"
            and pending_bytes > high_watermark
        ):
            return StepFunBackpressureResult(status=StepFunBackpressureStatus.DROP)
        return StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        await connection.close()


@pytest.mark.asyncio
async def test_adapter_should_connect_and_send_one_existing_session_update_payload() -> (
    None
):
    transport = FakeTransport()
    provider = StepFunRealtimeProvider(
        api_key="secret-api-key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    await provider.connect(_session_config())

    assert isinstance(provider, RealtimeProviderPort)
    assert transport.connect_calls == [
        {
            "api_key": "secret-api-key",
            "url": "wss://provider.example/realtime",
            "model": "stepaudio-2.5-realtime",
        }
    ]
    assert transport.sent == [
        {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": "qingchunshaonv",
                "temperature": 0.4,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {"type": "server_vad", "silence_duration_ms": 500},
                "input_audio_transcription": {"language": "zh", "model": "step-asr"},
                "instructions": "grounded instructions",
                "tools": [
                    {
                        "type": "function",
                        "name": "search_internal_knowledge",
                        "parameters": {"type": "object"},
                    }
                ],
            },
        }
    ]
    rendered = repr(provider)
    assert "secret-api-key" not in rendered
    assert "provider.example" not in rendered


@pytest.mark.parametrize(
    ("status_code", "category", "reason", "retryable"),
    [
        (
            401,
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.INVALID_CREDENTIALS,
            False,
        ),
        (402, ProviderErrorCategory.QUOTA, ProviderErrorReason.QUOTA_EXHAUSTED, False),
        (
            403,
            ProviderErrorCategory.AUTHENTICATION,
            ProviderErrorReason.FORBIDDEN,
            False,
        ),
        (429, ProviderErrorCategory.RATE_LIMIT, ProviderErrorReason.RATE_LIMITED, True),
        (
            503,
            ProviderErrorCategory.UNAVAILABLE,
            ProviderErrorReason.UPSTREAM_UNAVAILABLE,
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_adapter_should_map_connect_status_without_leaking_raw_message(
    status_code: int,
    category: ProviderErrorCategory,
    reason: ProviderErrorReason,
    retryable: bool,
) -> None:
    raw_message = "raw upstream body secret-token"
    transport = FakeTransport(
        connect_error=StepFunUpstreamConnectError(status_code, raw_message)
    )
    provider = StepFunRealtimeProvider(
        api_key="api-secret",
        url="wss://provider.example/realtime?region=cn",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.connect(_session_config())

    assert captured.value.category is category
    assert captured.value.reason is reason
    assert captured.value.retryable is retryable
    assert raw_message not in str(captured.value)
    assert raw_message not in repr(captured.value)
    assert "api-secret" not in repr(provider)


@pytest.mark.asyncio
async def test_adapter_should_send_receive_and_map_transport_failures() -> None:
    connection = FakeConnection(
        events=(b'{"type":"session.created","event_id":"event-1"}',)
    )
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    command = ProviderCommand(
        kind=ProviderCommandKind.APPEND_AUDIO,
        data={"audio": "AAE="},
    )

    assert (await provider.send(command)).accepted is True
    assert transport.sent[-1] == {"type": "input_audio_buffer.append", "audio": "AAE="}
    assert (await provider.receive(connection_epoch=9)).connection_epoch == 9

    transport.send_result = StepFunSendResult(
        status=StepFunSendStatus.FAILED,
        error_type="OSError",
    )
    failed = await provider.send(command)
    assert failed.accepted is False
    assert failed.error_category is ProviderErrorCategory.DISCONNECTED
    assert failed.error_reason is ProviderErrorReason.CONNECTION_CLOSED


@pytest.mark.asyncio
async def test_adapter_should_map_health_timeout_and_disconnect() -> None:
    transport = FakeTransport()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    disconnected = await provider.check_health(timeout_seconds=0.1)
    assert disconnected.healthy is False
    assert disconnected.error_reason is ProviderErrorReason.CONNECTION_CLOSED

    await provider.connect(_session_config())
    transport.health_result = StepFunHealthResult(
        status=StepFunHealthStatus.UNHEALTHY,
        error_type="TimeoutError",
    )
    timed_out = await provider.check_health(timeout_seconds=0.1)
    assert timed_out.healthy is False
    assert timed_out.error_category is ProviderErrorCategory.TIMEOUT
    assert timed_out.error_reason is ProviderErrorReason.IDLE_TIMEOUT


def test_adapter_should_delegate_backpressure_to_transport() -> None:
    transport = FakeTransport()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    audio = ProviderCommand(
        kind=ProviderCommandKind.APPEND_AUDIO,
        data={"audio": "AAE="},
    )
    control = ProviderCommand(kind=ProviderCommandKind.COMMIT_AUDIO, data={})

    assert provider.decide_backpressure(audio, pending_bytes=512 * 1024).accepted
    dropped: ProviderBackpressureResult = provider.decide_backpressure(
        audio,
        pending_bytes=512 * 1024 + 1,
    )
    assert dropped.accepted is False
    assert dropped.error_reason is ProviderErrorReason.BACKPRESSURE_LIMIT
    assert provider.decide_backpressure(
        control,
        pending_bytes=512 * 1024 + 1,
    ).accepted


@pytest.mark.asyncio
async def test_adapter_close_should_be_idempotent_and_allow_reconnect() -> None:
    connection = FakeConnection()
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    await provider.close()
    await provider.close()

    assert transport.close_calls == 1
    assert connection.close_count == 1
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
