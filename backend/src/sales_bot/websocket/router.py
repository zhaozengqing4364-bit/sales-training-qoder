"""
Sales Bot WebSocket Router.

Routes WebSocket connections for persona-centered sales sessions.
Legacy simple-handler mode is disabled to prevent policy bypass.
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket
from sqlalchemy import select

from common.auth.service import JWTError, resolve_websocket_token
from common.db.models import PracticeSession, Scenario, User
from common.db.session import AsyncSessionLocal
from common.knowledge.kb_lock_guard import is_kb_lock_unbound_snapshot
from common.monitoring.logger import get_logger
from common.monitoring.trace_context import normalize_trace_id
from common.websocket.session_manager import get_session_manager
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService

from .enhanced_handler import create_enhanced_sales_handler
from .stepfun_realtime_handler import create_stepfun_realtime_handler

logger = get_logger(__name__)

router = APIRouter()

# M020/S01/T01 current sales websocket auth posture.
# This is an explicit inventory of the shipped behavior before T02 tightens the authority line.
SALES_WS_AUTH_POLICY: dict[str, list[str] | dict[str, int] | str] = {
    "formal": ["authorization_bearer", "session_cookie"],
    "compatibility": ["query_token"],
    "current_resolution_order": "authorization_header -> query_token -> cookie_header",
    "reject_close_codes": {
        "unauthorized": 4001,
        "owner_mismatch": 4003,
        "kb_lock_unbound": 4410,
        "agent_persona_required": 4411,
    },
}


@router.websocket("/ws/sales")
async def sales_websocket(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None, description="Practice session UUID"),
    token: str = Query("", description="JWT authentication token (deprecated; use Authorization header)"),
    agent_id: Optional[str] = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: Optional[str] = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
    trace_id: str = Query("", description="Request trace id for observability"),
):
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
        trace_id=trace_id,
    )


@router.websocket("/ws/sales/{session_id}")
async def sales_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query("", description="JWT authentication token (deprecated; use Authorization header)"),
    agent_id: Optional[str] = Query(None, description="Agent UUID for enhanced mode"),
    persona_id: Optional[str] = Query(None, description="Persona UUID for enhanced mode"),
    voice_mode: str = Query("", description="Voice mode: legacy | stepfun_realtime"),
    trace_id: str = Query("", description="Request trace id for observability"),
):
    await _handle_sales_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        agent_id=agent_id,
        persona_id=persona_id,
        voice_mode=voice_mode,
        trace_id=trace_id,
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


async def _reject_sales_websocket(
    websocket: WebSocket,
    *,
    code: int,
    reason: str,
    log_message: str,
    **log_fields,
) -> None:
    logger.warning(log_message, **log_fields)
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


async def _handle_sales_websocket(
    websocket: WebSocket,
    session_id: Optional[str],
    token: str,
    agent_id: Optional[str],
    persona_id: Optional[str],
    voice_mode: str,
    trace_id: str,
):
    """
    WebSocket endpoint for sales practice.

    Supports:
    1. Realtime mode: With persisted session voice_mode = stepfun_realtime
    2. Enhanced mode: With persisted Agent + Persona runtime lock

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

    auth_token = _resolve_ws_token(websocket, token)
    user_id = _extract_user_id_from_token(auth_token)
    if user_id is None:
        await _reject_sales_websocket(
            websocket,
            code=4001,
            reason="Unauthorized",
            log_message="Rejected /ws/sales connection due to invalid token",
            session_id=resolved_session_id,
        )
        return

    session_owner_id = await _resolve_session_owner_id(resolved_session_id)
    if (
        session_owner_id
        and session_owner_id != user_id
        and not await _is_admin_user_id(user_id)
    ):
        await _reject_sales_websocket(
            websocket,
            code=4003,
            reason="ACCESS_DENIED",
            log_message="Rejected /ws/sales connection due to owner mismatch",
            session_id=resolved_session_id,
            request_user_id=user_id,
            session_owner_id=session_owner_id,
        )
        return

    resolved_agent_id = persisted_agent_id or agent_id
    resolved_persona_id = persisted_persona_id or persona_id

    if not (resolved_agent_id and resolved_persona_id):
        logger.warning(
            "Rejected /ws/sales connection due to missing agent/persona runtime lock",
            session_id=resolved_session_id,
            persisted_agent_id=persisted_agent_id,
            persisted_persona_id=persisted_persona_id,
        )
        await websocket.accept()
        await websocket.close(code=4411, reason="AGENT_PERSONA_REQUIRED")
        return

    if normalized_voice_mode == "stepfun_realtime":
        await _handle_stepfun_realtime_connection(
            websocket=websocket,
            session_id=resolved_session_id,
            token=auth_token,
            trace_id=normalize_trace_id(trace_id),
        )
    else:
        await _handle_enhanced_connection(
            websocket=websocket,
            session_id=resolved_session_id,
            token=auth_token,
            agent_id=resolved_agent_id,
            persona_id=resolved_persona_id,
            trace_id=normalize_trace_id(trace_id),
        )


