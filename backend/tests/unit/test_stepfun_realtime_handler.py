"""
Unit tests for StepFunRealtimeHandler realtime channel behavior.

Includes degraded/resumed coach health state tests for S07.
"""

from __future__ import annotations

# pyright: reportMissingImports=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportAttributeAccessIssue=false
import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, call

import pytest

import sales_bot.websocket.components.stepfun_turn_transcript_capture as transcript_capture_module
import sales_bot.websocket.stepfun_realtime_handler as stepfun_module
import sales_bot.websocket.stepfun_realtime_sales_stage as sales_stage_module
from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.components.stepfun_roleplay_runtime_helpers import (
    V1_ROLEPLAY_RUNTIME_METRICS_KEY,
    V1_ROLEPLAY_RUNTIME_STATE_KEY,
    apply_roleplay_state_card_update_to_policy,
)
from sales_bot.websocket.realtime_feedback_arbiter import RealtimeFeedbackPacingState
from sales_bot.websocket.stepfun_realtime_handler import (
    FunctionCallAuthority,
    FunctionCallState,
    RealtimeResponseState,
    StepFunRealtimeHandler,
)
from sales_bot.websocket.stepfun_realtime_policy import StepFunRealtimePolicyMixin
from sales_bot.websocket.stepfun_tool_execution import (
    StepFunToolExecutionModule,
    ToolRoutingDecision,
    ToolRoutingStatus,
)
from sales_bot.websocket.voice_runtime_profile import VoiceRuntimeProfile
from training_runtime import StepFunSessionConfig, build_stepfun_session_update_payload
from training_runtime.realtime import (
    ProviderBackpressureResult,
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
    RealtimeProviderSessionConfig,
    validate_provider_capabilities,
)
from training_runtime.stepfun_transport import (
    StepFunBackpressureResult,
    StepFunBackpressureStatus,
    StepFunHealthResult,
    StepFunHealthStatus,
    StepFunSendResult,
    StepFunSendStatus,
)


@pytest.fixture(autouse=True)
def _select_legacy_transport_unless_test_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "false")


def test_stepfun_transport_builds_session_update_payload_with_transcription_and_tools():
    payload = build_stepfun_session_update_payload(
        StepFunSessionConfig(
            voice="qingchunshaonv",
            temperature=0.42,
            input_audio_format="pcm16",
            output_audio_format="pcm16",
            turn_detection={"type": "server_vad"},
            input_transcription_enabled=True,
            input_transcription_language="zh",
            input_transcription_model="step-asr",
            instructions="保持销售训练角色。",
            tools=[{"type": "function", "name": "search_internal_knowledge"}],
        )
    )

    assert payload == {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": "qingchunshaonv",
            "temperature": 0.42,
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {"type": "server_vad"},
            "input_audio_transcription": {
                "language": "zh",
                "model": "step-asr",
            },
            "instructions": "保持销售训练角色。",
            "tools": [{"type": "function", "name": "search_internal_knowledge"}],
        },
    }


def test_policy_mixin_must_not_own_stepfun_upstream_connection():
    assert "_connect_upstream" not in StepFunRealtimePolicyMixin.__dict__


class RecordingRealtimeProvider:
    def __init__(self) -> None:
        self.connect_calls: list[RealtimeProviderSessionConfig] = []
        self.commands: list[ProviderCommand] = []
        self.events: asyncio.Queue[ProviderEvent] = asyncio.Queue()
        self.health_calls: list[float | None] = []
        self.backpressure_calls: list[tuple[ProviderCommand, int]] = []
        self.close_calls = 0

    @property
    def capabilities(self) -> RealtimeProviderCapabilities:
        return RealtimeProviderCapabilities(supported=frozenset())

    async def connect(self, config: RealtimeProviderSessionConfig) -> None:
        self.connect_calls.append(config)

    async def send(self, command: ProviderCommand) -> ProviderSendResult:
        self.commands.append(command)
        return ProviderSendResult(accepted=True)

    async def receive(self, *, connection_epoch: int) -> ProviderEvent:
        event = await self.events.get()
        assert event.connection_epoch == connection_epoch
        return event

    async def check_health(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> ProviderHealthResult:
        self.health_calls.append(timeout_seconds)
        return ProviderHealthResult(healthy=True)

    def decide_backpressure(
        self,
        command: ProviderCommand,
        *,
        pending_bytes: int,
    ) -> ProviderBackpressureResult:
        self.backpressure_calls.append((command, pending_bytes))
        return ProviderBackpressureResult(accepted=True)

    async def close(self) -> None:
        self.close_calls += 1


class BlockingCloseRealtimeProvider(RecordingRealtimeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.close_started = asyncio.Event()
        self.allow_close = asyncio.Event()

    async def close(self) -> None:
        self.close_calls += 1
        self.close_started.set()
        await self.allow_close.wait()


@pytest.mark.asyncio
async def test_provider_port_default_selection_is_frozen_and_does_not_shadow_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REALTIME_PROVIDER_PORT_ENABLED", raising=False)
    provider = RecordingRealtimeProvider()
    provider_factory_calls: list[dict[str, object]] = []
    legacy_transport = SimpleNamespace(
        connect=AsyncMock(side_effect=AssertionError("legacy transport shadowed")),
        send_json=AsyncMock(side_effect=AssertionError("legacy transport shadowed")),
        close=AsyncMock(side_effect=AssertionError("legacy transport shadowed")),
    )

    def provider_factory(**kwargs: object) -> RecordingRealtimeProvider:
        provider_factory_calls.append(kwargs)
        return provider

    handler = StepFunRealtimeHandler(
        stepfun_transport=legacy_transport,
        provider_factory=provider_factory,
    )
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "false")
    handler._stepfun_api_key = "test-api-key"
    handler._stepfun_url = "wss://stepfun.example/realtime"
    handler._effective_policy = {"turn_detection": "server_vad"}
    handler._build_stepfun_tools_from_policy = MagicMock(return_value=[])
    handler._enforce_stepfun_tool_guardrails = MagicMock(side_effect=lambda tools: tools)
    handler._ensure_upstream_keepalive_task = MagicMock()
    handler._maybe_start_kb_lock_warmup = AsyncMock()

    await handler._connect_upstream()
    accepted = await handler._send_upstream(
        {"type": "input_audio_buffer.append", "audio": "AAE="}
    )
    await handler._send_upstream_keepalive_ping(handler.upstream_ws)
    dropped = handler._should_drop_upstream_for_backpressure(
        {"type": "input_audio_buffer.append", "audio": "AAE="}
    )
    await handler._close_upstream()
    await handler._connect_upstream()

    assert handler._provider_port_enabled is True
    assert handler._selected_provider_path == "provider_port"
    assert len(provider_factory_calls) == 1
    assert provider_factory_calls[0]["api_key"] == "test-api-key"
    assert provider_factory_calls[0]["url"] == "wss://stepfun.example/realtime"
    assert provider_factory_calls[0]["transport"] is legacy_transport
    assert len(provider.connect_calls) == 2
    assert provider.connect_calls[0].model == handler._active_voice_runtime_profile().model_name
    assert provider.connect_calls[0].turn_detection == {"type": "server_vad"}
    assert [command.kind for command in provider.commands] == [
        ProviderCommandKind.APPEND_AUDIO
    ]
    assert accepted is True
    assert dropped is False
    assert provider.backpressure_calls[0][0].kind is ProviderCommandKind.APPEND_AUDIO
    assert provider.health_calls == [handler._upstream_keepalive_pong_timeout_seconds]
    assert provider.close_calls == 1
    legacy_transport.connect.assert_not_awaited()
    legacy_transport.send_json.assert_not_awaited()
    legacy_transport.close.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "expected_kind"),
    [
        (
            {"type": "input_audio_buffer.append", "audio": "AAE="},
            ProviderCommandKind.APPEND_AUDIO,
        ),
        ({"type": "input_audio_buffer.commit"}, ProviderCommandKind.COMMIT_AUDIO),
        ({"type": "input_audio_buffer.clear"}, ProviderCommandKind.CLEAR_AUDIO),
        (
            {
                "type": "response.create",
                "response": {"modalities": ["text", "audio"], "instructions": "go"},
            },
            ProviderCommandKind.CREATE_RESPONSE,
        ),
        (
            {"type": "response.cancel", "response_id": "response-1"},
            ProviderCommandKind.CANCEL_RESPONSE,
        ),
        (
            {
                "type": "conversation.item.create",
                "item": {
                    "id": "item-1",
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            },
            ProviderCommandKind.CREATE_CONVERSATION_ITEM,
        ),
        (
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": '{"count":1}',
                },
            },
            ProviderCommandKind.TOOL_OUTPUT,
        ),
    ],
)
@pytest.mark.asyncio
async def test_provider_send_facade_constructs_every_canonical_command(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    expected_kind: ProviderCommandKind,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    provider = RecordingRealtimeProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider

    assert await handler._send_upstream(payload) is True
    assert [command.kind for command in provider.commands] == [expected_kind]


@pytest.mark.asyncio
async def test_provider_response_create_injects_local_authority_without_legacy_payload_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    provider = RecordingRealtimeProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-7",
    )
    payload = {
        "type": "response.create",
        "response": {"modalities": ["text", "audio"]},
    }

    assert await handler._send_upstream(payload) is True

    assert payload == {
        "type": "response.create",
        "response": {"modalities": ["text", "audio"]},
    }
    assert provider.commands == [
        ProviderCommand(
            kind=ProviderCommandKind.CREATE_RESPONSE,
            data={
                "modalities": ("text", "audio"),
                "request_id": 7,
                "stream_id": "stream-7",
            },
        )
    ]


@pytest.mark.asyncio
async def test_cancelled_generation_rolls_connection_epoch_before_new_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 4
    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock()  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    await handler._clear_upstream_generation()

    handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_awaited_once_with()
    assert handler._connection_epoch == 5


@pytest.mark.asyncio
async def test_concurrent_generation_rollovers_share_one_physical_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 4
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    async def close_once() -> None:
        close_started.set()
        await release_close.wait()

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_once)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    first = asyncio.create_task(handler._clear_upstream_generation())
    await close_started.wait()
    second = asyncio.create_task(handler._clear_upstream_generation())
    await asyncio.sleep(0)

    assert handler._send_upstream.await_count == 2
    handler._close_upstream.assert_awaited_once_with()

    release_close.set()
    await asyncio.gather(first, second)

    handler._connect_upstream.assert_awaited_once_with()
    assert handler._connection_epoch == 5


@pytest.mark.asyncio
async def test_paused_close_only_rollover_cannot_be_upgraded_by_concurrent_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "paused"
    handler.upstream_ws = object()
    handler._connection_epoch = 4
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    async def close_once() -> None:
        close_started.set()
        await release_close.wait()
        handler.upstream_ws = None

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_once)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    close_only = asyncio.create_task(
        handler._clear_upstream_generation(reconnect=False)
    )
    await asyncio.wait_for(close_started.wait(), timeout=0.5)
    reconnect = asyncio.create_task(handler._clear_upstream_generation(reconnect=True))
    await asyncio.sleep(0)
    release_close.set()
    await asyncio.gather(close_only, reconnect)

    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_not_awaited()
    assert handler._connection_epoch == 5
    assert handler._upstream_rollover_phase == "idle"


@pytest.mark.asyncio
async def test_terminal_lifecycle_closes_connection_that_finishes_reconnect_in_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler.upstream_ws = object()
    connect_started = asyncio.Event()
    release_connect = asyncio.Event()
    new_upstream = object()
    close_calls = 0

    async def close_current() -> None:
        nonlocal close_calls
        close_calls += 1
        handler.upstream_ws = None

    async def connect_new() -> None:
        connect_started.set()
        await release_connect.wait()
        handler.upstream_ws = new_upstream

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_current)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock(side_effect=connect_new)  # type: ignore[method-assign]

    reconnect = asyncio.create_task(handler._clear_upstream_generation(reconnect=True))
    await asyncio.wait_for(connect_started.wait(), timeout=0.5)
    handler.session_status = "paused"
    close_only = asyncio.create_task(
        handler._clear_upstream_generation(reconnect=False)
    )
    release_connect.set()
    await asyncio.gather(reconnect, close_only)

    assert close_calls == 2
    handler._connect_upstream.assert_awaited_once_with()
    assert handler.upstream_ws is None
    assert handler._upstream_rollover_phase == "idle"


@pytest.mark.asyncio
async def test_cancelled_generation_rollover_finishes_once_before_propagating_first_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 4
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    async def close_once() -> None:
        close_started.set()
        await release_close.wait()

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_once)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    rollover = asyncio.create_task(handler._clear_upstream_generation())
    await close_started.wait()
    rollover.cancel("first-rollover-cancel")
    await asyncio.sleep(0)

    if rollover.done():
        release_close.set()
        await asyncio.gather(rollover, return_exceptions=True)
        pytest.fail("caller cancellation aborted the shared physical rollover")

    rollover.cancel("second-rollover-cancel")
    await asyncio.sleep(0)
    assert rollover.done() is False

    release_close.set()
    with pytest.raises(asyncio.CancelledError) as captured:
        await rollover

    assert captured.value.args == ("first-rollover-cancel",)
    assert handler._send_upstream.await_count == 2
    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_awaited_once_with()
    assert handler._connection_epoch == 5


@pytest.mark.asyncio
async def test_failed_generation_rollover_retries_reconnect_without_second_epoch_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 4

    async def close_once() -> None:
        handler.upstream_ws = None

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_once)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock(  # type: ignore[method-assign]
        side_effect=[RuntimeError("first reconnect failed"), None]
    )

    with pytest.raises(RuntimeError, match="first reconnect failed"):
        await handler._clear_upstream_generation()

    await handler._clear_upstream_generation()

    assert handler._send_upstream.await_count == 2
    handler._close_upstream.assert_awaited_once_with()
    assert handler._connect_upstream.await_count == 2
    assert handler._connection_epoch == 5


@pytest.mark.asyncio
async def test_failed_generation_close_retries_owned_cleanup_before_epoch_advance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 4
    close_attempts = 0

    async def close_with_first_failure() -> None:
        nonlocal close_attempts
        close_attempts += 1
        handler.upstream_ws = None
        if close_attempts == 1:
            raise RuntimeError("first close failed")

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_with_first_failure)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="first close failed"):
        await handler._clear_upstream_generation()

    await handler._clear_upstream_generation()

    assert handler._send_upstream.await_count == 2
    assert handler._close_upstream.await_count == 2
    handler._connect_upstream.assert_awaited_once_with()
    assert handler._connection_epoch == 5


def test_provider_port_false_constructs_only_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "false")
    provider_factory = MagicMock(side_effect=AssertionError("provider shadowed"))

    handler = StepFunRealtimeHandler(provider_factory=provider_factory)

    assert handler._provider_port_enabled is False
    assert handler._selected_provider_path == "legacy_stepfun_transport"
    assert handler._realtime_provider is None
    provider_factory.assert_not_called()

    diagnostics = handler.get_runtime_diagnostics()
    assert diagnostics["provider_port_enabled"] is False
    assert diagnostics["selected_provider_path"] == "legacy_stepfun_transport"
    assert "STEPFUN_API_KEY" not in repr(diagnostics)
    assert "STEPFUN_REALTIME_URL" not in repr(diagnostics)


@pytest.mark.asyncio
async def test_provider_capability_mismatch_fails_before_any_legacy_socket_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    legacy_transport = SimpleNamespace(connect=AsyncMock())

    class CapabilityRejectingProvider(RecordingRealtimeProvider):
        async def connect(self, config: RealtimeProviderSessionConfig) -> None:
            validate_provider_capabilities(capabilities=self.capabilities, config=config)

    handler = StepFunRealtimeHandler(
        stepfun_transport=legacy_transport,
        provider_factory=lambda **_kwargs: CapabilityRejectingProvider(),
    )
    handler._effective_policy = {"turn_detection": "server_vad"}
    handler._build_stepfun_tools_from_policy = MagicMock(return_value=[])
    handler._enforce_stepfun_tool_guardrails = MagicMock(side_effect=lambda tools: tools)

    with pytest.raises(RealtimeProviderError):
        await handler._connect_upstream()

    legacy_transport.connect.assert_not_awaited()
    assert handler.upstream_ws is None


@pytest.mark.asyncio
async def test_selected_provider_path_never_falls_back_after_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")

    class FailingConnectProvider(RecordingRealtimeProvider):
        async def connect(self, config: RealtimeProviderSessionConfig) -> None:
            self.connect_calls.append(config)
            raise RuntimeError("provider connect failed")

    provider = FailingConnectProvider()
    legacy_transport = SimpleNamespace(
        connect=AsyncMock(side_effect=AssertionError("legacy connect fallback")),
        send_json=AsyncMock(side_effect=AssertionError("legacy send fallback")),
        check_health=AsyncMock(side_effect=AssertionError("legacy health fallback")),
        decide_backpressure=MagicMock(
            side_effect=AssertionError("legacy backpressure fallback")
        ),
        close=AsyncMock(side_effect=AssertionError("legacy close fallback")),
    )
    handler = StepFunRealtimeHandler(
        stepfun_transport=legacy_transport,
        provider_factory=lambda **_kwargs: provider,
    )
    handler._effective_policy = {"turn_detection": "server_vad"}
    handler._build_stepfun_tools_from_policy = MagicMock(return_value=[])
    handler._enforce_stepfun_tool_guardrails = MagicMock(side_effect=lambda tools: tools)
    handler._stop_upstream_keepalive_task = AsyncMock()

    with pytest.raises(RuntimeError, match="provider connect failed"):
        await handler._connect_upstream()

    assert handler._using_provider_port() is True
    assert await handler._send_upstream({"type": "response.create"}) is False
    with pytest.raises(RuntimeError, match="realtime_provider_not_constructed"):
        marker = object()
        handler._realtime_provider = None
        await handler._send_upstream_keepalive_ping(marker)
    assert handler._should_drop_upstream_for_backpressure(
        {"type": "input_audio_buffer.append", "audio": "AAE="}
    ) is True
    handler._realtime_provider = provider
    await handler._close_upstream()

    assert provider.close_calls == 1
    legacy_transport.connect.assert_not_awaited()
    legacy_transport.send_json.assert_not_awaited()
    legacy_transport.check_health.assert_not_awaited()
    legacy_transport.decide_backpressure.assert_not_called()
    legacy_transport.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_close_preserves_repeated_cancellation_and_resets_local_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    provider = BlockingCloseRealtimeProvider()
    legacy_transport = SimpleNamespace(
        close=AsyncMock(side_effect=AssertionError("legacy close fallback"))
    )
    handler = StepFunRealtimeHandler(
        stepfun_transport=legacy_transport,
        provider_factory=lambda **_kwargs: provider,
    )
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._upstream_connected_at = 11.0
    handler._upstream_last_activity_at = 12.0
    handler._stop_upstream_keepalive_task = AsyncMock()

    close_task = asyncio.create_task(handler._close_upstream())
    await provider.close_started.wait()
    close_task.cancel()
    close_task.cancel()
    await asyncio.sleep(0)
    provider.allow_close.set()

    with pytest.raises(asyncio.CancelledError):
        await close_task

    assert provider.close_calls == 1
    assert handler.upstream_ws is None
    assert handler._upstream_connected_at == 0.0
    assert handler._upstream_last_activity_at == 0.0
    legacy_transport.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_close_prioritizes_first_cancel_over_late_cleanup_error_and_resets_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")

    class FailingAfterReleaseProvider(BlockingCloseRealtimeProvider):
        async def close(self) -> None:
            self.close_calls += 1
            self.close_started.set()
            await self.allow_close.wait()
            raise RuntimeError("late-cleanup-error")

    provider = FailingAfterReleaseProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._upstream_connected_at = 11.0
    handler._upstream_last_activity_at = 12.0
    handler._stop_upstream_keepalive_task = AsyncMock()

    close_task = asyncio.create_task(handler._close_upstream())
    await provider.close_started.wait()
    close_task.cancel("first-cancel")
    await asyncio.sleep(0)
    provider.allow_close.set()

    with pytest.raises(asyncio.CancelledError) as captured:
        await close_task

    assert captured.value.args == ("first-cancel",)
    assert provider.close_calls == 1
    assert handler.upstream_ws is None
    assert handler._upstream_connected_at == 0.0
    assert handler._upstream_last_activity_at == 0.0


@pytest.mark.asyncio
async def test_handler_close_raises_cleanup_error_without_cancel_and_resets_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")

    class FailingCloseProvider(RecordingRealtimeProvider):
        async def close(self) -> None:
            self.close_calls += 1
            raise RuntimeError("safe-cleanup-error")

    provider = FailingCloseProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._upstream_connected_at = 11.0
    handler._upstream_last_activity_at = 12.0
    handler._stop_upstream_keepalive_task = AsyncMock()

    with pytest.raises(RuntimeError, match="safe-cleanup-error"):
        await handler._close_upstream()

    assert provider.close_calls == 1
    assert handler.upstream_ws is None
    assert handler._upstream_connected_at == 0.0
    assert handler._upstream_last_activity_at == 0.0


