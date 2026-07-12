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
                data={
                    "modalities": ("audio", "text"),
                    "instructions": "grounded",
                    "request_id": 7,
                    "stream_id": "stream-local-7",
                },
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


def test_codec_accepts_stepaudio_2_5_pending_audio_item_with_empty_transcript() -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "event_id": "00000000-0000-4000-8000-000000000001",
                "type": "conversation.item.created",
                "item": {
                    "id": "item-1",
                    "object": "realtime.item",
                    "type": "message",
                    "status": "in_progress",
                    "role": "user",
                    "content": [{"type": "audio", "audio": "", "transcript": ""}],
                },
            }
        ),
        connection_epoch=1,
    )

    assert event.kind is ProviderEventKind.CONVERSATION_ITEM
    assert event.data["item_type"] == "message"
    assert event.data["role"] == "user"
    assert "transcript" not in event.data


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
    "raw_event_type",
    ["sk-live-secret", "provider.example", "query-secret"],
)
@pytest.mark.parametrize(
    "invalid_metadata",
    [
        {"request_id": "raw-request-secret"},
        {"response_id": ""},
        {"stream_id": {"raw": "stream-secret"}},
        {"call_id": ["call-secret"]},
        {"event_id": " "},
        {"turn_id": 123},
    ],
)
def test_codec_unknown_type_should_ignore_malformed_common_metadata(
    raw_event_type: str,
    invalid_metadata: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": raw_event_type,
                **invalid_metadata,
                "raw_data": "raw-body-secret",
            }
        ),
        connection_epoch=9,
    )

    assert event.kind is ProviderEventKind.UNKNOWN
    assert event.provider_event_type == "unknown"
    assert event.connection_epoch == 9
    assert event.request_id is None
    assert event.response_id is None
    assert event.stream_id is None
    assert event.call_id is None
    assert event.event_id is None
    assert event.turn_id is None
    assert event.timestamp_ms is None
    assert event.duration_ms is None
    assert event.data == {}
    rendered = f"{event!r} {event!s} {caplog.text}"
    assert raw_event_type not in rendered
    assert "raw-request-secret" not in rendered
    assert "stream-secret" not in rendered
    assert "call-secret" not in rendered
    assert "raw-body-secret" not in rendered


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


@pytest.mark.parametrize(
    "identifier_field",
    ["response_id", "stream_id", "call_id", "event_id", "turn_id"],
)
def test_codec_error_event_should_discard_all_upstream_identifiers(
    identifier_field: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    polluted = "wss://provider.example/realtime?api_key=secret-token raw-body"
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": "error",
                identifier_field: polluted,
                "error": {"status": 429, "message": polluted},
            }
        ),
        connection_epoch=2,
    )

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.RATE_LIMIT
    assert event.error_reason is ProviderErrorReason.RATE_LIMITED
    assert event.request_id is None
    assert event.response_id is None
    assert event.stream_id is None
    assert event.call_id is None
    assert event.event_id is None
    assert event.turn_id is None
    rendered = f"{event!r} {caplog.text}"
    assert "provider.example" not in rendered
    assert "secret-token" not in rendered
    assert "raw-body" not in rendered


@pytest.mark.parametrize(
    "metadata",
    [
        {"response_id": "POLLUTED"},
        {"response": {"id": "POLLUTED"}},
        {"stream_id": "POLLUTED"},
        {"call_id": "POLLUTED"},
        {"item": {"call_id": "POLLUTED"}},
        {"event_id": "POLLUTED"},
        {"id": "POLLUTED"},
        {"turn_id": "POLLUTED"},
        {"item_id": "POLLUTED"},
    ],
)
def test_codec_should_fail_closed_for_unsafe_event_identifier_metadata(
    metadata: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    polluted = "wss://provider.example/realtime?api_key=secret-token raw-body"
    raw = {
        "type": "session.created",
        **json.loads(json.dumps(metadata).replace("POLLUTED", polluted)),
    }

    event = StepFunEventCodec().decode_event(
        json.dumps(raw),
        connection_epoch=2,
    )

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    assert event.response_id is None
    assert event.stream_id is None
    assert event.call_id is None
    assert event.event_id is None
    assert event.turn_id is None
    rendered = f"{event!r} {caplog.text}"
    assert "provider.example" not in rendered
    assert "secret-token" not in rendered
    assert "raw-body" not in rendered


def test_codec_should_fail_closed_for_unsafe_function_output_call_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    polluted = "wss://provider.example/realtime?api_key=secret-token raw-body"
    event = StepFunEventCodec().decode_event(
        json.dumps(
            {
                "type": "response.done",
                "response_id": "response-safe",
                "response": {
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": polluted,
                            "name": "safe_name",
                            "arguments": "{}",
                        }
                    ]
                },
            }
        ),
        connection_epoch=2,
    )

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    rendered = f"{event!r} {caplog.text}"
    assert "provider.example" not in rendered
    assert "secret-token" not in rendered
    assert "raw-body" not in rendered


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


