"""
Sales Bot WebSocket Router

Routes WebSocket connections to appropriate handlers based on parameters.
Supports both SimpleSalesHandler (backward compatible) and EnhancedSalesHandler
(with Agent Platform integration).

References:
- Requirements: R11 (WebSocket Enhancement)
- Design: Section 20 (WebSocket Router)
- API Contract: docs/api-contract/websocket.md
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket
from sqlalchemy import select

from common.db.models import PracticeSession, Scenario
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from common.websocket.session_manager import get_session_manager

from .enhanced_handler import EnhancedSalesHandler, create_enhanced_sales_handler
from .simple_handler import SimpleSalesHandler, create_sales_handler
from .stepfun_realtime_handler import create_stepfun_realtime_handler

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/sales")
async def sales_websocket(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None, description="Practice session UUID"),
    token: str = Query("", description="JWT authentication token (deprecated; use Authorization header)"),
    agent_id: Optional[str] = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: Optional[str] = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
):
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
    )


@router.websocket("/ws/sales/{session_id}")
async def sales_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query("", description="JWT authentication token (deprecated; use Authorization header)"),
    agent_id: Optional[str] = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: Optional[str] = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
):
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
    )


def _parse_session_id(session_id: Optional[str]) -> str | None:
    candidate = (session_id or "").strip()
    if not candidate:
        return None

    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


async def _reject_invalid_session_id(websocket: WebSocket, session_id: Optional[str]):
    logger.warning("Rejected /ws/sales connection due to invalid session_id", session_id=session_id)
    await websocket.accept()
    await websocket.close(code=4400, reason="INVALID_SESSION_ID")


async def _handle_sales_websocket(
    websocket: WebSocket,
    session_id: Optional[str],
    token: str,
    agent_id: Optional[str],
    persona_id: Optional[str],
    voice_mode: str,
):
    """
    WebSocket endpoint for sales practice.

    Supports two modes:
    1. Simple mode (backward compatible): No agent_id/persona_id
       - Uses SimpleSalesHandler with hardcoded personas
       - For existing integrations

    2. Enhanced mode: With agent_id and persona_id
       - Uses EnhancedSalesHandler with Agent Platform integration
       - Supports capability modules (fuzzy detection, sales stage, scoring)
       - Stores messages for replay

    Query Parameters:
        session_id: Practice session UUID (path parameter)
        token: JWT authentication token
        agent_id: Optional Agent UUID for enhanced mode
        persona_id: Optional Persona UUID for enhanced mode

    WebSocket Messages:
        See docs/api-contract/websocket.md for message formats.
    """
    resolved_session_id = _parse_session_id(session_id)
    if not resolved_session_id:
        await _reject_invalid_session_id(websocket, session_id)
        return

    (
        session_scenario_type,
        persisted_voice_mode,
        persisted_agent_id,
        persisted_persona_id,
    ) = await _resolve_session_runtime(
        resolved_session_id
    )
    if session_scenario_type and session_scenario_type != "sales":
        logger.warning(
            "Rejected /ws/sales connection due to scenario mismatch",
            session_id=resolved_session_id,
            expected="sales",
            actual=session_scenario_type,
        )
        await websocket.accept()
        await websocket.close(code=4409, reason="SESSION_SCENARIO_MISMATCH")
        return

    kb_lock_unbound = await _is_kb_lock_unbound_session(resolved_session_id)
    if kb_lock_unbound:
        logger.warning(
            "Rejected /ws/sales connection due to KB lock without bound knowledge base",
            session_id=resolved_session_id,
        )
        await websocket.accept()
        await websocket.close(code=4410, reason="KB_LOCK_UNBOUND")
        return

    # Enforce voice mode lock from persisted session snapshot.
    normalized_voice_mode = _normalize_requested_voice_mode(voice_mode)
    if normalized_voice_mode and normalized_voice_mode != persisted_voice_mode:
        logger.warning(
            "Ignoring mismatched ws voice_mode override",
            session_id=resolved_session_id,
            requested=normalized_voice_mode,
            persisted=persisted_voice_mode,
        )
    normalized_voice_mode = persisted_voice_mode

    if agent_id and persisted_agent_id and agent_id != persisted_agent_id:
        logger.warning(
            "Ignoring mismatched ws agent_id override",
            session_id=resolved_session_id,
            requested=agent_id,
            persisted=persisted_agent_id,
        )
    if persona_id and persisted_persona_id and persona_id != persisted_persona_id:
        logger.warning(
            "Ignoring mismatched ws persona_id override",
            session_id=resolved_session_id,
            requested=persona_id,
            persisted=persisted_persona_id,
        )

    resolved_agent_id = persisted_agent_id or agent_id
    resolved_persona_id = persisted_persona_id or persona_id

    use_enhanced = resolved_agent_id is not None and resolved_persona_id is not None
    auth_token = _resolve_ws_token(websocket, token)

    if normalized_voice_mode == "stepfun_realtime":
        await _handle_stepfun_realtime_connection(
            websocket=websocket,
            session_id=resolved_session_id,
            token=auth_token,
        )
    elif use_enhanced:
        await _handle_enhanced_connection(
            websocket=websocket,
            session_id=resolved_session_id,
            token=auth_token,
            agent_id=resolved_agent_id,
            persona_id=resolved_persona_id,
        )
    else:
        await _handle_simple_connection(
            websocket=websocket,
            session_id=resolved_session_id,
            token=auth_token,
        )


def _resolve_ws_token(websocket: WebSocket, query_token: str) -> str:
    """Resolve auth token from header first, then query fallback."""
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return query_token


def _normalize_requested_voice_mode(voice_mode: str | None) -> str | None:
    mode = (voice_mode or "").strip().lower()
    if mode in {"legacy", "stepfun_realtime"}:
        return mode
    return None


def _default_voice_mode() -> str:
    default_mode = os.getenv("DEFAULT_VOICE_MODE", "legacy").strip().lower()
    if default_mode not in {"legacy", "stepfun_realtime"}:
        default_mode = "legacy"
    return default_mode


async def _resolve_session_runtime(
    session_id: str,
) -> tuple[str | None, str, str | None, str | None]:
    default_mode = _default_voice_mode()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    Scenario.scenario_type,
                    PracticeSession.voice_mode,
                    PracticeSession.agent_id,
                    PracticeSession.persona_id,
                )
                .join(
                    Scenario,
                    Scenario.scenario_id == PracticeSession.scenario_id,
                    isouter=True,
                )
                .where(PracticeSession.session_id == session_id)
            )
            row = result.first()
            if row:
                scenario_type, resolved_mode, agent_id, persona_id = row
                mode = str(resolved_mode or "").strip().lower()
                if mode in {"legacy", "stepfun_realtime"}:
                    return (
                        str(scenario_type or "").lower() or None,
                        mode,
                        str(agent_id) if agent_id else None,
                        str(persona_id) if persona_id else None,
                    )
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            f"Failed to resolve session runtime from session {session_id}: {exc}"
        )

    return None, default_mode, None, None


def _is_kb_lock_unbound_snapshot(snapshot: object) -> bool:
    if not isinstance(snapshot, dict):
        return False
    tool_policy = snapshot.get("tool_policy")
    if not isinstance(tool_policy, dict):
        return False
    if not bool(tool_policy.get("require_kb_grounding", False)):
        return False
    knowledge_base_ids = snapshot.get("knowledge_base_ids")
    if not isinstance(knowledge_base_ids, list):
        return True
    return not bool([item for item in knowledge_base_ids if str(item).strip()])


async def _is_kb_lock_unbound_session(session_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.voice_policy_snapshot).where(
                    PracticeSession.session_id == session_id
                )
            )
            snapshot = result.scalar_one_or_none()
            return _is_kb_lock_unbound_snapshot(snapshot)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            "Failed to evaluate KB lock binding before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return False


async def _handle_simple_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
):
    """Handle connection with SimpleSalesHandler (backward compatible)."""
    logger.info(
        f"Using SimpleSalesHandler for session {session_id}",
        session_id=session_id,
    )

    handler = create_sales_handler()

    # Default persona for backward compatibility
    handler.set_persona("impatient_ceo")

    # Try to link to existing bot session
    try:
        session_uuid = uuid.UUID(session_id)
        from sales_bot.services.bot_service import sales_bot_service

        if session_uuid in sales_bot_service.active_sessions:
            handler.set_bot_session(session_uuid)
    except (ValueError, KeyError):
        pass

    # Register with SessionManager for timeout/heartbeat tracking
    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler)
    try:
        await handler.handle_connection(websocket, session_id, token)
    finally:
        await session_manager.unregister_session(session_id)


async def _handle_stepfun_realtime_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
):
    """Handle connection with StepFun realtime end-to-end voice model."""
    logger.info(
        f"Using StepFunRealtimeHandler for session {session_id}",
        session_id=session_id,
    )

    handler = create_stepfun_realtime_handler()
    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler)
    try:
        await handler.handle_connection(websocket, session_id, token)
    finally:
        await session_manager.unregister_session(session_id)


async def _handle_enhanced_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
    agent_id: str,
    persona_id: str,
):
    """Handle connection with EnhancedSalesHandler (Agent Platform integration)."""
    logger.info(
        f"Using EnhancedSalesHandler for session {session_id}",
        session_id=session_id,
        agent_id=agent_id,
        persona_id=persona_id,
    )

    handler = create_enhanced_sales_handler()

    # Extract user_id from token
    user_id = _extract_user_id_from_token(token)
    if user_id is None:
        logger.warning(f"WebSocket auth rejected: invalid token for session {session_id}")
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # NEW-5 Fix: Use short-lived DB session ONLY for initialization (loading config).
    # The WebSocket handler will create its own short-lived sessions for runtime DB ops.
    from common.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        init_success = await handler.initialize(
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
            user_id=user_id,
            db=db,
        )

    if not init_success:
        logger.error(
            f"Failed to initialize EnhancedSalesHandler",
            session_id=session_id,
            agent_id=agent_id,
            persona_id=persona_id,
        )
        # Do NOT fallback to simple handler here. Simple mode has no Agent/Persona
        # capability pipeline and may silently skip knowledge retrieval.
        await websocket.accept()
        await websocket.close(code=4502, reason="ENHANCED_INIT_FAILED")
        return

    # Register with SessionManager for timeout/heartbeat tracking
    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler, user_id=user_id)
    try:
        # Handle the WebSocket connection (DB session already released)
        await handler.handle_connection(websocket, session_id, token)
    finally:
        await session_manager.unregister_session(session_id)


def _extract_user_id_from_token(token: str) -> str | None:
    """
    Extract user_id from JWT token.

    Returns None if token is invalid and not in development mode,
    causing the caller to reject the connection.
    """
    try:
        from common.auth.service import verify_token

        payload = verify_token(token)
        if payload and "sub" in payload:
            return payload["sub"]
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning(f"Failed to decode token: {e}")

    # Only allow fallback in development environment
    if os.getenv("ENVIRONMENT") == "development":
        logger.warning("Using dev-user-id fallback (development mode only)")
        return "dev-user-id"

    return None