@pytest.mark.asyncio
async def test_handle_connection_finishes_cleanup_before_propagating_repeated_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import common.services.session_runtime_lifecycle_hooks as lifecycle_hooks

    receive_started = asyncio.Event()
    close_started = asyncio.Event()
    allow_close = asyncio.Event()

    class BlockingWebSocket:
        headers: dict[str, str] = {}

        async def receive(self) -> dict[str, object]:
            receive_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def blocking_close() -> None:
        close_started.set()
        await allow_close.wait()

    async def block_upstream_receive() -> None:
        await asyncio.Event().wait()

    manager = SimpleNamespace(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
    )
    handler = StepFunRealtimeHandler()
    handler.manager = manager
    handler.state_service = SimpleNamespace(get_state=AsyncMock(return_value=Result.ok(None)))
    handler._stepfun_api_key = "test-api-key"
    handler._load_effective_policy = AsyncMock()
    handler._initialize_curriculum_stage_runtime = AsyncMock()
    handler._sync_session_state = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._receive_upstream_events = AsyncMock(side_effect=block_upstream_receive)
    handler._send_status = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._close_upstream = AsyncMock(side_effect=blocking_close)
    handler._save_session_state = AsyncMock()
    monkeypatch.setattr(stepfun_module, "verify_token", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(lifecycle_hooks, "mark_session_runtime_started", AsyncMock())

    lifecycle_task = asyncio.create_task(
        handler.handle_connection(
            cast(Any, BlockingWebSocket()),
            "session-cancel",
            "token",
        )
    )
    await receive_started.wait()
    lifecycle_task.cancel()
    await close_started.wait()
    lifecycle_task.cancel()
    await asyncio.sleep(0)
    allow_close.set()

    with pytest.raises(asyncio.CancelledError):
        await lifecycle_task

    handler._close_upstream.assert_awaited_once_with()
    handler._save_session_state.assert_awaited_once_with()
    manager.disconnect.assert_awaited_once_with(handler.scenario, "session-cancel")


@pytest.mark.asyncio
async def test_provider_event_is_consumed_through_canonical_compatibility_facade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    provider = RecordingRealtimeProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._connection_epoch = 7
    handler.current_request_id = 7
    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-7",
        response_id="response-7",
    )
    handler._function_call_authorities = {
        "call-7": FunctionCallAuthority(
            request_id=7,
            response_id="response-7",
            stream_id="stream-7",
        )
    }
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler.running = True
    captured: list[dict[str, object]] = []

    async def capture(event: dict[str, object]) -> None:
        captured.append(event)
        handler.running = False

    handler._handle_upstream_event = capture  # type: ignore[method-assign]
    await provider.events.put(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=7,
            request_id=7,
            response_id="response-7",
            stream_id="stream-7",
            data={
                "function_outputs": (
                    {
                        "call_id": "call-7",
                        "name": "search_internal_knowledge",
                        "arguments": '{"query":"产品"}',
                    },
                )
            },
        )
    )

    await handler._receive_upstream_events()

    assert captured == [
        {
            "type": "response.done",
            "request_id": 7,
            "response_id": "response-7",
            "stream_id": "stream-7",
            "response": {
                "id": "response-7",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-7",
                        "name": "search_internal_knowledge",
                        "arguments": '{"query":"产品"}',
                    }
                ],
            },
        }
    ]


@pytest.mark.asyncio
async def test_old_provider_receive_error_after_rollover_cannot_recover_or_stop_new_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")

    class LateFailingProvider(RecordingRealtimeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.first_receive_started = asyncio.Event()
            self.release_first_error = asyncio.Event()
            self.second_receive_started = asyncio.Event()
            self.receive_calls = 0

        async def receive(self, *, connection_epoch: int) -> ProviderEvent:
            self.receive_calls += 1
            if self.receive_calls == 1:
                assert connection_epoch == 4
                self.first_receive_started.set()
                await self.release_first_error.wait()
                raise RealtimeProviderError(
                    category=ProviderErrorCategory.DISCONNECTED,
                    reason=ProviderErrorReason.CONNECTION_CLOSED,
                    retryable=True,
                )
            assert connection_epoch == 5
            self.second_receive_started.set()
            await asyncio.Event().wait()
            raise AssertionError("cancelled receive must not resume")

    provider = LateFailingProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._connection_epoch = 4
    handler.running = True
    recover_called = asyncio.Event()

    async def close_old() -> None:
        handler.upstream_ws = None

    async def connect_new() -> None:
        handler.upstream_ws = provider

    async def recover_old(**_kwargs: object) -> bool:
        recover_called.set()
        return False

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_old)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock(side_effect=connect_new)  # type: ignore[method-assign]
    handler._record_upstream_disconnect_diagnostics = AsyncMock()  # type: ignore[method-assign]
    handler._recover_upstream_after_disconnect = AsyncMock(side_effect=recover_old)  # type: ignore[method-assign]
    handler._send_error = AsyncMock()  # type: ignore[method-assign]

    receiving = asyncio.create_task(handler._receive_upstream_events())
    await asyncio.wait_for(provider.first_receive_started.wait(), timeout=0.5)
    await asyncio.wait_for(handler._clear_upstream_generation(), timeout=0.5)
    provider.release_first_error.set()
    second_started = asyncio.create_task(provider.second_receive_started.wait())
    recovered = asyncio.create_task(recover_called.wait())
    done, pending = await asyncio.wait_for(
        asyncio.wait(
            {second_started, recovered},
            return_when=asyncio.FIRST_COMPLETED,
        ),
        timeout=0.5,
    )

    try:
        assert second_started in done
        assert recovered not in done
        handler._recover_upstream_after_disconnect.assert_not_awaited()
        handler._send_error.assert_not_awaited()
        assert handler.running is True
    finally:
        for task in pending:
            task.cancel()
        receiving.cancel()
        await asyncio.gather(
            receiving,
            second_started,
            recovered,
            return_exceptions=True,
        )


@pytest.mark.asyncio
async def test_old_legacy_receive_success_after_rollover_is_dropped_before_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "false")

    class BlockingLegacySocket:
        def __init__(self, payload: dict[str, object] | None = None) -> None:
            self.payload = payload
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def recv(self) -> str:
            self.started.set()
            await self.release.wait()
            if self.payload is None:
                await asyncio.Event().wait()
                raise AssertionError("unreachable")
            return json.dumps(self.payload)

    old_socket = BlockingLegacySocket(
        {
            "type": "response.created",
            "response_id": "response-old",
        }
    )
    new_socket = BlockingLegacySocket()
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler.upstream_ws = old_socket
    handler._connection_epoch = 4
    handler._handle_upstream_event = AsyncMock()  # type: ignore[method-assign]

    async def close_old() -> None:
        handler.upstream_ws = None

    async def connect_new() -> None:
        handler.upstream_ws = new_socket

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_old)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock(side_effect=connect_new)  # type: ignore[method-assign]

    receiving = asyncio.create_task(handler._receive_upstream_events())
    await asyncio.wait_for(old_socket.started.wait(), timeout=0.5)
    await asyncio.wait_for(handler._clear_upstream_generation(), timeout=0.5)
    handler._active_response = RealtimeResponseState(
        request_id=2,
        stream_id="stream-new",
    )
    old_socket.release.set()
    await asyncio.wait_for(new_socket.started.wait(), timeout=0.5)

    try:
        handler._handle_upstream_event.assert_not_awaited()
        assert handler._active_response.response_id is None
    finally:
        receiving.cancel()
        await asyncio.gather(receiving, return_exceptions=True)


@pytest.mark.asyncio
async def test_proactive_refresh_advances_generation_and_ignores_old_receive_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")

    class LateFailingProvider(RecordingRealtimeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.first_receive_started = asyncio.Event()
            self.release_first_error = asyncio.Event()
            self.second_receive_started = asyncio.Event()
            self.receive_calls = 0

        async def receive(self, *, connection_epoch: int) -> ProviderEvent:
            self.receive_calls += 1
            if self.receive_calls == 1:
                assert connection_epoch == 4
                self.first_receive_started.set()
                await self.release_first_error.wait()
                raise RealtimeProviderError(
                    category=ProviderErrorCategory.DISCONNECTED,
                    reason=ProviderErrorReason.CONNECTION_CLOSED,
                    retryable=True,
                )
            assert connection_epoch == 5
            self.second_receive_started.set()
            await asyncio.Event().wait()
            raise AssertionError("cancelled receive must not resume")

    provider = LateFailingProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler._connection_epoch = 4
    handler.running = True
    handler.session_status = "in_progress"

    async def close_old() -> None:
        handler.upstream_ws = None

    async def connect_new() -> None:
        handler.upstream_ws = provider

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_old)  # type: ignore[method-assign]
    handler._connect_upstream = AsyncMock(side_effect=connect_new)  # type: ignore[method-assign]
    handler._cancel_pending_response_after_commit = AsyncMock()  # type: ignore[method-assign]
    handler._reset_turn_runtime_state = MagicMock()  # type: ignore[method-assign]
    handler._send_status = AsyncMock()  # type: ignore[method-assign]
    handler._recover_upstream_after_disconnect = AsyncMock(return_value=False)  # type: ignore[method-assign]
    handler._record_upstream_disconnect_diagnostics = AsyncMock()  # type: ignore[method-assign]
    handler._send_error = AsyncMock()  # type: ignore[method-assign]

    receiving = asyncio.create_task(handler._receive_upstream_events())
    await asyncio.wait_for(provider.first_receive_started.wait(), timeout=0.5)
    assert await handler._refresh_upstream_for_next_input("before_text") is True
    assert handler._connection_epoch == 5
    assert handler._upstream_rollover_token > 0
    provider.release_first_error.set()
    await asyncio.wait_for(provider.second_receive_started.wait(), timeout=0.5)

    try:
        handler._recover_upstream_after_disconnect.assert_not_awaited()
        handler._send_error.assert_not_awaited()
        assert handler.running is True
    finally:
        receiving.cancel()
        await asyncio.gather(receiving, return_exceptions=True)


@pytest.mark.asyncio
async def test_stale_provider_event_epoch_is_ignored_before_legacy_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    handler = StepFunRealtimeHandler(
        provider_factory=lambda **_kwargs: RecordingRealtimeProvider()
    )
    handler._connection_epoch = 8
    handler._handle_upstream_event = AsyncMock()  # type: ignore[method-assign]

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_TEXT_DELTA,
            provider_event_type="response.text.delta",
            connection_epoch=7,
            response_id="response-stale",
            data={"text": "must-not-cross"},
        )
    )

    handler._handle_upstream_event.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_TEXT_DELTA,
            provider_event_type="response.text.delta",
            connection_epoch=8,
            request_id=6,
            response_id="response-current",
            stream_id="stream-current",
            data={"text": "stale text"},
        ),
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_AUDIO_DELTA,
            provider_event_type="response.audio.delta",
            connection_epoch=8,
            request_id=5,
            response_id="response-stale",
            stream_id="stream-current",
            data={"audio": "AAE="},
        ),
        ProviderEvent(
            kind=ProviderEventKind.THINKING_DONE,
            provider_event_type="response.thinking.done",
            connection_epoch=8,
            request_id=5,
            response_id="response-current",
            stream_id="stream-stale",
            data={"text": "stale thinking"},
        ),
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=8,
            request_id=5,
            response_id="response-stale",
            stream_id="stream-current",
            data={},
        ),
        ProviderEvent(
            kind=ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
            provider_event_type="response.function_call_arguments.done",
            connection_epoch=8,
            call_id="call-stale",
            data={"name": "search_internal_knowledge", "arguments": "{}"},
        ),
        ProviderEvent(
            kind=ProviderEventKind.CONVERSATION_ITEM,
            provider_event_type="conversation.item.created",
            connection_epoch=8,
            request_id=4,
            response_id="response-current",
            stream_id="stream-current",
            call_id="call-stale",
            data={"item_type": "function_call", "name": "search_internal_knowledge"},
        ),
    ],
    ids=[
        "text-request",
        "audio-response",
        "thinking-stream",
        "done-response",
        "args-call",
        "tool-request",
    ],
)
async def test_stale_provider_authority_is_rejected_before_any_side_effect(
    event: ProviderEvent,
) -> None:
    handler = StepFunRealtimeHandler()
    handler._connection_epoch = 8
    handler.current_request_id = 5
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    handler._function_call_states = {
        "call-current": FunctionCallState(
            call_id="call-current",
            name="search_internal_knowledge",
        )
    }
    handler._function_call_authorities = {
        "call-current": FunctionCallAuthority(
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
        )
    }
    handler._before_accepted_upstream_event = AsyncMock()  # type: ignore[method-assign]
    handler._route_accepted_upstream_event = AsyncMock()  # type: ignore[method-assign]

    await handler._handle_provider_event(event)

    handler._before_accepted_upstream_event.assert_not_awaited()
    handler._route_accepted_upstream_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_sparse_function_done_without_call_binding_fails_closed() -> None:
    handler = StepFunRealtimeHandler()
    handler._connection_epoch = 8
    handler.current_request_id = 5
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    handler._execute_function_call = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
            provider_event_type="response.function_call_arguments.done",
            connection_epoch=8,
            call_id="call-unbound",
            data={"name": "search_internal_knowledge", "arguments": "{}"},
        )
    )

    assert handler._function_call_states == {}
    handler._execute_function_call.assert_not_awaited()


def test_trusted_legacy_sparse_call_does_not_overwrite_explicit_stale_response() -> None:
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    handler._function_call_authorities = {
        "call-current": FunctionCallAuthority(
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
        )
    }
    stale = {
        "type": "response.function_call_arguments.done",
        "response_id": "response-stale",
        "call_id": "call-current",
        "name": "search_internal_knowledge",
        "arguments": "{}",
    }

    assert handler._correlate_trusted_legacy_raw_event(stale) == stale


@pytest.mark.asyncio
async def test_bound_sparse_call_rejects_explicit_malformed_authority() -> None:
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    handler._function_call_authorities = {
        "call-current": FunctionCallAuthority(
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
        )
    }
    handler._execute_function_call = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await handler._handle_upstream_event(
        {
            "type": "response.function_call_arguments.done",
            "response_id": "",
            "call_id": "call-current",
            "name": "search_internal_knowledge",
            "arguments": "{}",
        }
    )

    handler._execute_function_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_function_call_first_event_binds_explicit_active_authority() -> None:
    handler = StepFunRealtimeHandler()
    handler._connection_epoch = 8
    handler.current_request_id = 5
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    handler._execute_function_call = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.CONVERSATION_ITEM,
            provider_event_type="conversation.item.created",
            connection_epoch=8,
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
            call_id="call-bound",
            data={
                "item_type": "function_call",
                "name": "search_internal_knowledge",
            },
        )
    )
    authority = handler._function_call_authorities["call-bound"]
    assert authority.request_id == 5
    assert authority.response_id == "response-current"
    assert authority.stream_id == "stream-current"

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
            provider_event_type="response.function_call_arguments.delta",
            connection_epoch=8,
            call_id="call-bound",
            data={"arguments": '{"query":'},
        )
    )
    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
            provider_event_type="response.function_call_arguments.done",
            connection_epoch=8,
            call_id="call-bound",
            data={
                "name": "search_internal_knowledge",
                "arguments": '{"query":"产品"}',
            },
        )
    )

    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-bound",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"产品"}',
        trigger_followup_response=True,
    )


@pytest.mark.asyncio
async def test_matching_provider_response_done_cannot_register_unseen_tool() -> None:
    handler = StepFunRealtimeHandler()
    handler._connection_epoch = 8
    handler.current_request_id = 5
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
        text_parts=["合法正文"],
    )
    handler._persist_message = AsyncMock()
    handler._apply_roleplay_output_guard = AsyncMock(
        side_effect=lambda text, **_kwargs: text
    )
    handler._send_status = AsyncMock()
    handler._execute_function_call = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=8,
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
            data={
                "function_outputs": (
                    {
                        "call_id": "call-unbound",
                        "name": "search_internal_knowledge",
                        "arguments": "{}",
                    },
                )
            },
        )
    )

    assert handler._active_response is None
    handler._persist_message.assert_awaited_once()
    handler._execute_function_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_matching_raw_response_done_cannot_register_unseen_tool_call() -> None:
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
        text_parts=["最终回应"],
    )
    handler._persist_message = AsyncMock()
    handler._apply_roleplay_output_guard = AsyncMock(
        side_effect=lambda text, **_kwargs: text
    )
    handler._send_status = AsyncMock()
    handler._execute_function_call = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._create_response = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await handler._handle_upstream_response_done(
        {
            "type": "response.done",
            "request_id": 5,
            "stream_id": "stream-current",
            "response": {
                "id": "response-current",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-from-done",
                        "name": "search_internal_knowledge",
                        "arguments": '{"query":"产品"}',
                    }
                ],
            },
        }
    )

    assert handler._active_response is None
    assert "call-from-done" not in handler._function_call_authorities
    handler._persist_message.assert_awaited_once()
    handler._send_status.assert_awaited_with("listening")
    handler._execute_function_call.assert_not_awaited()
    handler._create_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_unauthorized_done_tool_is_filtered_but_response_still_finalizes() -> None:
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
        text_parts=["仍需持久化"],
    )
    handler._function_call_authorities = {
        "call-allowed": FunctionCallAuthority(
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
        ),
        "call-stale": FunctionCallAuthority(
            request_id=4,
            response_id="response-old",
            stream_id="stream-old",
        ),
    }
    handler._persist_message = AsyncMock()
    handler._apply_roleplay_output_guard = AsyncMock(
        side_effect=lambda text, **_kwargs: text
    )
    handler._send_status = AsyncMock()
    handler._execute_function_call = AsyncMock(return_value=False)  # type: ignore[method-assign]

    await handler._handle_upstream_response_done(
        {
            "type": "response.done",
            "request_id": 5,
            "stream_id": "stream-current",
            "response": {
                "id": "response-current",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": "search_internal_knowledge",
                        "arguments": "{}",
                    }
                    for call_id in ("call-stale", "call-allowed")
                ],
            },
        }
    )

    assert handler._active_response is None
    handler._persist_message.assert_awaited_once()
    handler._send_status.assert_awaited_with("listening")
    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-allowed",
        function_name="search_internal_knowledge",
        raw_arguments="{}",
        trigger_followup_response=False,
    )


@pytest.mark.asyncio
async def test_response_id_cannot_prebind_before_response_created() -> None:
    handler = StepFunRealtimeHandler()
    handler._connection_epoch = 8
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
    )
    handler._before_accepted_upstream_event = AsyncMock()  # type: ignore[method-assign]

    prebind_events = [
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_TEXT_DELTA,
            provider_event_type="response.text.delta",
            connection_epoch=8,
            request_id=5,
            response_id="response-old",
            stream_id="stream-current",
            data={"text": "不得预绑定"},
        ),
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_AUDIO_DELTA,
            provider_event_type="response.audio.delta",
            connection_epoch=8,
            request_id=5,
            response_id="response-old",
            stream_id="stream-current",
            data={"audio": "AAE="},
        ),
        ProviderEvent(
            kind=ProviderEventKind.THINKING_DONE,
            provider_event_type="response.thinking.done",
            connection_epoch=8,
            request_id=5,
            response_id="response-old",
            stream_id="stream-current",
            data={"text": "旧思考"},
        ),
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=8,
            request_id=5,
            response_id="response-old",
            stream_id="stream-current",
            data={},
        ),
        ProviderEvent(
            kind=ProviderEventKind.CONVERSATION_ITEM,
            provider_event_type="conversation.item.created",
            connection_epoch=8,
            request_id=5,
            response_id="response-old",
            stream_id="stream-current",
            call_id="call-old",
            data={
                "item_type": "function_call",
                "name": "search_internal_knowledge",
            },
        ),
    ]
    for event in prebind_events:
        await handler._handle_provider_event(event)

    handler._before_accepted_upstream_event.assert_not_awaited()
    assert handler._active_response.response_id is None

    await handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_CREATED,
            provider_event_type="response.created",
            connection_epoch=8,
            request_id=5,
            response_id="response-current",
            stream_id="stream-current",
        )
    )
    handler._before_accepted_upstream_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_response_created_requires_exact_active_request_and_stream_authority() -> None:
    raw_handler = StepFunRealtimeHandler()
    raw_handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
    )
    raw_events = [
        {
            "type": "response.created",
            "request_id": 4,
            "stream_id": "stream-current",
            "response": {"id": "response-stale-request"},
        },
        {
            "type": "response.created",
            "request_id": 5,
            "stream_id": "stream-stale",
            "response": {"id": "response-stale-stream"},
        },
        {
            "type": "response.created",
            "stream_id": "stream-current",
            "response": {"id": "response-missing-request"},
        },
        {
            "type": "response.created",
            "request_id": 5,
            "response": {"id": "response-missing-stream"},
        },
    ]
    for event in raw_events:
        await raw_handler._handle_upstream_event(event)
        assert raw_handler._active_response.response_id is None

    bound_handler = StepFunRealtimeHandler()
    bound_handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
        response_id="response-current",
    )
    await bound_handler._handle_upstream_event(
        {
            "type": "response.created",
            "request_id": 5,
            "stream_id": "stream-current",
            "response": {"id": "response-conflict"},
        }
    )
    assert bound_handler._active_response.response_id == "response-current"

    canonical_handler = StepFunRealtimeHandler()
    canonical_handler._connection_epoch = 8
    canonical_handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
    )
    await canonical_handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_CREATED,
            provider_event_type="response.created",
            connection_epoch=8,
            response_id="response-missing-authority",
        )
    )

    assert canonical_handler._active_response.response_id is None


@pytest.mark.asyncio
async def test_trusted_legacy_top_level_created_binds_and_preserves_kb_cancel_parity() -> (
    None
):
    bound = StepFunRealtimeHandler()
    bound._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-current",
    )
    correlated = bound._correlate_trusted_legacy_raw_event(
        {
            "type": "response.created",
            "response_id": "response-top-level",
        }
    )

    await bound._handle_upstream_event(correlated)

    assert bound._active_response.response_id == "response-top-level"
    assert correlated["response"] == {"id": "response-top-level"}

    unexpected = StepFunRealtimeHandler()
    unexpected.upstream_ws = object()
    unexpected._connection_epoch = 4
    unexpected._effective_policy = {
        "tool_policy": {"require_kb_grounding": True},
    }
    unexpected._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    unexpected._close_upstream = AsyncMock()  # type: ignore[method-assign]
    unexpected._connect_upstream = AsyncMock()  # type: ignore[method-assign]
    normalized = unexpected._correlate_trusted_legacy_raw_event(
        {
            "type": "response.created",
            "response_id": "response-unexpected",
        }
    )

    await unexpected._handle_upstream_event(normalized)

    unexpected._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    unexpected._close_upstream.assert_awaited_once_with()
    unexpected._connect_upstream.assert_awaited_once_with()
    assert unexpected._connection_epoch == 5