class ControlledCreateTransport(FakeTransport):
    def __init__(self, *, connection: FakeConnection) -> None:
        super().__init__(connection=connection)
        self.create_started = asyncio.Event()
        self.release_create = asyncio.Event()
        self.create_result = StepFunSendResult(status=StepFunSendStatus.SENT)

    async def send_json(
        self,
        _connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        self.sent.append(payload)
        if payload.get("type") == "session.update":
            return StepFunSendResult(status=StepFunSendStatus.SENT)
        if payload.get("type") == "response.create":
            self.create_started.set()
            await self.release_create.wait()
            return self.create_result
        return StepFunSendResult(status=StepFunSendStatus.SENT)


class DecodeTrackingCodec(StepFunEventCodec):
    def __init__(self) -> None:
        super().__init__()
        self.decoded = asyncio.Event()

    def decode_event(
        self,
        raw: str | bytes,
        *,
        connection_epoch: int,
    ) -> ProviderEvent:
        event = super().decode_event(raw, connection_epoch=connection_epoch)
        self.decoded.set()
        return event


class ControlledReceiveCancellationTransport(ControlledCreateTransport):
    def __init__(self, *, connection: FakeConnection) -> None:
        super().__init__(connection=connection)
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        self.close_started.set()
        await self.release_close.wait()
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


@pytest.mark.asyncio
async def test_adapter_correlates_real_sparse_response_and_tool_events_then_cleans_done() -> (
    None
):
    connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-7"}}',
            '{"type":"response.text.delta","delta":"hello"}',
            '{"type":"conversation.item.created","item":{"type":"function_call","call_id":"call-7","name":"search_internal_knowledge"}}',
            '{"type":"response.function_call_arguments.done","call_id":"call-7","name":"search_internal_knowledge","arguments":"{}"}',
            '{"type":"response.done","response":{"output":[{"type":"function_call","call_id":"call-7","name":"search_internal_knowledge","arguments":"{}"}]}}',
            '{"type":"response.function_call_arguments.done","call_id":"call-7","name":"search_internal_knowledge","arguments":"{}"}',
        )
    )
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    result = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_RESPONSE,
            data={
                "modalities": ("audio", "text"),
                "request_id": 7,
                "stream_id": "stream-7",
            },
        )
    )

    assert result.accepted is True
    assert transport.sent[-1] == {
        "type": "response.create",
        "response": {"modalities": ["audio", "text"]},
    }
    created = await provider.receive(connection_epoch=3)
    text_delta = await provider.receive(connection_epoch=3)
    item_created = await provider.receive(connection_epoch=3)
    arguments_done = await provider.receive(connection_epoch=3)
    response_done = await provider.receive(connection_epoch=3)
    late_arguments = await provider.receive(connection_epoch=3)

    for event in (
        created,
        text_delta,
        item_created,
        arguments_done,
        response_done,
    ):
        assert event.request_id == 7
        assert event.response_id == "response-7"
        assert event.stream_id == "stream-7"
    assert item_created.call_id == "call-7"
    assert arguments_done.call_id == "call-7"
    assert late_arguments.request_id is None
    assert late_arguments.response_id is None
    assert late_arguments.stream_id is None


@pytest.mark.asyncio
async def test_adapter_does_not_register_failed_or_mismatched_response_authority() -> None:
    stale_connection = FakeConnection()
    current_connection = FakeConnection(
        events=(
            '{"type":"response.created","request_id":99,"response":{"id":"response-wrong"}}',
            '{"type":"response.created","response":{"id":"response-current"}}',
        )
    )
    transport = SequencedTransport((stale_connection, current_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    transport.send_result = StepFunSendResult(
        status=StepFunSendStatus.FAILED,
        error_type="ConnectionClosed",
    )

    rejected = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_RESPONSE,
            data={
                "modalities": ("audio", "text"),
                "request_id": 7,
                "stream_id": "stream-7",
            },
        )
    )
    assert rejected.accepted is False

    transport.send_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    await provider.connect(_session_config())
    accepted = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_RESPONSE,
            data={
                "modalities": ("audio", "text"),
                "request_id": 8,
                "stream_id": "stream-8",
            },
        )
    )
    assert accepted.accepted is True

    mismatched = await provider.receive(connection_epoch=4)
    correlated = await provider.receive(connection_epoch=4)

    assert mismatched.request_id == 99
    assert mismatched.stream_id is None
    assert correlated.request_id == 8
    assert correlated.response_id == "response-current"
    assert correlated.stream_id == "stream-8"


