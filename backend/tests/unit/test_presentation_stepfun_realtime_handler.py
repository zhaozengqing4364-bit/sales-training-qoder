"""Unit tests for presentation StepFun realtime handler parity behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.error_handling.result import Result
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    PresentationStepFunRealtimeHandler,
)
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


@pytest.fixture
def handler() -> PresentationStepFunRealtimeHandler:
    instance = PresentationStepFunRealtimeHandler()
    instance.session_id = "session-presentation-stepfun-001"
    instance.websocket = Mock()
    return instance


def test_presentation_stepfun_handler_forwards_collaborator_factories():
    transport = SimpleNamespace()

    def db_session_factory():
        raise AssertionError("factory should only be stored during construction")

    def knowledge_service_factory(_db):
        raise AssertionError("factory should only be stored during construction")

    handler = PresentationStepFunRealtimeHandler(
        stepfun_transport=transport,
        db_session_factory=db_session_factory,
        knowledge_service_factory=knowledge_service_factory,
    )

    assert handler._stepfun_transport is transport
    assert handler._db_session_factory is db_session_factory
    assert handler._knowledge_service_factory is knowledge_service_factory
    assert handler.scenario == "presentation"
    assert handler.session_scenario_type == "presentation"


@pytest.mark.asyncio
async def test_handle_client_text_routes_page_change(handler):
    handler._handle_page_change = AsyncMock()

    await handler._handle_client_text(
        json.dumps({"type": "page_change", "data": {"page_number": 3}})
    )

    handler._handle_page_change.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_handle_client_text_control_start_emits_page_context(handler):
    handler._emit_current_page_context = AsyncMock()
    handler.session_status = "in_progress"

    with patch.object(
        StepFunRealtimeHandler,
        "_handle_client_text",
        new=AsyncMock(),
    ) as super_handle:
        await handler._handle_client_text(
            json.dumps({"type": "control", "data": {"action": "start"}})
        )

    super_handle.assert_awaited_once()
    handler._emit_current_page_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_current_page_context_uses_presentation_event_contract(handler):
    handler.current_page = 2
    handler._load_page_requirements = AsyncMock(
        return_value={
            "required_points": ["客户痛点", "业务价值"],
            "forbidden_words": ["大概"],
            "total_pages": 8,
            "page_content": "第二页内容",
        }
    )
    handler._initialize_page_feedback = AsyncMock()
    handler._presentation_event_emitter.send_page_context = AsyncMock()

    await handler._emit_current_page_context()

    handler._initialize_page_feedback.assert_awaited_once()
    handler._presentation_event_emitter.send_page_context.assert_awaited_once_with(
        page_number=2,
        requirements={
            "required_points": ["客户痛点", "业务价值"],
            "forbidden_words": ["大概"],
            "total_pages": 8,
            "page_content": "第二页内容",
        },
        session_status=handler.session_status,
        turn_count=handler.turn_count,
        session_id=handler.session_id,
    )


@pytest.mark.asyncio
async def test_sync_lifecycle_transition_start_emits_page_context(handler):
    handler._emit_current_page_context = AsyncMock()

    transition = SimpleNamespace(
        action="start",
        to_status="in_progress",
        ai_state="listening",
        scenario_type="presentation",
    )

    await handler.sync_lifecycle_transition(transition)

    assert handler.session_status == "in_progress"
    assert handler.ai_state == "listening"
    handler._emit_current_page_context.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_presentation_feedback_interrupt_path(handler):
    feedback = SimpleNamespace(
        point_results=[
            SimpleNamespace(
                point_id="session-presentation-stepfun-001:1",
                is_covered=True,
                point_content="客户痛点",
            )
        ],
        forbidden_matches=[
            SimpleNamespace(word="大概", suggestion="请改为明确数字或范围")
        ],
        should_interrupt=True,
        interruption_reason="forbidden_word",
        interruption_message="请避免模糊表达",
    )
    handler.feedback_service.check_transcript = AsyncMock(return_value=Result.ok(feedback))
    handler._load_page_requirements = AsyncMock(
        return_value={
            "required_points": ["客户痛点"],
            "forbidden_words": ["大概"],
        }
    )
    handler._resolve_interruption_guidance = AsyncMock(return_value="请避免模糊表达")
    handler._presentation_event_emitter.send_point_updates = AsyncMock()
    handler._presentation_event_emitter.send_forbidden_word_alert = AsyncMock()
    handler._presentation_event_emitter.send_feedback = AsyncMock()
    handler._presentation_event_emitter.send_interruption = AsyncMock()
    handler._handle_interrupt = AsyncMock()
    handler._send_status = AsyncMock()

    interrupted = await handler._evaluate_presentation_feedback("这段表达有点模糊")

    assert interrupted is True
    handler._handle_interrupt.assert_awaited_once_with("forbidden_word")
    handler._resolve_interruption_guidance.assert_awaited_once()
    handler._presentation_event_emitter.send_point_updates.assert_awaited_once()
    handler._presentation_event_emitter.send_forbidden_word_alert.assert_awaited_once()
    handler._presentation_event_emitter.send_feedback.assert_awaited_once()
    handler._presentation_event_emitter.send_interruption.assert_awaited_once()
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_transcription_completed_interrupt_short_circuits_response_creation(handler):
    handler._resolve_user_turn_number_for_transcript = Mock(return_value=1)
    handler._send_transcript = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._load_page_requirements = AsyncMock(
        return_value={
            "required_points": [],
            "forbidden_words": [],
            "total_pages": 1,
            "page_content": "",
        }
    )
    handler._initialize_page_feedback = AsyncMock()
    handler._evaluate_presentation_feedback = AsyncMock(return_value=True)
    handler._cancel_pending_response_after_commit = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock()

    await handler._handle_upstream_transcription_completed(
        {"transcript": "这段转写触发了中断"}
    )

    handler._cancel_pending_response_after_commit.assert_awaited_once()
    handler._prepare_grounding_context.assert_not_awaited()
    handler._create_response_from_pending_commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_transcription_completed_applies_transcript_normalization(handler):
    handler.current_page = 4
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
    handler._resolve_user_turn_number_for_transcript = Mock(return_value=1)
    handler._send_transcript = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._load_page_requirements = AsyncMock(
        return_value={
            "required_points": [],
            "forbidden_words": [],
            "total_pages": 1,
            "page_content": "",
        }
    )
    handler._initialize_page_feedback = AsyncMock()
    handler._evaluate_presentation_feedback = AsyncMock(return_value=False)
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response_from_pending_commit = AsyncMock()

    await handler._handle_upstream_transcription_completed(
        {"transcript": "这页重点介绍石溪平台"}
    )

    handler._send_transcript.assert_awaited_once_with("这页重点介绍石犀平台", is_final=True)
    persisted_kwargs = handler._persist_message.await_args.kwargs
    assert persisted_kwargs["content"] == "这页重点介绍石犀平台"
    assert persisted_kwargs["analysis_data"]["transcript_metadata"]["raw_text"] == "这页重点介绍石溪平台"
    assert persisted_kwargs["analysis_data"]["transcript_metadata"]["page_number"] == handler.current_page
    handler._prepare_grounding_context.assert_awaited_once_with("这页重点介绍石犀平台")
