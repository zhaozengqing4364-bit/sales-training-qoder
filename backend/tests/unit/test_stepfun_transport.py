from __future__ import annotations

import asyncio
import json

import pytest

import training_runtime.stepfun_transport as stepfun_transport_module
from training_runtime.stepfun_transport import (
    STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES,
    StepFunBackpressurePolicy,
    StepFunBackpressureStatus,
    StepFunHealthStatus,
    StepFunSendStatus,
    StepFunSessionConfig,
    StepFunTransport,
    build_stepfun_realtime_endpoint,
    build_stepfun_session_update_payload,
    resolve_stepfun_upstream_status_message,
)


def test_stepfun_default_backpressure_watermark_matches_legacy_runtime() -> None:
    assert STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES == 512 * 1024


class CloseRaisesRuntimeErrorWebSocket:
    def close(self) -> None:
        raise RuntimeError("already closed")


class RecordingWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.messages.append(payload)


class SendOnlyWebSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


class SendRaisesOSErrorWebSocket:
    async def send_json(self, payload: dict[str, object]) -> None:
        raise OSError("upstream closed")


class PongWebSocket:
    async def ping(self) -> object:
        return None


class PingRaisesRuntimeErrorWebSocket:
    async def ping(self) -> object:
        raise RuntimeError("ping failed")


class SlowPongWebSocket:
    async def ping(self) -> object:
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_connect_builds_stepfun_realtime_endpoint_and_authorization_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    upstream_ws = object()

    async def fake_connect(
        endpoint: str,
        *,
        additional_headers: dict[str, str],
    ) -> object:
        captured["endpoint"] = endpoint
        captured["additional_headers"] = additional_headers
        return upstream_ws

    monkeypatch.setattr(
        stepfun_transport_module.websockets,
        "connect",
        fake_connect,
    )

    result = await StepFunTransport().connect(
        api_key="test-stepfun-key",
        url="wss://api.stepfun.com/v1/realtime",
        model="stepaudio-2.5-realtime",
    )

    assert result is upstream_ws
    assert captured["endpoint"] == (
        "wss://api.stepfun.com/v1/realtime?model=stepaudio-2.5-realtime"
    )
    assert captured["additional_headers"] == {
        "Authorization": "Bearer test-stepfun-key"
    }


def test_should_build_stepfun_endpoint_for_step_plan_url() -> None:
    endpoint = build_stepfun_realtime_endpoint(
        "wss://api.stepfun.com/step_plan/v1/realtime",
        model="stepaudio-2.5-realtime",
    )

    assert endpoint == (
        "wss://api.stepfun.com/step_plan/v1/realtime?model=stepaudio-2.5-realtime"
    )


def test_should_replace_existing_stepfun_model_query_without_dropping_other_params() -> (
    None
):
    endpoint = build_stepfun_realtime_endpoint(
        "wss://api.stepfun.com/v1/realtime?foo=bar&model=old-model",
        model="stepaudio-2.5-realtime",
    )

    assert endpoint == (
        "wss://api.stepfun.com/v1/realtime?foo=bar&model=stepaudio-2.5-realtime"
    )


def test_should_reject_stepfun_endpoint_userinfo_without_leaking_secret() -> None:
    with pytest.raises(ValueError) as exc_info:
        build_stepfun_realtime_endpoint(
            "wss://user:secret-pass@api.stepfun.com/v1/realtime",
            model="stepaudio-2.5-realtime",
        )

    assert str(exc_info.value) == "stepfun_realtime_url_must_not_include_userinfo"
    assert "secret-pass" not in str(exc_info.value)


