"""Unit tests for StepFun realtime session persistence and recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


def test_create_state_snapshot_captures_minimal_runtime_recovery_fields() -> None:
    """Sales StepFun snapshots should carry reconnect-safe runtime context only."""
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stepfun-save-001"
    handler.user_id = "user-stepfun-save-001"
    handler.turn_count = 4
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.current_request_id = 9
    handler._last_emitted_stage = "discovery"
    handler._latest_score_snapshot = {"overall_score": 86.0}
    handler._latest_action_card = {"title": "先确认预算"}

    snapshot = handler._create_state_snapshot()

    assert snapshot.session_id == "session-stepfun-save-001"
    assert snapshot.scenario == "sales"
    assert snapshot.turn_count == 4
    assert snapshot.session_status == "in_progress"
    assert snapshot.ai_state == "listening"
    assert snapshot.user_id == "user-stepfun-save-001"
    assert snapshot.runtime_state == {
        "current_request_id": 9,
        "last_emitted_stage": "discovery",
        "latest_score_snapshot": {"overall_score": 86.0},
        "latest_action_card": {"title": "先确认预算"},
    }

    handler._latest_score_snapshot["overall_score"] = 20.0
    assert snapshot.runtime_state["latest_score_snapshot"]["overall_score"] == 86.0


@pytest.mark.asyncio
async def test_restore_session_state_rehydrates_minimal_runtime_and_emits_reconnected() -> None:
    """Reconnect should restore only the safe runtime subset and notify frontend."""
    handler = StepFunRealtimeHandler()
    handler._send_reconnection_success = AsyncMock()
    handler._active_response = object()
    handler._pending_grounding_context = "stale grounding"
    handler._pending_blocked_response_text = "stale blocked"
    handler._pending_tool_followup_response = True
    handler._awaiting_transcription_after_commit = True
    handler._has_uncommitted_audio = True

    state = SessionStateSnapshot(
        session_id="session-stepfun-restore-001",
        scenario="sales",
        turn_count=5,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "current_request_id": 6,
            "last_emitted_stage": "qualification",
            "latest_score_snapshot": {"overall_score": 91.0},
            "latest_action_card": {"title": "先确认关键需求"},
        },
    )

    await handler._restore_session_state(state)

    assert handler.turn_count == 5
    assert handler.session_status == "in_progress"
    assert handler.ai_state == "listening"
    assert handler.current_request_id == 6
    assert handler._last_emitted_stage == "qualification"
    assert handler._latest_score_snapshot == {"overall_score": 91.0}
    assert handler._latest_action_card == {"title": "先确认关键需求"}
    assert handler._active_response is None
    assert handler._pending_grounding_context == ""
    assert handler._pending_blocked_response_text == ""
    assert handler._pending_tool_followup_response is False
    assert handler._awaiting_transcription_after_commit is False
    assert handler._has_uncommitted_audio is False
    handler._send_reconnection_success.assert_awaited_once_with(state)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("session_status", "timeout_requested"),
    [
        ("scoring", False),
        ("completed", False),
        ("in_progress", True),
    ],
)
async def test_save_session_state_deletes_dirty_snapshots_for_terminal_or_timeout_disconnects(
    session_status: str,
    timeout_requested: bool,
) -> None:
    """Terminal and timeout exits should not leave reconnectable junk snapshots."""
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stepfun-cleanup-001"
    handler.session_status = session_status
    handler._timeout_disconnect_requested = timeout_requested
    handler.state_service = MagicMock()
    handler.state_service.save_state = AsyncMock(return_value=Result.ok(None))
    handler.state_service.delete_state = AsyncMock(return_value=Result.ok(None))

    await handler._save_session_state()

    handler.state_service.delete_state.assert_awaited_once_with(
        "session-stepfun-cleanup-001"
    )
    handler.state_service.save_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_enriches_session_timeout_event_with_recovery_diagnostics() -> None:
    """Timeout notifications should expose reconnect context instead of a bare generic message."""
    handler = StepFunRealtimeHandler()
    handler.websocket = AsyncMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.turn_count = 6

    await handler.send_message(
        {
            "type": "session_timeout",
            "timestamp": "2026-03-22T16:00:00+00:00",
            "data": {
                "message": "会话超时，请重新开始",
                "inactive_duration": 1900,
                "timeout_seconds": 1800,
            },
        }
    )

    sent = handler.manager.send_json.await_args_list[0].args[1]
    assert sent["type"] == "session_timeout"
    assert sent["data"]["session_status"] == "in_progress"
    assert sent["data"]["ai_state"] == "listening"
    assert sent["data"]["turn_count"] == 6
    assert sent["data"]["disconnect_reason"] == "session_timeout"
    assert handler._timeout_disconnect_requested is True