@pytest.mark.asyncio
async def test_no_active_response_event_matrix_has_narrow_cleanup_and_cancel_paths() -> None:
    sparse_done_handler = StepFunRealtimeHandler()
    sparse_done_handler._connection_epoch = 8
    sparse_done_handler._pending_tool_followup_response = True
    sparse_done_handler._send_status = AsyncMock()
    sparse_done_handler._execute_function_call = AsyncMock()  # type: ignore[method-assign]

    await sparse_done_handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_DONE,
            provider_event_type="response.done",
            connection_epoch=8,
            data={},
        )
    )

    assert sparse_done_handler._pending_tool_followup_response is False
    sparse_done_handler._send_status.assert_awaited_once_with("listening")
    sparse_done_handler._execute_function_call.assert_not_awaited()

    unexpected_created_handler = StepFunRealtimeHandler()
    unexpected_created_handler.upstream_ws = object()
    unexpected_created_handler._connection_epoch = 8
    unexpected_created_handler._is_kb_lock_required_for_current_policy = MagicMock(
        return_value=True
    )
    unexpected_created_handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    unexpected_created_handler._close_upstream = AsyncMock()  # type: ignore[method-assign]
    unexpected_created_handler._connect_upstream = AsyncMock()  # type: ignore[method-assign]

    await unexpected_created_handler._handle_provider_event(
        ProviderEvent(
            kind=ProviderEventKind.RESPONSE_CREATED,
            provider_event_type="response.created",
            connection_epoch=8,
            response_id="response-unexpected",
        )
    )

    assert unexpected_created_handler._active_response is None
    unexpected_created_handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    unexpected_created_handler._close_upstream.assert_awaited_once_with()
    unexpected_created_handler._connect_upstream.assert_awaited_once_with()
    assert unexpected_created_handler._connection_epoch == 9

    rejected_handler = StepFunRealtimeHandler()
    rejected_handler._handle_thinking_event = AsyncMock()
    await rejected_handler._handle_upstream_event(
        {"type": "response.thinking.done", "thinking": "不得进入副作用"}
    )

    rejected_handler._handle_thinking_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_upstream_delegates_connection_to_shared_stepfun_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "false")
    upstream_ws = object()
    transport = SimpleNamespace(
        connect=AsyncMock(return_value=upstream_ws),
        close=AsyncMock(),
    )
    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler._stepfun_api_key = "test-api-key"
    handler._stepfun_url = "wss://stepfun.example/realtime"
    handler._stepfun_model = "step-audio-test"
    handler._stepfun_voice = "voice-default"
    handler._effective_policy = {"turn_detection": "server_vad"}
    handler._stepfun_input_transcription_enabled = True
    handler._stepfun_input_transcription_language = "zh"
    handler._stepfun_input_transcription_model = "step-asr"
    handler._stepfun_instructions = "保持销售训练角色。"
    handler._build_stepfun_tools_from_policy = MagicMock(
        return_value=[{"type": "function", "name": "search_internal_knowledge"}]
    )
    handler._enforce_stepfun_tool_guardrails = MagicMock(
        side_effect=lambda tools: tools
    )
    handler._send_upstream = AsyncMock()
    handler._ensure_upstream_keepalive_task = MagicMock()
    handler._maybe_start_kb_lock_warmup = AsyncMock()

    await handler._connect_upstream()

    transport.connect.assert_awaited_once_with(
        api_key="test-api-key",
        url="wss://stepfun.example/realtime",
        model="step-audio-test",
    )
    assert handler.upstream_ws is upstream_ws
    assert handler._upstream_connected_at > 0
    assert handler._upstream_last_activity_at == handler._upstream_connected_at
    handler._send_upstream.assert_awaited_once()
    payload = handler._send_upstream.await_args.args[0]
    assert payload["type"] == "session.update"
    assert payload["session"]["modalities"] == ["text", "audio"]
    assert payload["session"]["voice"] == "voice-default"
    assert payload["session"]["turn_detection"] == {"type": "server_vad"}
    assert payload["session"]["input_audio_transcription"] == {
        "language": "zh",
        "model": "step-asr",
    }
    assert payload["session"]["tools"] == [
        {"type": "function", "name": "search_internal_knowledge"}
    ]
    handler._ensure_upstream_keepalive_task.assert_called_once_with()
    handler._maybe_start_kb_lock_warmup.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_send_upstream_delegates_to_transport_and_marks_activity_only_on_success():
    upstream_ws = object()
    transport = SimpleNamespace(
        send_json=AsyncMock(return_value=StepFunSendResult(status=StepFunSendStatus.SENT))
    )
    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler.upstream_ws = upstream_ws

    accepted = await handler._send_upstream({"type": "session.update"})

    assert accepted is True
    transport.send_json.assert_awaited_once_with(upstream_ws, {"type": "session.update"})
    assert handler._upstream_last_activity_at > 0

    failed_transport = SimpleNamespace(
        send_json=AsyncMock(return_value=StepFunSendResult(status=StepFunSendStatus.FAILED))
    )
    failed_handler = StepFunRealtimeHandler(stepfun_transport=failed_transport)
    failed_handler.upstream_ws = upstream_ws

    accepted = await failed_handler._send_upstream({"type": "response.create"})

    assert accepted is False
    failed_transport.send_json.assert_awaited_once_with(
        upstream_ws,
        {"type": "response.create"},
    )
    assert failed_handler._upstream_last_activity_at == 0.0


@pytest.mark.asyncio
async def test_apply_lifecycle_action_delegates_transition_to_session_control_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(status="preparing")
    transition = SimpleNamespace(action="start", to_status="in_progress", changed=True)
    adapter_calls: list[dict[str, Any]] = []

    class FakeDb:
        commit = AsyncMock()
        rollback = AsyncMock()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeLifecycleService:
        def __init__(self, db: Any) -> None:
            self.db = db

        async def get_session_with_scenario(self, session_id: str):
            assert session_id == "session-adapter-delegation"
            return session, "sales"

        async def transition(self, **kwargs):  # pragma: no cover - must use adapter seam
            raise AssertionError("handler bypassed SessionControlAdapter")

        async def trigger_report_generation_if_needed(self, observed_transition: Any) -> None:
            assert observed_transition is transition

    class FakeSessionControlAdapter:
        def __init__(self, lifecycle_service: Any) -> None:
            self.lifecycle_service = lifecycle_service

        async def apply_action(self, **kwargs):
            adapter_calls.append(kwargs)
            return transition

    monkeypatch.setattr(stepfun_module, "AsyncSessionLocal", FakeDb)
    monkeypatch.setattr(stepfun_module, "SessionLifecycleService", FakeLifecycleService)
    monkeypatch.setattr(stepfun_module, "SessionControlAdapter", FakeSessionControlAdapter)
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-adapter-delegation"
    handler._send_error = AsyncMock()
    handler._send_status = AsyncMock()

    result = await handler._apply_lifecycle_action("start")

    assert result is transition
    assert handler.session_status == "in_progress"
    assert adapter_calls == [
        {
            "session": session,
            "scenario_type": "sales",
            "action": "start",
        }
    ]


def test_stepfun_realtime_handler_defaults_to_latest_realtime_model(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("STEPFUN_REALTIME_MODEL", raising=False)

    handler = StepFunRealtimeHandler()

    assert handler._stepfun_model == "stepaudio-2.5-realtime"


def test_handler_applies_voice_runtime_profile_from_policy_snapshot() -> None:
    handler = StepFunRealtimeHandler()
    snapshot = {
        "voice_mode": "stepfun_realtime",
        "model_name": "step-audio-custom",
        "voice_name": "voice-custom",
        "temperature": 0.33,
        "instructions": "保持客户角色。",
        "instruction_contract_hash": "hash-custom",
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"network_access_mode": "off"},
    }

    profile = handler._apply_voice_runtime_profile(snapshot)

    assert isinstance(profile, VoiceRuntimeProfile)
    assert handler._voice_runtime_profile is profile
    assert handler._stepfun_model == "step-audio-custom"
    assert handler._stepfun_voice == "voice-custom"
    assert handler._stepfun_temperature == 0.33
    assert handler._stepfun_instructions == "保持客户角色。"
    assert handler._instruction_contract_hash == "hash-custom"


def test_stepfun_session_config_uses_voice_runtime_profile_as_canonical_source() -> None:
    handler = StepFunRealtimeHandler()
    handler._apply_voice_runtime_profile(
        {
            "voice_mode": "stepfun_realtime",
            "model_name": "step-audio-profile",
            "voice_name": "voice-profile",
            "temperature": 0.44,
            "instructions": "保持 profile 指令。",
            "instruction_contract_hash": "hash-profile",
            "knowledge_base_ids": ["kb-1"],
            "tool_policy": {"network_access_mode": "off"},
        }
    )
    handler._stepfun_voice = "voice-stale"
    handler._stepfun_temperature = 1.5
    handler._stepfun_instructions = "陈旧指令。"
    handler._effective_policy = {}
    handler._build_stepfun_tools_from_policy = MagicMock(return_value=[])
    handler._enforce_stepfun_tool_guardrails = MagicMock(side_effect=lambda tools: tools)

    config = handler._build_stepfun_session_config()

    assert config.voice == "voice-profile"
    assert config.temperature == 0.44
    assert config.instructions == "保持 profile 指令。"


def test_handler_delegates_tool_building_and_guardrails_to_execution_module():
    class DelegatingToolExecution(StepFunToolExecutionModule):
        def __init__(self) -> None:
            super().__init__()
            self.build_policy_calls: list[dict] = []
            self.guardrail_calls: list[tuple[list[dict], dict]] = []

        def build_tools_from_policy(self, policy: dict) -> list[dict]:
            self.build_policy_calls.append(policy)
            return [
                {"type": "function", "function": {"name": "search_internal_knowledge"}}
            ]

        def enforce_guardrails(self, tools: list[dict], policy: dict) -> list[dict]:
            self.guardrail_calls.append((tools, policy))
            return []

    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"network_access_mode": "off"},
    }
    tool_execution = DelegatingToolExecution()
    handler._tool_execution = tool_execution

    built_tools = handler._build_stepfun_tools_from_policy()
    guarded_tools = handler._enforce_stepfun_tool_guardrails(built_tools)

    assert tool_execution.build_policy_calls == [handler._effective_policy]
    assert tool_execution.guardrail_calls == [(built_tools, handler._effective_policy)]
    assert guarded_tools == []


@pytest.mark.asyncio
async def test_handle_client_text_persists_user_message_before_create_response():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 0

    handler._persist_message = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="opening")
    handler._run_realtime_feedback = AsyncMock(
        return_value={"score_snapshot": {"overall_score": 82}}
    )
    handler._prepare_grounding_context = AsyncMock()
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock()
    handler._create_response = AsyncMock()

    await handler._handle_client_text(
        json.dumps(
            {
                "type": "text",
                "data": {"text": "你好，给我介绍一下产品"},
            }
        )
    )

    handler._persist_message.assert_awaited_once_with(
        turn_number=1,
        role="user",
        content="你好，给我介绍一下产品",
        sales_stage="opening",
        analysis_data={"score_snapshot": {"overall_score": 82}},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="你好，给我介绍一下产品",
        turn_number=1,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="你好，给我介绍一下产品",
        turn_number=1,
        sales_stage="opening",
    )
    handler._prepare_grounding_context.assert_awaited_once_with(
        "你好，给我介绍一下产品"
    )
    handler._create_response.assert_awaited_once_with(count_turn=True)
    assert handler._send_upstream.await_count == 1

    payload = handler._send_upstream.await_args_list[0].args[0]
    assert payload["type"] == "conversation.item.create"
    assert payload["item"]["content"][0]["text"] == "你好，给我介绍一下产品"


@pytest.mark.asyncio
async def test_audio_chunk_backpressure_delegates_to_transport_and_drops_audio_append():
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(status=StepFunBackpressureStatus.DROP)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock()

    await handler._handle_client_text(
        json.dumps(
            {
                "type": "audio_chunk",
                "data": {"audio": "base64-audio"},
            }
        )
    )

    transport.decide_backpressure.assert_called_once()
    payload = transport.decide_backpressure.call_args.args[0]
    assert payload == {"type": "input_audio_buffer.append", "audio": "base64-audio"}
    handler._send_upstream.assert_not_awaited()
    assert handler._has_uncommitted_audio is False
    assert handler._audio_flow.get_input_buffer() == []


@pytest.mark.asyncio
async def test_audio_chunk_delegates_sent_audio_to_audio_flow_without_payload_change():
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock()

    await handler._handle_client_text(
        json.dumps(
            {
                "type": "audio_chunk",
                "data": {"audio": "base64-audio"},
            }
        )
    )

    transport.decide_backpressure.assert_called_once()
    assert transport.decide_backpressure.call_args.kwargs["pending_bytes"] == 0
    handler._send_upstream.assert_awaited_once_with(
        {"type": "input_audio_buffer.append", "audio": "base64-audio"}
    )
    assert handler._audio_flow.get_input_buffer() == ["base64-audio"]
    assert handler._has_uncommitted_audio is True


def test_summarize_pcm16_payload_returns_aggregate_audio_quality_only():
    payload = b"".join(
        sample.to_bytes(2, byteorder="little", signed=True)
        for sample in (0, 1000, -1000, 32767, -32768)
    )

    stats = StepFunRealtimeHandler._summarize_pcm16_payload(payload)

    assert stats == {
        "sample_count": 5,
        "rms": 20733.64,
        "peak_abs": 32768,
        "zero_ratio": 0.2,
        "payload_bytes": 10,
        "odd_byte_truncated": False,
    }
    assert "payload" not in stats
    assert "samples" not in stats


@pytest.mark.asyncio
async def test_binary_audio_quality_is_logged_and_reset_after_commit():
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock(return_value=True)
    handler._schedule_response_after_commit = AsyncMock()
    handler._log_latency_debug = MagicMock()
    payload = b"".join(
        sample.to_bytes(2, byteorder="little", signed=True)
        for sample in (0, 1000, -1000, 32767, -32768)
    )

    accepted = await handler._handle_binary_frame(
        bytes([StepFunRealtimeHandler.BINARY_AUDIO_CHUNK]) + payload
    )
    await handler._commit_and_respond()

    assert accepted is True
    handler._send_upstream.assert_any_await(
        {
            "type": "input_audio_buffer.append",
            "audio": "AADoAxj8/38AgA==",
        }
    )
    handler._send_upstream.assert_any_await({"type": "input_audio_buffer.commit"})
    assert handler._has_uncommitted_audio is False
    assert handler._summarize_pending_input_audio_quality() == {
        "audio_quality_frame_count": 0,
        "audio_quality_payload_bytes": 0,
        "audio_quality_sample_count": 0,
        "audio_quality_rms": 0.0,
        "audio_quality_peak_abs": 0,
        "audio_quality_zero_ratio": 0.0,
        "audio_quality_odd_payload_frames": 0,
    }

    commit_call = next(
        call_item
        for call_item in handler._log_latency_debug.call_args_list
        if call_item.args == ("audio_commit_requested",)
    )
    assert commit_call.kwargs["binary_frame_count"] == 1
    assert commit_call.kwargs["audio_quality_frame_count"] == 1
    assert commit_call.kwargs["audio_quality_payload_bytes"] == 10
    assert commit_call.kwargs["audio_quality_sample_count"] == 5
    assert commit_call.kwargs["audio_quality_rms"] == 20733.64
    assert commit_call.kwargs["audio_quality_peak_abs"] == 32768
    assert commit_call.kwargs["audio_quality_zero_ratio"] == 0.2


@pytest.mark.asyncio
async def test_binary_audio_quality_debug_log_does_not_duplicate_payload_bytes():
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock(return_value=True)
    handler._log_latency_debug = MagicMock()
    payload = b"".join(
        sample.to_bytes(2, byteorder="little", signed=True)
        for sample in (0, 1000, -1000, 32767, -32768)
    )

    for _ in range(20):
        await handler._handle_binary_frame(
            bytes([StepFunRealtimeHandler.BINARY_AUDIO_CHUNK]) + payload
        )

    received_call = next(
        call_item
        for call_item in handler._log_latency_debug.call_args_list
        if call_item.args == ("audio_binary_received",)
    )
    assert received_call.kwargs["frame_count"] == 20
    assert received_call.kwargs["payload_bytes"] == 10
    assert received_call.kwargs["sample_count"] == 5
    assert received_call.kwargs["rms"] == 20733.64
    assert received_call.kwargs["peak_abs"] == 32768
    assert received_call.kwargs["zero_ratio"] == 0.2