@pytest.mark.asyncio
async def test_adapter_cancel_command_clears_response_and_call_correlation() -> None:
    connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-7"}}',
            '{"type":"response.text.delta","delta":"late"}',
        )
    )
    transport = FakeTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_RESPONSE,
            data={
                "modalities": ("audio", "text"),
                "request_id": 7,
                "stream_id": "stream-7",
            },
        )
    )
    created = await provider.receive(connection_epoch=3)
    assert created.request_id == 7

    cancelled = await provider.send(
        ProviderCommand(
            kind=ProviderCommandKind.CANCEL_RESPONSE,
            data={"response_id": "response-7"},
        )
    )
    late = await provider.receive(connection_epoch=3)

    assert cancelled.accepted is True
    assert late.request_id is None
    assert late.response_id is None
    assert late.stream_id is None


@pytest.mark.parametrize("send_outcome", ["sent", "failed", "cancelled"])
@pytest.mark.asyncio
async def test_adapter_created_before_create_send_result_waits_for_transaction_outcome(
    send_outcome: str,
) -> None:
    connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-race"}}',
        )
    )
    transport = ControlledCreateTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    sending = asyncio.create_task(
        provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.CREATE_RESPONSE,
                data={
                    "modalities": ("audio", "text"),
                    "request_id": 7,
                    "stream_id": "stream-race",
                },
            )
        )
    )
    await transport.create_started.wait()
    receiving = asyncio.create_task(provider.receive(connection_epoch=3))
    await asyncio.sleep(0)

    assert receiving.done() is False

    if send_outcome == "cancelled":
        sending.cancel("cancel-create-send")
        with pytest.raises(asyncio.CancelledError):
            await sending
    else:
        if send_outcome == "failed":
            transport.create_result = StepFunSendResult(
                status=StepFunSendStatus.FAILED,
                error_type="ConnectionClosed",
            )
        transport.release_create.set()
        result = await sending
        assert result.accepted is (send_outcome == "sent")

    if send_outcome == "sent":
        event = await receiving
        assert event.request_id == 7
        assert event.response_id == "response-race"
        assert event.stream_id == "stream-race"
    else:
        with pytest.raises(RealtimeProviderError) as captured:
            await receiving
        assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED


@pytest.mark.asyncio
async def test_adapter_mismatched_created_before_send_result_still_waits_for_transaction() -> (
    None
):
    connection = FakeConnection(
        events=(
            '{"type":"response.created","request_id":99,"response":{"id":"response-other"}}',
        )
    )
    transport = ControlledCreateTransport(connection=connection)
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    sending = asyncio.create_task(
        provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.CREATE_RESPONSE,
                data={
                    "modalities": ("audio", "text"),
                    "request_id": 7,
                    "stream_id": "stream-race",
                },
            )
        )
    )
    await transport.create_started.wait()
    receiving = asyncio.create_task(provider.receive(connection_epoch=3))
    await asyncio.sleep(0)

    assert receiving.done() is False

    transport.release_create.set()
    assert (await sending).accepted is True
    event = await receiving
    assert event.request_id == 99
    assert event.response_id == "response-other"
    assert event.stream_id is None


