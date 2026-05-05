"""
Error handling middleware with graceful degradation
Constitution Principle I: User Experience Never Interrupts
All errors are caught and converted to fallback responses
"""

import traceback

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from common.monitoring.logger import get_logger, get_trace_id, set_trace_id
from common.monitoring.trace_context import build_traceparent, resolve_trace_headers

logger = get_logger(__name__)


class ErrorHandlerMiddleware:
    """
    Global error handler that catches all exceptions
    Never shows error popups to users - converts to graceful fallbacks
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    @staticmethod
    def _attach_trace_headers(
        message: Message,
        *,
        trace_id: str,
        response_traceparent: str | None,
        tracestate: str | None,
    ):
        headers = MutableHeaders(scope=message)
        headers["X-Trace-ID"] = trace_id

        effective_traceparent = response_traceparent or build_traceparent(trace_id)
        if effective_traceparent:
            headers["traceparent"] = effective_traceparent
        if tracestate:
            headers["tracestate"] = tracestate

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Process request with error handling"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request = Request(scope, receive=receive)
        trace_id, response_traceparent, tracestate = resolve_trace_headers(headers)
        set_trace_id(trace_id or "")

        async def send_with_trace_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._attach_trace_headers(
                    message,
                    trace_id=get_trace_id(),
                    response_traceparent=response_traceparent,
                    tracestate=tracestate,
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_trace_headers)

        except (RuntimeError, ValueError) as exc:
            # Log the full error with trace_id
            logger.error(
                f"Unhandled exception: {str(exc)}",
                path=request.url.path,
                method=request.method,
                traceback=traceback.format_exc(),
            )

            # Return fallback response - NEVER show raw error to user
            # User-facing: friendly status update
            # Admin-facing: full error details in logs
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "fallback": self._get_fallback_response(exc, request),
                    "trace_id": get_trace_id(),
                },
            )
            await response(scope, receive, send_with_trace_headers)

    def _get_fallback_response(self, exc: Exception, request: Request) -> str:
        """
        Map exception to user-friendly fallback message
        Constitution: No error popups, all errors convert to graceful degradation
        """
        error_type = type(exc).__name__

        # ASR failures - switch to browser ASR
        if "ASR" in error_type or "speech" in str(exc).lower():
            return "[USE_BROWSER_ASR]"

        # TTS failures - use browser TTS
        if "TTS" in error_type or "audio" in str(exc).lower():
            return "[USE_BROWSER_TTS]"

        # LLM timeout - use predefined response
        if "timeout" in str(exc).lower() or "LLM" in error_type:
            return "[FALLBACK_RESPONSE]"

        # Vector DB failure - use keyword search
        if "vector" in str(exc).lower() or "ChromaDB" in error_type:
            return "[USE_KEYWORD_SEARCH]"

        # Network/connection issues
        if "connection" in str(exc).lower() or "network" in error_type:
            return "[RECONNECTING]"

        # Default: generic fallback
        return "[PLEASE_TRY_AGAIN]"


async def global_exception_handler(request: Request, exc: Exception):
    """FastAPI global exception handler"""
    trace_id = get_trace_id()

    logger.error(
        f"Global exception handler triggered: {str(exc)}",
        path=request.url.path,
        method=request.method,
        traceback=traceback.format_exc(),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "fallback": "[PLEASE_TRY_AGAIN]",
            "trace_id": trace_id,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTPException handler with trace_id for observability."""
    trace_id = get_trace_id()
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
    else:
        message = str(detail)

    payload = {
        "success": False,
        "error": message,
        "message": message,
        "detail": detail,
        "trace_id": trace_id,
    }
    return JSONResponse(status_code=exc.status_code, content=payload)
