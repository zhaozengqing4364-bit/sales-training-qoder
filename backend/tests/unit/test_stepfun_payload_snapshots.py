"""Q-02 characterization snapshots for StepFun realtime outward payloads.

These tests pin the observable payload shapes before any future StepFun handler
decomposition.  They intentionally avoid splitting the large handler; they make
the existing protocol safer to refactor incrementally.
"""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from sales_bot.websocket.components.stepfun_function_call_helpers import (
    build_function_call_output_event,
)
from sales_bot.websocket.stepfun_realtime_handler import StepFunRealtimeHandler


class CaptureManager:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, _websocket, payload: dict) -> None:
        self.sent.append(copy.deepcopy(payload))


def _scrub_dynamic_fields(payload: dict) -> dict:
    scrubbed = copy.deepcopy(payload)
    if "timestamp" in scrubbed:
        scrubbed["timestamp"] = "<timestamp>"
    if "trace_id" in scrubbed:
        scrubbed["trace_id"] = "<trace_id>"
    if "stream_id" in scrubbed:
        scrubbed["stream_id"] = "<stream_id>"
    return scrubbed


@pytest.mark.asyncio
async def test_q02_response_create_payload_snapshot_preserves_instruction_contract():
    handler = StepFunRealtimeHandler()
    handler._stepfun_instructions = "基础指令"
    handler._pending_grounding_context = "证据片段"
    handler._send_status = AsyncMock()
    handler._send_upstream = AsyncMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert handler.current_request_id == 1
    assert handler.turn_count == 1
    handler._send_status.assert_awaited_once_with("thinking")
    handler._send_upstream.assert_awaited_once_with(
        {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": "基础指令\n\n【当前轮内部知识依据】\n证据片段",
            },
        }
    )


@pytest.mark.asyncio
async def test_q02_kb_lock_blocked_response_tts_payload_snapshot():
    handler = StepFunRealtimeHandler()
    manager = CaptureManager()
    blocked_text = "当前内部知识库没有足够依据回答这个问题。"
    handler.manager = manager
    handler.websocket = object()
    handler.session_id = "session-1"
    handler._pending_blocked_response_text = blocked_text
    handler._send_status = AsyncMock()
    handler._persist_message = AsyncMock()
    handler._append_sales_stage_context_message = MagicMock()

    created = await handler._create_response(count_turn=True)

    assert created is True
    assert _scrub_dynamic_fields(manager.sent[0]) == {
        "type": "tts_audio",
        "timestamp": "<timestamp>",
        "stream_id": "<stream_id>",
        "request_id": 1,
        "data": {
            "text": blocked_text,
            "audio": "",
            "audio_format": "",
            "duration_ms": len(blocked_text) * 100,
            "fallback": "browser_tts",
            "playback_rate": 1.0,
        },
    }
    assert handler._pending_blocked_response_text == ""
    handler._send_status.assert_any_await("thinking")
    handler._send_status.assert_any_await("listening")


def test_q02_function_call_tool_result_payload_snapshot():
    event = build_function_call_output_event(
        call_id="call-001",
        output_payload={
            "query": "产品定价",
            "count": 1,
            "results": [{"knowledge_base_id": "kb-1", "snippet": "证据"}],
        },
    )

    assert event == {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": "call-001",
            "output": json.dumps(
                {
                    "query": "产品定价",
                    "count": 1,
                    "results": [{"knowledge_base_id": "kb-1", "snippet": "证据"}],
                },
                ensure_ascii=False,
            ),
        },
    }


@pytest.mark.asyncio
async def test_q02_realtime_feedback_score_update_payload_snapshot():
    handler = StepFunRealtimeHandler()
    manager = CaptureManager()
    handler.manager = manager
    handler.websocket = object()
    handler.session_id = "session-1"

    await handler._send_score_update(
        turn_number=3,
        overall_score=82.5,
        dimension_scores={"discovery": 80.0, "objection": 85.0},
        suggestions=["追问预算优先级"],
        stage_name="异议处理",
        claim_truth={"status": "supported"},
    )

    assert _scrub_dynamic_fields(manager.sent[0]) == {
        "type": "score_update",
        "timestamp": "<timestamp>",
        "trace_id": "<trace_id>",
        "data": {
            "session_id": "session-1",
            "turn_count": 3,
            "overall_score": 82.5,
            "dimension_scores": {"discovery": 80.0, "objection": 85.0},
            "suggestions": ["追问预算优先级"],
            "stage_name": "异议处理",
            "claim_truth": {"status": "supported"},
        },
    }


@pytest.mark.asyncio
async def test_q02_resume_message_routes_to_listening_status_snapshot():
    handler = StepFunRealtimeHandler()
    handler._apply_lifecycle_action = AsyncMock(return_value=object())
    handler._send_status = AsyncMock()

    await handler._handle_client_text(json.dumps({"type": "resume"}))

    handler._apply_lifecycle_action.assert_awaited_once_with("resume")
    handler._send_status.assert_awaited_once_with("listening")


@pytest.mark.asyncio
async def test_q02_text_response_create_failure_emits_stable_error_fallback():
    handler = StepFunRealtimeHandler()
    handler.session_status = "in_progress"
    handler._analyze_and_emit_sales_stage = AsyncMock(return_value="opening")
    handler._run_realtime_feedback = AsyncMock(return_value={})
    handler._persist_message = AsyncMock()
    handler._send_upstream = AsyncMock()
    handler._prepare_grounding_context = AsyncMock()
    handler._create_response = AsyncMock(side_effect=RuntimeError("boom"))
    handler._send_error = AsyncMock()

    await handler._handle_client_text(
        json.dumps({"type": "text", "data": {"text": "介绍一下产品"}})
    )

    handler._send_error.assert_awaited_once_with(
        "[RESPONSE_CREATE_FAILED]",
        "响应生成暂时失败，请重试。",
    )