@pytest.mark.parametrize("send_outcome", ["sent", "failed"])
@pytest.mark.asyncio
async def test_adapter_cancelled_receive_after_decode_retires_generation_before_send_result(
    send_outcome: str,
) -> None:
    cancelled_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-cancelled"}}',
        )
    )
    reconnect_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-new"}}',
        )
    )
    transport = ControlledReceiveCancellationTransport(
        connection=cancelled_connection
    )
    codec = DecodeTrackingCodec()
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
        codec=codec,
    )
    await provider.connect(_session_config())
    create = ProviderCommand(
        kind=ProviderCommandKind.CREATE_RESPONSE,
        data={
            "modalities": ("audio", "text"),
            "request_id": 7,
            "stream_id": "stream-cancelled",
        },
    )
    sending = asyncio.create_task(provider.send(create))
    await transport.create_started.wait()
    receiving = asyncio.create_task(provider.receive(connection_epoch=3))
    await codec.decoded.wait()

    receiving.cancel("first-receive-cancel")
    for _ in range(5):
        if transport.close_started.is_set():
            break
        await asyncio.sleep(0)

    if not transport.close_started.is_set():
        transport.release_create.set()
        transport.release_close.set()
        await asyncio.gather(sending, receiving, return_exceptions=True)
        pytest.fail("cancelled receive did not retire its decoded generation")
    assert receiving.done() is False

    if send_outcome == "failed":
        transport.create_result = StepFunSendResult(
            status=StepFunSendStatus.FAILED,
            error_type="ConnectionClosed",
        )
    transport.release_create.set()
    assert (await sending).accepted is False

    receiving.cancel("second-receive-cancel")
    await asyncio.sleep(0)
    assert receiving.done() is False
    with pytest.raises(RealtimeProviderError):
        await provider.connect(_session_config())

    transport.release_close.set()
    with pytest.raises(asyncio.CancelledError) as captured:
        await receiving

    assert captured.value.args == ("first-receive-cancel",)
    assert transport.close_calls == 1
    assert cancelled_connection.close_count == 1
    assert "connected=False" in repr(provider)

    transport.connection = reconnect_connection
    transport.create_result = StepFunSendResult(status=StepFunSendStatus.SENT)
    await provider.connect(_session_config())
    new_create = ProviderCommand(
        kind=ProviderCommandKind.CREATE_RESPONSE,
        data={
            "modalities": ("audio", "text"),
            "request_id": 8,
            "stream_id": "stream-new",
        },
    )
    assert (await provider.send(new_create)).accepted is True
    created = await provider.receive(connection_epoch=4)
    assert created.request_id == 8
    assert created.response_id == "response-new"
    assert created.stream_id == "stream-new"


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


@pytest.mark.asyncio
async def test_adapter_cancel_requires_new_generation_before_next_response_claim() -> None:
    old_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-old"}}',
        )
    )
    new_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-new"}}',
        )
    )
    transport = SequencedTransport((old_connection, new_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    old_create = ProviderCommand(
        kind=ProviderCommandKind.CREATE_RESPONSE,
        data={
            "modalities": ("audio", "text"),
            "request_id": 1,
            "stream_id": "stream-old",
        },
    )
    new_create = ProviderCommand(
        kind=ProviderCommandKind.CREATE_RESPONSE,
        data={
            "modalities": ("audio", "text"),
            "request_id": 2,
            "stream_id": "stream-new",
        },
    )
    assert (await provider.send(old_create)).accepted is True
    assert (
        await provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.CANCEL_RESPONSE,
                data={},
            )
        )
    ).accepted is True

    same_generation = await provider.send(new_create)
    late_old = await provider.receive(connection_epoch=4)

    assert same_generation.accepted is False
    assert late_old.response_id == "response-old"
    assert late_old.request_id is None
    assert late_old.stream_id is None

    await provider.close()
    await provider.connect(_session_config())
    assert (await provider.send(new_create)).accepted is True
    created = await provider.receive(connection_epoch=5)
    assert created.request_id == 2
    assert created.response_id == "response-new"
    assert created.stream_id == "stream-new"


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
        if payload.get("type") not in {
            "input_audio_buffer.append",
            "response.create",
        }:
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
        if payload.get("type") not in {
            "input_audio_buffer.append",
            "response.create",
        }:
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
    current_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-current"}}',
        )
        if operation == "send"
        else ()
    )
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
                    kind=ProviderCommandKind.CREATE_RESPONSE,
                    data={
                        "modalities": ("audio", "text"),
                        "request_id": 7,
                        "stream_id": "stream-stale",
                    },
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
        uncorrelated = await provider.receive(connection_epoch=5)
        assert uncorrelated.response_id == "response-current"
        assert uncorrelated.request_id is None
        assert uncorrelated.stream_id is None
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


