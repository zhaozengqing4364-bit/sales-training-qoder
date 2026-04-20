from pydantic import BaseModel

from common.api.response import error_response, success_response


class ExamplePayload(BaseModel):
    value: str


def test_success_response_normalizes_pydantic_payload() -> None:
    assert success_response(ExamplePayload(value="ok"), trace_id="trace-1") == {
        "success": True,
        "data": {"value": "ok"},
        "trace_id": "trace-1",
    }


def test_error_response_uses_complete_envelope() -> None:
    assert error_response(
        "[EXAMPLE_FAILED]",
        "示例失败",
        trace_id="trace-2",
    ) == {
        "success": False,
        "data": None,
        "error": "[EXAMPLE_FAILED]",
        "message": "示例失败",
        "trace_id": "trace-2",
    }