@pytest.mark.asyncio
async def test_binary_audio_quality_does_not_count_backpressure_dropped_audio():
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(status=StepFunBackpressureStatus.DROP)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._send_upstream = AsyncMock()
    payload = b"".join(
        sample.to_bytes(2, byteorder="little", signed=True)
        for sample in (0, 1000, -1000, 32767, -32768)
    )

    accepted = await handler._handle_binary_frame(
        bytes([StepFunRealtimeHandler.BINARY_AUDIO_CHUNK]) + payload
    )

    assert accepted is False
    transport.decide_backpressure.assert_called_once()
    handler._send_upstream.assert_not_awaited()
    assert handler._summarize_pending_input_audio_quality() == {
        "audio_quality_frame_count": 0,
        "audio_quality_payload_bytes": 0,
        "audio_quality_sample_count": 0,
        "audio_quality_rms": 0.0,
        "audio_quality_peak_abs": 0,
        "audio_quality_zero_ratio": 0.0,
        "audio_quality_odd_payload_frames": 0,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "frame"),
    [
        ("empty", b""),
        ("empty_chunk", bytes([StepFunRealtimeHandler.BINARY_AUDIO_CHUNK])),
        ("invalid", b"\x7fnot-audio"),
        ("interrupt", bytes([StepFunRealtimeHandler.BINARY_AUDIO_INTERRUPT])),
        ("lifecycle_rejected", b"\x01audio"),
        ("upstream_not_ready", b"\x01audio"),
        ("upstream_rejected", b"\x01audio"),
    ],
)
async def test_binary_audio_disposition_rejects_non_accepted_frames(
    case: str,
    frame: bytes,
) -> None:
    transport = SimpleNamespace(
        decide_backpressure=MagicMock(
            return_value=StepFunBackpressureResult(
                status=StepFunBackpressureStatus.ALLOW
            )
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=cast(Any, transport))
    handler.session_status = "in_progress"
    handler._handle_interrupt = AsyncMock()
    handler._ensure_input_allowed = AsyncMock(return_value=case != "lifecycle_rejected")
    handler._ensure_upstream_ready_for_input = AsyncMock(
        return_value=case != "upstream_not_ready"
    )
    handler._send_upstream = AsyncMock(return_value=case != "upstream_rejected")

    accepted = await handler._handle_binary_frame(frame)

    assert accepted is False
    assert handler._audio_flow.get_input_buffer() == []
    assert handler._has_uncommitted_audio is False
    if case == "interrupt":
        handler._handle_interrupt.assert_awaited_once_with("user_speaking")


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_persists_user_message_before_response_created():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(
        return_value={"fuzzy_words": [{"category": "uncertain"}]}
    )
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "这是语音最终识别文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是语音最终识别文本",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=3,
        role="user",
        content="这是语音最终识别文本",
        sales_stage="discovery",
        analysis_data={"fuzzy_words": [{"category": "uncertain"}]},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="这是语音最终识别文本",
        turn_number=3,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="这是语音最终识别文本",
        turn_number=3,
        sales_stage="discovery",
    )
    handler._prepare_grounding_context.assert_awaited_once_with("这是语音最终识别文本")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_persists_user_message_after_response_created():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._active_response = RealtimeResponseState(
        request_id=9,
        stream_id="stream-after-create",
    )

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="presentation")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    await handler._handle_upstream_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "这是新一轮语音文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是新一轮语音文本",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=2,
        role="user",
        content="这是新一轮语音文本",
        sales_stage="presentation",
        analysis_data={},
    )
    handler._analyze_and_emit_sales_stage.assert_awaited_once_with(
        user_text="这是新一轮语音文本",
        turn_number=2,
    )
    handler._run_realtime_feedback.assert_awaited_once_with(
        user_text="这是新一轮语音文本",
        turn_number=2,
        sales_stage="presentation",
    )
    handler._prepare_grounding_context.assert_awaited_once_with("这是新一轮语音文本")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_extracts_nested_content_transcript():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item": {
                "id": "item-1",
                "content": [
                    {
                        "type": "input_audio",
                        "transcript": "我想了解一下你们现在售前新人培训怎么做。",
                    }
                ],
            },
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "我想了解一下你们现在售前新人培训怎么做。",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=2,
        role="user",
        content="我想了解一下你们现在售前新人培训怎么做。",
        sales_stage="discovery",
        analysis_data={},
    )
    handler._prepare_grounding_context.assert_awaited_once_with(
        "我想了解一下你们现在售前新人培训怎么做。"
    )


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_extracts_nested_transcript_field():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "event-1",
            "item_id": "item-1",
            "content_index": 0,
            "transcript": {"text": "我是来了解你们售前培训现状的。"},
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "我是来了解你们售前培训现状的。",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=2,
        role="user",
        content="我是来了解你们售前培训现状的。",
        sales_stage="discovery",
        analysis_data={},
    )


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_falls_back_to_created_item_transcript():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "conversation.item.created",
            "item": {
                "id": "item-1",
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "audio": {
                            "transcript": "我想先了解你们目前售前新人培养的流程。",
                        },
                    }
                ],
            },
        }
    )
    await handler._handle_upstream_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "item-1",
            "content_index": 0,
            "transcript": "",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "我想先了解你们目前售前新人培养的流程。",
        is_final=True,
    )
    handler._persist_message.assert_awaited_once_with(
        turn_number=2,
        role="user",
        content="我想先了解你们目前售前新人培养的流程。",
        sales_stage="discovery",
        analysis_data={},
    )
    handler._prepare_grounding_context.assert_awaited_once_with(
        "我想先了解你们目前售前新人培养的流程。"
    )


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_logs_empty_transcript_shape():
    handler = StepFunRealtimeHandler()
    handler._latest_input_transcript_delta = ""
    handler._log_latency_debug = MagicMock()

    await handler._handle_upstream_transcription_completed(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "item-empty",
            "content_index": 0,
            "transcript": "   ",
        }
    )

    handler._log_latency_debug.assert_called_once()
    args, kwargs = handler._log_latency_debug.call_args
    assert args == ("transcription_completed_empty_text",)
    assert kwargs["transcript_shape"] == {"type": "str", "length": 3, "blank": True}
    assert kwargs["transcript_string_length"] == 3
    assert kwargs["transcript_blank"] is True


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_applies_transcript_normalization():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._effective_policy = {
        "tool_policy": {
            "transcript_normalization_enabled": True,
            "transcript_normalization_lexicon": [
                {
                    "canonical_term": "石犀",
                    "aliases": ["石溪"],
                    "scope": "global",
                    "replace_on_final_only": True,
                }
            ],
        }
    }

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "这是石溪平台的最终识别文本",
        }
    )

    handler._send_transcript.assert_awaited_once_with(
        "这是石犀平台的最终识别文本",
        is_final=True,
    )
    persisted_kwargs = handler._persist_message.await_args.kwargs
    assert persisted_kwargs["content"] == "这是石犀平台的最终识别文本"
    assert (
        persisted_kwargs["analysis_data"]["transcript_metadata"]["raw_text"]
        == "这是石溪平台的最终识别文本"
    )
    handler._prepare_grounding_context.assert_awaited_once_with(
        "这是石犀平台的最终识别文本"
    )


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_does_not_schedule_followup_when_response_active():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=3,
        stream_id="stream-active-response",
    )

    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()

    async def _fake_prepare(_transcript: str) -> None:
        handler._pending_grounding_context = "prefetched grounding"

    handler._prepare_grounding_context = AsyncMock(side_effect=_fake_prepare)
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    await handler._handle_upstream_event(
        {
            "type": "input_audio_buffer.transcription.completed",
            "transcript": "介绍一下我们的产品",
        }
    )

    assert handler._pending_tool_followup_response is False
    assert handler._grounding_preparation_in_progress is False
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_waits_for_grounding_then_creates_response(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._grounding_preparation_in_progress = True
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    sleep_calls = 0

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            handler._grounding_preparation_in_progress = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback()

    handler._create_response_from_pending_commit.assert_awaited_once()
    assert sleep_calls >= 2


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_waits_for_transcription_before_creating_response(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._awaiting_transcription_after_commit = True
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    sleep_calls = 0

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            handler._awaiting_transcription_after_commit = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback()

    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_recover_upstream_after_disconnect_uses_shared_jitter_backoff(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler._upstream_auto_recover_enabled = True
    handler._upstream_auto_recover_max_retries = 1
    handler._upstream_auto_recover_base_delay_seconds = 0.4
    handler._upstream_auto_recover_max_delay_seconds = 5.0

    helper_calls = []

    def _fake_backoff(**kwargs):
        helper_calls.append(kwargs)
        return 0.05

    sleep_mock = AsyncMock()
    monkeypatch.setattr(
        stepfun_module,
        "compute_jitter_backoff_seconds",
        _fake_backoff,
    )
    monkeypatch.setattr(stepfun_module.asyncio, "sleep", sleep_mock)

    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    recovered = await handler._recover_upstream_after_disconnect(
        close_code=1006,
        close_reason="socket closed",
        ws_lifetime_ms=2000.0,
    )

    assert recovered is True
    assert helper_calls == [
        {
            "attempt": 1,
            "base_delay_seconds": 0.4,
            "max_delay_seconds": 5.0,
        }
    ]
    sleep_mock.assert_awaited_once_with(0.05)


@pytest.mark.asyncio
async def test_recover_upstream_after_disconnect_clears_stale_turn_runtime_state(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler._upstream_auto_recover_enabled = True
    handler._upstream_auto_recover_max_retries = 1
    handler._active_response = RealtimeResponseState(
        request_id=5,
        stream_id="stream-recover-reset",
    )
    handler._function_call_states = {
        "call-recover-reset": FunctionCallState(
            call_id="call-recover-reset",
            name="search_internal_knowledge",
            delta_arguments='{"query":"报价"}',
        )
    }
    handler._executed_call_ids = {"call-recover-reset"}
    handler._pending_grounding_context = "stale grounding"
    handler._pending_blocked_response_text = "stale blocked"
    handler._latest_input_transcript_delta = "stale delta"
    handler._pending_tool_followup_response = True
    handler._awaiting_transcription_after_commit = True
    handler._allow_late_transcription_response = True
    handler._has_uncommitted_audio = True

    sleep_mock = AsyncMock()
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    monkeypatch.setattr(
        stepfun_module,
        "compute_jitter_backoff_seconds",
        lambda **_kwargs: 0.0,
    )
    monkeypatch.setattr(stepfun_module.asyncio, "sleep", sleep_mock)

    recovered = await handler._recover_upstream_after_disconnect(
        close_code=1006,
        close_reason="socket closed",
        ws_lifetime_ms=1800.0,
    )

    assert recovered is True
    assert handler._active_response is None
    assert handler._function_call_states == {}
    assert handler._executed_call_ids == set()
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""
    assert handler._latest_input_transcript_delta == ""
    assert handler._pending_tool_followup_response is False
    assert handler._awaiting_transcription_after_commit is False
    assert handler._allow_late_transcription_response is False
    assert handler._has_uncommitted_audio is False


@pytest.mark.asyncio
async def test_ensure_upstream_ready_refreshes_stale_connection_before_input(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.session_status = "in_progress"
    handler.upstream_ws = object()
    handler._upstream_connected_at = 10.0
    handler._upstream_last_activity_at = 10.0
    handler._upstream_proactive_refresh_idle_seconds = 45.0
    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-stale-before-input",
    )
    handler._pending_grounding_context = "stale grounding"
    handler._pending_blocked_response_text = "stale blocked"
    handler._has_uncommitted_audio = True

    monkeypatch.setattr(
        stepfun_module.asyncio,
        "get_running_loop",
        lambda: SimpleNamespace(time=lambda: 60.0),
    )
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    ready = await handler._ensure_upstream_ready_for_input("text")

    assert ready is True
    handler._close_upstream.assert_awaited_once()
    handler._connect_upstream.assert_awaited_once()
    handler._cancel_pending_response_after_commit.assert_awaited_once()
    handler._send_status.assert_awaited_once_with("listening")
    assert handler._active_response is None
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""
    assert handler._has_uncommitted_audio is False


@pytest.mark.asyncio
async def test_ensure_upstream_ready_keeps_recent_connection(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler.upstream_ws = object()
    handler._upstream_connected_at = 10.0
    handler._upstream_last_activity_at = 58.0
    handler._upstream_proactive_refresh_idle_seconds = 45.0

    monkeypatch.setattr(
        stepfun_module.asyncio,
        "get_running_loop",
        lambda: SimpleNamespace(time=lambda: 60.0),
    )
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    ready = await handler._ensure_upstream_ready_for_input("audio_chunk")

    assert ready is True
    handler._close_upstream.assert_not_awaited()
    handler._connect_upstream.assert_not_awaited()
    handler._cancel_pending_response_after_commit.assert_not_awaited()
    handler._send_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_interrupt_clears_turn_runtime_state_before_notifying_client():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.websocket = MagicMock()
    handler.upstream_ws = object()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._send_status = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-interrupt-reset",
    )
    handler._function_call_states = {
        "call-interrupt-reset": FunctionCallState(
            call_id="call-interrupt-reset",
            name="search_internal_knowledge",
            delta_arguments='{"query":"预算"}',
        )
    }
    handler._executed_call_ids = {"call-interrupt-reset"}
    handler._pending_grounding_context = "stale grounding"
    handler._pending_blocked_response_text = "stale blocked"
    handler._latest_input_transcript_delta = "stale delta"
    handler._pending_tool_followup_response = True
    handler._awaiting_transcription_after_commit = True
    handler._allow_late_transcription_response = True
    handler._has_uncommitted_audio = True

    await handler._handle_interrupt("user_speaking")

    assert handler._active_response is None
    assert handler._function_call_states == {}
    assert handler._executed_call_ids == set()
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""
    assert handler._latest_input_transcript_delta == ""
    assert handler._pending_tool_followup_response is False
    assert handler._awaiting_transcription_after_commit is False
    assert handler._allow_late_transcription_response is False
    assert handler._has_uncommitted_audio is False
    handler._cancel_pending_response_after_commit.assert_awaited_once()
    handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_awaited_once_with()
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_sync_lifecycle_transition_clears_turn_runtime_state_when_paused():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.ai_state = "speaking"
    handler.upstream_ws = object()
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._close_upstream = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=11,
        stream_id="stream-pause-reset",
    )
    handler._function_call_states = {
        "call-pause-reset": FunctionCallState(
            call_id="call-pause-reset",
            name="search_internal_knowledge",
            delta_arguments='{"query":"方案"}',
        )
    }
    handler._executed_call_ids = {"call-pause-reset"}
    handler._pending_grounding_context = "stale grounding"
    handler._pending_blocked_response_text = "stale blocked"
    handler._latest_input_transcript_delta = "stale delta"
    handler._pending_tool_followup_response = True
    handler._awaiting_transcription_after_commit = True
    handler._allow_late_transcription_response = True
    handler._has_uncommitted_audio = True

    transition = SimpleNamespace(
        action="pause",
        to_status="paused",
        ai_state="idle",
        scenario_type="sales",
    )

    await handler.sync_lifecycle_transition(transition)

    assert handler.session_status == "paused"
    assert handler.ai_state == "idle"
    assert handler._active_response is None
    assert handler._function_call_states == {}
    assert handler._executed_call_ids == set()
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""
    assert handler._latest_input_transcript_delta == ""
    assert handler._pending_tool_followup_response is False
    assert handler._awaiting_transcription_after_commit is False
    assert handler._allow_late_transcription_response is False
    assert handler._has_uncommitted_audio is False
    handler._cancel_pending_response_after_commit.assert_awaited_once()
    handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    handler._close_upstream.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_paused_lifecycle_retries_failed_provider_close_without_upstream_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALTIME_PROVIDER_PORT_ENABLED", "true")
    provider = RecordingRealtimeProvider()
    handler = StepFunRealtimeHandler(provider_factory=lambda **_kwargs: provider)
    handler._realtime_provider = provider
    handler.upstream_ws = provider
    handler.running = True
    handler.session_status = "in_progress"
    close_attempts = 0

    async def close_with_first_failure() -> None:
        nonlocal close_attempts
        close_attempts += 1
        handler.upstream_ws = None
        if close_attempts == 1:
            raise RuntimeError("first provider close failed")

    handler._send_upstream = AsyncMock(return_value=True)  # type: ignore[method-assign]
    handler._close_upstream = AsyncMock(side_effect=close_with_first_failure)  # type: ignore[method-assign]
    handler._cancel_pending_response_after_commit = AsyncMock()  # type: ignore[method-assign]
    transition = SimpleNamespace(
        action="pause",
        to_status="paused",
        ai_state="idle",
        scenario_type="sales",
    )

    await handler.sync_lifecycle_transition(transition)
    assert handler._upstream_rollover_phase == "closing"
    assert handler.upstream_ws is None
    await handler.sync_lifecycle_transition(transition)

    assert close_attempts == 2
    assert handler._upstream_rollover_phase == "idle"
    assert handler.upstream_ws is None


@pytest.mark.asyncio
async def test_handle_upstream_transcription_completed_ignores_duplicate_transcript_within_window():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 2
    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)

    event = {
        "type": "input_audio_buffer.transcription.completed",
        "transcript": "重复转写",
    }
    await handler._handle_upstream_event(event)
    await handler._handle_upstream_event(event)

    handler._send_transcript.assert_awaited_once_with("重复转写", is_final=True)
    handler._persist_message.assert_awaited_once()
    handler._prepare_grounding_context.assert_awaited_once_with("重复转写")
    handler._create_response_from_pending_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_grounding_context_short_query_still_retrieves_knowledge():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        }
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 1,
            "results": [
                {
                    "snippet": "标准版报价可按年付费，支持按席位扩容。",
                }
            ],
        }
    )

    await handler._prepare_grounding_context("价")

    handler._tool_search_internal_knowledge.assert_awaited_once_with(
        {"query": "价", "top_k": 3}
    )
    assert "用户问题：价" in handler._pending_grounding_context
    assert "标准版报价可按年付费" in handler._pending_grounding_context
    assert "以命中片段为准" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_uses_pipeline_retrieve_for_prefetch():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        }
    }
    handler._tool_search_internal_knowledge = AsyncMock()
    pipeline = SimpleNamespace(
        retrieve=AsyncMock(
            return_value={
                "count": 1,
                "results": [{"snippet": "标准版报价可按年付费。"}],
            }
        ),
        evaluate_retrieval=handler._grounding_pipeline.evaluate_retrieval,
    )
    cast(Any, handler)._grounding_pipeline = pipeline

    await handler._prepare_grounding_context("标准版价格")

    pipeline.retrieve.assert_awaited_once_with("标准版价格", top_k=3)
    handler._tool_search_internal_knowledge.assert_not_awaited()
    assert "标准版报价可按年付费" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_maybe_start_kb_lock_warmup_delegates_to_grounding_pipeline():
    handler = StepFunRealtimeHandler()
    handler._kb_lock_warmup_enabled = True
    handler._effective_policy = {
        "knowledge_base_ids": [" kb-1 ", "", "kb-2"],
        "tool_policy": {"require_kb_grounding": True},
    }
    pipeline = SimpleNamespace(warmup=AsyncMock())
    cast(Any, handler)._grounding_pipeline = pipeline

    await handler._maybe_start_kb_lock_warmup()
    assert handler._kb_lock_warmup_task is not None
    await handler._kb_lock_warmup_task

    pipeline.warmup.assert_awaited_once_with(["kb-1", "kb-2"])


@pytest.mark.asyncio
async def test_prepare_grounding_context_empty_query_skips_retrieval():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        }
    }
    handler._tool_search_internal_knowledge = AsyncMock()

    await handler._prepare_grounding_context("   ")

    handler._tool_search_internal_knowledge.assert_not_awaited()
    assert handler._pending_grounding_context == ""


@pytest.mark.asyncio
async def test_prepare_grounding_context_skips_retrieval_for_phase4_local_provider(
    monkeypatch,
):
    monkeypatch.setenv("PHASE4_E2E_PROVIDER", "local")
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock()
    pipeline = SimpleNamespace(
        evaluate=AsyncMock(),
        retrieve=AsyncMock(),
        evaluate_retrieval=handler._grounding_pipeline.evaluate_retrieval,
    )
    cast(Any, handler)._grounding_pipeline = pipeline

    await handler._prepare_grounding_context("业务目标")

    pipeline.evaluate.assert_not_awaited()
    pipeline.retrieve.assert_not_awaited()
    handler._tool_search_internal_knowledge.assert_not_awaited()
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""


@pytest.mark.asyncio
async def test_prepare_grounding_context_forces_retrieval_when_kb_bound_and_internal_flag_disabled():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": False,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 1,
            "results": [
                {
                    "snippet": "实习专家产品名录包含标准版与企业版。",
                }
            ],
        }
    )

    await handler._prepare_grounding_context("请介绍实习专家产品名录")

    handler._tool_search_internal_knowledge.assert_awaited_once_with(
        {"query": "请介绍实习专家产品名录", "top_k": 3}
    )
    assert "实习专家产品名录" in handler._pending_grounding_context


@pytest.mark.asyncio
async def test_prepare_grounding_context_allows_generation_when_kb_lock_off_and_retrieval_empty():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
            "retrieval_top_k": 3,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 0,
            "results": [],
            "message": "未命中",
        }
    )

    await handler._prepare_grounding_context("我们的产品线有哪些")

    assert handler._pending_blocked_response_text == ""
    assert handler._pending_grounding_context == ""


@pytest.mark.asyncio
async def test_prepare_grounding_context_blocks_bound_kb_query_when_retrieval_empty_and_lock_on():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()
    cast(Any, handler)._grounding_pipeline = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(
                allow_generation=False,
                status="blocked_empty",
                user_message=(
                    "当前内部知识库没有足够依据回答这个问题，"
                    "请补充更具体的关键词、版本信息或业务场景。"
                ),
                result_count=0,
                retrieval_mode="",
                error_detail="",
                duration_ms=1.0,
                phase_breakdown={},
            )
        ),
    )

    await handler._prepare_grounding_context("我们的产品线有哪些")

    assert handler._pending_grounding_context == ""
    assert "没有足够依据" in handler._pending_blocked_response_text
    assert "更具体的关键词" in handler._pending_blocked_response_text


@pytest.mark.asyncio
async def test_prepare_grounding_context_blocks_bound_kb_query_when_kb_not_ready_and_lock_on():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()
    cast(Any, handler)._grounding_pipeline = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(
                allow_generation=False,
                status="blocked_not_ready",
                user_message="当前会话已开启知识库强制模式，但知识库文档尚未处理完成。请稍后重试。",
                result_count=0,
                retrieval_mode="",
                error_detail="",
                duration_ms=1.0,
                phase_breakdown={},
            )
        ),
    )

    await handler._prepare_grounding_context("请介绍实习专家产品名录")

    assert handler._pending_grounding_context == ""
    assert "知识库强制模式" in handler._pending_blocked_response_text


@pytest.mark.asyncio
async def test_prepare_grounding_context_sets_blocked_response_when_kb_lock_blocks():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()
    pipeline = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(
                allow_generation=False,
                status="blocked_empty",
                user_message="知识库未命中，请补充关键词",
                result_count=0,
                retrieval_mode="",
                error_detail="",
            )
        ),
    )
    cast(Any, handler)._grounding_pipeline = pipeline

    await handler._prepare_grounding_context("介绍产品价格")

    assert handler._pending_blocked_response_text == "知识库未命中，请补充关键词"
    assert handler._pending_grounding_context == ""
    assert handler._record_kb_lock_decision.await_count == 1
    record_args = handler._record_kb_lock_decision.await_args
    assert record_args is not None
    decision_kwargs = record_args.kwargs
    assert decision_kwargs["status"] == "blocked_empty"
    assert decision_kwargs["blocked"] is True


@pytest.mark.asyncio
async def test_prepare_grounding_context_delegates_kb_lock_to_grounding_pipeline():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "enable_internal_retrieval": True,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()
    pipeline = SimpleNamespace(
        evaluate=AsyncMock(
            return_value=SimpleNamespace(
                allow_generation=True,
                status="pass",
                grounding_context="管线返回的 grounding",
                user_message="",
                result_count=1,
                retrieval_mode="hybrid",
                error_detail="",
                decision_id="decision-from-pipeline",
                duration_ms=12.3,
                phase_breakdown={"phase_total_ms": 12.3},
            )
        )
    )
    cast(Any, handler)._grounding_pipeline = pipeline

    await handler._prepare_grounding_context("介绍产品价格")

    pipeline.evaluate.assert_awaited_once()
    assert pipeline.evaluate.await_args.kwargs["query"] == "介绍产品价格"
    context = pipeline.evaluate.await_args.kwargs["context"]
    assert context.effective_policy is handler._effective_policy
    assert context.record_metric == handler._record_knowledge_runtime_metric
    assert handler._pending_grounding_context == "管线返回的 grounding"
    record_args = handler._record_kb_lock_decision.await_args
    assert record_args is not None
    decision_kwargs = record_args.kwargs
    assert decision_kwargs["status"] == "pass"
    assert decision_kwargs["blocked"] is False


@pytest.mark.asyncio
async def test_prepare_grounding_context_timeout_blocks_even_in_coach_mode(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
            "retrieval_top_k": 3,
        },
    }
    handler._record_kb_lock_decision = AsyncMock()

    async def _raise_timeout(awaitable, *_args, **_kwargs):
        awaitable.close()
        raise stepfun_module.asyncio.TimeoutError

    monkeypatch.setattr(stepfun_module.asyncio, "wait_for", _raise_timeout)

    await handler._prepare_grounding_context("我这轮话术应该怎么讲更清楚")

    assert handler._pending_grounding_context == ""
    assert "知识检索超时" in handler._pending_blocked_response_text
    decision_kwargs = handler._record_kb_lock_decision.await_args.kwargs
    assert decision_kwargs["status"] == "blocked_search_timeout"
    assert decision_kwargs["blocked"] is True


@pytest.mark.asyncio
async def test_prepare_grounding_context_blocks_bound_kb_query_when_non_strict_retrieval_times_out(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": False,
        },
    }

    async def _raise_timeout(awaitable, *_args, **_kwargs):
        awaitable.close()
        raise stepfun_module.asyncio.TimeoutError

    monkeypatch.setattr(stepfun_module.asyncio, "wait_for", _raise_timeout)

    await handler._prepare_grounding_context("帮我介绍一下石溪科技。")

    assert handler._pending_grounding_context == ""
    assert "知识检索超时" in handler._pending_blocked_response_text
    assert "这个问题" in handler._pending_blocked_response_text


@pytest.mark.asyncio
async def test_prepare_grounding_context_blocks_bound_kb_query_when_non_strict_retrieval_payload_is_invalid():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": False,
        },
    }
    handler._tool_search_internal_knowledge = AsyncMock(return_value=None)

    await handler._prepare_grounding_context("帮我介绍一下石溪科技。")

    assert handler._pending_grounding_context == ""
    assert "检索结果不可用" in handler._pending_blocked_response_text
    assert "这个问题" in handler._pending_blocked_response_text


