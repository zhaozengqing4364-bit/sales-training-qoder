"""FastAPI Main Application
Entry point for the AI Practice System backend.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# Backward compatibility shim: main is imported directly by tooling/tests.
import websocket_routes as _presentation_websocket_routes
from app_factory import create_app
from app_lifespan import lifespan as _factory_lifespan

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))


# Keep app creation single-source via factory.
app = create_app()

# Preserve compatibility imports expected by the existing main.py test surface.
create_app = create_app
lifespan = _factory_lifespan

_parse_session_id = _presentation_websocket_routes._parse_session_id
_reject_invalid_presentation_session = (
    _presentation_websocket_routes._reject_invalid_presentation_session
)
_normalize_requested_voice_mode = (
    _presentation_websocket_routes._normalize_requested_voice_mode
)
_default_voice_mode = _presentation_websocket_routes._default_voice_mode
_resolve_presentation_runtime = _presentation_websocket_routes._resolve_presentation_runtime
_is_presentation_kb_lock_unbound_session = (
    _presentation_websocket_routes._is_presentation_kb_lock_unbound_session
)
_resolve_presentation_session_owner_id = (
    _presentation_websocket_routes._resolve_presentation_session_owner_id
)
_is_admin_user_id = _presentation_websocket_routes._is_admin_user_id


# Keep explicit helper used by unit tests for presentation WebSocket behavior.
async def _handle_presentation_websocket(
    websocket,
    session_id: str | None,
    token: str,
    voice_mode: str | None = None,
    trace_id: str = "",
) -> None:
    await _presentation_websocket_routes._handle_presentation_websocket(
        websocket,
        session_id,
        token,
        voice_mode,
        trace_id,
        resolve_runtime=_resolve_presentation_runtime,
        is_kb_lock_unbound=_is_presentation_kb_lock_unbound_session,
        resolve_owner_id=_resolve_presentation_session_owner_id,
        is_admin_user_id=_is_admin_user_id,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=3444, reload=True, log_level="info")
