"""Golden contracts for the StepFun realtime codec and Provider adapter."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Mapping
from pathlib import Path

import pytest
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)
from websockets.frames import Close

from training_runtime.realtime.provider import (
    ProviderBackpressureResult,
    ProviderCommand,
    ProviderCommandKind,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEvent,
    ProviderEventKind,
    ProviderHealthResult,
    ProviderSendResult,
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
    StepFunTransport,
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
        self.connect_exception: BaseException | None = None
        self.send_exception: BaseException | None = None
        self.health_exception: BaseException | None = None
        self.close_exception: BaseException | None = None
        self.connect_calls: list[dict[str, str]] = []
        self.sent: list[dict[str, object]] = []
        self.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
        self.health_result = StepFunHealthResult(status=StepFunHealthStatus.HEALTHY)
        self.close_calls = 0

    async def connect(self, *, api_key: str, url: str, model: str) -> FakeConnection:
        self.connect_calls.append({"api_key": api_key, "url": url, "model": model})
        if self.connect_exception is not None:
            raise self.connect_exception
        if self.connect_error is not None:
            raise self.connect_error
        return self.connection

    async def send_json(
        self,
        _connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        self.sent.append(payload)
        if self.send_exception is not None:
            raise self.send_exception
        return self.send_result

    async def check_health(
        self,
        _connection: object,
        *,
        timeout_seconds: float | None = None,
    ) -> StepFunHealthResult:
        del timeout_seconds
        if self.health_exception is not None:
            raise self.health_exception
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
        if self.close_exception is not None:
            raise self.close_exception


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
    assert captured.value.__cause__ is None
    assert "api-secret" not in repr(provider)


def _assert_safe_provider_error(
    error: RealtimeProviderError,
    *,
    category: ProviderErrorCategory,
    reason: ProviderErrorReason,
) -> None:
    assert error.category is category
    assert error.reason is reason
    assert error.__cause__ is None
    rendered = f"{error!s} {error!r}"
    assert "provider.example" not in rendered
    assert "secret-token" not in rendered
    assert "raw-body" not in rendered


@pytest.mark.asyncio
async def test_adapter_connect_should_fail_safe_for_unknown_exception() -> None:
    transport = FakeTransport()
    transport.connect_exception = Exception(
        "wss://provider.example/realtime?token=secret-token raw-body"
    )
    provider = StepFunRealtimeProvider(
        api_key="api-secret",
        url="wss://provider.example/realtime?region=cn",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.connect(_session_config())

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.UNAVAILABLE,
        reason=ProviderErrorReason.UPSTREAM_UNAVAILABLE,
    )


@pytest.mark.asyncio
async def test_adapter_connect_should_preserve_cancellation() -> None:
    transport = FakeTransport()
    transport.connect_exception = asyncio.CancelledError()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(asyncio.CancelledError):
        await provider.connect(_session_config())


@pytest.mark.asyncio
async def test_adapter_initial_send_should_close_socket_and_preserve_cancellation() -> (
    None
):
    connection = FakeConnection()
    transport = FakeTransport(connection=connection)
    transport.send_exception = asyncio.CancelledError()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(asyncio.CancelledError):
        await provider.connect(_session_config())

    assert transport.close_calls == 1
    assert connection.close_count == 1
    assert "connected=False" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_initial_send_should_close_socket_on_unknown_io_failures() -> (
    None
):
    connection = FakeConnection()
    transport = FakeTransport(connection=connection)
    transport.send_exception = Exception(
        "wss://provider.example/realtime?token=secret-token raw-body-send"
    )
    transport.close_exception = Exception("raw-body-close secret-token")
    provider = StepFunRealtimeProvider(
        api_key="api-secret",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.connect(_session_config())

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
    )
    assert transport.close_calls == 1
    assert connection.close_count == 1
    assert "connected=False" in repr(provider)


@pytest.mark.parametrize(
    ("exception_type", "close_code"),
    [(ConnectionClosedOK, 1000), (ConnectionClosedError, 1011)],
)
@pytest.mark.asyncio
async def test_adapter_initial_session_update_should_close_real_connection_closed(
    exception_type: type[ConnectionClosed],
    close_code: int,
) -> None:
    secret = "wss://provider.example/realtime?token=secret-token raw-body"
    closed = exception_type(Close(close_code, secret), None)

    class InitialSendClosedConnection(FakeConnection):
        async def send_json(self, payload: dict[str, object]) -> None:
            del payload
            raise closed

    connection = InitialSendClosedConnection()
    transport = StepFunTransport(
        local_provider_enabled=lambda: True,
        local_provider_factory=lambda: connection,
    )
    provider = StepFunRealtimeProvider(
        api_key="api-secret",
        url="wss://provider.example/realtime",
        transport=transport,
    )

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.connect(_session_config())

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
    )
    assert connection.close_count == 1


@pytest.mark.parametrize(
    ("exception_type", "close_code"),
    [(ConnectionClosedOK, 1000), (ConnectionClosedError, 1011)],
)
@pytest.mark.asyncio
async def test_adapter_receive_should_sanitize_real_websocket_close_exceptions(
    exception_type: type[ConnectionClosed],
    close_code: int,
) -> None:
    secret = "wss://provider.example/realtime?token=secret-query raw-body"
    closed = exception_type(Close(close_code, secret), None)

    class ClosedConnection(FakeConnection):
        async def recv(self) -> str | bytes:
            raise closed

    transport = FakeTransport(connection=ClosedConnection())
    provider = StepFunRealtimeProvider(
        api_key="api-secret",
        url="wss://provider.example/realtime?region=cn",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.receive(connection_epoch=2)

    assert captured.value.category is ProviderErrorCategory.DISCONNECTED
    assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert captured.value.retryable is True
    assert captured.value.__cause__ is None
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value)


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
async def test_adapter_send_should_fail_safe_for_unknown_exception() -> None:
    transport = FakeTransport()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.send_exception = Exception(
        "wss://provider.example/realtime?token=secret-token raw-body"
    )

    result = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.APPEND_AUDIO,
            data={"audio": "AAE="},
        )
    )

    assert result.accepted is False
    assert result.error_category is ProviderErrorCategory.DISCONNECTED
    assert result.error_reason is ProviderErrorReason.CONNECTION_CLOSED
    assert "secret-token" not in repr(result)


@pytest.mark.asyncio
async def test_adapter_receive_should_fail_safe_for_unknown_exception() -> None:
    class UnknownFailureConnection(FakeConnection):
        async def recv(self) -> str | bytes:
            raise Exception(
                "wss://provider.example/realtime?token=secret-token raw-body"
            )

    transport = FakeTransport(connection=UnknownFailureConnection())
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.receive(connection_epoch=3)

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
    )


@pytest.mark.asyncio
async def test_adapter_receive_should_fail_safe_when_codec_raises_on_invalid_frame() -> (
    None
):
    class InvalidFrameConnection(FakeConnection):
        async def recv(self) -> object:  # type: ignore[override]
            return object()

    class UnknownFailureCodec(StepFunEventCodec):
        def decode_event(
            self,
            raw: str | bytes,
            *,
            connection_epoch: int,
        ) -> ProviderEvent:
            del raw, connection_epoch
            raise Exception("raw-body secret-token")

    transport = FakeTransport(connection=InvalidFrameConnection())
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
        codec=UnknownFailureCodec(),
    )
    await provider.connect(_session_config())

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.receive(connection_epoch=3)

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
    )


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


@pytest.mark.asyncio
async def test_adapter_health_should_fail_safe_for_unknown_exception() -> None:
    transport = FakeTransport()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.health_exception = Exception(
        "wss://provider.example/realtime?token=secret-token raw-body"
    )

    result = await provider.check_health(timeout_seconds=0.1)

    assert result.healthy is False
    assert result.error_category is ProviderErrorCategory.DISCONNECTED
    assert result.error_reason is ProviderErrorReason.CONNECTION_CLOSED
    assert "secret-token" not in repr(result)


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


@pytest.mark.asyncio
async def test_adapter_close_should_clear_state_and_sanitize_unknown_exception() -> (
    None
):
    connection = FakeConnection()
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.close_exception = Exception(
        "wss://provider.example/realtime?token=secret-token raw-body"
    )

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.close()

    _assert_safe_provider_error(
        captured.value,
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
    )
    assert transport.close_calls == 1
    assert connection.close_count == 1
    assert "connected=False" in repr(provider)
    transport.close_exception = None
    await provider.close()
    assert transport.close_calls == 2


class SequencedTransport(FakeTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connection=connections[0])
        self.connections = deque(connections)

    async def connect(self, *, api_key: str, url: str, model: str) -> FakeConnection:
        self.connect_calls.append({"api_key": api_key, "url": url, "model": model})
        return self.connections.popleft()


class LinearizedConnectTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.first_connect_started = asyncio.Event()
        self.release_first_connect = asyncio.Event()
        self.session_update_connections: list[FakeConnection] = []

    async def connect(self, *, api_key: str, url: str, model: str) -> FakeConnection:
        self.connect_calls.append({"api_key": api_key, "url": url, "model": model})
        connection = self.connections.popleft()
        if len(self.connect_calls) == 1:
            self.first_connect_started.set()
            await self.release_first_connect.wait()
        return connection

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        assert isinstance(connection, FakeConnection)
        self.sent.append(payload)
        if payload.get("type") == "session.update":
            self.session_update_connections.append(connection)
        return self.send_result


@pytest.mark.asyncio
async def test_adapter_concurrent_connect_should_open_and_configure_once() -> None:
    connection = FakeConnection()
    transport = LinearizedConnectTransport((connection,))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    first = asyncio.create_task(provider.connect(_session_config()))
    await transport.first_connect_started.wait()

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.connect(_session_config())

    assert captured.value.category is ProviderErrorCategory.PROTOCOL
    assert len(transport.connect_calls) == 1
    assert transport.session_update_connections == []
    transport.release_first_connect.set()
    await first
    assert len(transport.connect_calls) == 1
    assert transport.session_update_connections == [connection]
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_close_during_connect_should_not_revive_stale_connection() -> (
    None
):
    stale_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = LinearizedConnectTransport((stale_connection, current_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    stale_connect = asyncio.create_task(provider.connect(_session_config()))
    await transport.first_connect_started.wait()
    await provider.close()
    await provider.connect(_session_config())
    assert "connected=True" in repr(provider)

    transport.release_first_connect.set()
    with pytest.raises(RealtimeProviderError) as captured:
        await stale_connect

    assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
    assert transport.session_update_connections == [current_connection]
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_cancel_during_connect_should_release_lifecycle_for_reconnect() -> (
    None
):
    stale_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = LinearizedConnectTransport((stale_connection, current_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    cancelled = asyncio.create_task(provider.connect(_session_config()))
    await transport.first_connect_started.wait()
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert transport.session_update_connections == [current_connection]
    assert "connected=True" in repr(provider)


@pytest.mark.parametrize("operation", ["send", "receive", "health"])
@pytest.mark.asyncio
async def test_adapter_terminal_current_io_should_disconnect_close_and_reconnect(
    operation: str,
) -> None:
    first_connection = FakeConnection()
    second_connection = FakeConnection()
    transport = SequencedTransport((first_connection, second_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    if operation == "send":
        transport.send_result = StepFunSendResult(
            status=StepFunSendStatus.FAILED,
            error_type="ConnectionClosedError",
        )
        result = await provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.APPEND_AUDIO,
                data={"audio": "AAE="},
            )
        )
        assert result.accepted is False
    elif operation == "receive":
        with pytest.raises(RealtimeProviderError) as captured:
            await provider.receive(connection_epoch=1)
        assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    else:
        transport.health_result = StepFunHealthResult(
            status=StepFunHealthStatus.UNHEALTHY,
            error_type="ConnectionClosedError",
        )
        result = await provider.check_health()
        assert result.error_reason is ProviderErrorReason.CONNECTION_CLOSED

    assert first_connection.close_count == 1
    assert "connected=False" in repr(provider)
    transport.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    transport.health_result = StepFunHealthResult(status=StepFunHealthStatus.HEALTHY)
    await provider.connect(_session_config())
    assert "connected=True" in repr(provider)
    assert second_connection.close_count == 0


class LateSendTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.send_started = asyncio.Event()
        self.release_send = asyncio.Event()

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        del connection
        self.sent.append(payload)
        if payload.get("type") != "input_audio_buffer.append":
            return StepFunSendResult(status=StepFunSendStatus.SENT)
        self.send_started.set()
        await self.release_send.wait()
        return StepFunSendResult(
            status=StepFunSendStatus.FAILED,
            error_type="ConnectionClosedError",
        )


@pytest.mark.asyncio
async def test_adapter_late_stale_send_failure_should_not_clear_new_connection() -> (
    None
):
    stale_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = LateSendTransport((stale_connection, current_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    late_send = asyncio.create_task(
        provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.APPEND_AUDIO,
                data={"audio": "AAE="},
            )
        )
    )
    await transport.send_started.wait()
    await provider.close()
    await provider.connect(_session_config())

    transport.release_send.set()
    result = await late_send

    assert result.accepted is False
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_timeout_and_protocol_error_should_keep_current_connection() -> (
    None
):
    connection = FakeConnection(events=("not-json",))
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.health_result = StepFunHealthResult(
        status=StepFunHealthStatus.UNHEALTHY,
        error_type="TimeoutError",
    )

    health = await provider.check_health(timeout_seconds=0.1)
    event = await provider.receive(connection_epoch=4)

    assert health.error_reason is ProviderErrorReason.IDLE_TIMEOUT
    assert event.kind is ProviderEventKind.ERROR
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    assert connection.close_count == 0
    assert "connected=True" in repr(provider)


def test_codec_extreme_json_depth_should_map_to_protocol_error() -> None:
    raw = (
        '{"type":"conversation.item.input_audio_transcription.completed",'
        '"content":' + "[" * 1500 + '"deep"' + "]" * 1500 + "}"
    )

    event = StepFunEventCodec().decode_event(raw, connection_epoch=7)

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT


class LateReceiveConnection(FakeConnection):
    def __init__(self) -> None:
        super().__init__()
        self.receive_started = asyncio.Event()
        self.release_receive = asyncio.Event()

    async def recv(self) -> str | bytes:
        self.receive_started.set()
        await self.release_receive.wait()
        return '{"type":"session.created"}'


class StaleSuccessTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.send_started = asyncio.Event()
        self.release_send = asyncio.Event()
        self.health_started = asyncio.Event()
        self.release_health = asyncio.Event()
        self.late_health_result = StepFunHealthResult(
            status=StepFunHealthStatus.HEALTHY
        )

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        del connection
        self.sent.append(payload)
        if payload.get("type") != "input_audio_buffer.append":
            return StepFunSendResult(status=StepFunSendStatus.SENT)
        self.send_started.set()
        await self.release_send.wait()
        return StepFunSendResult(status=StepFunSendStatus.SENT)

    async def check_health(
        self,
        connection: object,
        *,
        timeout_seconds: float | None = None,
    ) -> StepFunHealthResult:
        del connection, timeout_seconds
        self.health_started.set()
        await self.release_health.wait()
        return self.late_health_result


@pytest.mark.parametrize(
    "operation",
    ["send", "receive", "health_healthy", "health_timeout"],
)
@pytest.mark.asyncio
async def test_adapter_stale_success_and_nonterminal_results_should_fail_closed(
    operation: str,
) -> None:
    stale_connection: FakeConnection
    if operation == "receive":
        stale_connection = LateReceiveConnection()
    else:
        stale_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = StaleSuccessTransport((stale_connection, current_connection))
    if operation == "health_timeout":
        transport.late_health_result = StepFunHealthResult(
            status=StepFunHealthStatus.UNHEALTHY,
            error_type="TimeoutError",
        )
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    if operation == "send":
        pending = asyncio.create_task(
            provider.send(
                ProviderCommand(
                    kind=ProviderCommandKind.APPEND_AUDIO,
                    data={"audio": "AAE="},
                )
            )
        )
        await transport.send_started.wait()
    elif operation == "receive":
        assert isinstance(stale_connection, LateReceiveConnection)
        pending = asyncio.create_task(provider.receive(connection_epoch=5))
        await stale_connection.receive_started.wait()
    else:
        pending = asyncio.create_task(provider.check_health(timeout_seconds=0.1))
        await transport.health_started.wait()

    await provider.close()
    await provider.connect(_session_config())
    if operation == "send":
        transport.release_send.set()
        send_result = await pending
        assert isinstance(send_result, ProviderSendResult)
        assert send_result.accepted is False
    elif operation == "receive":
        stale_connection.release_receive.set()
        with pytest.raises(RealtimeProviderError) as captured:
            await pending
        assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    else:
        transport.release_health.set()
        health_result = await pending
        assert isinstance(health_result, ProviderHealthResult)
        assert health_result.healthy is False
        assert health_result.error_reason is ProviderErrorReason.CONNECTION_CLOSED

    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_connect_cleanup_should_preserve_original_cancellation() -> None:
    transport = FakeTransport()
    transport.send_exception = asyncio.CancelledError("primary-cancel")
    transport.close_exception = asyncio.CancelledError("cleanup-cancel")
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(asyncio.CancelledError) as captured:
        await provider.connect(_session_config())

    assert captured.value.args == ("primary-cancel",)
    transport.send_exception = None
    transport.close_exception = None
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    await provider.close()
    await provider.connect(_session_config())
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_connect_cleanup_base_exception_should_release_reservation() -> (
    None
):
    class CleanupBaseFailure(BaseException):
        pass

    transport = FakeTransport()
    transport.send_exception = Exception("raw-body secret-token")
    transport.close_exception = CleanupBaseFailure("cleanup-base")
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    with pytest.raises(CleanupBaseFailure) as captured:
        await provider.connect(_session_config())

    assert captured.value.args == ("cleanup-base",)
    transport.send_exception = None
    transport.close_exception = None
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    await provider.close()
    await provider.connect(_session_config())
    assert "connected=True" in repr(provider)


class BlockedInitialSessionUpdateTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.first_connection = connections[0]
        self.initial_send_started = asyncio.Event()
        self.release_initial_send = asyncio.Event()
        self.completed_session_updates: list[FakeConnection] = []

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        assert isinstance(connection, FakeConnection)
        self.sent.append(payload)
        if (
            payload.get("type") == "session.update"
            and connection is self.first_connection
        ):
            self.initial_send_started.set()
            await self.release_initial_send.wait()
        if payload.get("type") == "session.update":
            self.completed_session_updates.append(connection)
        return StepFunSendResult(status=StepFunSendStatus.SENT)


@pytest.mark.asyncio
async def test_adapter_close_should_detach_and_close_blocked_pending_connection() -> (
    None
):
    pending_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = BlockedInitialSessionUpdateTransport(
        (pending_connection, current_connection)
    )
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    stale_connect = asyncio.create_task(provider.connect(_session_config()))
    await transport.initial_send_started.wait()
    await provider.close()
    pending_close_count_at_close_return = pending_connection.close_count
    await provider.connect(_session_config())

    transport.release_initial_send.set()
    with pytest.raises(RealtimeProviderError) as captured:
        await stale_connect

    assert pending_close_count_at_close_return == 1
    assert pending_connection.close_count == 1
    assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert transport.completed_session_updates == [
        current_connection,
        pending_connection,
    ]
    assert current_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_pending_connect_cancellation_after_close_should_not_double_close() -> (
    None
):
    pending_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = BlockedInitialSessionUpdateTransport(
        (pending_connection, current_connection)
    )
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    stale_connect = asyncio.create_task(provider.connect(_session_config()))
    await transport.initial_send_started.wait()
    await provider.close()
    pending_close_count_at_close_return = pending_connection.close_count
    await provider.connect(_session_config())

    stale_connect.cancel()
    with pytest.raises(asyncio.CancelledError):
        await stale_connect

    assert pending_close_count_at_close_return == 1
    assert pending_connection.close_count == 1
    assert current_connection.close_count == 0
    assert "connected=True" in repr(provider)


class BlockingCloseTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        self.close_started.set()
        await self.release_close.wait()
        await connection.close()


class RetryableCloseTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.fail_close = True

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        if self.fail_close:
            raise Exception("wss://provider.example?token=secret-token raw-body")
        await connection.close()


@pytest.mark.asyncio
async def test_adapter_cancelled_public_close_should_finish_physical_cleanup() -> None:
    closing_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = BlockingCloseTransport((closing_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    closing = asyncio.create_task(provider.close())
    await transport.close_started.wait()
    closing.cancel()
    await asyncio.sleep(0)
    close_done_before_release = closing.done()
    transport.release_close.set()

    with pytest.raises(asyncio.CancelledError):
        await closing

    assert close_done_before_release is False
    assert closing_connection.close_count == 1
    assert transport.close_calls == 1
    assert "connected=False" in repr(provider)
    await provider.close()
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_failed_public_close_should_require_safe_cleanup_retry() -> None:
    failed_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = RetryableCloseTransport((failed_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    with pytest.raises(RealtimeProviderError) as captured:
        await provider.close()

    assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert captured.value.__cause__ is None
    assert "secret-token" not in repr(captured.value)
    assert failed_connection.close_count == 0
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED

    transport.fail_close = False
    await provider.close()
    assert failed_connection.close_count == 1
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.parametrize(
    "constant",
    ["NaN", "Infinity", "-Infinity", "1e400"],
)
def test_codec_should_reject_nested_non_finite_json_constants(constant: str) -> None:
    raw = '{"type":"session.created","nested":{"values":[0,' + constant + "]}}"

    event = StepFunEventCodec().decode_event(raw, connection_epoch=8)

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT


def test_codec_command_encode_should_reject_nested_non_finite_number() -> None:
    unsafe_command = object.__new__(ProviderCommand)
    object.__setattr__(
        unsafe_command,
        "kind",
        ProviderCommandKind.CREATE_CONVERSATION_ITEM,
    )
    object.__setattr__(
        unsafe_command,
        "data",
        {
            "role": "user",
            "content": (
                {
                    "type": "input_text",
                    "text": {"unsafe": float("nan")},
                },
            ),
        },
    )

    with pytest.raises(ValueError, match="finite"):
        StepFunEventCodec().encode_command(unsafe_command)


@pytest.mark.parametrize("operation", ["send", "receive", "health"])
@pytest.mark.asyncio
async def test_adapter_terminal_retirement_should_block_concurrent_reconnect(
    operation: str,
) -> None:
    retiring_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = BlockingCloseTransport((retiring_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    if operation == "send":
        transport.send_result = StepFunSendResult(
            status=StepFunSendStatus.FAILED,
            error_type="ConnectionClosedError",
        )
        terminal_operation = asyncio.create_task(
            provider.send(
                ProviderCommand(
                    kind=ProviderCommandKind.APPEND_AUDIO,
                    data={"audio": "AAE="},
                )
            )
        )
    elif operation == "receive":
        terminal_operation = asyncio.create_task(provider.receive(connection_epoch=1))
    else:
        transport.health_result = StepFunHealthResult(
            status=StepFunHealthStatus.UNHEALTHY,
            error_type="ConnectionClosedError",
        )
        terminal_operation = asyncio.create_task(provider.check_health())

    await transport.close_started.wait()
    public_close = asyncio.create_task(provider.close())
    await asyncio.sleep(0)
    public_close_done_before_release = public_close.done()
    transport.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    reconnect_error: RealtimeProviderError | None = None
    try:
        await provider.connect(_session_config())
    except RealtimeProviderError as error:
        reconnect_error = error
    transport.release_close.set()
    await public_close

    if operation == "receive":
        with pytest.raises(RealtimeProviderError):
            await terminal_operation
    else:
        await terminal_operation

    assert reconnect_error is not None
    assert reconnect_error.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert public_close_done_before_release is False
    assert len(transport.connect_calls) == 1
    assert transport.close_calls == 1
    assert retiring_connection.close_count == 1
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_terminal_retirement_failure_should_retry_before_reconnect() -> (
    None
):
    retiring_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = RetryableCloseTransport((retiring_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.send_result = StepFunSendResult(
        status=StepFunSendStatus.FAILED,
        error_type="ConnectionClosedError",
    )

    result = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.APPEND_AUDIO,
            data={"audio": "AAE="},
        )
    )

    assert result.accepted is False
    assert retiring_connection.close_count == 0
    transport.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert len(transport.connect_calls) == 1

    transport.fail_close = False
    await provider.close()
    assert retiring_connection.close_count == 1
    assert transport.close_calls == 2
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0


@pytest.mark.parametrize("primary_outcome", ["failed", "cancelled"])
@pytest.mark.asyncio
async def test_adapter_initial_send_cleanup_failure_should_block_until_close_retry(
    primary_outcome: str,
) -> None:
    failed_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = RetryableCloseTransport((failed_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    if primary_outcome == "failed":
        transport.send_result = StepFunSendResult(
            status=StepFunSendStatus.FAILED,
            error_type="ConnectionClosedError",
        )
        with pytest.raises(RealtimeProviderError) as captured:
            await provider.connect(_session_config())
        assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    else:
        transport.send_exception = asyncio.CancelledError()
        with pytest.raises(asyncio.CancelledError):
            await provider.connect(_session_config())

    assert failed_connection.close_count == 0
    assert transport.close_calls == 1
    transport.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    transport.send_exception = None
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert len(transport.connect_calls) == 1

    transport.fail_close = False
    await provider.close()
    assert failed_connection.close_count == 1
    assert transport.close_calls == 2
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0
    assert "connected=True" in repr(provider)