def test_enforce_tool_policy_guardrails_auto_enables_kb_lock_for_legacy_snapshot(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["require_kb_grounding"] is True
    assert tool_policy["retrieval_priority"] == "kb_only"
    assert tool_policy["enable_web_search"] is False
    assert (
        handler._effective_policy["source"]["kb_lock_default"]
        == "auto_enabled_when_kb_bound"
    )


def test_enforce_tool_policy_guardrails_backfills_legacy_false_kb_lock(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-legacy-false-1"],
        "turn_detection": "server_vad",
        "tool_policy": {
            "require_kb_grounding": False,
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "persona_policy": {"tool_policy": {}},
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["require_kb_grounding"] is True
    assert handler._effective_policy["turn_detection"] is None
    assert (
        handler._effective_policy["source"]["kb_lock_legacy_snapshot_backfill"]
        == "require_kb_grounding_false_to_true"
    )
    assert (
        handler._effective_policy["source"]["turn_detection_enforcement"]
        == "manual_commit_required_by_kb_lock"
    )


def test_enforce_tool_policy_guardrails_respects_explicit_persona_disable(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-explicit-disable-1"],
        "tool_policy": {
            "require_kb_grounding": False,
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "persona_policy": {
            "tool_policy": {"require_kb_grounding": False},
        },
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    assert handler._effective_policy["tool_policy"]["require_kb_grounding"] is False
    assert "kb_lock_legacy_snapshot_backfill" not in handler._effective_policy["source"]


def test_enforce_tool_policy_guardrails_keeps_kb_lock_off_when_snapshot_kb_only(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-explicit-disable-1"],
        "tool_policy": {
            "require_kb_grounding": False,
            "retrieval_priority": "kb_only",
            "network_access_mode": "off",
            "enable_internal_retrieval": True,
            "enable_web_search": False,
        },
        "persona_policy": {
            "tool_policy": {"require_kb_grounding": False},
        },
        "source": {},
        "instructions": "角色设定",
    }
    monkeypatch.setenv("PERSONA_AUTO_REQUIRE_KB_GROUNDING_WHEN_BOUND", "true")

    changed = handler._enforce_tool_policy_guardrails()

    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["require_kb_grounding"] is False
    assert tool_policy["retrieval_priority"] == "kb_first"
    assert changed is True
    assert (
        handler._effective_policy["source"]["kb_lock_legacy_snapshot_backfill"]
        == "kb_only_downgraded_to_kb_first_when_lock_disabled"
    )


@pytest.mark.asyncio
async def test_create_response_uses_local_blocked_message_without_upstream_call():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._pending_blocked_response_text = "当前会话必须先命中知识库，暂不生成回答。"
    handler._stepfun_playback_rate = 1.25
    handler.turn_count = 0

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler.turn_count == 1
    handler._send_upstream.assert_not_awaited()
    handler._persist_message.assert_awaited_once_with(
        turn_number=1,
        role="assistant",
        content="当前会话必须先命中知识库，暂不生成回答。",
    )
    assert handler.manager.send_json.await_count == 1
    payload = handler.manager.send_json.await_args_list[0].args[1]
    assert payload["type"] == "tts_audio"
    assert payload["data"]["text"] == "当前会话必须先命中知识库，暂不生成回答。"
    assert payload["data"]["playback_rate"] == 1.25


@pytest.mark.asyncio
async def test_create_and_flush_response_updates_turn_coordinator_speaking_state():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._persist_message = AsyncMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler._turn_coordinator.is_speaking() is True

    flushed = await handler._flush_active_response({"response": {"output": []}})

    assert flushed is True
    assert handler._turn_coordinator.is_speaking() is False
    handler._send_status.assert_has_awaits([call("thinking"), call("listening")])


@pytest.mark.asyncio
async def test_handle_upstream_speech_started_notifies_turn_coordinator():
    handler = StepFunRealtimeHandler()
    handler._turn_coordinator.start_turn("turn-speech")

    await handler._handle_upstream_event({"type": "input_audio_buffer.speech_started"})

    current_turn = handler._turn_coordinator.get_current_turn()
    assert current_turn is not None
    assert current_turn.user_audio_active is True


@pytest.mark.asyncio
async def test_handle_upstream_speech_stopped_notifies_turn_coordinator():
    handler = StepFunRealtimeHandler()
    handler._turn_coordinator.start_turn("turn-speech")
    handler._turn_coordinator.on_user_audio_start()

    await handler._handle_upstream_event({"type": "input_audio_buffer.speech_stopped"})

    current_turn = handler._turn_coordinator.get_current_turn()
    assert current_turn is not None
    assert current_turn.user_audio_active is False


@pytest.mark.asyncio
async def test_create_response_resolves_interruption_without_payload_shape_change():
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()
    handler._turn_coordinator.start_turn("turn-overlap")
    handler._turn_coordinator.on_user_audio_start()
    handler._turn_coordinator.on_model_response_start()

    created = await handler._create_response(count_turn=True)

    assert created is True
    handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
            call({"type": "response.create", "response": {"modalities": ["audio", "text"]}}),
        ]
    )
    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_forward_audio_delta_chunk_includes_server_playback_rate():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=3,
        stream_id="stream-rate",
    )
    handler._stepfun_output_audio_format = "pcm16"
    handler._stepfun_output_sample_rate = 24000
    handler._stepfun_playback_rate = 1.25

    await handler._forward_audio_delta_chunk("AAECAw==")

    payload = handler.manager.send_json.await_args.args[1]
    assert payload["type"] == "tts_chunk"
    assert payload["data"]["playback_rate"] == 1.25


@pytest.mark.asyncio
async def test_forward_audio_delta_chunk_appends_output_audio_without_payload_change():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=3,
        stream_id="stream-output-flow",
    )
    handler._stepfun_output_audio_format = "pcm16"
    handler._stepfun_output_sample_rate = 24000
    handler._stepfun_playback_rate = 1.25

    await handler._forward_audio_delta_chunk("AAECAw==")

    payload = handler.manager.send_json.await_args.args[1]
    assert payload["type"] == "tts_chunk"
    assert payload["stream_id"] == "stream-output-flow"
    assert payload["request_id"] == 3
    assert payload["data"] == {
        "chunk_index": 0,
        "audio": "AAECAw==",
        "duration_ms": 0,
        "is_final": False,
        "audio_format": "pcm16",
        "sample_rate": 24000,
        "playback_rate": 1.25,
    }
    assert handler._audio_flow.get_output_buffer() == ["AAECAw=="]


@pytest.mark.asyncio
async def test_flush_active_response_persists_assistant_message_and_sends_final_chunk():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 3
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()

    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-xyz",
        chunk_index=2,
        total_duration_ms=1200,
    )
    handler._persist_message = AsyncMock()
    handler._send_status = AsyncMock()

    await handler._flush_active_response(
        {
            "response": {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "这是 AI 回复"}],
                    }
                ]
            }
        }
    )

    handler._persist_message.assert_awaited_once_with(
        turn_number=3,
        role="assistant",
        content="这是 AI 回复",
    )
    handler._send_status.assert_awaited_once_with("listening")
    assert handler.manager.send_json.await_count == 1

    message = handler.manager.send_json.await_args_list[0].args[1]
    assert message["type"] == "tts_chunk"
    assert message["stream_id"] == "stream-xyz"
    assert message["request_id"] == 7
    assert message["data"]["is_final"] is True
    assert message["data"]["text"] == "这是 AI 回复"


@pytest.mark.asyncio
async def test_flush_active_response_drains_output_audio_and_preserves_final_chunk_shape():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 3
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=7,
        stream_id="stream-xyz",
        chunk_index=2,
        total_duration_ms=1200,
    )
    handler._audio_flow.append_output_audio("chunk-1")
    handler._audio_flow.append_output_audio("chunk-2")
    handler._persist_message = AsyncMock()
    handler._send_status = AsyncMock()

    await handler._flush_active_response(
        {
            "response": {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "这是 AI 回复"}],
                    }
                ]
            }
        }
    )

    assert handler._audio_flow.get_output_buffer() == []
    message = handler.manager.send_json.await_args_list[0].args[1]
    assert message["type"] == "tts_chunk"
    assert message["stream_id"] == "stream-xyz"
    assert message["request_id"] == 7
    assert message["data"] == {
        "chunk_index": 2,
        "audio": "",
        "duration_ms": 0,
        "is_final": True,
        "text": "这是 AI 回复",
        "total_duration_ms": 1200,
        "audio_format": "pcm16",
        "sample_rate": 24000,
        "playback_rate": 1.0,
    }


def test_extract_text_payload_prefers_text_and_supports_legacy_content():
    assert (
        StepFunRealtimeHandler._extract_text_payload(
            {"text": "新字段优先", "content": "旧字段"}
        )
        == "新字段优先"
    )
    assert (
        StepFunRealtimeHandler._extract_text_payload({"content": "兼容旧字段"})
        == "兼容旧字段"
    )
    assert StepFunRealtimeHandler._extract_text_payload({}) == ""


@pytest.mark.asyncio
async def test_commit_and_respond_ignores_duplicate_without_new_audio():
    handler = StepFunRealtimeHandler()
    handler._send_upstream = AsyncMock()
    handler._schedule_response_after_commit = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    handler._has_uncommitted_audio = False
    await handler._commit_and_respond()
    handler._send_upstream.assert_not_awaited()
    handler._schedule_response_after_commit.assert_not_awaited()
    handler._create_response_from_pending_commit.assert_not_awaited()

    handler._has_uncommitted_audio = True
    await handler._commit_and_respond()
    handler._send_upstream.assert_awaited_once_with(
        {"type": "input_audio_buffer.commit"}
    )
    handler._schedule_response_after_commit.assert_awaited_once()
    handler._create_response_from_pending_commit.assert_not_awaited()
    assert handler._has_uncommitted_audio is False

    await handler._commit_and_respond()
    assert handler._send_upstream.await_count == 1
    assert handler._schedule_response_after_commit.await_count == 1
    handler._create_response_from_pending_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_function_call_defers_followup_while_response_active():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=1, stream_id="stream-active"
    )
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "query": "产品",
            "count": 1,
            "results": [{"snippet": "石犀平台能力"}],
        }
    )
    handler._send_upstream = AsyncMock()
    handler._create_response = AsyncMock()

    executed = await handler._execute_function_call(
        call_id="call-1",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"产品"}',
        trigger_followup_response=True,
    )

    assert executed is True
    assert handler._pending_tool_followup_response is True
    handler._create_response.assert_not_awaited()
    handler._send_upstream.assert_awaited_once()
    payload = handler._send_upstream.await_args.args[0]
    assert payload["item"]["type"] == "function_call_output"
    assert payload["item"]["call_id"] == "call-1"


@pytest.mark.asyncio
async def test_handler_routes_tool_call_through_module_decide():
    class RoutingToolExecution(StepFunToolExecutionModule):
        def __init__(self) -> None:
            super().__init__()
            self.routing_calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

        def decide_tool_routing(self, tool_call, *, turn_context):  # type: ignore[no-untyped-def]
            self.routing_calls.append((tool_call, turn_context))
            return ToolRoutingDecision(
                status=ToolRoutingStatus.SKIP_DUPLICATE,
                stable_key="duplicate-key",
                should_execute=False,
            )

    handler = StepFunRealtimeHandler()
    tool_execution = RoutingToolExecution()
    handler._tool_execution = tool_execution
    handler.session_id = "session-routing"
    handler.turn_count = 3
    handler._send_upstream = AsyncMock()

    executed = await handler._execute_function_call(
        call_id="call-routed",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"产品"}',
        trigger_followup_response=True,
    )

    assert executed is False
    assert tool_execution.routing_calls == [
        (
            {"id": "call-routed", "name": "search_internal_knowledge", "arguments": {"query": "产品"}},
            {"session_id": "session-routing", "turn_id": 3, "call_id": "call-routed"},
        )
    ]
    handler._send_upstream.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_function_call_skips_legacy_executed_call_id_before_module_routing():
    handler = StepFunRealtimeHandler()
    handler._executed_call_ids = {"call-duplicate"}
    handler._tool_execution.decide_tool_routing = MagicMock(
        wraps=handler._tool_execution.decide_tool_routing
    )
    handler._tool_search_internal_knowledge = AsyncMock()
    handler._send_upstream = AsyncMock()

    executed = await handler._execute_function_call(
        call_id="call-duplicate",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"产品"}',
        trigger_followup_response=True,
    )

    assert executed is False
    handler._tool_execution.decide_tool_routing.assert_not_called()
    handler._tool_search_internal_knowledge.assert_not_awaited()
    handler._send_upstream.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_uses_module_cache_for_repeated_searches():
    class CacheToolExecution(StepFunToolExecutionModule):
        def __init__(self) -> None:
            super().__init__()
            self.get_calls: list[str] = []
            self.cache_calls: list[tuple[str, dict[str, Any], float]] = []
            self.execute_count = 0

        def get_cached_result(self, cache_key: str) -> dict[str, Any] | None:
            self.get_calls.append(cache_key)
            return super().get_cached_result(cache_key)

        def cache_result(self, cache_key: str, result: dict[str, Any], *, ttl_seconds: float) -> None:
            self.cache_calls.append((cache_key, result, ttl_seconds))
            super().cache_result(cache_key, result, ttl_seconds=ttl_seconds)

        async def execute_tool(self, tool_call, *, context):  # type: ignore[no-untyped-def]
            self.execute_count += 1
            return {"query": tool_call["arguments"]["query"], "count": 1, "results": [{"snippet": "石犀"}]}

    handler = StepFunRealtimeHandler()
    handler.session_id = "session-cache"
    handler._tool_execution = CacheToolExecution()
    handler._internal_retrieval_cache_ttl_seconds = 5.0

    first = await handler._tool_search_internal_knowledge({"query": "产品", "top_k": 3})
    second = await handler._tool_search_internal_knowledge({"top_k": 3, "query": "产品"})

    assert first == second == {"query": "产品", "count": 1, "results": [{"snippet": "石犀"}]}
    tool_execution = cast(CacheToolExecution, handler._tool_execution)
    assert tool_execution.execute_count == 1
    assert len(tool_execution.get_calls) == 2
    assert len(tool_execution.cache_calls) == 1


@pytest.mark.asyncio
async def test_execute_function_call_blocks_followup_when_bound_kb_query_is_ungrounded():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "require_kb_grounding": False,
        },
    }
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._sales_stage_lock = asyncio.Lock()
    handler._feedback_context = None
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "query": "帮我介绍一下石溪科技。",
            "count": 0,
            "results": [],
            "message": "未命中",
            "_answerability": {
                "answerability": "insufficient",
                "source_status": "miss",
                "citations": [],
            },
        }
    )

    executed = await handler._execute_function_call(
        call_id="call-ungrounded-product",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"帮我介绍一下石溪科技。"}',
        trigger_followup_response=True,
    )

    assert executed is True
    persist_args = handler._persist_message.await_args
    assert persist_args is not None
    assert "没有足够依据" in persist_args.kwargs["content"]
    assert handler._pending_blocked_response_text == ""
    assert handler._pending_grounding_context == ""
    assert handler._send_upstream.await_count == 1
    send_upstream_args = handler._send_upstream.await_args
    assert send_upstream_args is not None
    function_output = send_upstream_args.args[0]
    assert function_output["item"]["type"] == "function_call_output"
    handler.manager.send_json.assert_awaited_once()
    manager_send_args = handler.manager.send_json.await_args
    assert manager_send_args is not None
    blocked_payload = manager_send_args.args[1]
    assert blocked_payload["type"] == "tts_audio"
    assert "没有足够依据" in blocked_payload["data"]["text"]


@pytest.mark.asyncio
async def test_accumulate_function_call_arguments_prefers_done_payload_without_duplication():
    handler = StepFunRealtimeHandler()
    handler._execute_function_call = AsyncMock(return_value=True)
    handler._active_response = RealtimeResponseState(
        request_id=1,
        response_id="response-1",
        stream_id="stream-1",
    )

    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-dup",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀',
            "request_id": 1,
            "response_id": "response-1",
            "stream_id": "stream-1",
        }
    )
    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-dup",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀产品"}',
        },
        done=True,
    )

    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-dup",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"石犀产品"}',
        trigger_followup_response=True,
    )


@pytest.mark.asyncio
async def test_accumulate_function_call_arguments_falls_back_to_delta_when_done_invalid():
    handler = StepFunRealtimeHandler()
    handler._execute_function_call = AsyncMock(return_value=True)
    handler._active_response = RealtimeResponseState(
        request_id=1,
        response_id="response-1",
        stream_id="stream-1",
    )

    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-fallback",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"石犀产品"}',
            "request_id": 1,
            "response_id": "response-1",
            "stream_id": "stream-1",
        }
    )
    await handler._accumulate_function_call_arguments(
        {
            "call_id": "call-fallback",
            "name": "search_internal_knowledge",
            "arguments": '{"query":',
        },
        done=True,
    )

    handler._execute_function_call.assert_awaited_once_with(
        call_id="call-fallback",
        function_name="search_internal_knowledge",
        raw_arguments='{"query":"石犀产品"}',
        trigger_followup_response=True,
    )


@pytest.mark.asyncio
async def test_response_done_triggers_pending_tool_followup_response():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=12,
        stream_id="stream-followup",
    )
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock(return_value=True)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=False)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_awaited_once()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_does_not_duplicate_followup_when_done_handler_already_triggered():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=13,
        stream_id="stream-done-handler",
    )
    handler._pending_tool_followup_response = True
    handler._flush_active_response = AsyncMock(return_value=True)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=True)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_awaited_once()
    handler._handle_function_calls_from_response_done.assert_awaited_once()
    handler._create_response.assert_not_awaited()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_clears_stale_followup_without_creating_when_no_active_response():
    handler = StepFunRealtimeHandler()
    handler._pending_tool_followup_response = True
    handler._send_status = AsyncMock()
    handler._flush_active_response = AsyncMock(return_value=False)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=False)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"output": []}}
    )

    handler._flush_active_response.assert_not_awaited()
    handler._send_status.assert_awaited_once_with("listening")
    handler._handle_function_calls_from_response_done.assert_not_awaited()
    handler._create_response.assert_not_awaited()
    assert handler._pending_tool_followup_response is False


@pytest.mark.asyncio
async def test_response_done_with_id_is_rejected_when_no_active_response():
    handler = StepFunRealtimeHandler()
    handler._flush_active_response = AsyncMock(return_value=False)
    handler._handle_function_calls_from_response_done = AsyncMock(return_value=True)
    handler._create_response = AsyncMock()

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"id": "resp-stale", "output": []}}
    )

    handler._flush_active_response.assert_not_awaited()
    handler._handle_function_calls_from_response_done.assert_not_awaited()
    handler._create_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_active_response_ignores_mismatched_done_response_id():
    handler = StepFunRealtimeHandler()
    handler._active_response = RealtimeResponseState(
        request_id=9,
        stream_id="stream-current",
        response_id="resp-current",
    )
    handler._persist_message = AsyncMock()
    handler._send_status = AsyncMock()

    flushed = await handler._flush_active_response(
        {"response": {"id": "resp-stale", "output": []}}
    )

    assert flushed is False
    assert handler._active_response is not None
    assert handler._active_response.response_id == "resp-current"
    handler._persist_message.assert_not_awaited()
    handler._send_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_skips_stale_generation(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._pending_response_generation = 4
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)

    async def _fake_sleep(_seconds: float) -> None:
        return None

    async def _stop_after_first_ping(_upstream_ws: object) -> None:
        handler.running = False
        await handler._stepfun_transport.check_health(
            _upstream_ws,
            timeout_seconds=handler._upstream_keepalive_pong_timeout_seconds,
        )

    handler._send_upstream_keepalive_ping = _stop_after_first_ping  # type: ignore[method-assign]

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._pending_response_timeout_fallback(expected_generation=3)

    handler._create_response_from_pending_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_keepalive_loop_sends_ping_when_upstream_connection_is_idle(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.running = True
    handler._upstream_keepalive_interval_seconds = 5.0
    handler._upstream_keepalive_pong_timeout_seconds = 1.0
    handler._upstream_last_activity_at = 0.0

    pong_waiter = asyncio.Future()
    pong_waiter.set_result(0.02)
    upstream_ws = SimpleNamespace(ping=AsyncMock(return_value=pong_waiter))
    handler.upstream_ws = upstream_ws

    sleep_calls = 0

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 1:
            handler.running = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._run_upstream_keepalive_loop(upstream_ws)

    upstream_ws.ping.assert_awaited_once()
    assert handler._upstream_last_activity_at > 0


@pytest.mark.asyncio
async def test_upstream_keepalive_loop_skips_ping_when_recent_activity_exists(
    monkeypatch,
):
    transport = SimpleNamespace(check_health=AsyncMock())
    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler.running = True
    handler._upstream_keepalive_interval_seconds = 5.0
    handler._upstream_last_activity_at = asyncio.get_running_loop().time()

    upstream_ws = object()
    handler.upstream_ws = upstream_ws

    async def _fake_sleep(_seconds: float) -> None:
        handler.running = False

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._run_upstream_keepalive_loop(upstream_ws)

    transport.check_health.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_keepalive_loop_delegates_health_check_and_stops_when_unhealthy(
    monkeypatch,
):
    upstream_ws = object()
    transport = SimpleNamespace(
        check_health=AsyncMock(
            return_value=StepFunHealthResult(
                status=StepFunHealthStatus.UNHEALTHY,
                error_type="TimeoutError",
            )
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler.running = True
    handler.session_id = "session-health"
    handler.upstream_ws = upstream_ws
    handler._upstream_keepalive_interval_seconds = 5.0
    handler._upstream_keepalive_pong_timeout_seconds = 1.25
    handler._upstream_connected_at = 0.0
    handler._upstream_last_activity_at = 0.0

    async def _fake_sleep(_seconds: float) -> None:
        return None

    async def _stop_after_first_ping(_upstream_ws: object) -> None:
        handler.running = False
        await handler._stepfun_transport.check_health(
            _upstream_ws,
            timeout_seconds=handler._upstream_keepalive_pong_timeout_seconds,
        )

    handler._send_upstream_keepalive_ping = _stop_after_first_ping  # type: ignore[method-assign]

    monkeypatch.setattr(stepfun_module.asyncio, "sleep", _fake_sleep)

    await handler._run_upstream_keepalive_loop(upstream_ws)

    transport.check_health.assert_awaited_once_with(
        upstream_ws,
        timeout_seconds=1.25,
    )
    assert handler._upstream_last_activity_at == 0.0


@pytest.mark.asyncio
async def test_send_upstream_keepalive_ping_delegates_to_transport_health_check():
    upstream_ws = object()
    transport = SimpleNamespace(
        check_health=AsyncMock(
            return_value=StepFunHealthResult(status=StepFunHealthStatus.HEALTHY)
        )
    )
    handler = StepFunRealtimeHandler(stepfun_transport=transport)
    handler._upstream_keepalive_pong_timeout_seconds = 1.25

    await handler._send_upstream_keepalive_ping(upstream_ws)

    transport.check_health.assert_awaited_once_with(
        upstream_ws,
        timeout_seconds=1.25,
    )
    assert handler._upstream_last_activity_at > 0


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_suppresses_blocked_copy_when_transcription_missing_under_kb_lock(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"require_kb_grounding": True},
    }
    handler._awaiting_transcription_after_commit = True
    handler._pending_response_after_commit = True
    handler._record_kb_lock_decision = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    monkeypatch.setattr(stepfun_module, "PENDING_RESPONSE_FALLBACK_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "TRANSCRIPTION_WAIT_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "GROUNDING_WAIT_GRACE_SECONDS", 0.0)

    await handler._pending_response_timeout_fallback()

    assert handler._pending_blocked_response_text == ""
    handler._record_kb_lock_decision.assert_awaited_once_with(
        status="transcription_timeout_suppressed",
        blocked=False,
    )
    handler._cancel_pending_response_after_commit.assert_awaited_once()
    handler._send_status.assert_awaited_once_with("listening")
    handler._create_response_from_pending_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_response_timeout_fallback_creates_response_without_transcript_when_kb_lock_off(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"require_kb_grounding": False},
    }
    handler._awaiting_transcription_after_commit = True
    handler._pending_response_after_commit = True
    handler._record_kb_lock_decision = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=True)
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._send_status = AsyncMock()

    monkeypatch.setattr(stepfun_module, "PENDING_RESPONSE_FALLBACK_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "TRANSCRIPTION_WAIT_GRACE_SECONDS", 0.0)
    monkeypatch.setattr(stepfun_module, "GROUNDING_WAIT_GRACE_SECONDS", 0.0)

    await handler._pending_response_timeout_fallback()

    handler._create_response_from_pending_commit.assert_awaited_once()
    handler._cancel_pending_response_after_commit.assert_not_awaited()
    handler._send_status.assert_not_awaited()
    handler._record_kb_lock_decision.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_final_user_transcript_creates_response_after_suppressed_timeout_when_transcript_arrives_late():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 0
    handler._allow_late_transcription_response = True
    handler._send_transcript = AsyncMock()
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="discovery")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock(return_value=False)
    handler._create_response = AsyncMock(return_value=True)

    await handler._handle_final_user_transcript("这是晚到的最终转写")

    handler._create_response_from_pending_commit.assert_awaited_once()
    handler._create_response.assert_awaited_once_with(count_turn=True)
    assert handler._allow_late_transcription_response is False