def _resolve_ws_token(websocket: WebSocket, query_token: str) -> str:
    """Resolve sales websocket auth using the shipped compatibility order."""
    return resolve_websocket_token(
        query_token=query_token,
        authorization_header=websocket.headers.get("authorization", ""),
        cookie_header=websocket.headers.get("cookie", ""),
    )


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


async def _resolve_session_owner_id(session_id: str) -> str | None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.user_id).where(
                    PracticeSession.session_id == session_id
                )
            )
            owner_id = result.scalar_one_or_none()
            return str(owner_id) if owner_id else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve session owner before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return None


async def _is_admin_user_id(user_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.role).where(User.user_id == user_id)
            )
            role = result.scalar_one_or_none()
            return str(role or "").lower() == "admin"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve websocket user role before session access check",
            user_id=user_id,
            error=str(exc),
        )
        return False


async def _is_kb_lock_unbound_session(session_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession).where(
                    PracticeSession.session_id == session_id
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                return False

            snapshot = (
                session.voice_policy_snapshot
                if isinstance(session.voice_policy_snapshot, dict)
                else None
            )
            if snapshot and not is_kb_lock_unbound_snapshot(snapshot):
                return False

            policy_service = VoiceRuntimePolicyService(db)
            resolved_policy = await policy_service.resolve_effective_policy(
                agent_id=session.agent_id,
                persona_id=session.persona_id,
                voice_mode_override=session.voice_mode,
                runtime_profile_override=session.voice_runtime_profile_id,
            )
            refreshed_policy = _merge_snapshot_runtime_overlays(
                resolved_policy=resolved_policy,
                snapshot=snapshot,
            )
            if snapshot != refreshed_policy:
                session.voice_policy_snapshot = refreshed_policy
                await db.commit()
            return is_kb_lock_unbound_snapshot(refreshed_policy)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to evaluate KB lock binding before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return False


def _merge_snapshot_runtime_overlays(
    *,
    resolved_policy: dict,
    snapshot: dict | None,
) -> dict:
    merged = dict(resolved_policy)
    if not isinstance(snapshot, dict):
        return merged

    runtime_metrics = snapshot.get("runtime_metrics")
    if isinstance(runtime_metrics, dict):
        merged["runtime_metrics"] = runtime_metrics
    if "agent_persona_override_config" in snapshot:
        merged["agent_persona_override_config"] = snapshot.get(
            "agent_persona_override_config"
        )
    return merged


async def _handle_stepfun_realtime_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
    trace_id: str | None = None,
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
        await handler.handle_connection(
            websocket,
            session_id,
            token,
            trace_id=trace_id,
        )
    finally:
        await session_manager.unregister_session(session_id)


async def _handle_enhanced_connection(
    websocket: WebSocket,
    session_id: str,
    token: str,
    agent_id: str,
    persona_id: str,
    trace_id: str | None = None,
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
        await handler.handle_connection(
            websocket,
            session_id,
            token,
            trace_id=trace_id,
        )
    finally:
        await session_manager.unregister_session(session_id)


def _extract_user_id_from_token(token: str) -> str | None:
    """
    Extract user_id from JWT token.

    Returns None if token is invalid so the caller can reject the connection.
    """
    try:
        from common.auth.service import verify_token

        payload = verify_token(token)
        if payload and "sub" in payload:
            return payload["sub"]
    except (JWTError, RuntimeError, ValueError, OSError) as e:
        logger.warning(f"Failed to decode token: {e}")

    return None