class CancelledSendTransport(BlockingCloseTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.send_started = asyncio.Event()

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        del connection
        self.sent.append(payload)
        if payload.get("type") == "session.update":
            return StepFunSendResult(status=StepFunSendStatus.SENT)
        self.send_started.set()
        await asyncio.Event().wait()
        raise AssertionError("cancelled send must not resume")


class RetryableCloseTransport(SequencedTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.fail_close = True

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        if self.fail_close:
            raise Exception("wss://provider.example?token=secret-token raw-body")
        await connection.close()


class CancelledSendRetryTransport(RetryableCloseTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.send_started = asyncio.Event()

    async def send_json(
        self,
        connection: object,
        payload: dict[str, object],
    ) -> StepFunSendResult:
        del connection
        self.sent.append(payload)
        if payload.get("type") == "session.update":
            return StepFunSendResult(status=StepFunSendStatus.SENT)
        self.send_started.set()
        await asyncio.Event().wait()
        raise AssertionError("cancelled send must not resume")


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


@pytest.mark.asyncio
async def test_adapter_cancelled_send_cleanup_failure_should_preserve_retry() -> None:
    failed_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = CancelledSendRetryTransport((failed_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    sending = asyncio.create_task(
        provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.APPEND_AUDIO,
                data={"audio": "AAE="},
            )
        )
    )
    await transport.send_started.wait()

    sending.cancel("send-cancel-before-cleanup-failure")
    with pytest.raises(asyncio.CancelledError) as captured:
        await sending

    assert captured.value.args == ("send-cancel-before-cleanup-failure",)
    assert transport.close_calls == 1
    assert failed_connection.close_count == 0
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED

    transport.fail_close = False
    await provider.close()
    assert transport.close_calls == 2
    assert failed_connection.close_count == 1
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0


@pytest.mark.parametrize("repeat_cancel", [False, True])
@pytest.mark.asyncio
async def test_adapter_cancelled_send_should_retire_current_generation_before_raise(
    repeat_cancel: bool,
) -> None:
    cancelled_connection = FakeConnection()
    reconnect_connection = FakeConnection(
        events=(
            '{"type":"response.created","response":{"id":"response-after-cancel"}}',
        )
    )
    transport = CancelledSendTransport((cancelled_connection, reconnect_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    sending = asyncio.create_task(
        provider.send(
            ProviderCommand(
                kind=ProviderCommandKind.CREATE_RESPONSE,
                data={
                    "modalities": ("audio", "text"),
                    "request_id": 7,
                    "stream_id": "stream-cancelled",
                },
            )
        )
    )
    await transport.send_started.wait()
    sending.cancel("first-send-cancel")
    await asyncio.sleep(0)

    assert sending.done() is False
    await transport.close_started.wait()
    if repeat_cancel:
        sending.cancel("second-send-cancel")
        await asyncio.sleep(0)
        assert sending.done() is False

    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert len(transport.connect_calls) == 1

    transport.release_close.set()
    with pytest.raises(asyncio.CancelledError) as captured:
        await sending

    assert captured.value.args == ("first-send-cancel",)
    assert transport.close_calls == 1
    assert cancelled_connection.close_count == 1
    await provider.connect(_session_config())
    uncorrelated = await provider.receive(connection_epoch=9)
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0
    assert uncorrelated.response_id == "response-after-cancel"
    assert uncorrelated.request_id is None
    assert uncorrelated.stream_id is None
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_stale_cancelled_send_should_not_retire_new_generation() -> None:
    stale_connection = FakeConnection()
    current_connection = FakeConnection()
    transport = LateSendTransport((stale_connection, current_connection))
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    stale_send = asyncio.create_task(
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

    stale_send.cancel("stale-send-cancel")
    with pytest.raises(asyncio.CancelledError) as captured:
        await stale_send

    assert captured.value.args == ("stale-send-cancel",)
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
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


class BacklogDrainTransport(SequencedTransport):
    def __init__(
        self,
        connections: tuple[FakeConnection, ...],
        *,
        stale_connection: FakeConnection,
        fail_current_close: bool,
        block_current_close: bool = False,
    ) -> None:
        super().__init__(connections)
        self.stale_connection = stale_connection
        self.current_connection = connections[0]
        self.fail_current_close = fail_current_close
        self.block_current_close = block_current_close
        self.stale_close_started = asyncio.Event()
        self.release_stale_close = asyncio.Event()
        self.current_close_started = asyncio.Event()
        self.release_current_close = asyncio.Event()

    async def close(self, connection: FakeConnection) -> None:
        self.close_calls += 1
        if connection is self.stale_connection:
            self.stale_close_started.set()
            await self.release_stale_close.wait()
        elif connection is self.current_connection:
            self.current_close_started.set()
            if self.block_current_close:
                await self.release_current_close.wait()
            if self.fail_current_close:
                raise Exception("wss://provider.example?token=secret-token raw-body")
        await connection.close()


async def _provider_with_stale_cleanup_and_current_connection(
    *,
    fail_current_close: bool,
    block_current_close: bool = False,
) -> tuple[
    StepFunRealtimeProvider,
    BacklogDrainTransport,
    FakeConnection,
    FakeConnection,
    FakeConnection,
]:
    stale_connection = FakeConnection()
    current_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = BacklogDrainTransport(
        (current_connection, reconnect_connection),
        stale_connection=stale_connection,
        fail_current_close=fail_current_close,
        block_current_close=block_current_close,
    )
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())
    async with provider._lifecycle_lock:
        cleanup_task = provider._schedule_close_cleanup_locked(stale_connection)
    assert cleanup_task is not None
    await transport.stale_close_started.wait()
    return (
        provider,
        transport,
        stale_connection,
        current_connection,
        reconnect_connection,
    )


@pytest.mark.asyncio
async def test_adapter_public_close_should_drain_connection_joining_active_cleanup() -> (
    None
):
    (
        provider,
        transport,
        stale_connection,
        current_connection,
        reconnect_connection,
    ) = await _provider_with_stale_cleanup_and_current_connection(
        fail_current_close=False
    )

    closing = asyncio.create_task(provider.close())
    await asyncio.sleep(0)
    assert closing.done() is False
    transport.release_stale_close.set()
    await closing

    assert transport.close_calls == 2
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 1
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0
    assert "connected=True" in repr(provider)


@pytest.mark.asyncio
async def test_adapter_public_close_drain_failure_should_remain_retryable() -> None:
    (
        provider,
        transport,
        stale_connection,
        current_connection,
        reconnect_connection,
    ) = await _provider_with_stale_cleanup_and_current_connection(
        fail_current_close=True
    )

    closing = asyncio.create_task(provider.close())
    await asyncio.sleep(0)
    transport.release_stale_close.set()
    with pytest.raises(RealtimeProviderError) as captured:
        await closing

    assert captured.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert captured.value.__cause__ is None
    assert "secret-token" not in repr(captured.value)
    assert transport.close_calls == 2
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
    with pytest.raises(RealtimeProviderError):
        await provider.connect(_session_config())

    transport.fail_current_close = False
    await provider.close()
    assert transport.close_calls == 3
    assert current_connection.close_count == 1
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0


@pytest.mark.asyncio
async def test_adapter_cancelled_public_close_should_finish_all_drain_batches() -> None:
    (
        provider,
        transport,
        stale_connection,
        current_connection,
        reconnect_connection,
    ) = await _provider_with_stale_cleanup_and_current_connection(
        fail_current_close=False
    )

    closing = asyncio.create_task(provider.close())
    await asyncio.sleep(0)
    closing.cancel("first-close-cancel")
    await asyncio.sleep(0)
    assert closing.done() is False
    transport.release_stale_close.set()

    with pytest.raises(asyncio.CancelledError) as captured:
        await closing

    assert captured.value.args == ("first-close-cancel",)
    assert transport.close_calls == 2
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 1
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0


@pytest.mark.asyncio
async def test_adapter_repeated_close_cancel_with_drain_failure_should_keep_retry() -> (
    None
):
    (
        provider,
        transport,
        stale_connection,
        current_connection,
        reconnect_connection,
    ) = await _provider_with_stale_cleanup_and_current_connection(
        fail_current_close=True,
        block_current_close=True,
    )

    closing = asyncio.create_task(provider.close())
    await asyncio.sleep(0)
    closing.cancel("first-close-cancel")
    transport.release_stale_close.set()
    try:
        await asyncio.wait_for(transport.current_close_started.wait(), timeout=0.1)
        current_close_started = True
    except TimeoutError:
        current_close_started = False
    if current_close_started:
        closing.cancel("second-close-cancel")
        await asyncio.sleep(0)
        assert closing.done() is False
        transport.release_current_close.set()

    with pytest.raises(asyncio.CancelledError) as captured:
        await closing

    assert current_close_started is True
    assert captured.value.args == ("first-close-cancel",)
    assert transport.close_calls == 2
    assert stale_connection.close_count == 1
    assert current_connection.close_count == 0
    with pytest.raises(RealtimeProviderError):
        await provider.connect(_session_config())

    transport.fail_current_close = False
    transport.block_current_close = False
    await provider.close()
    assert transport.close_calls == 3
    assert current_connection.close_count == 1
    await provider.connect(_session_config())
    assert reconnect_connection.close_count == 0


class RegistrationWindowTransport(RetryableCloseTransport):
    def __init__(self, connections: tuple[FakeConnection, ...]) -> None:
        super().__init__(connections)
        self.connect_return_ready = asyncio.Event()
        self.release_connect_return = asyncio.Event()

    async def connect(self, *, api_key: str, url: str, model: str) -> FakeConnection:
        self.connect_calls.append({"api_key": api_key, "url": url, "model": model})
        connection = self.connections.popleft()
        self.connect_return_ready.set()
        await self.release_connect_return.wait()
        return connection


@pytest.mark.asyncio
async def test_adapter_repeated_cancel_before_pending_register_should_retain_socket() -> (
    None
):
    unregistered_connection = FakeConnection()
    reconnect_connection = FakeConnection()
    transport = RegistrationWindowTransport(
        (unregistered_connection, reconnect_connection)
    )
    provider = StepFunRealtimeProvider(
        api_key="key",
        url="wss://provider.example/realtime",
        transport=transport,  # type: ignore[arg-type]
    )

    connecting = asyncio.create_task(provider.connect(_session_config()))
    await transport.connect_return_ready.wait()
    await provider._lifecycle_lock.acquire()
    transport.release_connect_return.set()
    await asyncio.sleep(0)
    connecting.cancel("first-register-cancel")
    await asyncio.sleep(0)
    connecting.cancel("second-register-cancel")
    await asyncio.sleep(0)
    assert connecting.done() is False
    provider._lifecycle_lock.release()

    with pytest.raises(asyncio.CancelledError) as captured:
        await connecting

    assert captured.value.args == ("first-register-cancel",)
    assert transport.close_calls == 1
    assert unregistered_connection.close_count == 0
    with pytest.raises(RealtimeProviderError) as reconnect_blocked:
        await provider.connect(_session_config())
    assert reconnect_blocked.value.reason is ProviderErrorReason.CONNECTION_CLOSED
    assert len(transport.connect_calls) == 1

    transport.fail_close = False
    await provider.close()
    assert transport.close_calls == 2
    assert unregistered_connection.close_count == 1
    await provider.connect(_session_config())
    assert len(transport.connect_calls) == 2
    assert reconnect_connection.close_count == 0


_KNOWN_PROVIDER_CREDENTIALS = (
    "sk-live-secret",
    "prefix-sk-live-secret-suffix",
    "provider.example",
    "query-secret",
)


def _assert_sensitive_identifier_rejected(
    event: ProviderEvent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    assert event.request_id is None
    assert event.response_id is None
    assert event.stream_id is None
    assert event.call_id is None
    assert event.event_id is None
    assert event.turn_id is None
    assert event.data == {}
    assert getattr(event, "__cause__", None) is None
    rendered = f"{event!r} {event!s} {caplog.text}"
    for sensitive in (
        "sk-live-secret",
        "provider.example",
        "query-secret",
    ):
        assert sensitive not in rendered


@pytest.mark.parametrize(
    "identifier_field",
    ["response_id", "stream_id", "call_id", "event_id", "turn_id"],
)
@pytest.mark.parametrize("polluted", _KNOWN_PROVIDER_CREDENTIALS)
@pytest.mark.asyncio
async def test_adapter_receive_should_reject_known_secret_in_top_level_identifier(
    identifier_field: str,
    polluted: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(
        events=(json.dumps({"type": "session.created", identifier_field: polluted}),)
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=query-secret",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    _assert_sensitive_identifier_rejected(event, caplog)


@pytest.mark.parametrize("polluted", _KNOWN_PROVIDER_CREDENTIALS)
@pytest.mark.asyncio
async def test_adapter_receive_should_reject_known_secret_in_nested_call_id(
    polluted: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(
        events=(
            json.dumps(
                {
                    "type": "response.done",
                    "response_id": "response-safe",
                    "response": {
                        "output": [
                            {
                                "type": "function_call",
                                "call_id": polluted,
                                "name": "safe_name",
                                "arguments": "{}",
                            }
                        ]
                    },
                }
            ),
        )
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=query-secret",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    _assert_sensitive_identifier_rejected(event, caplog)


@pytest.mark.parametrize(
    "raw_payload",
    [
        {
            "type": "response.text.delta",
            "response_id": "response-safe",
            "delta": "Do not reveal sk-live-secret in text",
        },
        {
            "type": "response.audio_transcript.done",
            "response_id": "response-safe",
            "transcript": "query-secret",
        },
        {
            "type": "response.function_call_arguments.done",
            "response_id": "response-safe",
            "call_id": "call-safe",
            "arguments": {"token": "query-secret"},
        },
        {
            "type": "response.done",
            "response": {
                "id": "response-safe",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-safe",
                        "name": "safe_name",
                        "arguments": '{"token":"query-secret"}',
                    }
                ],
            },
        },
    ],
)
@pytest.mark.asyncio
async def test_adapter_receive_should_reject_secret_in_any_canonical_data_string(
    raw_payload: dict[str, object],
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(events=(json.dumps(raw_payload),))
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=query-secret",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    _assert_sensitive_identifier_rejected(event, caplog)


@pytest.mark.asyncio
async def test_adapter_receive_should_reject_numeric_request_id_matching_credential(
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(
        events=(json.dumps({"type": "session.created", "request_id": 12345}),)
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=12345",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    _assert_sensitive_identifier_rejected(event, caplog)
    assert "12345" not in f"{event!r} {event!s} {caplog.text}"


@pytest.mark.asyncio
async def test_adapter_content_scan_should_keep_endpoint_language_and_substrings() -> (
    None
):
    natural_text = (
        "provider.example 的说明位于 wss://provider.example/realtime，"
        "monkey 中的连续字母不应命中短 query secret。"
    )
    connection = FakeConnection(
        events=(
            json.dumps(
                {
                    "type": "response.text.delta",
                    "response_id": "response-safe",
                    "delta": natural_text,
                }
            ),
        )
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=key",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.RESPONSE_TEXT_DELTA
    assert event.data == {"text": natural_text}


@pytest.mark.asyncio
async def test_adapter_content_scan_should_reject_exact_short_query_token() -> None:
    connection = FakeConnection(
        events=(
            json.dumps(
                {
                    "type": "response.function_call_arguments.done",
                    "response_id": "response-safe",
                    "call_id": "call-safe",
                    "arguments": {"token": "key"},
                }
            ),
        )
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=key",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    assert event.data == {}


@pytest.mark.asyncio
async def test_adapter_receive_should_preserve_legal_opaque_ids_but_redact_repr(
    caplog: pytest.LogCaptureFixture,
) -> None:
    opaque = "opaque-token-123"
    connection = FakeConnection(
        events=(
            json.dumps(
                {
                    "type": "session.created",
                    "response_id": opaque,
                    "stream_id": opaque,
                    "call_id": opaque,
                    "event_id": opaque,
                    "turn_id": opaque,
                }
            ),
        )
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=query-secret",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.SESSION_READY
    assert event.response_id == opaque
    assert event.stream_id == opaque
    assert event.call_id == opaque
    assert event.event_id == opaque
    assert event.turn_id == opaque
    assert opaque not in f"{event!r} {event!s} {caplog.text}"


@pytest.mark.parametrize(
    "raw_event_type",
    ["sk-live-secret", "provider.example", "query-secret"],
)
@pytest.mark.asyncio
async def test_adapter_unknown_event_type_should_never_cross_raw_value(
    raw_event_type: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = FakeConnection(events=(json.dumps({"type": raw_event_type}),))
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url="wss://provider.example/realtime?token=query-secret",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.UNKNOWN
    assert event.provider_event_type == "unknown"
    rendered = f"{event!r} {event!s} {caplog.text}"
    assert raw_event_type not in rendered


@pytest.mark.parametrize(
    "safe_query_key",
    ["design", "author", "monkey", "signature_version"],
)
@pytest.mark.asyncio
async def test_adapter_should_not_treat_query_key_substrings_as_sensitive(
    safe_query_key: str,
) -> None:
    opaque = "opaque-query-value"
    connection = FakeConnection(
        events=(json.dumps({"type": "session.created", "event_id": opaque}),)
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url=f"wss://provider.example/realtime?{safe_query_key}={opaque}",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.SESSION_READY
    assert event.event_id == opaque


@pytest.mark.asyncio
async def test_adapter_should_reject_exact_sensitive_signature_query_key() -> None:
    secret = "signature-secret"
    connection = FakeConnection(
        events=(json.dumps({"type": "session.created", "event_id": secret}),)
    )
    provider = StepFunRealtimeProvider(
        api_key="sk-live-secret",
        url=f"wss://provider.example/realtime?signature={secret}",
        transport=FakeTransport(connection=connection),  # type: ignore[arg-type]
    )
    await provider.connect(_session_config())

    event = await provider.receive(connection_epoch=3)

    assert event.kind is ProviderEventKind.ERROR
    assert event.error_category is ProviderErrorCategory.PROTOCOL
    assert event.error_reason is ProviderErrorReason.INVALID_EVENT
    assert secret not in f"{event!r} {event!s}"
