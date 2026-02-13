"""
Unit tests for presentation WebSocket message persistence behavior.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from presentation_coach.websocket.presentation_handler import (
    PresentationWebSocketHandler,
)


class _FakeSessionFactory:
    """Async context manager compatible with AsyncSessionLocal usage."""

    def __call__(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def handler() -> PresentationWebSocketHandler:
    """Create handler with mocked ASR/TTS dependencies."""
    with (
        patch(
            "presentation_coach.websocket.presentation_handler.get_asr_service",
            return_value=Mock(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.get_tts_service",
            return_value=Mock(),
        ),
    ):
        instance = PresentationWebSocketHandler()

    original_send_json = instance.manager.send_json
    instance.manager.active_connections["presentation"].clear()
    instance.manager.active_connections["sales"].clear()

    yield instance

    instance.manager.active_connections["presentation"].clear()
    instance.manager.active_connections["sales"].clear()
    instance.manager.send_json = original_send_json


@pytest.mark.asyncio
async def test_save_conversation_message_tracks_turns(
    handler: PresentationWebSocketHandler,
):
    """User message increments turn; assistant reply reuses current turn."""
    handler.session_id = "session-123"

    storage = Mock()
    storage.save_message = AsyncMock(
        side_effect=[
            Result.ok(SimpleNamespace(id="user-msg-id")),
            Result.ok(SimpleNamespace(id="assistant-msg-id")),
        ]
    )

    with (
        patch(
            "presentation_coach.websocket.presentation_handler.AsyncSessionLocal",
            _FakeSessionFactory(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.MessageStorageService",
            return_value=storage,
        ),
    ):
        user_message_id = await handler._save_conversation_message(
            role="user",
            content="用户发言",
        )
        assistant_message_id = await handler._save_conversation_message(
            role="assistant",
            content="AI 反馈",
        )

    assert user_message_id == "user-msg-id"
    assert assistant_message_id == "assistant-msg-id"
    assert handler.turn_count == 1

    first_call = storage.save_message.await_args_list[0].kwargs
    second_call = storage.save_message.await_args_list[1].kwargs
    assert first_call["turn_number"] == 1
    assert first_call["role"] == "user"
    assert second_call["turn_number"] == 1
    assert second_call["role"] == "assistant"


@pytest.mark.asyncio
async def test_check_and_interrupt_updates_user_feedback(
    handler: PresentationWebSocketHandler,
):
    """Interrupt decision writes AI feedback into persisted user message."""
    handler.session_id = "session-456"
    handler.current_page = 2
    handler.transcript_buffer = "这段表达有点模糊"
    handler.manager.active_connections["presentation"]["session-456"] = Mock()

    decision = {"type": "vague_response", "trigger": "有点模糊"}
    handler.interruption_detector.should_interrupt = AsyncMock(
        return_value=Result.ok(decision)
    )

    handler._save_conversation_message = AsyncMock(return_value="user-msg-001")
    handler._update_message_analysis = AsyncMock()
    handler._send_interruption = AsyncMock()

    coach_service = Mock()
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok(
            {
                "required_points": ["痛点", "价值"],
                "forbidden_words": ["大概", "可能"],
            }
        )
    )

    with (
        patch(
            "presentation_coach.websocket.presentation_handler.AsyncSessionLocal",
            _FakeSessionFactory(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationCoachService",
            return_value=coach_service,
        ),
    ):
        await handler._check_and_interrupt()

    handler._save_conversation_message.assert_awaited_once_with(
        role="user",
        content="这段表达有点模糊",
    )
    handler._update_message_analysis.assert_awaited_once_with(
        message_id="user-msg-001",
        analysis_data={"ai_feedback": "vague_response:有点模糊"},
    )
    handler._send_interruption.assert_awaited_once_with(decision)
    assert handler.transcript_buffer == ""


@pytest.mark.asyncio
async def test_handle_message_accepts_legacy_page_payload(
    handler: PresentationWebSocketHandler,
):
    """`page_change` should accept legacy `{page: n}` payloads."""
    handler._handle_page_change = AsyncMock()

    await handler.handle_message(
        {
            "type": "page_change",
            "data": {"page": 3},
        }
    )

    handler._handle_page_change.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_handle_message_accepts_page_number_payload(
    handler: PresentationWebSocketHandler,
):
    """`page_change` should accept current `{page_number: n}` payloads."""
    handler._handle_page_change = AsyncMock()

    await handler.handle_message(
        {
            "type": "page_change",
            "data": {"page_number": 4},
        }
    )

    handler._handle_page_change.assert_awaited_once_with(4)


@pytest.mark.asyncio
async def test_handle_message_rejects_invalid_page_payload(
    handler: PresentationWebSocketHandler,
):
    """Invalid `page_change` payload should be ignored safely."""
    handler._handle_page_change = AsyncMock()

    await handler.handle_message(
        {
            "type": "page_change",
            "data": {"page_number": "invalid"},
        }
    )

    handler._handle_page_change.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_realtime_feedback_forbidden_word_emits_two_events(
    handler: PresentationWebSocketHandler,
):
    """Forbidden word feedback should emit feedback + forbidden_word events."""
    websocket = Mock()
    handler.manager.active_connections["presentation"]["session-789"] = websocket
    handler.manager.send_json = AsyncMock()

    await handler._send_realtime_feedback(
        {
            "type": "forbidden_word",
            "trigger": "大概",
            "reason": "请避免模糊表达",
        }
    )

    sent_types = [
        call.args[1]["type"] for call in handler.manager.send_json.await_args_list
    ]
    assert "feedback" in sent_types
    assert "forbidden_word" in sent_types


@pytest.mark.asyncio
async def test_send_page_context_emits_slide_and_point_updates(
    handler: PresentationWebSocketHandler,
):
    """Page context should emit slide_update, point_covered and status events."""
    websocket = Mock()
    handler.manager.active_connections["presentation"]["session-ctx"] = websocket
    handler.manager.send_json = AsyncMock()

    await handler._send_page_context(
        ws=websocket,
        page_number=2,
        requirements={
            "total_pages": 6,
            "page_content": "第二页内容",
            "required_points": ["客户痛点", "解决方案"],
        },
    )

    sent_types = [
        call.args[1]["type"] for call in handler.manager.send_json.await_args_list
    ]
    assert "slide_update" in sent_types
    assert "point_covered" in sent_types
    assert "status" in sent_types


@pytest.mark.asyncio
async def test_reconnection_restores_session_state(
    handler: PresentationWebSocketHandler,
):
    """Reconnection restores session state from snapshot."""
    handler.session_id = "session-reconnect-123"
    handler.turn_count = 5
    handler.current_page = 3
    handler.session_status = "in_progress"
    handler.ai_state = "listening"

    # Create a state snapshot
    state = SessionStateSnapshot(
        session_id="session-reconnect-123",
        scenario="presentation",
        turn_count=5,
        current_page=3,
        session_status="in_progress",
        ai_state="listening",
        user_id="user-123",
    )

    # Mock the send_reconnection_success and restore_page_context methods
    handler._send_reconnection_success = AsyncMock()
    handler._restore_page_context = AsyncMock()

    # Restore state
    await handler._restore_session_state(state)

    # Verify state is restored
    assert handler.turn_count == 5
    assert handler.current_page == 3
    assert handler.session_status == "in_progress"
    assert handler.ai_state == "listening"

    # Verify reconnection success was sent
    handler._send_reconnection_success.assert_awaited_once_with(state)

    # Verify page context was restored
    handler._restore_page_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnection_restores_page_context(
    handler: PresentationWebSocketHandler,
):
    """Reconnection restores page context by sending current page requirements."""
    handler.session_id = "session-page-ctx-456"
    handler.current_page = 2
    handler.turn_count = 3

    websocket = Mock()
    handler.manager.active_connections["presentation"]["session-page-ctx-456"] = websocket
    handler.manager.send_json = AsyncMock()

    # Mock coach service
    coach_service = Mock()
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok({
            "total_pages": 5,
            "page_content": "第二页内容",
            "required_points": ["痛点", "价值"],
        })
    )

    with (
        patch(
            "presentation_coach.websocket.presentation_handler.AsyncSessionLocal",
            _FakeSessionFactory(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationCoachService",
            return_value=coach_service,
        ),
    ):
        await handler._restore_page_context()

    # Verify coach service was called with correct parameters
    coach_service.get_current_page_requirements.assert_awaited_once_with(
        "session-page-ctx-456",
        2
    )

    # Verify page context was sent
    sent_messages = [call.args[1] for call in handler.manager.send_json.await_args_list]
    message_types = [msg["type"] for msg in sent_messages]

    assert "slide_update" in message_types
    assert "point_covered" in message_types
    assert "status" in message_types


@pytest.mark.asyncio
async def test_reconnection_handles_missing_page_context_gracefully(
    handler: PresentationWebSocketHandler,
):
    """Reconnection handles missing page context gracefully without errors."""
    handler.session_id = "session-no-ctx-789"
    handler.current_page = 1

    # Mock coach service returning failure
    coach_service = Mock()
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.fail("[PAGE_NOT_FOUND] Page not found")
    )

    with (
        patch(
            "presentation_coach.websocket.presentation_handler.AsyncSessionLocal",
            _FakeSessionFactory(),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationCoachService",
            return_value=coach_service,
        ),
    ):
        # Should not raise exception
        await handler._restore_page_context()


@pytest.mark.asyncio
async def test_reconnection_handles_no_active_websocket_gracefully(
    handler: PresentationWebSocketHandler,
):
    """Reconnection handles missing active websocket gracefully."""
    handler.session_id = "session-no-ws-000"
    handler.current_page = 1

    # No active connection - should log warning and return
    with (
        patch(
            "presentation_coach.websocket.presentation_handler.AsyncSessionLocal",
            _FakeSessionFactory(),
        ),
    ):
        # Should not raise exception
        await handler._restore_page_context()


@pytest.mark.asyncio
async def test_restore_session_state_handles_none_values(
    handler: PresentationWebSocketHandler,
):
    """Restore session state handles None values with defaults."""
    handler.session_id = "session-null-111"

    # Create state with None values
    state = SessionStateSnapshot(
        session_id="session-null-111",
        scenario="presentation",
        turn_count=0,
        current_page=None,
        session_status="in_progress",
        ai_state=None,
    )

    handler._send_reconnection_success = AsyncMock()
    handler._restore_page_context = AsyncMock()

    await handler._restore_session_state(state)

    # Verify defaults are applied
    assert handler.current_page == 1  # Default to 1
    assert handler.ai_state == "idle"  # Default to "idle"
