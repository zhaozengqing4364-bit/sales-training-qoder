"""
Unit tests for presentation WebSocket message persistence behavior.
"""

import asyncio
import base64
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


def test_get_active_websocket_does_not_fallback_to_other_session(
    handler: PresentationWebSocketHandler,
):
    """A missing current session must not reuse another session websocket."""
    other_websocket = Mock()
    own_websocket = Mock()
    handler.session_id = "current-session"
    handler.websocket = own_websocket
    handler.manager.active_connections["presentation"]["other-session"] = (
        other_websocket
    )

    assert handler._get_active_websocket() is None


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
async def test_sync_lifecycle_transition_restores_page_context_on_start(
    handler: PresentationWebSocketHandler,
):
    """REST start/resume should rehydrate page context for cookie-auth flows."""
    handler._restore_page_context = AsyncMock()
    handler._stop_streaming_asr = AsyncMock()

    transition = SimpleNamespace(
        action="start",
        to_status="in_progress",
        ai_state="listening",
        scenario_type="presentation",
    )

    await handler.sync_lifecycle_transition(transition)

    assert handler.session_status == "in_progress"
    assert handler.ai_state == "listening"
    handler._restore_page_context.assert_awaited_once()
    handler._stop_streaming_asr.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_lifecycle_transition_stops_asr_on_pause(
    handler: PresentationWebSocketHandler,
):
    """REST pause/end should quiet the live ASR loop without replaying transcripts."""
    handler._restore_page_context = AsyncMock()
    handler._stop_streaming_asr = AsyncMock()

    transition = SimpleNamespace(
        action="pause",
        to_status="paused",
        ai_state="idle",
        scenario_type="presentation",
    )

    await handler.sync_lifecycle_transition(transition)

    assert handler.session_status == "paused"
    assert handler.ai_state == "idle"
    handler._restore_page_context.assert_not_awaited()
    handler._stop_streaming_asr.assert_awaited_once_with(process_transcript=False)


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
    handler.feedback_service.check_transcript = AsyncMock(return_value=Result.ok(None))
    handler._load_effective_ai_policy = AsyncMock(
        return_value={
            "fallback_config": {"enable_interruption_detector_fallback": True},
        }
    )

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
        analysis_data={
            "ai_feedback": "vague_response:有点模糊",
            "transcript_metadata": {"page_number": 2},
        },
    )
    handler._send_interruption.assert_awaited_once_with(decision)
    assert handler.transcript_buffer == ""


@pytest.mark.asyncio
async def test_update_message_analysis_passes_transcript_metadata_to_storage(
    handler: PresentationWebSocketHandler,
):
    """Legacy handler should persist current page metadata through storage.update_analysis."""
    storage = Mock()
    storage.update_analysis = AsyncMock(return_value=Result.ok(SimpleNamespace()))

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
        success = await handler._update_message_analysis(
            message_id="user-msg-002",
            analysis_data={
                "ai_feedback": "vague_response:有点模糊",
                "transcript_metadata": {"page_number": 3},
            },
        )

    assert success is True
    storage.update_analysis.assert_awaited_once_with(
        message_id="user-msg-002",
        fuzzy_words=None,
        transcript_metadata={"page_number": 3},
        sales_stage=None,
        score_snapshot=None,
        ai_feedback="vague_response:有点模糊",
    )


