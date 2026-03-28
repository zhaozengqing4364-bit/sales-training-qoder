import pytest
from unittest.mock import AsyncMock

from common.websocket.session_state_service import SessionStateSnapshot
from sales_bot.websocket.enhanced_handler import EnhancedSalesHandler


@pytest.mark.asyncio
async def test_enhanced_handler_snapshot_persists_non_healthy_coach_state() -> None:
    handler = EnhancedSalesHandler()
    handler.session_id = "session-legacy-coach"
    handler.turn_count = 3
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.user_id = "user-1"
    handler._coach_health = "degraded"
    handler._coach_health_reason = "capability_pipeline_failed"

    snapshot = handler._create_state_snapshot()

    assert snapshot.runtime_state == {
        "coach_health": {
            "status": "degraded",
            "reason": "capability_pipeline_failed",
            "message": "实时辅导暂不可用，训练仍可继续。",
        }
    }


@pytest.mark.asyncio
async def test_enhanced_handler_restore_session_state_restores_coach_health() -> None:
    handler = EnhancedSalesHandler()
    handler._send_reconnection_success = AsyncMock()

    state = SessionStateSnapshot(
        session_id="session-legacy-coach",
        scenario="sales",
        turn_count=4,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "coach_health": {
                "status": "degraded",
                "reason": "capability_pipeline_failed",
                "message": "实时辅导暂不可用，训练仍可继续。",
            }
        },
        user_id="user-1",
    )

    await handler._restore_session_state(state)

    assert handler.turn_count == 4
    assert handler.session_status == "in_progress"
    assert handler.ai_state == "listening"
    assert handler._coach_health == "degraded"
    assert handler._coach_health_reason == "capability_pipeline_failed"
    handler._send_reconnection_success.assert_awaited_once()
    emitted_snapshot = handler._send_reconnection_success.await_args.args[0]
    assert emitted_snapshot.session_id == "session-legacy-coach"
    assert emitted_snapshot.user_id == "user-1"
    assert emitted_snapshot.runtime_state == {
        "coach_health": {
            "status": "degraded",
            "reason": "capability_pipeline_failed",
            "message": "实时辅导暂不可用，训练仍可继续。",
        }
    }


@pytest.mark.asyncio
async def test_enhanced_handler_restore_session_state_emits_normalized_coach_health_snapshot() -> None:
    handler = EnhancedSalesHandler()
    handler._send_reconnection_success = AsyncMock()

    state = SessionStateSnapshot(
        session_id="session-legacy-coach-normalized",
        scenario="sales",
        turn_count=4,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "coach_health": {
                "status": "paused",
                "reason": " capability_pipeline_failed ",
                "message": "旧的异常消息",
            }
        },
        user_id="user-1",
    )

    await handler._restore_session_state(state)

    assert handler._coach_health == "healthy"
    assert handler._coach_health_reason == "capability_pipeline_failed"
    handler._send_reconnection_success.assert_awaited_once()
    emitted_snapshot = handler._send_reconnection_success.await_args.args[0]
    assert emitted_snapshot.session_id == "session-legacy-coach-normalized"
    assert emitted_snapshot.user_id == "user-1"
    assert emitted_snapshot.runtime_state == {
        "coach_health": {
            "status": "healthy",
            "reason": "capability_pipeline_failed",
            "message": "实时辅导正常。",
        }
    }


@pytest.mark.asyncio
async def test_enhanced_handler_restore_session_state_syncs_initialized_capability_processor() -> None:
    handler = EnhancedSalesHandler()
    handler._send_reconnection_success = AsyncMock()
    handler.capability_processor = type(
        "ProcessorStub",
        (),
        {"coach_health": "healthy", "_coach_health_reason": None},
    )()

    state = SessionStateSnapshot(
        session_id="session-legacy-coach",
        scenario="sales",
        turn_count=4,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "coach_health": {
                "status": "degraded",
                "reason": "capability_pipeline_failed",
                "message": "实时辅导暂不可用，训练仍可继续。",
            }
        },
        user_id="user-1",
    )

    await handler._restore_session_state(state)

    assert handler.capability_processor.coach_health == "degraded"
    assert handler.capability_processor._coach_health_reason == "capability_pipeline_failed"
    assert handler.get_runtime_diagnostics()["coach_health"]["status"] == "degraded"
    assert handler._create_state_snapshot().runtime_state == {
        "coach_health": {
            "status": "degraded",
            "reason": "capability_pipeline_failed",
            "message": "实时辅导暂不可用，训练仍可继续。",
        }
    }
