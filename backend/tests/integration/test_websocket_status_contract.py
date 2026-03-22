"""Integration tests for unified websocket status/event contract."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from presentation_coach.websocket.presentation_handler import PresentationWebSocketHandler
from sales_bot.websocket.simple_handler import SimpleSalesHandler
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


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
