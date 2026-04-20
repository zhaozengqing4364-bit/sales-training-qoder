"""Unit tests for StepFun upstream event router helpers."""

from __future__ import annotations

from sales_bot.websocket.components.stepfun_upstream_router import (
    UpstreamEventRoute,
    classify_upstream_event,
    extract_error_message,
    extract_function_call_from_item_created,
    extract_response_done_function_calls,
)


def test_classify_upstream_event_routes_core_types():
    assert classify_upstream_event("session.created") == UpstreamEventRoute.IGNORE
    assert (
        classify_upstream_event("conversation.item.created")
        == UpstreamEventRoute.CONVERSATION_ITEM_CREATED
    )
    assert (
        classify_upstream_event("input_audio_buffer.transcription.delta")
        == UpstreamEventRoute.TRANSCRIPTION_DELTA
    )
    assert (
        classify_upstream_event("conversation.item.input_audio_transcription.completed")
        == UpstreamEventRoute.TRANSCRIPTION_COMPLETED
    )
    assert classify_upstream_event("response.done") == UpstreamEventRoute.RESPONSE_DONE
    assert classify_upstream_event("error") == UpstreamEventRoute.ERROR
    assert classify_upstream_event("unknown.event") == UpstreamEventRoute.UNHANDLED


def test_extract_function_call_from_item_created_only_function_call_type():
    event = {
        "item": {
            "type": "function_call",
            "call_id": "call-1",
            "name": "search_internal_knowledge",
        }
    }

    assert extract_function_call_from_item_created(event) == (
        "call-1",
        "search_internal_knowledge",
    )
    assert extract_function_call_from_item_created({"item": {"type": "message"}}) is None
    assert extract_function_call_from_item_created({}) is None


def test_extract_response_done_function_calls_filters_invalid_items():
    event = {
        "response": {
            "output": [
                {"type": "message", "content": []},
                {
                    "type": "function_call",
                    "call_id": "call-a",
                    "name": "search_internal_knowledge",
                    "arguments": '{"query":"产品"}',
                },
            ]
        }
    }

    assert extract_response_done_function_calls(event) == [
        {
            "call_id": "call-a",
            "name": "search_internal_knowledge",
            "arguments": '{"query":"产品"}',
        }
    ]
    assert extract_response_done_function_calls({}) == []


def test_extract_error_message_with_fallback():
    assert extract_error_message({"message": "具体错误"}) == "具体错误"
    assert extract_error_message({"message": "   "}) == "Realtime 服务返回错误"
    assert extract_error_message({}) == "Realtime 服务返回错误"