@pytest.mark.asyncio
async def test_handle_upstream_response_created_cancels_unexpected_response_when_kb_lock_required():
    handler = StepFunRealtimeHandler()
    handler.upstream_ws = object()
    handler._connection_epoch = 2
    handler._effective_policy = {
        "tool_policy": {"require_kb_grounding": True},
    }
    handler._send_upstream = AsyncMock()
    handler._close_upstream = AsyncMock()
    handler._connect_upstream = AsyncMock()

    await handler._handle_upstream_response_created(
        {"type": "response.created", "response": {"id": "resp-auto-1"}}
    )

    handler._send_upstream.assert_has_awaits(
        [
            call({"type": "response.cancel"}),
            call({"type": "input_audio_buffer.clear"}),
        ]
    )
    handler._close_upstream.assert_awaited_once_with()
    handler._connect_upstream.assert_awaited_once_with()
    assert handler._connection_epoch == 3


@pytest.mark.asyncio
async def test_persist_runtime_metrics_to_session_updates_snapshot_copy(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-test"
    handler._effective_policy = {
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 2,
                "hit_query_count": 1,
                "hit_rate": 0.5,
            }
        }
    }

    original_snapshot = {"knowledge_base_ids": ["kb-1"]}
    session_obj = SimpleNamespace(voice_policy_snapshot=original_snapshot)

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        async def commit(self):
            return None

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )

    await handler._persist_runtime_metrics_to_session()

    assert session_obj.voice_policy_snapshot is not original_snapshot
    runtime = session_obj.voice_policy_snapshot.get("runtime_metrics", {}).get(
        "knowledge_retrieval", {}
    )
    assert runtime.get("attempt_count") == 2
    assert runtime.get("hit_query_count") == 1
    assert runtime.get("hit_rate") == 0.5
    assert session_obj.voice_policy_snapshot.get("knowledge_base_ids") == ["kb-1"]


@pytest.mark.asyncio
async def test_persist_runtime_metrics_to_session_persists_roleplay_observability_snapshot(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-v1-persist"
    handler._effective_policy = {
        "roleplay_contract_hash": "sha256:frozen-contract",
        "roleplay_contract": {
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        },
        "session_state_card": {
            "schema_version": "session_state_card_v1",
            "version": 4,
            "sequence": 8,
            "current_phase_id": "solution_credibility",
            "customer_attitude": "谨慎，要求 PoC 指标",
            "quality_flags": ["knowledge_gap_degradation"],
        },
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 1,
                "hit_query_count": 0,
                "recent_attempts": [],
            },
            V1_ROLEPLAY_RUNTIME_METRICS_KEY: {
                "knowledge_timeout_count": 1,
                "quality_flags": ["knowledge_gap_degradation"],
            },
        },
    }
    original_snapshot = {
        "voice_mode": "stepfun_realtime",
        "roleplay_contract_hash": "sha256:frozen-contract",
    }
    session_obj = SimpleNamespace(voice_policy_snapshot=original_snapshot)

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        async def execute(self, _stmt):
            return DummyResult()

        async def commit(self):
            return None

    class DummyDbSessionContext:
        def __init__(self):
            self.db = DummyDb()

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )

    await handler._persist_runtime_metrics_to_session()

    snapshot_metrics = session_obj.voice_policy_snapshot["runtime_metrics"][
        V1_ROLEPLAY_RUNTIME_METRICS_KEY
    ]
    assert snapshot_metrics["roleplay_contract_hash"] == "sha256:frozen-contract"
    assert snapshot_metrics["state_card_version"] == 4
    assert snapshot_metrics["knowledge_timeout_count"] == 1
    assert snapshot_metrics["quality_flags"] == ["knowledge_gap_degradation"]
    assert session_obj.voice_policy_snapshot["session_state_card"]["version"] == 4


@pytest.mark.asyncio
async def test_record_knowledge_runtime_metric_passes_ledger_event_through_existing_persistence_path(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {}
    handler._persist_runtime_metrics_to_session = AsyncMock()

    apply_mock = MagicMock()
    monkeypatch.setattr(stepfun_module, "apply_knowledge_runtime_metric", apply_mock)

    ledger_event = {
        "attempted_at": "2026-03-28T12:00:00Z",
        "query": "企业版报价",
        "status": "hit",
        "result_count": 1,
        "retrieval_mode": "vector",
        "knowledge_base_ids": ["kb-1"],
        "result_summaries": [
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "score": 0.88,
                "snippet": "企业版报价支持按年付费。",
                "retrieval_mode": "vector",
            }
        ],
    }

    await handler._record_knowledge_runtime_metric(
        query="企业版报价",
        result_count=1,
        status="hit",
        knowledge_base_ids=["kb-1"],
        top_k=3,
        similarity_threshold=0.65,
        retrieval_mode="vector",
        ledger_event=ledger_event,
    )

    apply_mock.assert_called_once_with(
        effective_policy=handler._effective_policy,
        query="企业版报价",
        result_count=1,
        status="hit",
        knowledge_base_ids=["kb-1"],
        top_k=3,
        similarity_threshold=0.65,
        error_message=None,
        retrieval_mode="vector",
        ledger_event=ledger_event,
    )
    handler._persist_runtime_metrics_to_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_knowledge_runtime_metric_keeps_warning_only_failure_surface_after_in_memory_update(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {}
    handler._persist_runtime_metrics_to_session = AsyncMock(
        side_effect=RuntimeError("db down")
    )

    warning_mock = MagicMock()
    monkeypatch.setattr(stepfun_module.logger, "warning", warning_mock)

    await handler._record_knowledge_runtime_metric(
        query="竞品价格",
        result_count=0,
        status="search_failed",
        knowledge_base_ids=["kb-1"],
        error_message="[EMBEDDING_TIMEOUT]",
        retrieval_mode="vector",
        ledger_event={
            "attempted_at": "2026-03-28T12:00:00Z",
            "query": "竞品价格",
            "status": "search_failed",
            "result_count": 0,
            "retrieval_mode": "vector",
            "knowledge_base_ids": ["kb-1"],
            "error_summary": "[EMBEDDING_TIMEOUT]",
            "result_summaries": [],
        },
    )

    metrics = handler._effective_policy["runtime_metrics"]["knowledge_retrieval"]
    assert metrics["last_status"] == "search_failed"
    assert metrics["last_error"] == "[EMBEDDING_TIMEOUT]"
    assert len(metrics["recent_attempts"]) == 1
    assert metrics["recent_attempts"][0]["status"] == "search_failed"
    warning_mock.assert_called_once()
    assert "Failed to record knowledge runtime metric" in warning_mock.call_args.args[0]


@pytest.mark.asyncio
async def test_reconnect_restores_roleplay_runtime_state_from_existing_snapshot() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-v1-reconnect"
    handler._effective_policy = {
        "roleplay_contract_hash": "sha256:frozen-contract",
        "roleplay_contract": {
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        },
        "session_state_card": {
            "schema_version": "session_state_card_v1",
            "version": 1,
            "sequence": 1,
            "current_phase_id": "opening_intent",
            "customer_attitude": "谨慎但愿意继续听",
            "quality_flags": [],
        },
    }
    handler._send_reconnection_success = AsyncMock()

    snapshot = SessionStateSnapshot(
        session_id="session-v1-reconnect",
        scenario="sales",
        turn_count=2,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            V1_ROLEPLAY_RUNTIME_STATE_KEY: {
                "roleplay_contract_hash": "sha256:frozen-contract",
                "session_state_card": {
                    "schema_version": "session_state_card_v1",
                    "version": 3,
                    "sequence": 7,
                    "current_phase_id": "solution_credibility",
                    "customer_attitude": "谨慎，要求 PoC 指标",
                    "quality_flags": ["knowledge_gap_degradation"],
                },
            }
        },
        user_id="user-v1",
    )

    await handler._restore_session_state(snapshot)

    restored_card = handler._effective_policy["session_state_card"]
    assert restored_card["version"] == 3
    assert restored_card["current_phase_id"] == "solution_credibility"
    metrics = handler._effective_policy["runtime_metrics"][
        V1_ROLEPLAY_RUNTIME_METRICS_KEY
    ]
    assert metrics["roleplay_contract_hash"] == "sha256:frozen-contract"
    assert metrics["state_card_version"] == 3
    assert metrics["quality_flags"] == ["knowledge_gap_degradation"]


@pytest.mark.asyncio
async def test_stale_roleplay_state_card_update_after_reconnect_is_ignored() -> None:
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "roleplay_contract_hash": "sha256:frozen-contract",
        "roleplay_contract": {
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        },
        "session_state_card": {
            "schema_version": "session_state_card_v1",
            "version": 3,
            "sequence": 7,
            "current_phase_id": "solution_credibility",
            "customer_attitude": "谨慎，要求 PoC 指标",
            "quality_flags": ["knowledge_gap_degradation"],
        },
    }

    result = apply_roleplay_state_card_update_to_policy(
        handler._effective_policy,
        {
            "version": 2,
            "sequence": 6,
            "current_phase_id": "next_step_advancement",
            "customer_attitude": "错误覆盖为认可",
        },
    )

    assert result.status == "stale"
    assert handler._effective_policy["session_state_card"]["version"] == 3
    assert (
        handler._effective_policy["session_state_card"]["customer_attitude"]
        == "谨慎，要求 PoC 指标"
    )


@pytest.mark.asyncio
async def test_knowledge_timeout_quality_flag_persists_into_roleplay_runtime_observability():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "roleplay_contract_hash": "sha256:frozen-contract",
        "roleplay_contract": {
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        },
        "session_state_card": {
            "schema_version": "session_state_card_v1",
            "version": 1,
            "sequence": 0,
            "current_phase_id": "opening_intent",
            "customer_attitude": "谨慎但愿意继续听",
            "quality_flags": [],
        },
    }
    handler._persist_runtime_metrics_to_session = AsyncMock()

    await handler._record_knowledge_runtime_metric(
        query="石犀平台 PoC 指标",
        result_count=0,
        status="search_failed",
        knowledge_base_ids=["kb-product"],
        error_message="[KB_TIMEOUT]",
        retrieval_mode="vector",
    )

    metrics = handler._effective_policy["runtime_metrics"][
        V1_ROLEPLAY_RUNTIME_METRICS_KEY
    ]
    assert metrics["knowledge_timeout_count"] == 1
    assert metrics["quality_flags"] == ["knowledge_gap_degradation"]
    assert metrics["roleplay_contract_hash"] == "sha256:frozen-contract"
    handler._persist_runtime_metrics_to_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_blocking_roleplay_violation_marks_runtime_for_manual_review() -> None:
    handler = StepFunRealtimeHandler()
    handler.turn_count = 4
    handler._current_sales_stage_code = MagicMock(return_value="discovery")
    handler._roleplay_visible_keys = MagicMock(return_value=["customer_background"])
    handler._roleplay_disclosed_keys = MagicMock(return_value=[])
    handler._roleplay_contract = MagicMock(
        return_value={
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        }
    )
    handler._effective_policy = {
        "roleplay_contract_hash": "sha256:frozen-contract",
        "roleplay_contract": {
            "contract_version": "it_leader_roleplay_v1",
            "audit": {"contract_hash": "sha256:frozen-contract"},
        },
        "session_state_card": {
            "schema_version": "session_state_card_v1",
            "version": 1,
            "sequence": 0,
            "current_phase_id": "opening_intent",
            "customer_attitude": "谨慎但愿意继续听",
            "quality_flags": [],
        },
    }

    await handler._record_roleplay_compliance_decision(
        {
            "severity": "blocking",
            "violation_code": "ROLEPLAY_HIDDEN_INFORMATION_LEAK",
            "action": "cancel_stream",
        },
        response_id="resp-1",
        action_override="cancel_stream",
        count_violation=True,
    )

    metrics = handler._effective_policy["runtime_metrics"][
        V1_ROLEPLAY_RUNTIME_METRICS_KEY
    ]
    assert metrics["blocking_violation_count"] == 1
    assert metrics["violation_count"] == 1
    assert metrics["manual_review_required"] is True
    assert "blocking_violation_count:1" in metrics["quality_flags"]


def test_v1_disabled_runtime_state_does_not_include_roleplay_observability() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-legacy"
    handler._effective_policy = {
        "runtime_metrics": {
            "knowledge_retrieval": {
                "attempt_count": 1,
                "recent_attempts": [],
            }
        }
    }

    apply_roleplay_state_card_update_to_policy(
        handler._effective_policy,
        {
            "version": 2,
            "sequence": 2,
            "current_phase_id": "solution_credibility",
        },
    )
    snapshot = handler._create_state_snapshot()

    assert V1_ROLEPLAY_RUNTIME_METRICS_KEY not in handler._effective_policy[
        "runtime_metrics"
    ]
    runtime_state = snapshot.runtime_state or {}
    assert V1_ROLEPLAY_RUNTIME_STATE_KEY not in runtime_state


@pytest.mark.asyncio
async def test_load_effective_policy_prefers_frozen_session_snapshot_over_live_resolution(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-frozen"

    frozen_snapshot = {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "profile-frozen",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "output_sample_rate": 24000,
        "instructions": "frozen pressure instructions",
        "instruction_contract_hash": "hash-frozen",
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {"enable_internal_retrieval": True},
        "customer_pressure": {
            "source": "explicit",
            "pressure_direction": {"sales_focus": "proof"},
            "follow_up_behavior": {"require_evidence": True},
        },
    }
    session_obj = SimpleNamespace(
        session_id="session-frozen",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        voice_policy_snapshot=frozen_snapshot,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id="profile-frozen",
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, _stmt):
            return DummyResult()

    dummy_db = DummyDb()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return dummy_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyVoiceRuntimePolicyService:
        def __init__(self, _db):
            pass

        async def resolve_effective_policy(self, **_kwargs):
            raise AssertionError("live voice policy should not be re-resolved")

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(
        stepfun_module,
        "VoiceRuntimePolicyService",
        DummyVoiceRuntimePolicyService,
    )

    handler._refresh_sales_stage_runtime_config = AsyncMock()
    handler._enforce_tool_policy_guardrails = MagicMock(return_value=False)
    handler._ensure_knowledge_runtime_metrics = MagicMock()

    await handler._load_effective_policy()

    assert handler._effective_policy == frozen_snapshot
    assert handler._stepfun_instructions == "frozen pressure instructions"
    assert handler._instruction_contract_hash == "hash-frozen"
    handler._refresh_sales_stage_runtime_config.assert_awaited_once()
    handler._enforce_tool_policy_guardrails.assert_called_once_with()
    handler._ensure_knowledge_runtime_metrics.assert_called_once_with()
    dummy_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_effective_policy_merges_active_kb_dictionary_into_transcript_normalization(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-dictionary"

    frozen_snapshot = {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "profile-dict",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "output_sample_rate": 24000,
        "instructions": "dictionary merge instructions",
        "instruction_contract_hash": "hash-dictionary",
        "knowledge_base_ids": ["kb-dict-1"],
        "tool_policy": {
            "transcript_normalization_enabled": True,
            "transcript_normalization_lexicon": [],
        },
    }
    session_obj = SimpleNamespace(
        session_id="session-dictionary",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        voice_policy_snapshot=frozen_snapshot,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id="profile-dict",
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, _stmt):
            return DummyResult()

    dummy_db = DummyDb()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return dummy_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeKnowledgeService:
        def __init__(self, _db):
            pass

        async def active_dictionary_lexicon(self, kb_ids):
            assert kb_ids == ["kb-dict-1"]
            return [
                {
                    "canonical_term": "石犀科技",
                    "aliases": ["实习科技"],
                    "entity_type": "organization",
                    "confidence": 0.96,
                    "scope": "knowledge_base:kb-dict-1",
                }
            ]

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", FakeKnowledgeService)

    handler._refresh_sales_stage_runtime_config = AsyncMock()
    handler._enforce_tool_policy_guardrails = MagicMock(return_value=False)
    handler._ensure_knowledge_runtime_metrics = MagicMock()

    await handler._load_effective_policy()

    assert handler._effective_policy["tool_policy"]["transcript_normalization_enabled"] is True
    assert handler._effective_policy["tool_policy"]["transcript_normalization_lexicon"][0]["canonical_term"] == "石犀科技"
    assert handler._effective_policy["source"]["kb_dictionary_lexicon"] == "knowledge_base_active_dictionary"
    dummy_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_load_effective_policy_uses_injected_db_and_knowledge_factories_without_monkeypatch():
    frozen_snapshot = {
        "voice_mode": "stepfun_realtime",
        "runtime_profile_id": "profile-injected",
        "model_name": "step-audio-2",
        "voice_name": "qingchunshaonv",
        "temperature": 0.7,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "output_sample_rate": 24000,
        "instructions": "injected factory instructions",
        "instruction_contract_hash": "hash-injected",
        "knowledge_base_ids": ["kb-injected-1"],
        "tool_policy": {
            "transcript_normalization_enabled": True,
            "transcript_normalization_lexicon": [],
        },
    }
    session_obj = SimpleNamespace(
        session_id="session-injected",
        agent_id="agent-1",
        persona_id="persona-1",
        user_id="user-1",
        voice_policy_snapshot=frozen_snapshot,
        voice_mode="stepfun_realtime",
        voice_runtime_profile_id="profile-injected",
    )

    class DummyResult:
        def scalar_one_or_none(self):
            return session_obj

    class DummyDb:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, _stmt):
            return DummyResult()

    dummy_db = DummyDb()
    opened_contexts = []
    created_services = []

    class DummyDbSessionContext:
        async def __aenter__(self):
            return dummy_db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, db):
            self.db = db

        async def active_dictionary_lexicon(self, kb_ids):
            assert kb_ids == ["kb-injected-1"]
            return [
                {
                    "canonical_term": "注入知识库术语",
                    "aliases": ["注入知识"],
                    "entity_type": "term",
                    "confidence": 0.97,
                    "scope": "knowledge_base:kb-injected-1",
                }
            ]

    def db_session_factory():
        context = DummyDbSessionContext()
        opened_contexts.append(context)
        return context

    def knowledge_service_factory(db):
        assert db is dummy_db
        service = DummyKnowledgeService(db)
        created_services.append(service)
        return service

    handler = StepFunRealtimeHandler(
        db_session_factory=db_session_factory,
        knowledge_service_factory=knowledge_service_factory,
    )
    handler.session_id = "session-injected"
    handler._refresh_sales_stage_runtime_config = AsyncMock()
    handler._enforce_tool_policy_guardrails = MagicMock(return_value=False)
    handler._ensure_knowledge_runtime_metrics = MagicMock()

    await handler._load_effective_policy()

    assert len(opened_contexts) == 1
    assert len(created_services) == 1
    assert created_services[0].db is dummy_db
    assert handler._effective_policy["tool_policy"]["transcript_normalization_lexicon"][0]["canonical_term"] == "注入知识库术语"
    assert handler._effective_policy["source"]["kb_dictionary_lexicon"] == "knowledge_base_active_dictionary"
    dummy_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_includes_error_detail_on_failure(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 3,
            "retrieval_similarity_threshold": 0.65,
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            return Result.fail(
                "[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR] 402"
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {"query": "十七科技实习产品", "top_k": 3}
    )

    assert payload["count"] == 0
    assert payload["message"] == "知识检索失败"
    assert "[EMBEDDING_API_ERROR]" in payload["error"]

    kwargs = handler._record_knowledge_runtime_metric.await_args.kwargs
    assert kwargs["status"] == "search_failed"
    assert kwargs["knowledge_base_ids"] == ["kb-1"]
    assert "[EMBEDDING_API_ERROR]" in str(kwargs["error_message"])


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_marks_keyword_fallback_hits(monkeypatch):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 3,
            "retrieval_similarity_threshold": 0.65,
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "十七科技实习产品支持智能销售训练",
                        "score": 0.81,
                        "retrieval_mode": "keyword_fallback",
                    }
                ]
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {"query": "实习产品是什么", "top_k": 3}
    )

    assert payload["count"] == 1
    assert payload["retrieval_mode"] == "keyword_fallback"
    assert payload["results"][0]["retrieval_mode"] == "keyword_fallback"

    kwargs = handler._record_knowledge_runtime_metric.await_args.kwargs
    assert kwargs["status"] == "hit_keyword_fallback"
    assert kwargs["retrieval_mode"] == "keyword_fallback"


@pytest.mark.asyncio
async def test_tool_search_internal_knowledge_respects_hybrid_and_metadata_filter(
    monkeypatch,
):
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "retrieval_top_k": 4,
            "retrieval_similarity_threshold": 0.65,
            "retrieval_enable_hybrid": False,
            "retrieval_keyword_candidate_limit": 16,
            "retrieval_metadata_filter": {
                "product_line": "enterprise",
                "regions": ["cn", "sg"],
            },
        },
        "knowledge_base_ids": ["kb-1"],
    }
    handler._record_knowledge_runtime_metric = AsyncMock()

    captured: dict[str, object] = {}

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummyKnowledgeService:
        def __init__(self, _db):
            pass

        async def search_multiple(self, **kwargs):
            captured.update(kwargs)
            return Result.ok(
                [
                    {
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "content": "企业版支持私有化部署和统一权限管理。",
                        "score": 0.88,
                        "retrieval_mode": "vector",
                    }
                ]
            )

    monkeypatch.setattr(
        stepfun_module, "AsyncSessionLocal", lambda: DummyDbSessionContext()
    )
    monkeypatch.setattr(stepfun_module, "KnowledgeService", DummyKnowledgeService)

    payload = await handler._tool_search_internal_knowledge(
        {
            "query": "请详细介绍企业版功能和部署流程以及安全策略",
            "top_k": 4,
            "metadata_filter": {
                "region": "cn",
                "levels": [1, " ", 2],
                "empty": "   ",
            },
        }
    )

    assert payload["count"] == 1
    assert captured["enable_hybrid"] is False
    assert captured["keyword_candidate_limit"] == 16
    assert captured["metadata_filter"] == {
        "region": "cn",
        "levels": [1, 2],
    }


