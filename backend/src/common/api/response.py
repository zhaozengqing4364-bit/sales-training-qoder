"""Unified API Response Helpers.

Provides consistent response formatting across all API endpoints.
Follows the Result[T] pattern for error handling.

Usage:
    from common.api.response import success_response, error_response

    @router.get("/users/{id}")
    async def get_user(id: str):
        user = await get_user_by_id(id)
        if not user:
            return error_response("[USER_NOT_FOUND]")
        return success_response(user_data)
"""
from typing import Any

from common.monitoring.logger import get_trace_id


def _jsonable_data(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data


def success_response(
    data: Any,
    trace_id: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Create unified success response.

    Args:
        data: Response data to include
        trace_id: Optional trace ID for request tracking

    Returns:
        Dict with success=True and data
    """
    payload = {
        "success": True,
        "data": _jsonable_data(data),
        "trace_id": trace_id or get_trace_id(),
    }
    if message is not None:
        payload["message"] = message
    return payload


def error_response(
    error_code: str,
    message: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """
    Create unified error response.

    Replaces HTTPException raises to follow Result[T] pattern.

    Args:
        error_code: Error code (e.g., "[USER_NOT_FOUND]")
        message: Optional human-readable message
        trace_id: Optional trace ID for request tracking

    Returns:
        Dict with success=False and error details
    """
    return {
        "success": False,
        "data": None,
        "error": error_code,
        "message": message or error_code,
        "trace_id": trace_id or get_trace_id(),
    }


def server_error_response(
    error_code: str,
    message: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """
    Create unified 5xx server error response.

    Args:
        error_code: Stable backend error code (e.g., "[DB_COMMIT_FAILED]")
        message: Optional message for display/log correlation
        trace_id: Optional trace ID for request tracking

    Returns:
        Dict payload for 500-class responses
    """
    return error_response(error_code=error_code, message=message, trace_id=trace_id)
