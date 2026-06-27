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
from sales_bot.websocket.stepfun_realtime_handler import (
    StepFunRealtimeHandler,
    StepFunRealtimeSharedHandler,
)
from sales_bot.websocket.stepfun_realtime_sales_stage import (
    StepFunRealtimeSalesStageMixin,
)


@pytest.fixture
def handler() -> PresentationStepFunRealtimeHandler:
    instance = PresentationStepFunRealtimeHandler()
    instance.session_id = "session-presentation-stepfun-001"
    instance.user_id = "user-presentation-stepfun-001"
    instance.websocket = Mock()
    return instance


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_exc):
        return None


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
async def test_handle_connection_closes_on_invalid_token(handler):
    handler.websocket.close = AsyncMock()
    handler.manager.connect = AsyncMock()

    with patch(
        "sales_bot.websocket.stepfun_realtime_handler.verify_token",
        side_effect=ValueError("bad token"),
    ):
        await handler.handle_connection(
            handler.websocket,
            handler.session_id,
            "bad-token",
        )

    handler.websocket.close.assert_awaited_once_with(
        code=4401,
        reason="unauthorized",
    )
    handler.manager.connect.assert_not_awaited()


def test_presentation_stepfun_handler_does_not_inherit_sales_stage_mixin():
    assert isinstance(StepFunRealtimeHandler(), StepFunRealtimeSalesStageMixin)
    assert not isinstance(
        PresentationStepFunRealtimeHandler(),
        StepFunRealtimeSalesStageMixin,
    )


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
        StepFunRealtimeSharedHandler,
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
async def test_load_page_requirements_uses_injected_db_session_factory(handler):
    db = Mock()
    handler._db_session_factory = Mock(return_value=_AsyncContext(db))
    with patch(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationCoachService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_current_page_requirements = AsyncMock(
            return_value=Result.ok({"required_points": ["价值"], "total_pages": 3})
        )

        result = await handler._load_page_requirements(2)

    handler._db_session_factory.assert_called_once_with()
    service_cls.assert_called_once_with(db)
    assert result["required_points"] == ["价值"]


@pytest.mark.asyncio
async def test_load_presentation_ai_policy_uses_injected_db_session_factory(handler):
    db = Mock()
    handler._db_session_factory = Mock(return_value=_AsyncContext(db))
    with patch(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationAIPolicyService"
    ) as service_cls:
        service = service_cls.return_value
        service.resolve_effective_policy_for_session_result = AsyncMock(
            return_value=Result.ok({"source": "session"})
        )

        await handler._load_presentation_ai_policy()

    handler._db_session_factory.assert_called_once_with()
    service_cls.assert_called_once_with(db)
    assert handler._presentation_ai_policy == {"source": "session"}


@pytest.mark.asyncio
async def test_resolve_interruption_guidance_uses_injected_db_session_factory(handler):
    db = Mock()
    db.execute = AsyncMock(return_value=Mock(first=Mock(return_value=None)))
    handler._db_session_factory = Mock(return_value=_AsyncContext(db))
    handler.prompt_role_resolver.resolve_interruption_message = Mock(
        return_value="请补充关键结论。"
    )
    with patch(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler.PromptTemplateService"
    ) as service_cls:
        service = service_cls.return_value
        service.get_template_for_scenario = AsyncMock(return_value=None)

        guidance = await handler._resolve_interruption_guidance(
            reason="missing_required_point",
            trigger="第一页",
            requirements={"required_points": ["价值"]},
            fallback_message="fallback",
        )

    handler._db_session_factory.assert_called_once_with()
    service_cls.assert_called_once_with(db)
    assert guidance == "请补充关键结论。"


@pytest.mark.asyncio
async def test_handle_client_text_routes_shared_text_without_sales_stage(handler):
    handler.session_status = "in_progress"
    handler._ensure_input_allowed = AsyncMock(return_value=True)
    handler._ensure_upstream_ready_for_input = AsyncMock(return_value=True)
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._update_roleplay_disclosure_state = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response = AsyncMock()

    await handler._handle_client_text(
        json.dumps({"type": "text", "data": {"text": "讲第一页"}})
    )

    handler._persist_message.assert_awaited_once()
    assert handler._persist_message.await_args.kwargs["sales_stage"] is None
    handler._create_response.assert_awaited_once_with(count_turn=True)


@pytest.mark.asyncio
async def test_send_status_uses_presentation_event_contract(handler):
    handler.current_page = 2
    handler.session_status = "in_progress"
    handler.turn_count = 3
    handler._presentation_event_emitter.send_status = AsyncMock()

    await handler._send_status("listening")

    assert handler.ai_state == "listening"
    handler._presentation_event_emitter.send_status.assert_awaited_once_with(
        ai_state="listening",
        session_status="in_progress",
        turn_count=3,
        current_page=2,
    )


@pytest.mark.asyncio
async def test_send_error_uses_presentation_event_contract(handler):
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.turn_count = 3
    handler._record_runtime_error = Mock()
    handler._presentation_event_emitter.send_error = AsyncMock()

    await handler._send_error("[STEPFUN_UPSTREAM_ERROR]", "上游连接失败")

    handler._record_runtime_error.assert_called_once_with(
        "[STEPFUN_UPSTREAM_ERROR]",
        "上游连接失败",
    )
    handler._presentation_event_emitter.send_error.assert_awaited_once_with(
        code="[STEPFUN_UPSTREAM_ERROR]",
        message="上游连接失败",
        session_status="in_progress",
        ai_state="listening",
        turn_count=3,
    )


@pytest.mark.asyncio
async def test_send_heartbeat_uses_stepfun_envelope(handler):
    handler.manager.send_json = AsyncMock()

    await handler._send_heartbeat()

    handler.manager.send_json.assert_awaited_once()
    websocket, payload = handler.manager.send_json.await_args.args
    assert websocket is handler.websocket
    assert payload["type"] == "heartbeat"


@pytest.mark.asyncio
async def test_send_transcript_uses_presentation_event_contract(handler):
    handler._presentation_event_emitter.send_transcript = AsyncMock()

    await handler._send_transcript("最终转写", is_final=True)

    handler._presentation_event_emitter.send_transcript.assert_awaited_once_with(
        text="最终转写",
        is_final=True,
    )


@pytest.mark.asyncio
async def test_handle_session_end_uses_presentation_event_contract(handler):
    handler.session_status = "completed"
    handler.turn_count = 2
    handler.running = True
    handler._presentation_event_emitter.send_session_ended = AsyncMock()

    await handler._handle_session_end()

    handler._presentation_event_emitter.send_session_ended.assert_awaited_once_with(
        session_id=handler.session_id,
        session_status="completed",
        turn_count=2,
    )
    assert handler.running is False


@pytest.mark.asyncio
async def test_persist_message_uses_stepfun_message_storage_helper(handler):
    with patch(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler.save_stepfun_message",
        new=AsyncMock(return_value=True),
    ) as save_message:
        await handler._persist_message(
            turn_number=1,
            role="user",
            content="  讲业务目标  ",
            analysis_data={"transcript_metadata": {"page_number": 2}},
        )

    save_message.assert_awaited_once()
    assert save_message.await_args.kwargs["session_id"] == handler.session_id
    assert save_message.await_args.kwargs["turn_number"] == 1
    assert save_message.await_args.kwargs["role"] == "user"
    assert save_message.await_args.kwargs["content"] == "讲业务目标"
    assert save_message.await_args.kwargs["analysis_payload"]["transcript_metadata"] == {
        "page_number": 2
    }


@pytest.mark.asyncio
async def test_persist_message_skips_blank_content(handler):
    with patch(
        "presentation_coach.websocket.presentation_stepfun_realtime_handler.save_stepfun_message",
        new=AsyncMock(),
    ) as save_message:
        await handler._persist_message(
            turn_number=1,
            role="assistant",
            content="   ",
        )

    save_message.assert_not_awaited()


def test_resolve_user_turn_number_matches_stepfun_transcript_timing(handler):
    handler.turn_count = 0
    handler._active_response = None

    assert handler._resolve_user_turn_number_for_transcript() == 1

    handler.turn_count = 2
    handler._active_response = SimpleNamespace()

    assert handler._resolve_user_turn_number_for_transcript() == 2


def test_extract_response_text_uses_stepfun_response_contract(handler):
    assert (
        handler._extract_response_text(
            {
                "response": {
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "请继续保持逐页证据链。",
                                }
                            ]
                        }
                    ]
                }
            }
        )
        == "请继续保持逐页证据链。"
    )


def test_sales_stage_context_append_is_noop_for_presentation(handler):
    handler._sales_stage_context = None

    assert (
        handler._append_sales_stage_context_message(
            role="assistant",
            content="presentation response",
            turn_number=1,
        )
        is None
    )
    assert handler._sales_stage_context is None


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
