"""Unit tests for StepFun realtime session persistence and recovery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import common.api.practice as practice_api
from common.db.models import PracticeSession
from common.error_handling.result import Result
from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "main_capability_not_passed",
            "issue_text": "证据不足，当前无法评估。",
            "recovery_rule": "请先完成至少一轮有效互动后再结束。",
        },
        "next_goal": {
            "goal_type": "main_capability_focus",
            "goal_text": "先完成一轮有效互动再评估。",
            "rule": "补齐用户表达和AI回应后再结束。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def test_create_state_snapshot_captures_minimal_runtime_recovery_fields_and_normalizes_legacy_score() -> None:
    """Sales StepFun snapshots should carry reconnect-safe runtime context only."""
    handler = StepFunRealtimeHandler()
    handler.session_id = "session-stepfun-save-001"
    handler.user_id = "user-stepfun-save-001"
    handler.turn_count = 4
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.current_request_id = 9
    handler._last_emitted_stage = "discovery"
    handler._latest_score_snapshot = {"overall": 86.0}
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

    handler._latest_score_snapshot["overall"] = 20.0
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
            "latest_score_snapshot": {"overall": 91.0},
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


def test_apply_latest_scores_to_session_supports_legacy_overall_and_marks_zero_turn_not_evaluable() -> None:
    handler = StepFunRealtimeHandler()
    handler.turn_count = 0
    handler._latest_score_snapshot = {
        "overall": 84.0,
        "dimension_scores": {
            "专业度": 90.0,
            "沟通技巧": 82.0,
            "销售流程": 80.0,
        },
    }

    session = MagicMock()
    session.logic_score = None
    session.accuracy_score = None
    session.completeness_score = None

    handler._apply_latest_scores_to_session(session)

    assert session.logic_score == 84.0
    assert session.accuracy_score == 84.0
    assert session.completeness_score == 84.0
    assert session.effectiveness_snapshot["evaluable"] is False
    assert session.effectiveness_snapshot["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"


@pytest.mark.asyncio
async def test_sync_sales_realtime_terminal_evidence_uses_latest_message_score_snapshot() -> None:
    session = SimpleNamespace(
        session_id=str(uuid.uuid4()),
        voice_mode="stepfun_realtime",
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=None,
    )
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=SimpleNamespace(
            first=lambda: (
                {
                    "overall": 88.0,
                    "dimension_scores": {
                        "专业度": 91.0,
                        "沟通技巧": 86.0,
                        "销售流程": 87.0,
                    },
                },
            )
        )
    )

    source = await practice_api._sync_sales_realtime_terminal_evidence(
        session_id=session.session_id,
        session=session,
        db=db,
    )

    assert source == "stepfun_message_analysis"
    assert session.logic_score == 91.0
    assert session.accuracy_score == 86.0
    assert session.completeness_score == 87.0
    assert session.effectiveness_snapshot is None


@pytest.mark.asyncio
async def test_prepare_terminal_lifecycle_result_marks_stepfun_session_not_evaluable_without_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = str(uuid.uuid4())
    session = PracticeSession(
        session_id=session_id,
        user_id=str(uuid.uuid4()),
        scenario_id=str(uuid.uuid4()),
        voice_mode="stepfun_realtime",
        status="in_progress",
        start_time=datetime.now(UTC) - timedelta(minutes=2),
    )
    session.effectiveness_snapshot = _make_effectiveness_snapshot(
        evaluable=False,
        reason="INSUFFICIENT_TURN_DATA",
    )

    transition = SimpleNamespace(
        changed=True,
        session=session,
        action="end",
        to_status="scoring",
        scenario_type="sales",
    )
    lifecycle_service = MagicMock()
    lifecycle_service.transition = AsyncMock(return_value=transition)

    sync_evidence_mock = AsyncMock(return_value="stepfun_runtime")
    summary_mock = AsyncMock(return_value=Result.fail("[SUMMARY_FAILED]"))
    cleanup_mock = AsyncMock(return_value=Result.ok({"session_id": session_id}))
    logger_info = MagicMock()

    monkeypatch.setattr(
        practice_api,
        "_sync_sales_realtime_terminal_evidence",
        sync_evidence_mock,
    )
    monkeypatch.setattr(practice_api.summary_service, "generate_summary", summary_mock)
    monkeypatch.setattr(practice_api.sales_bot_service, "end_session", cleanup_mock)
    monkeypatch.setattr(
        practice_api,
        "_ensure_effectiveness_snapshot",
        lambda current_session: current_session.effectiveness_snapshot,
    )
    monkeypatch.setattr(practice_api.logger, "info", logger_info)

    result = await practice_api._prepare_terminal_lifecycle_result(
        session_id=session_id,
        session=session,
        scenario_type="sales",
        lifecycle_service=lifecycle_service,
        db=MagicMock(),
    )

    assert result.summary is None
    assert result.snapshot["evaluable"] is False
    assert result.snapshot["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"
    sync_evidence_mock.assert_awaited_once()
    summary_mock.assert_not_awaited()
    cleanup_mock.assert_awaited_once_with(uuid.UUID(session_id))
    assert any(
        call.args and call.args[0] == "practice_session_evidence_not_evaluable"
        for call in logger_info.call_args_list
    )
