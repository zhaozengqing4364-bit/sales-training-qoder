"""Unit tests for StepFun function-call helper utilities."""

from __future__ import annotations

import json

from sales_bot.websocket.components.stepfun_function_call_helpers import (
    build_function_call_output_event,
    build_unsupported_function_output,
    decode_function_arguments,
    is_json_object_payload,
    parse_function_call_event,
)


def test_parse_function_call_event_extracts_string_fields():
    call_id, name, arguments_part = parse_function_call_event(
        {
            "call_id": 123,
            "name": "search_internal_knowledge",
            "arguments": {"query": "产品"},
        }
    )

    assert call_id == "123"
    assert name == "search_internal_knowledge"
    assert arguments_part == '{"query": "产品"}'


def test_decode_function_arguments_handles_valid_and_invalid_json():
    assert decode_function_arguments('{"query":"产品","top_k":3}') == {
        "query": "产品",
        "top_k": 3,
    }
    assert decode_function_arguments("[1,2,3]") == {}
    assert decode_function_arguments("not-json") == {}


def test_is_json_object_payload_validates_object_strings():
    assert is_json_object_payload('{"query":"产品"}') is True
    assert is_json_object_payload('{"query":1}') is True
    assert is_json_object_payload('["a","b"]') is False
    assert is_json_object_payload("not-json") is False


def test_build_unsupported_function_output_contains_supported_functions():
    payload = build_unsupported_function_output("unknown_fn")
    assert payload["error"] == "Unsupported function 'unknown_fn'"
    assert payload["supported_functions"] == ["search_internal_knowledge"]


def test_build_function_call_output_event_serializes_payload():
    event = build_function_call_output_event(
        call_id="call-001",
        output_payload={"query": "产品", "count": 2},
    )

    assert event["type"] == "conversation.item.create"
    assert event["item"]["type"] == "function_call_output"
    assert event["item"]["call_id"] == "call-001"
    assert json.loads(event["item"]["output"]) == {"query": "产品", "count": 2}
