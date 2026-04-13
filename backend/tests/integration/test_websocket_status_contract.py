"""Integration tests for unified websocket status/event contract."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.auth.service import get_session_cookie_name, resolve_websocket_auth
from common.websocket.session_manager import SessionManager
from common.websocket.session_state_service import SessionStateService, SessionStateSnapshot
from presentation_coach.websocket.presentation_handler import PresentationWebSocketHandler
from sales_bot.websocket.simple_handler import SimpleSalesHandler
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def ping(self) -> None:
        return None


def test_websocket_auth_prefers_session_cookie_before_query_token_compatibility():
    cookie_name = get_session_cookie_name()
    resolution = resolve_websocket_auth(
        query_token="query-token",
        authorization_header="",
        cookie_header=f"{cookie_name}=cookie-token",
    )

    assert resolution["token"] == "cookie-token"
    assert resolution["transport"] == "session_cookie"
    assert resolution["compatibility_mode"] is False


def test_websocket_query_token_is_marked_as_compatibility_transport():
    resolution = resolve_websocket_auth(
        query_token="query-token",
        authorization_header="",
        cookie_header="",
    )

    assert resolution["token"] == "query-token"
    assert resolution["transport"] == "query_token"
    assert resolution["compatibility_mode"] is True


@pytest.mark.asyncio
async def test_session_manager_stats_surface_process_local_runtime_visibility() -> None:
    manager = SessionManager(timeout_seconds=120, heartbeat_interval=15)
    handler = StepFunRealtimeHandler()
    handler.session_status = "paused"
    handler.ai_state = "idle"
    handler.current_request_id = 4
    handler._connection_epoch = 2
    handler._record_disconnect_reason("upstream_disconnect")
    handler._record_runtime_error("[STEPFUN_UPSTREAM_ERROR]", "上游连接异常")

    await manager.register_session("session-visibility-001", handler, user_id="user-1")

    stats = manager.get_stats()
    tracked = stats["tracked_sessions"][0]

    assert stats["connection_visibility"] == {
        "scope": "process_local",
        "shared_across_instances": False,
        "survives_restart": False,
        "running": False,
    }
    assert tracked["session_id"] == "session-visibility-001"
    assert tracked["session_status"] == "paused"
    assert tracked["ai_state"] == "idle"
    assert tracked["runtime_diagnostics"]["session_status"] == "paused"
    assert tracked["runtime_diagnostics"]["ai_state"] == "idle"
    assert tracked["runtime_diagnostics"]["reconnect_state"] == {
        "connection_epoch": 2,
        "request_epoch": 4,
        "last_disconnect_reason": "upstream_disconnect",
        "last_error": {
            "code": "[STEPFUN_UPSTREAM_ERROR]",
            "message": "上游连接异常",
        },
    }


@pytest.mark.asyncio
async def test_session_state_service_stats_surface_snapshot_reconnect_signals() -> None:
    service = SessionStateService(state_ttl=600, cleanup_interval=30, key_prefix="ws:test:")
    service._redis = _FakeRedis()
    service._running = True

    snapshot = SessionStateSnapshot(
        session_id="session-snapshot-visibility-001",
        scenario="sales",
        turn_count=3,
        current_page=7,
        session_status="paused",
        ai_state="idle",
        runtime_state={
            "current_request_id": 4,
            "reconnect_state": {
                "connection_epoch": 2,
                "request_epoch": 4,
                "last_disconnect_reason": "upstream_disconnect",
                "last_error": {
                    "code": "[STEPFUN_UPSTREAM_ERROR]",
                    "message": "上游连接异常",
                },
            },
        },
        user_id="user-visibility",
    )

    save_result = await service.save_state(snapshot)
    assert save_result.is_success

    stats = service.get_stats()
    assert stats["last_saved_snapshot"] == {
        "session_id": "session-snapshot-visibility-001",
        "scenario": "sales",
        "turn_count": 3,
        "current_page": 7,
        "session_status": "paused",
        "ai_state": "idle",
        "user_id": "user-visibility",
        "last_activity": snapshot.last_activity,
        "runtime_keys": ["current_request_id", "reconnect_state"],
        "request_epoch": 4,
        "connection_epoch": 2,
        "last_disconnect_reason": "upstream_disconnect",
        "last_error": {
            "code": "[STEPFUN_UPSTREAM_ERROR]",
            "message": "上游连接异常",
        },
        "reconnect_state": {
            "connection_epoch": 2,
            "request_epoch": 4,
            "last_disconnect_reason": "upstream_disconnect",
            "last_error": {
                "code": "[STEPFUN_UPSTREAM_ERROR]",
                "message": "上游连接异常",
            },
        },
    }


@pytest.mark.asyncio
async def test_simple_handler_status_includes_trace_and_core_fields():
    """`status` must include trace_id + stable lifecycle fields."""
    handler = SimpleSalesHandler()
    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_status = "in_progress"
    handler.turn_count = 3

    await handler._send_status("thinking")

    sent = handler.manager.send_json.call_args[0][1]
    assert sent["type"] == "status"
    assert sent.get("trace_id")
    assert sent["data"]["session_status"] == "in_progress"
    assert sent["data"]["ai_state"] == "thinking"
    assert sent["data"]["turn_count"] == 3


@pytest.mark.asyncio
async def test_simple_handler_error_includes_trace_and_state_context():
    """`error` should include trace_id + lifecycle context for observability."""
    handler = SimpleSalesHandler()
    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_status = "paused"
    handler.turn_count = 7

    await handler._send_error("[PROCESSING_ERROR]", "处理失败")

    sent = handler.manager.send_json.call_args[0][1]
    assert sent["type"] == "error"
    assert sent.get("trace_id")
    assert sent["data"]["code"] == "[PROCESSING_ERROR]"
    assert sent["data"]["session_status"] == "paused"
    assert sent["data"]["ai_state"] == "idle"
    assert sent["data"]["turn_count"] == 7


@pytest.mark.asyncio
async def test_stepfun_handler_status_and_error_include_trace_id():
    """StepFun handler must keep status/error envelope aligned with legacy handler."""
    handler = StepFunRealtimeHandler()
    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_status = "in_progress"
    handler.turn_count = 11

    await handler._send_status("listening")
    status_sent = handler.manager.send_json.call_args[0][1]
    assert status_sent["type"] == "status"
    assert status_sent.get("trace_id")
    assert status_sent["data"]["session_status"] == "in_progress"
    assert status_sent["data"]["ai_state"] == "listening"
    assert status_sent["data"]["turn_count"] == 11

    handler.manager.send_json.reset_mock()
    await handler._send_error("[STEPFUN_UPSTREAM_ERROR]", "上游连接异常")
    error_sent = handler.manager.send_json.call_args[0][1]
    assert error_sent["type"] == "error"
    assert error_sent.get("trace_id")
    assert error_sent["data"]["session_status"] == "in_progress"
    assert error_sent["data"]["ai_state"] == handler.ai_state
    assert error_sent["data"]["turn_count"] == 11

    reconnect_state = handler.get_runtime_diagnostics()["reconnect_state"]
    diagnostics = handler.get_runtime_diagnostics()
    assert diagnostics["session_status"] == "in_progress"
    assert diagnostics["ai_state"] == handler.ai_state
    assert reconnect_state["connection_epoch"] == 0
    assert reconnect_state["request_epoch"] == 0
    assert reconnect_state["last_disconnect_reason"] is None
    assert reconnect_state["last_error"] == {
        "code": "[STEPFUN_UPSTREAM_ERROR]",
        "message": "上游连接异常",
    }


@pytest.mark.asyncio
async def test_stepfun_handler_session_timeout_event_includes_restore_context():
    """Timeout events should expose enough state to explain why recovery is blocked."""
    handler = StepFunRealtimeHandler()
    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.turn_count = 4

    await handler.send_message(
        {
            "type": "session_timeout",
            "timestamp": "2026-03-22T16:00:00+00:00",
            "data": {
                "message": "会话超时，请重新开始",
                "inactive_duration": 1810,
                "timeout_seconds": 1800,
            },
        }
    )

    timeout_sent = handler.manager.send_json.call_args[0][1]
    assert timeout_sent["type"] == "session_timeout"
    assert timeout_sent["data"]["session_status"] == "in_progress"
    assert timeout_sent["data"]["ai_state"] == "listening"
    assert timeout_sent["data"]["turn_count"] == 4
    assert timeout_sent["data"]["disconnect_reason"] == "session_timeout"


@pytest.mark.asyncio
async def test_presentation_handler_status_error_and_session_end_include_trace_id():
    """Presentation handler must expose the same observability fields."""
    with (
        patch("presentation_coach.websocket.presentation_handler.get_asr_service", return_value=MagicMock()),
        patch("presentation_coach.websocket.presentation_handler.get_tts_service", return_value=MagicMock()),
        patch(
            "presentation_coach.websocket.presentation_handler.get_interruption_detector",
            return_value=MagicMock(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.get_forbidden_matcher",
            return_value=MagicMock(),
        ),
    ):
        handler = PresentationWebSocketHandler()

    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_id = "session-xyz"
    handler.session_status = "scoring"
    handler.turn_count = 5

    await handler._send_status("idle")
    status_sent = handler.manager.send_json.call_args[0][1]
    assert status_sent["type"] == "status"
    assert status_sent.get("trace_id")
    assert status_sent["data"]["session_status"] == "scoring"
    assert status_sent["data"]["ai_state"] == "idle"
    assert status_sent["data"]["turn_count"] == 5

    handler.manager.send_json.reset_mock()
    await handler._send_error("[PRESENTATION_ERROR]", "演练异常")
    error_sent = handler.manager.send_json.call_args[0][1]
    assert error_sent["type"] == "error"
    assert error_sent.get("trace_id")
    assert error_sent["data"]["session_status"] == "scoring"
    assert error_sent["data"]["ai_state"] == "idle"
    assert error_sent["data"]["turn_count"] == 5

    handler.manager.send_json.reset_mock()
    await handler._handle_session_end()
    ended_sent = handler.manager.send_json.call_args[0][1]
    assert ended_sent["type"] == "session_ended"
    assert ended_sent.get("trace_id")
    assert ended_sent["data"]["session_status"] == "scoring"
    assert ended_sent["data"]["turn_count"] == 5


@pytest.mark.asyncio
async def test_presentation_page_context_status_syncs_handler_ai_state():
    """`_send_page_context` should keep handler ai_state consistent with emitted status."""
    with (
        patch("presentation_coach.websocket.presentation_handler.get_asr_service", return_value=MagicMock()),
        patch("presentation_coach.websocket.presentation_handler.get_tts_service", return_value=MagicMock()),
        patch(
            "presentation_coach.websocket.presentation_handler.get_interruption_detector",
            return_value=MagicMock(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.get_forbidden_matcher",
            return_value=MagicMock(),
        ),
    ):
        handler = PresentationWebSocketHandler()

    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_point_updates = AsyncMock()  # type: ignore[method-assign]
    handler.session_status = "in_progress"
    handler.turn_count = 2

    ws = AsyncMock()
    await handler._send_page_context(
        ws=ws,
        page_number=3,
        requirements={
            "total_pages": 9,
            "page_content": "demo",
            "required_points": [],
        },
    )

    status_event = handler.manager.send_json.call_args_list[-1][0][1]
    assert status_event["type"] == "status"
    assert status_event["data"]["ai_state"] == "listening"
    assert handler.ai_state == "listening"