def test_merge_sales_stage_runtime_config_persona_override_agent():
    merged = StepFunRealtimeHandler._merge_sales_stage_runtime_config(
        {
            "sales_stage": {
                "enabled": False,
                "history_window": 6,
                "enforce_transitions": False,
            }
        },
        {
            "sales_stage": {
                "enabled": True,
                "history_window": 4,
            }
        },
    )

    assert merged["enabled"] is True
    assert merged["history_window"] == 4
    assert merged["enforce_transitions"] is False


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_suppresses_duplicate_stage_events():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-1"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()
    handler._sales_stage_capability.execute = AsyncMock(
        side_effect=[
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
        ]
    )

    first_stage = await handler._analyze_and_emit_sales_stage(
        user_text="你好，我们先认识一下",
        turn_number=1,
    )
    second_stage = await handler._analyze_and_emit_sales_stage(
        user_text="继续介绍背景",
        turn_number=2,
    )

    assert first_stage == "opening"
    assert second_stage == "opening"
    handler._send_stage_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_emits_on_stage_change():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-2"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()
    handler._sales_stage_capability.execute = AsyncMock(
        side_effect=[
            MagicMock(
                success=True,
                data={
                    "current_stage": "opening",
                    "stage_name": "开场破冰",
                    "key_actions": ["建立信任"],
                    "guidance": "保持自然开场",
                    "progress": 0.2,
                    "stage_changed": False,
                },
            ),
            MagicMock(
                success=True,
                data={
                    "current_stage": "discovery",
                    "stage_name": "需求挖掘",
                    "key_actions": ["深入痛点"],
                    "guidance": "多问开放式问题",
                    "progress": 0.4,
                    "stage_changed": True,
                    "previous_stage": "opening",
                },
            ),
        ]
    )

    await handler._analyze_and_emit_sales_stage(
        user_text="你好，我们先认识一下",
        turn_number=1,
    )
    latest_stage = await handler._analyze_and_emit_sales_stage(
        user_text="你们当前最大的业务痛点是什么？",
        turn_number=2,
    )

    assert latest_stage == "discovery"
    assert handler._send_stage_update.await_count == 2


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_returns_none_when_disabled():
    handler = StepFunRealtimeHandler()
    handler._sales_stage_enabled = False
    handler._ensure_sales_stage_context = AsyncMock()

    result = await handler._analyze_and_emit_sales_stage(
        user_text="这段输入不应触发阶段分析",
        turn_number=1,
    )

    assert result is None
    handler._ensure_sales_stage_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_message_updates_stage_when_duplicate_key_hit():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-dup-1"
    handler._persisted_message_keys.add((1, "user", "同一条消息"))
    handler._update_existing_message_sales_stage = AsyncMock()

    await handler._persist_message(
        turn_number=1,
        role="user",
        content="同一条消息",
        sales_stage="discovery",
    )

    handler._update_existing_message_sales_stage.assert_awaited_once_with(
        turn_number=1,
        role="user",
        content="同一条消息",
        sales_stage="discovery",
        fuzzy_words=None,
        score_snapshot=None,
        ai_feedback=None,
    )


def test_apply_latest_scores_to_session_maps_sales_rollups_and_snapshot():
    handler = StepFunRealtimeHandler()
    handler.turn_count = 4
    handler._latest_score_snapshot = {
        "overall_score": 84.0,
        "dimension_scores": {
            "价值表达": 90.0,
            "客户收益连接": 84.0,
            "证据使用": 58.0,
            "异议处理": 76.0,
            "推进下一步": 86.0,
        },
    }

    session = MagicMock()
    session.logic_score = None
    session.accuracy_score = None
    session.completeness_score = None

    handler._apply_latest_scores_to_session(session)

    assert session.logic_score == pytest.approx(87.6)
    assert session.accuracy_score == pytest.approx(69.7)
    assert session.completeness_score == pytest.approx(80.0)
    assert session.effectiveness_snapshot["main_issue"]["issue_type"] == "evidence_gap"
    assert (
        session.effectiveness_snapshot["next_goal"]["goal_type"] == "evidence_backing"
    )
    assert session.effectiveness_snapshot["evaluable"] is True


@pytest.mark.asyncio
async def test_create_response_merges_base_contract_and_grounding_instructions():
    handler = StepFunRealtimeHandler()
    handler._stepfun_instructions = "【系统总指令】始终扮演采购总监。"
    handler._pending_grounding_context = "用户问题：最新报价策略"
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    payload = handler._send_upstream.await_args.args[0]
    assert payload["type"] == "response.create"
    instructions = payload["response"]["instructions"]
    assert "始终扮演采购总监" in instructions
    assert "用户问题：最新报价策略" in instructions
    handler._send_status.assert_awaited_once_with("thinking")


@pytest.mark.asyncio
async def test_create_response_blocks_product_overview_when_bound_kb_retrieval_is_empty():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": False,
        },
    }
    handler._stepfun_instructions = "【系统总指令】你是企业产品专家。"
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 0,
            "results": [],
            "message": "未命中",
        }
    )
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.websocket = MagicMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_lock = asyncio.Lock()
    handler._feedback_context = None

    await handler._prepare_grounding_context("请你讲一下实习，介绍一下实习这个产品。")
    created = await handler._create_response(count_turn=True)

    assert created is True
    handler._send_upstream.assert_not_awaited()
    handler.manager.send_json.assert_awaited_once()
    blocked_payload = handler.manager.send_json.await_args.args[1]
    assert blocked_payload["type"] == "tts_audio"
    assert "内部知识库没有足够依据" in blocked_payload["data"]["text"]


@pytest.mark.asyncio
async def test_create_response_blocks_product_overview_when_bound_kb_retrieval_is_empty_even_without_strict_lock():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": False,
        },
    }
    handler._stepfun_instructions = "【系统总指令】你是企业产品专家。"
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 0,
            "results": [],
            "message": "未命中",
            "_answerability": {
                "answerability": "insufficient",
                "source_status": "miss",
            },
        }
    )
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.websocket = MagicMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_lock = asyncio.Lock()
    handler._feedback_context = None

    await handler._prepare_grounding_context("帮我介绍一下石溪科技。")
    created = await handler._create_response(count_turn=True)

    assert created is True
    handler._send_upstream.assert_not_awaited()
    handler.manager.send_json.assert_awaited_once()
    blocked_payload = handler.manager.send_json.await_args.args[1]
    assert blocked_payload["type"] == "tts_audio"
    assert "内部知识库没有足够依据" in blocked_payload["data"]["text"]


@pytest.mark.asyncio
async def test_create_response_blocks_when_strict_kb_answerability_is_insufficient():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": True,
        },
    }
    handler._stepfun_instructions = "【系统总指令】你是企业产品专家。"
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.websocket = MagicMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_lock = asyncio.Lock()
    handler._feedback_context = None
    handler._latest_knowledge_answer_diagnostics = {
        "mode": "grounded_strict",
        "answerability": "insufficient",
        "source_status": "miss",
        "rewritten_queries": ["实习 产品介绍"],
        "citations": [],
    }
    handler._pending_blocked_response_text = (
        "当前内部知识库没有足够依据回答这个问题，请补充更具体的产品关键词或版本信息。"
    )

    created = await handler._create_response(count_turn=True)

    assert created is True
    handler._send_upstream.assert_not_awaited()
    handler.manager.send_json.assert_awaited_once()
    blocked_payload = handler.manager.send_json.await_args.args[1]
    assert blocked_payload["type"] == "tts_audio"
    assert "没有足够依据" in blocked_payload["data"]["text"]


@pytest.mark.asyncio
async def test_create_response_marks_partial_answerability_when_overview_query_only_has_one_citation():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": False,
        },
    }
    handler._stepfun_instructions = "【系统总指令】你是企业产品专家。"
    handler._tool_search_internal_knowledge = AsyncMock(
        return_value={
            "count": 1,
            "results": [
                {
                    "knowledge_base_id": "kb-1",
                    "knowledge_base_name": "产品知识库",
                    "document_title": "实习专家产品手册",
                    "snippet": "实习专家是一款企业内部智能演练平台。",
                    "score": 0.91,
                    "retrieval_mode": "hybrid",
                }
            ],
            "_answerability": {
                "mode": "grounded_preferred",
                "answerability": "partial",
                "source_status": "hit",
                "rewritten_queries": ["实习 产品介绍"],
                "citations": [
                    {
                        "claim": "实习专家是一款企业内部智能演练平台。",
                        "knowledge_base_id": "kb-1",
                        "knowledge_base_name": "产品知识库",
                        "document_title": "实习专家产品手册",
                        "snippet": "实习专家是一款企业内部智能演练平台。",
                        "score": 0.91,
                    }
                ],
            },
        }
    )
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()

    await handler._prepare_grounding_context("请介绍一下实习这个产品")
    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler._latest_knowledge_answer_diagnostics is not None
    assert handler._latest_knowledge_answer_diagnostics["answerability"] == "partial"
    payload = handler._send_upstream.await_args.args[0]
    instructions = payload["response"]["instructions"]
    assert "若信息不足，请明确说明不确定之处" in instructions


@pytest.mark.asyncio
async def test_flush_active_response_trims_unsupported_sentences_in_partial_mode():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_context = None
    handler._feedback_context = None
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
    )
    handler._active_response.text_parts = [
        "实习专家是一款企业内部智能演练平台。它覆盖所有海外市场并且已经支持 200 个国家。"
    ]
    handler._latest_knowledge_answer_diagnostics = {
        "mode": "grounded_preferred",
        "answerability": "partial",
        "source_status": "hit",
        "rewritten_queries": ["实习专家 产品介绍"],
        "citations": [
            {
                "claim": "实习专家是一款企业内部智能演练平台。",
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "document_title": "实习专家产品手册",
                "snippet": "实习专家是一款企业内部智能演练平台。",
                "score": 0.92,
            }
        ],
    }

    await handler._flush_active_response(
        {"type": "response.done", "response": {"id": "resp-1"}}
    )

    sent_payload = handler.manager.send_json.await_args_list[0].args[1]
    assert sent_payload["type"] == "tts_audio"
    assert sent_payload["data"]["text"] == "实习专家是一款企业内部智能演练平台。"
    handler._persist_message.assert_awaited_once()
    persisted_text = handler._persist_message.await_args.kwargs["content"]
    assert persisted_text == "实习专家是一款企业内部智能演练平台。"


@pytest.mark.asyncio
async def test_flush_active_response_falls_back_when_partial_mode_has_no_supported_sentence():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_context = None
    handler._feedback_context = None
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
    )
    handler._active_response.text_parts = [
        "它覆盖所有海外市场并且已经支持 200 个国家。"
    ]
    handler._latest_knowledge_answer_diagnostics = {
        "mode": "grounded_preferred",
        "answerability": "partial",
        "source_status": "hit",
        "rewritten_queries": ["实习专家 产品介绍"],
        "citations": [
            {
                "claim": "实习专家是一款企业内部智能演练平台。",
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "document_title": "实习专家产品手册",
                "snippet": "实习专家是一款企业内部智能演练平台。",
                "score": 0.92,
            }
        ],
    }

    await handler._flush_active_response(
        {"type": "response.done", "response": {"id": "resp-1"}}
    )

    sent_payload = handler.manager.send_json.await_args_list[0].args[1]
    assert (
        sent_payload["data"]["text"]
        == "当前内部知识库仅支持部分信息，暂无法确认更多细节。"
    )
    persisted_text = handler._persist_message.await_args.kwargs["content"]
    assert persisted_text == "当前内部知识库仅支持部分信息，暂无法确认更多细节。"


@pytest.mark.asyncio
async def test_prepare_grounding_context_blocks_any_bound_kb_query_when_coach_mode_times_out():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "knowledge_base_ids": ["kb-1"],
        "tool_policy": {
            "enable_internal_retrieval": True,
            "retrieval_top_k": 3,
            "require_kb_grounding": True,
            "kb_lock_mode": "coach_mode",
        },
    }
    handler._kb_lock_decision_timeout_seconds = 0.001

    async def _never_returns(*_args, **_kwargs):
        await asyncio.sleep(0.02)
        return {}

    async def fake_wait_for(awaitable, timeout):
        awaitable.close()
        raise TimeoutError

    with pytest.MonkeyPatch.context() as mp:
        pipeline = SimpleNamespace(evaluate=_never_returns)
        cast(Any, handler)._grounding_pipeline = pipeline
        mp.setattr(stepfun_module.asyncio, "wait_for", fake_wait_for)
        mp.setattr(handler, "_record_kb_lock_decision", AsyncMock())
        await handler._prepare_grounding_context(
            "请你讲一下实习，介绍一下实习这个产品。"
        )

    assert handler._pending_grounding_context == ""
    assert "知识检索超时" in handler._pending_blocked_response_text
    assert "这个问题" in handler._pending_blocked_response_text


@pytest.mark.asyncio
async def test_handle_upstream_response_text_delta_does_not_cancel_stream_on_question_limit():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "max_questions_per_turn": 1,
        }
    }
    handler._send_upstream = AsyncMock()
    handler._active_response = RealtimeResponseState(request_id=1, stream_id="stream-1")

    await handler._handle_upstream_response_text_delta(
        {
            "type": "response.text.delta",
            "delta": "好的，我先介绍产品。你更关心哪个方向？还想了解价格吗？",
        }
    )

    assert handler._active_response is not None
    assert handler._active_response.text_parts == [
        "好的，我先介绍产品。你更关心哪个方向？还想了解价格吗？"
    ]
    handler._send_upstream.assert_not_awaited()


@pytest.mark.asyncio
async def test_flush_active_response_emits_runtime_answer_diagnostics_and_citations():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_context = None
    handler._feedback_context = None
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
    )
    handler._active_response.text_parts = ["实习专家是一款企业内部智能演练平台。"]
    handler._latest_knowledge_answer_diagnostics = {
        "mode": "grounded_strict",
        "answerability": "sufficient",
        "source_status": "hit",
        "audit_run_id": "run-knowledge-1",
        "rewritten_queries": ["实习专家 产品介绍", "实习专家 核心能力"],
        "citations": [
            {
                "claim": "实习专家是一款企业内部智能演练平台。",
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "document_title": "实习专家产品手册",
                "snippet": "实习专家是一款面向企业内部训练的智能演练平台。",
                "score": 0.92,
            }
        ],
    }

    await handler._flush_active_response(
        {"type": "response.done", "response": {"id": "resp-1"}}
    )

    sent_payload = handler.manager.send_json.await_args_list[0].args[1]
    assert sent_payload["type"] == "tts_audio"
    assert sent_payload["data"]["text"] == "实习专家是一款企业内部智能演练平台。"
    assert (
        sent_payload["data"]["knowledge_answer_diagnostics"]["answerability"]
        == "sufficient"
    )
    assert (
        sent_payload["data"]["knowledge_answer_diagnostics"]["audit_run_id"]
        == "run-knowledge-1"
    )
    assert sent_payload["data"]["knowledge_answer_diagnostics"][
        "rewritten_queries"
    ] == ["实习专家 产品介绍", "实习专家 核心能力"]
    assert (
        sent_payload["data"]["knowledge_answer_diagnostics"]["citations"][0][
            "document_title"
        ]
        == "实习专家产品手册"
    )
    handler._persist_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_active_response_preserves_full_transcript_without_question_trim():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._sales_stage_context = None
    handler._feedback_context = None
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
    )
    full_text = (
        "浩哥，您提到产品风险，我能理解您对这个很在意。"
        "能简单说说您目前遇到的具体情况吗？"
        "另外也可以先说说预算范围和决策节奏。"
    )
    handler._active_response.text_parts = [full_text]

    await handler._flush_active_response(
        {"type": "response.done", "response": {"id": "resp-1"}}
    )

    sent_payload = handler.manager.send_json.await_args_list[0].args[1]
    assert sent_payload["data"]["text"] == full_text
    persist_args = handler._persist_message.await_args
    assert persist_args is not None
    assert persist_args.kwargs["content"] == full_text


def test_enforce_tool_policy_guardrails_disables_web_search_without_kb():
    handler = StepFunRealtimeHandler()
    handler._effective_policy = {
        "tool_policy": {
            "enable_web_search": True,
            "enable_internal_retrieval": False,
            "network_access_mode": "controlled",
            "allow_web_search_without_kb": False,
        },
        "knowledge_base_ids": [],
        "source": {},
        "instructions": "原始指令",
    }

    changed = handler._enforce_tool_policy_guardrails()

    assert changed is True
    tool_policy = handler._effective_policy["tool_policy"]
    assert tool_policy["enable_web_search"] is False
    assert tool_policy["network_access_mode"] == "controlled"
    assert (
        handler._effective_policy["source"]["tool_policy_enforcement"] == "no_kb_no_web"
    )


@pytest.mark.asyncio
async def test_run_realtime_feedback_keeps_single_action_card_and_prioritizes_score_over_low_severity_fuzzy_detection():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-priority"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = True
    handler._realtime_scoring_enabled = True

    handler._fuzzy_detection_capability = MagicMock()
    handler._fuzzy_detection_capability.on_session_start = AsyncMock()
    handler._fuzzy_detection_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "detections": [
                    {
                        "category": "filler",
                        "matched": ["嗯"],
                        "suggestion": "减少填充词，保持表达流畅。",
                        "severity": "low",
                    }
                ]
            }
        )
    )
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 83.0,
                "dimension_scores": {
                    "价值表达": 83.0,
                    "客户收益连接": 81.0,
                    "证据使用": 60.0,
                    "异议处理": 78.0,
                    "推进下一步": 67.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们先聊聊产品价值。",
        turn_number=2,
        sales_stage="discovery",
    )

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_cards = [
        payload for payload in sent_payloads if payload["type"] == "action_card"
    ]

    assert analysis["fuzzy_words"] == [
        {
            "category": "filler",
            "matched": ["嗯"],
            "suggestion": "减少填充词，保持表达流畅。",
            "severity": "low",
        }
    ]
    assert analysis["score_snapshot"]["overall_score"] == 83.0
    assert (
        analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    )
    assert len(action_cards) == 1
    assert action_cards[0]["data"] == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }


@pytest.mark.asyncio
async def test_run_realtime_feedback_suppresses_duplicate_action_card_for_same_turn():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-suppress"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 61.0,
                    "异议处理": 76.0,
                    "推进下一步": 64.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    first_analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )
    second_analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )

    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_cards = [
        payload for payload in sent_payloads if payload["type"] == "action_card"
    ]
    score_updates = [
        payload for payload in sent_payloads if payload["type"] == "score_update"
    ]

    assert (
        first_analysis["ai_feedback"]
        == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    )
    assert second_analysis == {
        "score_snapshot": {
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 61.0,
                "异议处理": 76.0,
                "推进下一步": 64.0,
            },
            "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
            "stage_name": "需求挖掘",
        },
        "objection_ledger": {
            "objection_family": "roi_proof",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "closure_state": "open",
        },
    }
    assert len(action_cards) == 1
    assert len(score_updates) == 2
    assert action_cards[0]["data"] == expected_action_card
    assert handler._latest_action_card == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_emits_canonical_sales_score_and_action_card():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-feedback"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 61.0,
                    "异议处理": 76.0,
                    "推进下一步": 64.0,
                },
                "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以用客户案例说明ROI。",
        turn_number=3,
        sales_stage="discovery",
    )

    expected_snapshot = {
        "overall_score": 82.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 80.0,
            "证据使用": 61.0,
            "异议处理": 76.0,
            "推进下一步": 64.0,
        },
        "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
        "stage_name": "需求挖掘",
    }
    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": {
            "objection_family": "roi_proof",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "closure_state": "open",
        },
        "ai_feedback": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
    }
    assert handler._latest_score_snapshot == expected_snapshot
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(
        payload for payload in sent_payloads if payload["type"] == "score_update"
    )
    action_card = next(
        payload for payload in sent_payloads if payload["type"] == "action_card"
    )

    assert score_update["data"] == {
        "session_id": "session-realtime-feedback",
        "turn_count": 3,
        "overall_score": 82.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 80.0,
            "证据使用": 61.0,
            "异议处理": 76.0,
            "推进下一步": 64.0,
        },
        "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
        "stage_name": "需求挖掘",
        "claim_truth": {
            "status": "evidence_pending",
            "label": "证据待补齐",
            "source": "objection_ledger",
            "reason": "open_objection_ledger",
            "closure_state": "open",
        },
        "live_session_summary": {
            "alignment_used": True,
            "stage_key": "discovery",
            "focus_type": "evidence_gap",
            "fallback_reason": None,
            "main_issue": {
                "issue_type": "evidence_gap",
                "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
            },
            "next_goal": {
                "goal_type": "evidence_backing",
                "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                "rule": "至少补上一条证据和一个明确的下一步动作。",
            },
            "claim_truth": {
                "status": "evidence_pending",
                "label": "证据待补齐",
                "source": "objection_ledger",
                "reason": "open_objection_ledger",
                "closure_state": "open",
            },
        },
    }
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_analyze_and_emit_sales_stage_retains_latest_rich_stage_data_for_followup_feedback():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stage-rich"
    handler._ensure_sales_stage_context = AsyncMock()
    handler._sales_stage_context = MagicMock()
    handler._sales_stage_context.turn_count = 0
    handler._sales_stage_context.add_message = MagicMock()
    handler._send_stage_update = AsyncMock()

    stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._sales_stage_capability.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, data=stage_data)
    )

    latest_stage = await handler._analyze_and_emit_sales_stage(
        user_text="我们可以约下周确认试点。",
        turn_number=3,
    )

    assert latest_stage == "closing"
    assert getattr(handler, "_latest_stage_data", None) == stage_data


