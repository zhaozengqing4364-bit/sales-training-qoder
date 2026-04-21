from unittest.mock import AsyncMock

import pytest

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


@pytest.mark.asyncio
async def test_enhanced_handler_runtime_diagnostics_surface_live_session_summary_from_processor() -> None:
    handler = EnhancedSalesHandler()
    handler.capability_processor = type(
        "ProcessorStub",
        (),
        {
            "coach_health": "healthy",
            "_coach_health_reason": None,
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
                    "status": "weak_evidence",
                    "label": "证据偏弱",
                    "source": "score_snapshot",
                    "reason": "low_evidence_score",
                    "evidence_score": 61.0,
                },
            },
        },
    )()

    diagnostics = handler.get_runtime_diagnostics()

    assert diagnostics["claim_truth"] == {
        "status": "weak_evidence",
        "label": "证据偏弱",
        "source": "score_snapshot",
        "reason": "low_evidence_score",
        "evidence_score": 61.0,
    }
    assert diagnostics["live_session_summary"] == {
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
            "status": "weak_evidence",
            "label": "证据偏弱",
            "source": "score_snapshot",
            "reason": "low_evidence_score",
            "evidence_score": 61.0,
        },
    }
    assert handler._create_state_snapshot().runtime_state == {
        "live_session_summary": diagnostics["live_session_summary"],
    }


@pytest.mark.asyncio
async def test_enhanced_handler_restore_session_state_rehydrates_live_session_summary() -> None:
    handler = EnhancedSalesHandler()
    handler._send_reconnection_success = AsyncMock()

    state = SessionStateSnapshot(
        session_id="session-live-summary",
        scenario="sales",
        turn_count=5,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={
            "live_session_summary": {
                "alignment_used": True,
                "stage_key": "objection",
                "focus_type": "objection_handling_gap",
                "fallback_reason": None,
                "main_issue": {
                    "issue_type": "objection_handling_gap",
                    "issue_text": "面对价格、竞品或风险顾虑时，承接和重构回应还不够到位。",
                    "recovery_rule": "下一轮先复述顾虑，再用收益、证据和试点方案回应。",
                },
                "next_goal": {
                    "goal_type": "objection_reframe",
                    "goal_text": "下一轮先承接价格/竞品/风险顾虑，再用收益和证据回应。",
                    "rule": "先复述顾虑，再给回应，最后落到低风险推进方案。",
                },
                "claim_truth": {
                    "status": "unsupported_claim",
                    "label": "未被证据支撑",
                    "source": "objection_ledger",
                    "reason": "gap_acknowledged",
                    "closure_state": "gap_acknowledged",
                },
            }
        },
        user_id="user-1",
    )

    await handler._restore_session_state(state)

    diagnostics = handler.get_runtime_diagnostics()
    assert diagnostics["live_session_summary"] == state.runtime_state["live_session_summary"]
    assert diagnostics["claim_truth"] == {
        "status": "unsupported_claim",
        "label": "未被证据支撑",
        "source": "objection_ledger",
        "reason": "gap_acknowledged",
        "closure_state": "gap_acknowledged",
    }
