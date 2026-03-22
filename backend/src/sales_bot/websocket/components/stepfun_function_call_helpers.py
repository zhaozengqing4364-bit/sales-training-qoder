"""Helper utilities for StepFun function-call argument parsing and payloads."""

from __future__ import annotations

import json
from typing import Any

SUPPORTED_FUNCTIONS = ("search_internal_knowledge",)


def parse_function_call_event(event: dict[str, Any]) -> tuple[str, str, str]:
    """Extract call_id/name/arguments from function_call_arguments events."""
    call_id = str(event.get("call_id") or "")
    name = str(event.get("name") or "")
    raw_arguments = event.get("arguments")
    if isinstance(raw_arguments, str):
        arguments_part = raw_arguments
    elif isinstance(raw_arguments, dict):
        arguments_part = json.dumps(raw_arguments, ensure_ascii=False)
    elif raw_arguments is None:
        arguments_part = ""
    else:
        arguments_part = str(raw_arguments)
    return call_id, name, arguments_part


def decode_function_arguments(raw_arguments: str) -> dict[str, Any]:
    """Decode function-call JSON arguments into an object payload."""
    try:
        arguments_obj = json.loads(raw_arguments or "{}")
        if isinstance(arguments_obj, dict):
            return arguments_obj
    except json.JSONDecodeError:
        pass
    return {}


def is_json_object_payload(raw_arguments: str) -> bool:
    try:
        return isinstance(json.loads(raw_arguments or "{}"), dict)
    except json.JSONDecodeError:
        return False


def build_unsupported_function_output(function_name: str) -> dict[str, Any]:
    """Build standardized unsupported-function error payload."""
    return {
        "error": f"Unsupported function '{function_name}'",
        "supported_functions": list(SUPPORTED_FUNCTIONS),
    }


def build_function_call_output_event(
    *,
    call_id: str,
    output_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build upstream event payload for function_call_output item."""
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps(output_payload, ensure_ascii=False),
        },
    }