@pytest.mark.asyncio
async def test_run_realtime_feedback_passes_rich_stage_and_raw_score_context_to_arbiter_while_score_update_stays_stable():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-rich-context"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    raw_score_payload = {
        "overall": 78.0,
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "dimensions": [
            {"name": "推进下一步", "score": 65.0, "delta": -6.0, "trend": "down"},
            {"name": "证据使用", "score": 74.0, "delta": 1.0, "trend": "up"},
        ],
        "feedback": "继续回应客户顾虑。",
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(data=raw_score_payload)
    )
    handler._feedback_arbiter = MagicMock()
    handler._feedback_arbiter.decide.return_value = SimpleNamespace(
        action_card=None,
        state=RealtimeFeedbackPacingState(),
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以约下周确认试点。",
        turn_number=4,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "促成成交",
    }

    assert analysis == {"score_snapshot": expected_snapshot}
    assert handler._latest_score_snapshot == expected_snapshot

    handler._feedback_arbiter.decide.assert_called_once()
    arbiter_kwargs = handler._feedback_arbiter.decide.call_args.kwargs
    assert arbiter_kwargs["stage_context"] == {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    assert (
        arbiter_kwargs["score_context"]["dimensions"] == raw_score_payload["dimensions"]
    )
    assert arbiter_kwargs["score_context"]["feedback"] == "继续回应客户顾虑。"
    assert (
        arbiter_kwargs["score_context"]["dimension_scores"]
        == raw_score_payload["dimension_scores"]
    )
    assert arbiter_kwargs["score_context"]["stage_name"] == "促成成交"

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(
        payload for payload in sent_payloads if payload["type"] == "score_update"
    )
    assert score_update["data"] == {
        "session_id": "session-realtime-rich-context",
        "turn_count": 4,
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "促成成交",
        "claim_truth": {
            "status": "weak_evidence",
            "label": "证据偏弱",
            "source": "score_snapshot",
            "reason": "low_evidence_score",
            "evidence_score": 74.0,
        },
        "live_session_summary": {
            "alignment_used": True,
            "stage_key": "closing",
            "focus_type": "next_step_gap",
            "fallback_reason": None,
            "main_issue": {
                "issue_type": "next_step_gap",
                "issue_text": "对话结束前没有形成明确的下一步动作、责任人或时间点。",
                "recovery_rule": "下一轮必须落到试点、会议、报价或负责人确认中的一个动作。",
            },
            "next_goal": {
                "goal_type": "next_step_commitment",
                "goal_text": "下一轮必须把试点、会议、报价或责任人确认成明确下一步。",
                "rule": "每轮结尾至少确认一个动作、一个时间点和一个责任人。",
            },
            "claim_truth": {
                "status": "weak_evidence",
                "label": "证据偏弱",
                "source": "score_snapshot",
                "reason": "low_evidence_score",
                "evidence_score": 74.0,
            },
        },
    }
    assert "dimensions" not in score_update["data"]


@pytest.mark.asyncio
async def test_run_realtime_feedback_uses_declining_dimension_to_match_classic_action_card():
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-realtime-declining-dimension"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._latest_stage_data = {
        "current_stage": "objection",
        "stage_name": "异议处理",
        "key_actions": ["承接顾虑"],
        "guidance": "围绕风险与证据回应",
        "progress": 0.6,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall": 76.0,
                "overall_score": 76.0,
                "dimension_scores": {
                    "价值表达": 82.0,
                    "客户收益连接": 79.0,
                    "证据使用": 66.0,
                    "异议处理": 72.0,
                    "推进下一步": 78.0,
                },
                "dimensions": [
                    {"name": "证据使用", "score": 66.0, "delta": 1.0, "trend": "up"},
                    {"name": "异议处理", "score": 72.0, "delta": -9.0, "trend": "down"},
                ],
                "feedback": "继续回应客户顾虑。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="客户担心实施风险和价格。",
        turn_number=5,
        sales_stage="objection",
    )

    expected_snapshot = {
        "overall_score": 76.0,
        "dimension_scores": {
            "价值表达": 82.0,
            "客户收益连接": 79.0,
            "证据使用": 66.0,
            "异议处理": 72.0,
            "推进下一步": 78.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "异议处理",
    }
    expected_action_card = {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": {
            "objection_family": "price_pressure",
            "promised_proof": "补充报价依据和版本差异",
            "next_expected_evidence": "说明报价逻辑、预算回收或折扣边界",
            "closure_state": "open",
        },
        "ai_feedback": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
    }
    assert handler._latest_score_snapshot == expected_snapshot
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(
        payload for payload in sent_payloads if payload["type"] == "action_card"
    )
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_opens_competitor_objection_ledger_and_keeps_claim_truth_pending() -> (
    None
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-competitor-ledger-open"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._latest_stage_data = {
        "current_stage": "objection",
        "stage_name": "异议处理",
        "key_actions": ["承接替代方案顾虑"],
        "guidance": "围绕差异化收益和迁移风险回应",
        "progress": 0.6,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 77.0,
                "dimension_scores": {
                    "价值表达": 80.0,
                    "客户收益连接": 78.0,
                    "证据使用": 68.0,
                    "异议处理": 62.0,
                    "推进下一步": 70.0,
                },
                "feedback": "继续回应客户顾虑。",
            }
        )
    )
    handler._feedback_arbiter = MagicMock()
    handler._feedback_arbiter.decide.return_value = SimpleNamespace(
        action_card=None,
        state=RealtimeFeedbackPacingState(),
    )

    analysis = await handler._run_realtime_feedback(
        user_text="竞品A已经能做这个了，你们为什么更稳妥？",
        turn_number=5,
        sales_stage="objection",
    )

    expected_snapshot = {
        "overall_score": 77.0,
        "dimension_scores": {
            "价值表达": 80.0,
            "客户收益连接": 78.0,
            "证据使用": 68.0,
            "异议处理": 62.0,
            "推进下一步": 70.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
        "stage_name": "异议处理",
    }
    expected_ledger = {
        "objection_family": "competitor_alternative",
        "promised_proof": "补充竞品差异和替代依据",
        "next_expected_evidence": "说明为什么比现有方案更稳妥",
        "closure_state": "open",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_claim_truth == {
        "status": "evidence_pending",
        "label": "证据待补齐",
        "source": "objection_ledger",
        "reason": "open_objection_ledger",
        "closure_state": "open",
    }

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(
        payload for payload in sent_payloads if payload["type"] == "score_update"
    )
    assert score_update["data"]["claim_truth"] == {
        "status": "evidence_pending",
        "label": "证据待补齐",
        "source": "objection_ledger",
        "reason": "open_objection_ledger",
        "closure_state": "open",
    }


@pytest.mark.asyncio
async def test_run_realtime_feedback_marks_implementation_evidence_verified_after_risk_proof_arrives() -> (
    None
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-implementation-ledger-verified"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._objection_ledger = {
        "objection_family": "implementation_risk",
        "promised_proof": "补充实施排期和服务边界",
        "next_expected_evidence": "确认试点范围、负责人和风险兜底",
        "closure_state": "open",
    }
    handler._latest_stage_data = {
        "current_stage": "objection",
        "stage_name": "异议处理",
        "key_actions": ["拆解实施风险"],
        "guidance": "用试点边界、负责人和SLA回应上线顾虑",
        "progress": 0.7,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 84.0,
                "dimension_scores": {
                    "价值表达": 82.0,
                    "客户收益连接": 80.0,
                    "证据使用": 86.0,
                    "异议处理": 84.0,
                    "推进下一步": 79.0,
                },
                "feedback": "保持当前节奏，继续确认下一步。",
            }
        )
    )
    handler._feedback_arbiter = MagicMock()
    handler._feedback_arbiter.decide.return_value = SimpleNamespace(
        action_card=None,
        state=RealtimeFeedbackPacingState(),
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们会安排两周试点、实施负责人和SLA兜底，把上线风险先收敛在试点范围内。",
        turn_number=6,
        sales_stage="objection",
    )

    expected_snapshot = {
        "overall_score": 84.0,
        "dimension_scores": {
            "价值表达": 82.0,
            "客户收益连接": 80.0,
            "证据使用": 86.0,
            "异议处理": 84.0,
            "推进下一步": 79.0,
        },
        "suggestions": ["保持当前节奏，继续确认下一步。"],
        "stage_name": "异议处理",
    }
    expected_ledger = {
        "objection_family": "implementation_risk",
        "promised_proof": "补充实施排期和服务边界",
        "next_expected_evidence": "确认试点范围、负责人和风险兜底",
        "closure_state": "evidence_provided",
    }
    expected_claim_truth = {
        "status": "evidence_verified",
        "label": "证据已验证",
        "source": "objection_ledger",
        "reason": "evidence_provided",
        "evidence_score": 86.0,
        "closure_state": "evidence_provided",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_claim_truth == expected_claim_truth

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    score_update = next(
        payload for payload in sent_payloads if payload["type"] == "score_update"
    )
    assert score_update["data"]["claim_truth"] == expected_claim_truth


@pytest.mark.asyncio
async def test_run_realtime_feedback_reuses_open_objection_ledger_when_score_focus_drifts() -> (
    None
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-drift"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 79.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 82.0,
                    "证据使用": 88.0,
                    "异议处理": 81.0,
                    "推进下一步": 52.0,
                },
                "feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="我们可以先聊一下后面的协同流程。",
        turn_number=6,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 79.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 82.0,
            "证据使用": 88.0,
            "异议处理": 81.0,
            "推进下一步": 52.0,
        },
        "suggestions": ["明确试点、会议、报价或负责人确认中的一个动作。"],
        "stage_name": "促成成交",
    }
    expected_action_card = {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    expected_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
        "ai_feedback": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(
        payload for payload in sent_payloads if payload["type"] == "action_card"
    )
    assert action_card["data"] == expected_action_card


@pytest.mark.asyncio
async def test_run_realtime_feedback_marks_objection_ledger_gap_acknowledged_and_releases_focus() -> (
    None
):
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-close"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._fuzzy_detection_enabled = False
    handler._realtime_scoring_enabled = True
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    handler._latest_stage_data = {
        "current_stage": "closing",
        "stage_name": "成交推进",
        "key_actions": ["锁定动作"],
        "guidance": "推动明确下一步",
        "progress": 0.8,
        "stage_changed": True,
    }
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.on_session_start = AsyncMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            data={
                "overall_score": 79.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 82.0,
                    "证据使用": 88.0,
                    "异议处理": 81.0,
                    "推进下一步": 52.0,
                },
                "feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
            }
        )
    )

    analysis = await handler._run_realtime_feedback(
        user_text="这个 ROI 案例我们现在确实没有，得回去确认后再给你。",
        turn_number=6,
        sales_stage="closing",
    )

    expected_snapshot = {
        "overall_score": 79.0,
        "dimension_scores": {
            "价值表达": 84.0,
            "客户收益连接": 82.0,
            "证据使用": 88.0,
            "异议处理": 81.0,
            "推进下一步": 52.0,
        },
        "suggestions": ["明确试点、会议、报价或负责人确认中的一个动作。"],
        "stage_name": "促成成交",
    }
    expected_action_card = {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    }
    expected_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "gap_acknowledged",
    }

    assert analysis == {
        "score_snapshot": expected_snapshot,
        "objection_ledger": expected_ledger,
        "ai_feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
    }
    assert handler._objection_ledger == expected_ledger
    assert handler._latest_action_card == expected_action_card

    sent_payloads = [call.args[1] for call in handler.manager.send_json.await_args_list]
    action_card = next(
        payload for payload in sent_payloads if payload["type"] == "action_card"
    )
    assert action_card["data"] == expected_action_card


def test_create_state_snapshot_includes_objection_ledger_copy() -> None:
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-objection-ledger-save"
    handler._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补同类客户 ROI 案例",
        "next_expected_evidence": "给出量化回本周期",
        "closure_state": "open",
    }

    snapshot = handler._create_state_snapshot()

    assert snapshot.runtime_state["objection_ledger"] == {
        "objection_family": "roi_proof",
        "promised_proof": "补同类客户 ROI 案例",
        "next_expected_evidence": "给出量化回本周期",
        "closure_state": "open",
    }

    handler._objection_ledger["closure_state"] = "gap_acknowledged"
    assert snapshot.runtime_state["objection_ledger"]["closure_state"] == "open"


@pytest.mark.asyncio
async def test_restore_session_state_rehydrates_objection_ledger() -> None:
    handler = StepFunRealtimeHandler()
    handler._send_reconnection_success = AsyncMock()

    state = SessionStateSnapshot(
        session_id="session-objection-ledger-restore",
        scenario="sales",
        turn_count=3,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "objection_ledger": {
                "objection_family": "implementation_risk",
                "promised_proof": "补实施排期与服务边界",
                "next_expected_evidence": "确认试点负责人",
                "closure_state": "open",
            }
        },
    )

    await handler._restore_session_state(state)

    assert handler._objection_ledger == {
        "objection_family": "implementation_risk",
        "promised_proof": "补实施排期与服务边界",
        "next_expected_evidence": "确认试点负责人",
        "closure_state": "open",
    }
    handler._send_reconnection_success.assert_awaited_once()
    emitted_snapshot = handler._send_reconnection_success.await_args.args[0]
    assert emitted_snapshot.session_id == state.session_id
    assert emitted_snapshot.turn_count == state.turn_count
    assert emitted_snapshot.session_status == state.session_status
    assert emitted_snapshot.ai_state == state.ai_state
    emitted_runtime_state = emitted_snapshot.runtime_state
    assert emitted_runtime_state is not None
    assert emitted_runtime_state == {
        "objection_ledger": {
            "objection_family": "implementation_risk",
            "promised_proof": "补实施排期与服务边界",
            "next_expected_evidence": "确认试点负责人",
            "closure_state": "open",
        },
        "reconnect_state": {
            "connection_epoch": 1,
            "request_epoch": 0,
            "last_disconnect_reason": None,
            "last_error": None,
        },
    }


# ── S07: Coach health degraded/resumed state ──


@pytest.mark.asyncio
async def test_run_realtime_feedback_marks_coach_degraded_when_capability_pipeline_fails():
    """When scoring capability raises, the handler should set coach_health to 'degraded'."""
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 1
    handler.session_id = "session-degraded-test"

    handler._ensure_feedback_context = AsyncMock()
    handler._feedback_context = SimpleNamespace(
        turn_count=1,
        add_message=MagicMock(),
    )
    handler._send_score_update = AsyncMock()
    handler._send_fuzzy_detection = AsyncMock()
    handler._send_action_card = AsyncMock()
    handler._send_coach_health = AsyncMock()

    # Scoring capability raises an exception
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        side_effect=RuntimeError("scoring service unavailable")
    )

    handler._fuzzy_detection_enabled = True
    handler._fuzzy_detection_capability = MagicMock()
    handler._fuzzy_detection_capability.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, data={"detections": []})
    )

    handler._sales_stage_enabled = True

    await handler._run_realtime_feedback(
        user_text="我们这个产品的 ROI 很高",
        turn_number=1,
        sales_stage="discovery",
    )

    # Coach health should be marked degraded
    assert handler._coach_health == "degraded"
    # The handler should have emitted a coach_health_update to the frontend
    handler._send_coach_health.assert_awaited()
    # Session status should still be usable (in_progress)
    assert handler.session_status == "in_progress"


@pytest.mark.asyncio
async def test_run_realtime_feedback_clears_coach_degraded_state_after_successful_resume():
    """After a degraded turn, a successful next evaluation should set coach_health to 'resumed'."""
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 2
    handler.session_id = "session-resume-test"

    handler._ensure_feedback_context = AsyncMock()
    handler._feedback_context = SimpleNamespace(
        turn_count=2,
        add_message=MagicMock(),
    )
    handler._send_score_update = AsyncMock()
    handler._send_fuzzy_detection = AsyncMock()
    handler._send_action_card = AsyncMock()
    handler._send_coach_health = AsyncMock()

    # Simulate prior degraded state
    handler._coach_health = "degraded"

    # This turn succeeds
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        return_value=SimpleNamespace(
            success=True,
            data={
                "dimension_scores": {"价值表达": 78.0},
                "overall_score": 78.0,
                "feedback": "尝试更具体的 ROI 表达",
            },
        )
    )

    handler._fuzzy_detection_enabled = True
    handler._fuzzy_detection_capability = MagicMock()
    handler._fuzzy_detection_capability.execute = AsyncMock(
        return_value=SimpleNamespace(success=True, data={"detections": []})
    )

    handler._sales_stage_enabled = True

    await handler._run_realtime_feedback(
        user_text="根据我们的数据，客户 ROI 达到了 35%",
        turn_number=2,
        sales_stage="discovery",
    )

    # Coach health should transition from degraded -> resumed
    assert handler._coach_health == "resumed"
    handler._send_coach_health.assert_awaited()


@pytest.mark.asyncio
async def test_capability_pipeline_fails_does_not_change_training_session_status():
    """When the coaching pipeline fails, session status must remain in_progress."""
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler.turn_count = 1
    handler.session_id = "session-status-test"

    handler._ensure_feedback_context = AsyncMock()
    handler._feedback_context = SimpleNamespace(
        turn_count=1,
        add_message=MagicMock(),
    )
    handler._send_score_update = AsyncMock()
    handler._send_fuzzy_detection = AsyncMock()
    handler._send_action_card = AsyncMock()
    handler._send_coach_health = AsyncMock()

    # All capabilities fail
    handler._realtime_scoring_enabled = True
    handler._realtime_scoring_capability = MagicMock()
    handler._realtime_scoring_capability.execute = AsyncMock(
        side_effect=RuntimeError("scoring down")
    )

    handler._fuzzy_detection_enabled = True
    handler._fuzzy_detection_capability = MagicMock()
    handler._fuzzy_detection_capability.execute = AsyncMock(
        side_effect=RuntimeError("fuzzy detection down")
    )

    handler._sales_stage_enabled = True

    await handler._run_realtime_feedback(
        user_text="这个功能对我们帮助很大",
        turn_number=1,
        sales_stage="opening",
    )

    # Training session must still be usable
    assert handler.session_status == "in_progress"
    assert handler._coach_health == "degraded"

    assert handler.session_status == "in_progress"
    assert handler._coach_health == "degraded"


@pytest.mark.asyncio
async def test_handle_upstream_response_audio_transcript_done_dispatches_capture_without_blocking():
    release_sink = asyncio.Event()
    sink_started = asyncio.Event()
    captured: list[dict[str, Any]] = []

    async def sink(payload: dict[str, Any]) -> None:
        captured.append(payload)
        sink_started.set()
        await release_sink.wait()

    handler = StepFunRealtimeHandler(transcript_capture_sink=sink)
    handler.session_id = "session-turn-capture"
    handler.turn_count = 2
    handler._effective_policy = {
        "instruction_contract_hash": "policy-hash-1",
        "knowledge_base_ids": ["kb-1"],
    }
    handler._latest_knowledge_answer_diagnostics = {
        "mode": "grounded_strict",
        "answerability": "sufficient",
        "source_status": "hit",
        "audit_run_id": "run-1",
        "citations": [
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "document_title": "产品手册",
                "snippet": "不应泄露到 capture",
                "claim": "不应泄露到 capture",
                "score": 0.91,
            }
        ],
    }
    handler._active_response = RealtimeResponseState(
        request_id=2,
        stream_id="stream-2",
        response_id="resp-2",
    )
    handler._handle_emotion_event = AsyncMock()
    handler._handle_thinking_event = AsyncMock()

    await asyncio.wait_for(
        handler._handle_upstream_event(
            {
                "type": "response.audio_transcript.done",
                "response_id": "resp-2",
                "transcript": "这是最终的销售回答。",
                "thinking": "不能进入采集 payload",
            }
        ),
        timeout=0.1,
    )

    await asyncio.wait_for(sink_started.wait(), timeout=1.0)
    assert not release_sink.is_set()
    assert len(captured) == 1
    payload = captured[0]
    assert payload["speaker"] == "assistant"
    assert payload["transcript"] == "这是最终的销售回答。"
    assert payload["response_id"] == "resp-2"
    assert payload["turn_id"] == "2"
    assert payload["turn_index"] == 2
    assert payload["instruction_contract_hash"] == "policy-hash-1"
    assert "thinking" not in payload
    assert payload["grounding_metadata"] == {
        "knowledge_base_ids": ["kb-1"],
        "mode": "grounded_strict",
        "answerability": "sufficient",
        "source_status": "hit",
        "audit_run_id": "run-1",
        "citation_count": 1,
        "citations": [
            {
                "knowledge_base_id": "kb-1",
                "knowledge_base_name": "产品知识库",
                "document_title": "产品手册",
                "score": 0.91,
            }
        ],
    }

    release_sink.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_stale_raw_assistant_transcript_is_rejected_before_capture_sink() -> None:
    captured: list[dict[str, Any]] = []
    handler = StepFunRealtimeHandler(transcript_capture_sink=captured.append)
    handler.session_id = "session-stale-capture"
    handler.turn_count = 2
    handler._active_response = RealtimeResponseState(
        request_id=2,
        stream_id="stream-current",
        response_id="response-current",
    )
    original_preflight = handler._preflight_upstream_event
    handler._preflight_upstream_event = MagicMock(wraps=original_preflight)  # type: ignore[method-assign]

    await handler._handle_upstream_event(
        {
            "type": "response.audio_transcript.done",
            "request_id": 2,
            "stream_id": "stream-current",
            "response_id": "response-stale",
            "transcript": "旧响应不得进入采集。",
        }
    )

    assert captured == []
    handler._preflight_upstream_event.assert_called_once()


@pytest.mark.asyncio
async def test_response_done_capture_sink_failure_does_not_interrupt_flush(
    monkeypatch: pytest.MonkeyPatch,
):
    def failing_sink(_payload: dict[str, Any]) -> None:
        raise RuntimeError("sink down")

    capture_logger = MagicMock()
    monkeypatch.setattr(transcript_capture_module, "logger", capture_logger)

    handler = StepFunRealtimeHandler(transcript_capture_sink=failing_sink)
    handler.session_id = "session-capture-failure"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._sales_stage_context = None
    handler._feedback_context = None
    handler.turn_count = 1
    handler._handle_emotion_event = AsyncMock()
    handler._handle_thinking_event = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
        response_id="resp-1",
    )
    handler._active_response.text_parts = ["您好，这是最终回复。"]
    save_message = AsyncMock(return_value=True)
    monkeypatch.setattr(sales_stage_module, "save_stepfun_message", save_message)

    await handler._handle_upstream_event(
        {"type": "response.done", "response": {"id": "resp-1", "output": []}}
    )

    handler.manager.send_json.assert_awaited_once()
    save_message.assert_awaited_once()
    capture_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_send_transcript_final_dispatches_learner_capture() -> None:
    captured: list[dict[str, Any]] = []
    handler = StepFunRealtimeHandler(transcript_capture_sink=captured.append)
    handler.session_id = "session-learner-capture"
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._resolve_user_turn_number_for_transcript = MagicMock(return_value=3)

    await handler._send_transcript("客户更关心实施周期。", is_final=True)

    assert len(captured) == 1
    payload = captured[0]
    assert payload["speaker"] == "learner"
    assert payload["transcript"] == "客户更关心实施周期。"
    assert payload["response_id"] is None
    assert payload["turn_id"] is None
    assert payload["turn_index"] == 3
    assert payload["source_event_type"] == "input_audio_transcription.completed"


@pytest.mark.asyncio
async def test_handle_upstream_response_audio_transcript_done_skips_blank_capture():
    captured: list[dict[str, Any]] = []
    handler = StepFunRealtimeHandler(transcript_capture_sink=captured.append)
    handler.session_id = "session-empty-capture"
    handler.turn_count = 1
    handler._active_response = RealtimeResponseState(
        request_id=1,
        stream_id="stream-1",
        response_id="resp-1",
    )
    handler._handle_emotion_event = AsyncMock()
    handler._handle_thinking_event = AsyncMock()

    await handler._handle_upstream_event(
        {
            "type": "response.audio_transcript.done",
            "response_id": "resp-1",
            "transcript": "   ",
        }
    )

    assert captured == []
