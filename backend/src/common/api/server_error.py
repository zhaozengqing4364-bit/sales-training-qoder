"""Unified helpers for returning standardized 5xx API responses."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from common.api.response import server_error_response
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def build_server_error(
    error_code: str,
    *,
    status_code: int = 500,
    message: str | None = None,
    exc: Exception | None = None,
    **context: Any,
) -> JSONResponse:
    """Log a server-side failure and return normalized 5xx payload."""
    if exc is not None:
        logger.error(
            "Server error response generated",
            error_code=error_code,
            status_code=status_code,
            error_message=str(exc),
            **context,
        )
    else:
        logger.error(
            "Server error response generated",
            error_code=error_code,
            status_code=status_code,
            **context,
        )

    return JSONResponse(
        status_code=status_code,
        content=server_error_response(error_code=error_code, message=message),
    )
