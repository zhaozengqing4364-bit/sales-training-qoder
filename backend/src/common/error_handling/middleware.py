"""
Error handling middleware with graceful degradation
Constitution Principle I: User Experience Never Interrupts
All errors are caught and converted to fallback responses
"""
import traceback

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from common.monitoring.logger import get_logger, get_trace_id, set_trace_id

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler that catches all exceptions
    Never shows error popups to users - converts to graceful fallbacks
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """Process request with error handling"""
        # Extract or generate trace_id
        trace_id = request.headers.get("X-Trace-ID", "")
        if trace_id:
            set_trace_id(trace_id)

        try:
            response = await call_next(request)
            return response

        except Exception as exc:
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
            return JSONResponse(
                status_code=status.HTTP_200_OK,  # Always 200 - no error status
                content={
                    "success": False,
                    "fallback": self._get_fallback_response(exc, request),
                    "trace_id": get_trace_id(),
                }
            )

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
        status_code=status.HTTP_200_OK,
        content={
            "success": False,
            "fallback": "[PLEASE_TRY_AGAIN]",
            "trace_id": trace_id,
        }
    )