@pytest.mark.asyncio
async def test_check_and_interrupt_sends_chat_response_on_non_interrupt(
    handler: PresentationWebSocketHandler,
):
    """Non-interrupt turns should emit chat-visible acknowledgement."""
    handler.session_id = "session-ack-001"
    handler.current_page = 1
    handler.transcript_buffer = "这段讲解已经完成"
    handler.manager.active_connections["presentation"][handler.session_id] = Mock()
    handler.manager.send_json = AsyncMock()

    handler._initialize_page_feedback = AsyncMock()
    handler._save_conversation_message = AsyncMock(return_value="user-msg-ack")
    handler._load_effective_ai_policy = AsyncMock(
        return_value={
            "fallback_config": {"enable_interruption_detector_fallback": True},
        }
    )
    handler.feedback_service.check_transcript = AsyncMock(return_value=Result.ok(None))
    handler.interruption_detector.should_interrupt = AsyncMock(
        return_value=Result.ok(None)
    )

    coach_service = Mock()
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok(
            {
                "required_points": [],
                "forbidden_words": [],
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

    sent_types = [
        call.args[1]["type"] for call in handler.manager.send_json.await_args_list
    ]
    assert "response" in sent_types
    assert "feedback" not in sent_types
    assert sent_types[-1] == "status"


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
    """Page context should emit slide_update, points_reset, point_covered and status."""
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
    assert "points_reset" in sent_types
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
    handler.manager.active_connections["presentation"]["session-page-ctx-456"] = (
        websocket
    )
    handler.manager.send_json = AsyncMock()

    # Mock coach service
    coach_service = Mock()
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok(
            {
                "total_pages": 5,
                "page_content": "第二页内容",
                "required_points": ["痛点", "价值"],
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
        await handler._restore_page_context()

    # Verify coach service was called with correct parameters
    coach_service.get_current_page_requirements.assert_awaited_once_with(
        "session-page-ctx-456", 2
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


@pytest.mark.asyncio
async def test_handle_audio_chunk_decodes_base64_and_enqueues_audio(
    handler: PresentationWebSocketHandler,
):
    """Audio chunk should decode base64 payload and feed ASR queue."""
    audio_bytes = b"fake-pcm-data"
    handler._enqueue_audio_bytes = AsyncMock()

    await handler._handle_audio_chunk(
        {
            "audio": base64.b64encode(audio_bytes).decode("utf-8"),
        }
    )

    handler._enqueue_audio_bytes.assert_awaited_once_with(audio_bytes)


@pytest.mark.asyncio
async def test_send_point_updates_emits_frontend_contract_shape(
    handler: PresentationWebSocketHandler,
):
    """`point_covered` events should match frontend expected data keys."""
    websocket = Mock()
    handler.manager.send_json = AsyncMock()

    await handler._send_point_updates(
        websocket,
        [
            {
                "point_id": "session-1:1",
                "is_covered": True,
                "content": "客户痛点",
            },
            {
                "point_id": "session-1:2",
                "is_covered": False,
                "content": "解决方案",
            },
        ],
    )

    assert handler.manager.send_json.await_count == 2
    first_payload = handler.manager.send_json.await_args_list[0].args[1]["data"]
    assert first_payload["point_id"] == "session-1:1"
    assert first_payload["is_covered"] is True
    assert first_payload["content"] == "客户痛点"


@pytest.mark.asyncio
async def test_send_point_updates_replace_existing_emits_reset_event(
    handler: PresentationWebSocketHandler,
):
    """replace_existing should emit explicit reset signal for point state."""
    websocket = Mock()
    handler.manager.send_json = AsyncMock()

    await handler._send_point_updates(
        websocket,
        [],
        replace_existing=True,
    )

    sent_types = [
        call.args[1]["type"] for call in handler.manager.send_json.await_args_list
    ]
    assert sent_types == ["points_reset"]


@pytest.mark.asyncio
async def test_handle_audio_end_preserves_short_recognized_transcript(
    handler: PresentationWebSocketHandler,
):
    """Short utterances with transcript should still reach interruption checks."""
    handler.audio_buffer_size = handler.MIN_AUDIO_SIZE - 1
    handler.current_transcript = "好的"
    handler.transcript_buffer = ""
    handler.asr_queue = asyncio.Queue()
    handler._check_and_interrupt = AsyncMock()

    await handler._handle_audio_end()

    handler._check_and_interrupt.assert_awaited_once()
    assert handler.transcript_buffer == "好的"


@pytest.mark.asyncio
async def test_handle_message_routes_interrupt_and_control(
    handler: PresentationWebSocketHandler,
):
    """Message router should delegate interrupt/control payloads."""
    handler._handle_interrupt = AsyncMock()
    handler._handle_control = AsyncMock()

    await handler.handle_message(
        {
            "type": "interrupt",
            "data": {"reason": "user_speaking"},
        }
    )
    await handler.handle_message(
        {
            "type": "control",
            "data": {"action": "pause"},
        }
    )

    handler._handle_interrupt.assert_awaited_once_with("user_speaking")
    handler._handle_control.assert_awaited_once_with("pause")


@pytest.mark.asyncio
async def test_handle_interrupt_emits_interrupted_and_status(
    handler: PresentationWebSocketHandler,
):
    """Interrupt should stop AI speaking and emit contract events."""
    websocket = Mock()
    handler.session_id = "session-interrupt-001"
    handler.session_status = "in_progress"
    handler.turn_count = 3
    handler.is_ai_speaking = True
    handler.manager.active_connections["presentation"][handler.session_id] = websocket
    handler.manager.send_json = AsyncMock()

    await handler._handle_interrupt("user_speaking")

    assert handler.is_ai_speaking is False
    sent_messages = [call.args[1] for call in handler.manager.send_json.await_args_list]
    message_types = [message["type"] for message in sent_messages]
    assert message_types == ["interrupted", "status"]
    interrupted_payload = sent_messages[0]["data"]
    assert interrupted_payload["reason"] == "user_speaking"
    assert interrupted_payload["ai_state"] == "listening"


@pytest.mark.asyncio
async def test_handle_control_start_success_updates_status(
    handler: PresentationWebSocketHandler,
):
    """Control start should call service and move session to in_progress."""
    handler.session_id = "session-control-start-001"
    handler._send_status = AsyncMock()

    coach_service = Mock()
    coach_service.start_session = AsyncMock(return_value=Result.ok({}))

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
        await handler._handle_control("start")

    coach_service.start_session.assert_awaited_once_with("session-control-start-001")
    assert handler.session_status == "in_progress"
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_handle_control_end_success_calls_session_end(
    handler: PresentationWebSocketHandler,
):
    """Control end should complete session and emit session end workflow."""
    handler.session_id = "session-control-end-001"
    handler._handle_session_end = AsyncMock()

    coach_service = Mock()
    coach_service.end_session = AsyncMock(return_value=Result.ok({}))

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
        await handler._handle_control("end")

    coach_service.end_session.assert_awaited_once_with("session-control-end-001")
    assert handler.session_status == "completed"
    handler._handle_session_end.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_interrupt_cancels_active_tts_task_and_emits_stream_id(
    handler: PresentationWebSocketHandler,
):
    websocket = Mock()
    handler.session_id = "session-interrupt-stream-001"
    handler.session_status = "in_progress"
    handler.turn_count = 4
    handler.is_ai_speaking = True
    handler.current_stream_id = "stream-001"
    handler.manager.active_connections["presentation"][handler.session_id] = websocket
    handler.manager.send_json = AsyncMock()

    async def _pending_tts():
        while True:
            await asyncio.sleep(0.1)

    tts_task = asyncio.create_task(_pending_tts())
    handler._tts_task = tts_task

    try:
        await handler._handle_interrupt("user_speaking")
    finally:
        if not tts_task.done():
            tts_task.cancel()
            try:
                await tts_task
            except asyncio.CancelledError:
                pass

    assert tts_task.cancelled()
    interrupted_payload = handler.manager.send_json.await_args_list[0].args[1]
    assert interrupted_payload["type"] == "interrupted"
    assert interrupted_payload["stream_id"] == "stream-001"


@pytest.mark.asyncio
async def test_handle_control_start_sends_initial_page_context(
    handler: PresentationWebSocketHandler,
):
    websocket = Mock()
    handler.session_id = "session-control-start-context-001"
    handler.current_page = 1
    handler.manager.active_connections["presentation"][handler.session_id] = websocket
    handler._send_status = AsyncMock()
    handler._send_page_context = AsyncMock()
    handler._initialize_page_feedback = AsyncMock()

    coach_service = Mock()
    coach_service.start_session = AsyncMock(return_value=Result.ok({}))
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok(
            {
                "total_pages": 6,
                "page_content": "第一页内容",
                "required_points": ["客户背景", "产品价值"],
                "forbidden_words": ["大概"],
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
        await handler._handle_control("start")

    coach_service.start_session.assert_awaited_once_with(
        "session-control-start-context-001"
    )
    coach_service.get_current_page_requirements.assert_awaited_once_with(
        "session-control-start-context-001",
        1,
    )
    handler._initialize_page_feedback.assert_awaited_once_with(
        session_id="session-control-start-context-001",
        page_number=1,
        requirements={
            "total_pages": 6,
            "page_content": "第一页内容",
            "required_points": ["客户背景", "产品价值"],
            "forbidden_words": ["大概"],
        },
    )
    handler._send_page_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_control_start_emits_slide_update_and_status_contract(
    handler: PresentationWebSocketHandler,
):
    """Start control should emit slide_update/points_reset/point_covered/status."""
    websocket = Mock()
    handler.session_id = "session-control-start-contract-001"
    handler.current_page = 2
    handler.manager.active_connections["presentation"][handler.session_id] = websocket
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()

    coach_service = Mock()
    coach_service.start_session = AsyncMock(return_value=Result.ok({}))
    coach_service.get_current_page_requirements = AsyncMock(
        return_value=Result.ok(
            {
                "total_pages": 8,
                "page_content": "第二页：价值主张",
                "required_points": ["客户痛点", "业务价值"],
                "forbidden_words": ["可能"],
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
        await handler._handle_control("start")

    sent_messages = [call.args[1] for call in handler.manager.send_json.await_args_list]
    sent_types = [payload["type"] for payload in sent_messages]

    assert sent_types == [
        "slide_update",
        "points_reset",
        "point_covered",
        "point_covered",
        "status",
    ]
    slide_payload = sent_messages[0]["data"]
    assert slide_payload["current_page"] == 2
    assert slide_payload["page_number"] == 2
    assert slide_payload["total_pages"] == 8
    assert slide_payload["content"] == "第二页：价值主张"
    assert slide_payload["page_content"] == "第二页：价值主张"

    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_handle_control_start_allows_non_awaitable_requirements(
    handler: PresentationWebSocketHandler,
):
    """Start control should not fail when requirements method returns plain Mock."""
    handler.session_id = "session-control-start-non-awaitable-001"
    handler._send_status = AsyncMock()
    handler._send_page_context = AsyncMock()
    handler._initialize_page_feedback = AsyncMock()

    coach_service = Mock()
    coach_service.start_session = AsyncMock(return_value=Result.ok({}))
    coach_service.get_current_page_requirements = Mock(return_value=Mock())

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
        await handler._handle_control("start")

    coach_service.start_session.assert_awaited_once_with(
        "session-control-start-non-awaitable-001"
    )
    coach_service.get_current_page_requirements.assert_called_once_with(
        "session-control-start-non-awaitable-001",
        1,
    )
    handler._initialize_page_feedback.assert_not_awaited()
    handler._send_page_context.assert_not_awaited()
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_handle_message_heartbeat_ack_is_noop(
    handler: PresentationWebSocketHandler,
):
    handler._touch_session_activity = AsyncMock()
    handler._handle_audio_chunk = AsyncMock()
    handler._handle_control = AsyncMock()

    await handler.handle_message(
        {
            "type": "heartbeat_ack",
            "data": {"client_ts": "2026-02-15T00:00:00Z"},
        }
    )

    handler._touch_session_activity.assert_awaited_once()
    handler._handle_audio_chunk.assert_not_called()
    handler._handle_control.assert_not_called()


@pytest.mark.asyncio
async def test_handle_binary_interrupt_frame_without_audio_payload(
    handler: PresentationWebSocketHandler,
):
    handler._handle_interrupt = AsyncMock()
    handler._enqueue_audio_bytes = AsyncMock()

    await handler._handle_binary_frame(bytes([handler.BINARY_AUDIO_INTERRUPT]))

    handler._handle_interrupt.assert_awaited_once_with("user_speaking")
    handler._enqueue_audio_bytes.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_audio_bytes_emits_backpressure_slow_down(
    handler: PresentationWebSocketHandler,
):
    handler.asr_queue = asyncio.Queue(maxsize=handler.ASR_QUEUE_MAX_SIZE)
    for _ in range(handler.ASR_HIGH_WATERMARK):
        handler.asr_queue.put_nowait(b"x")
    handler._send_backpressure = AsyncMock()

    await handler._enqueue_audio_bytes(b"payload")

    handler._send_backpressure.assert_awaited_once_with(
        "slow_down",
        handler.ASR_HIGH_WATERMARK,
    )
    assert handler._backpressure_active is True


@pytest.mark.asyncio
async def test_enqueue_audio_bytes_emits_backpressure_resume(
    handler: PresentationWebSocketHandler,
):
    handler.asr_queue = asyncio.Queue(maxsize=handler.ASR_QUEUE_MAX_SIZE)
    for _ in range(handler.ASR_LOW_WATERMARK):
        handler.asr_queue.put_nowait(b"x")
    handler._backpressure_active = True
    handler._send_backpressure = AsyncMock()

    await handler._enqueue_audio_bytes(b"payload")

    handler._send_backpressure.assert_awaited_once_with(
        "resume",
        handler.ASR_LOW_WATERMARK,
    )
    assert handler._backpressure_active is False