def test_should_reject_stepfun_endpoint_sensitive_query_without_leaking_secret() -> (
    None
):
    with pytest.raises(ValueError) as exc_info:
        build_stepfun_realtime_endpoint(
            "wss://api.stepfun.com/v1/realtime?api_key=query-secret&region=cn",
            model="stepaudio-2.5-realtime",
        )

    assert (
        str(exc_info.value) == "stepfun_realtime_url_must_not_include_sensitive_query"
    )
    assert "query-secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_should_ignore_safe_close_errors_when_upstream_is_already_closed() -> (
    None
):
    transport = StepFunTransport()

    await transport.close(CloseRaisesRuntimeErrorWebSocket())


@pytest.mark.asyncio
async def test_should_fallback_to_send_when_upstream_has_no_send_json() -> None:
    transport = StepFunTransport()
    websocket = SendOnlyWebSocket()
    payload = {"type": "session.update", "session": {"voice": "demo"}}

    result = await transport.send_json(websocket, payload)

    assert result.status == StepFunSendStatus.SENT
    assert len(websocket.messages) == 1
    assert json.loads(websocket.messages[0]) == payload


@pytest.mark.asyncio
async def test_should_send_json_event_when_websocket_accepts_payload() -> None:
    transport = StepFunTransport()
    websocket = RecordingWebSocket()
    payload = {"type": "session.update"}

    result = await transport.send_json(websocket, payload)

    assert result.status == StepFunSendStatus.SENT
    assert websocket.messages == [payload]


@pytest.mark.asyncio
async def test_should_return_failed_send_result_when_websocket_send_errors() -> None:
    transport = StepFunTransport()

    result = await transport.send_json(
        SendRaisesOSErrorWebSocket(), {"type": "input_audio_buffer.append"}
    )

    assert result.status == StepFunSendStatus.FAILED
    assert result.error_type == "OSError"


@pytest.mark.asyncio
async def test_should_report_healthy_when_keepalive_ping_succeeds() -> None:
    transport = StepFunTransport()

    result = await transport.check_health(PongWebSocket())

    assert result.status == StepFunHealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_should_report_unhealthy_when_keepalive_ping_errors() -> None:
    transport = StepFunTransport()

    result = await transport.check_health(PingRaisesRuntimeErrorWebSocket())

    assert result.status == StepFunHealthStatus.UNHEALTHY
    assert result.error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_should_report_unhealthy_when_keepalive_ping_times_out() -> None:
    transport = StepFunTransport()

    result = await transport.check_health(SlowPongWebSocket(), timeout_seconds=0.001)

    assert result.status == StepFunHealthStatus.UNHEALTHY
    assert result.error_type == "TimeoutError"


def test_should_drop_audio_append_when_pending_bytes_exceed_backpressure_watermark() -> (
    None
):
    transport = StepFunTransport()
    payload = {"type": "input_audio_buffer.append", "audio": "..."}

    result = transport.decide_backpressure(
        payload,
        pending_bytes=1025,
        policy=StepFunBackpressurePolicy(high_watermark_bytes=1024),
    )

    assert result.status == StepFunBackpressureStatus.DROP


def test_resolve_stepfun_upstream_status_message_for_billing_errors() -> None:
    assert "402" in resolve_stepfun_upstream_status_message(402)
    assert "STEPFUN_API_KEY" in resolve_stepfun_upstream_status_message(401)


def test_build_session_update_payload_includes_required_modalities() -> None:
    payload = build_stepfun_session_update_payload(
        StepFunSessionConfig(
            voice="qingchunshaonv",
            temperature=0.7,
            input_audio_format="pcm16",
            output_audio_format="pcm16",
        )
    )

    assert payload["session"]["modalities"] == ["text", "audio"]


@pytest.mark.parametrize(
    "event_type",
    ["response.cancel", "input_audio_buffer.clear", "session.update"],
)
def test_should_allow_control_events_when_pending_bytes_exceed_backpressure_watermark(
    event_type: str,
) -> None:
    transport = StepFunTransport()

    result = transport.decide_backpressure(
        {"type": event_type},
        pending_bytes=2048,
        policy=StepFunBackpressurePolicy(high_watermark_bytes=1024),
    )

    assert result.status == StepFunBackpressureStatus.ALLOW
