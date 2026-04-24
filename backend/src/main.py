"""
FastAPI Main Application
Entry point for the AI Practice System backend.
"""

from __future__ import annotations

import os
import sys

# Add src to path for imports when this module is executed directly.
sys.path.insert(0, os.path.dirname(__file__))

from app_factory import create_app  # noqa: E402
from app_lifespan import lifespan  # noqa: E402
from common.db.session import get_db  # noqa: E402
from http_routes import (  # noqa: E402
    CSRF_EXEMPT_PATHS,
    _check_database_readiness,
    _csrf_validation_failed_response,
    _is_csrf_exempt_path,
    csrf_protection_middleware,
    dev_login,
    health_check,
    metrics_export,
)
from websocket_routes import (  # noqa: E402
    _default_voice_mode,
    _handle_presentation_websocket as _presentation_websocket_handler,
    _is_admin_user_id,
    _is_presentation_kb_lock_unbound_session,
    _normalize_requested_voice_mode,
    _parse_session_id,
    _reject_invalid_presentation_session,
    _resolve_presentation_runtime,
    _resolve_presentation_session_owner_id,
    presentation_websocket,
    presentation_websocket_with_path,
)

app = create_app()


async def _handle_presentation_websocket(
    websocket,
    session_id: str | None,
    token: str,
    voice_mode: str | None = None,
    trace_id: str = "",
):
    """
    Backward-compatible presentation WebSocket helper.

    Existing tests and integrations patch helper functions on ``main`` directly;
    route wiring lives in ``websocket_routes`` while this facade preserves that
    import-and-patch contract.
    """
    await _presentation_websocket_handler(
        websocket=websocket,
        session_id=session_id,
        token=token,
        voice_mode=voice_mode,
        trace_id=trace_id,
        resolve_runtime=_resolve_presentation_runtime,
        is_kb_lock_unbound=_is_presentation_kb_lock_unbound_session,
        resolve_owner_id=_resolve_presentation_session_owner_id,
        is_admin_user_id=_is_admin_user_id,
    )


__all__ = [
    "CSRF_EXEMPT_PATHS",
    "_check_database_readiness",
    "_csrf_validation_failed_response",
    "_default_voice_mode",
    "_handle_presentation_websocket",
    "_is_admin_user_id",
    "_is_csrf_exempt_path",
    "_is_presentation_kb_lock_unbound_session",
    "_normalize_requested_voice_mode",
    "_parse_session_id",
    "_reject_invalid_presentation_session",
    "_resolve_presentation_runtime",
    "_resolve_presentation_session_owner_id",
    "app",
    "create_app",
    "csrf_protection_middleware",
    "dev_login",
    "get_db",
    "health_check",
    "lifespan",
    "metrics_export",
    "presentation_websocket",
    "presentation_websocket_with_path",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=3444, reload=True, log_level="info")
