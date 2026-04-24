"""WebSocket route handlers for the backend application."""

from __future__ import annotations

import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, FastAPI, Query, WebSocket
from sqlalchemy import select

from common.auth.service import JWTError, resolve_websocket_token
from common.db.models import PracticeSession, Scenario, User
from common.db.session import AsyncSessionLocal
from common.knowledge.kb_lock_guard import is_kb_lock_unbound_snapshot
from common.monitoring.logger import get_logger
from common.monitoring.trace_context import normalize_trace_id
from sales_bot.websocket.router import router as sales_ws_router

logger = get_logger(__name__)
router = APIRouter()

ResolveRuntime = Callable[[str], Awaitable[tuple[str | None, str]]]
ResolveFlag = Callable[[str], Awaitable[bool]]
ResolveOwner = Callable[[str], Awaitable[str | None]]


def _parse_session_id(session_id: str | None) -> str | None:
    candidate = (session_id or "").strip()
    if not candidate:
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


async def _reject_invalid_presentation_session(
    websocket: WebSocket, session_id: str | None
) -> None:
    logger.warning(
        "Rejected /ws/presentation connection due to invalid session_id",
        session_id=session_id,
    )
    await websocket.accept()
    await websocket.close(code=4400, reason="INVALID_SESSION_ID")


async def _handle_presentation_websocket(
    websocket: WebSocket,
    session_id: str | None,
    token: str,
    voice_mode: str | None = None,
    trace_id: str = "",
    *,
    resolve_runtime: ResolveRuntime | None = None,
    is_kb_lock_unbound: ResolveFlag | None = None,
    resolve_owner_id: ResolveOwner | None = None,
    is_admin_user_id: ResolveFlag | None = None,
) -> None:
    from common.auth.service import verify_token
    from common.websocket.session_manager import get_session_manager
    from presentation_coach.websocket.presentation_handler import (
        PresentationWebSocketHandler,
    )
    from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
        PresentationStepFunRealtimeHandler,
    )

    resolve_runtime = resolve_runtime or _resolve_presentation_runtime
    is_kb_lock_unbound = (
        is_kb_lock_unbound or _is_presentation_kb_lock_unbound_session
    )
    resolve_owner_id = resolve_owner_id or _resolve_presentation_session_owner_id
    is_admin_user_id = is_admin_user_id or _is_admin_user_id

    resolved_session_id = _parse_session_id(session_id)
    if not resolved_session_id:
        await _reject_invalid_presentation_session(websocket, session_id)
        return

    scenario_type, persisted_voice_mode = await resolve_runtime(resolved_session_id)
    if scenario_type and scenario_type != "presentation":
        logger.warning(
            "Rejected /ws/presentation connection due to scenario mismatch",
            session_id=resolved_session_id,
            expected="presentation",
            actual=scenario_type,
        )
        await websocket.accept()
        await websocket.close(code=4409, reason="SESSION_SCENARIO_MISMATCH")
        return

    kb_lock_unbound = await is_kb_lock_unbound(resolved_session_id)
    if kb_lock_unbound:
        logger.warning(
            "Rejected /ws/presentation connection due to KB lock without bound knowledge base",
            session_id=resolved_session_id,
        )
        await websocket.accept()
        await websocket.close(code=4410, reason="KB_LOCK_UNBOUND")
        return

    token = resolve_websocket_token(
        query_token=token,
        authorization_header=websocket.headers.get("authorization", ""),
        cookie_header=websocket.headers.get("cookie", ""),
    )

    requested_mode = _normalize_requested_voice_mode(voice_mode)
    if requested_mode and requested_mode != persisted_voice_mode:
        logger.warning(
            "Ignoring mismatched presentation ws voice_mode override",
            session_id=resolved_session_id,
            requested=requested_mode,
            persisted=persisted_voice_mode,
        )

    effective_voice_mode = persisted_voice_mode
    handler: Any
    if effective_voice_mode == "stepfun_realtime":
        handler = PresentationStepFunRealtimeHandler()
    else:
        handler = PresentationWebSocketHandler()

    try:
        payload = verify_token(token)
        if payload and isinstance(payload.get("sub"), str):
            user_id = payload["sub"]
        elif payload and isinstance(payload.get("user_id"), str):
            user_id = payload["user_id"]
        else:
            user_id = None
    except (JWTError, RuntimeError, ValueError, OSError):
        logger.warning(
            "Failed to resolve websocket user from token",
            session_id=resolved_session_id,
        )
        user_id = None

    if user_id is None:
        await websocket.accept()
        await websocket.close(code=4001, reason="Unauthorized")
        return

    session_owner_id = await resolve_owner_id(resolved_session_id)
    if (
        session_owner_id
        and session_owner_id != user_id
        and not await is_admin_user_id(user_id)
    ):
        logger.warning(
            "Rejected /ws/presentation connection due to owner mismatch",
            session_id=resolved_session_id,
            request_user_id=user_id,
            session_owner_id=session_owner_id,
        )
        await websocket.accept()
        await websocket.close(code=4003, reason="ACCESS_DENIED")
        return

    session_manager = get_session_manager()
    await session_manager.register_session(
        resolved_session_id,
        handler,
        user_id=user_id,
    )
    try:
        await handler.handle_connection(
            websocket,
            resolved_session_id,
            token,
            trace_id=normalize_trace_id(trace_id),
        )
    finally:
        await session_manager.unregister_session(resolved_session_id)


async def _resolve_presentation_session_owner_id(session_id: str) -> str | None:
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
            "Failed to resolve presentation session owner before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return None


async def _is_admin_user_id(user_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User.role).where(User.user_id == user_id))
            return str(result.scalar_one_or_none() or "").lower() == "admin"
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve websocket user role before presentation access check",
            user_id=user_id,
            error=str(exc),
        )
        return False


@router.websocket("/ws/presentation")
async def presentation_websocket(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    token: str = Query(""),
    voice_mode: str | None = Query(
        None, description="Voice mode: legacy | stepfun_realtime"
    ),
    trace_id: str = Query("", description="Request trace id for observability"),
) -> None:
    """WebSocket endpoint for PPT presentation coaching (query session_id)."""
    await _handle_presentation_websocket(
        websocket,
        session_id,
        token,
        voice_mode,
        trace_id,
    )


@router.websocket("/ws/presentation/{session_id}")
async def presentation_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
    voice_mode: str | None = Query(
        None, description="Voice mode: legacy | stepfun_realtime"
    ),
    trace_id: str = Query("", description="Request trace id for observability"),
) -> None:
    """WebSocket endpoint for PPT presentation coaching (path session_id)."""
    await _handle_presentation_websocket(
        websocket,
        session_id,
        token,
        voice_mode,
        trace_id,
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


async def _resolve_presentation_runtime(
    session_id: str,
) -> tuple[str | None, str]:
    default_mode = _default_voice_mode()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(
                    Scenario.scenario_type,
                    PracticeSession.voice_mode,
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
                scenario_type, resolved_mode = row
                mode = str(resolved_mode or "").strip().lower()
                if mode not in {"legacy", "stepfun_realtime"}:
                    mode = default_mode
                return str(scenario_type or "").lower() or None, mode
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            f"Failed to resolve presentation runtime for {session_id}: {exc}"
        )
    return None, default_mode


async def _is_presentation_kb_lock_unbound_session(session_id: str) -> bool:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.voice_policy_snapshot).where(
                    PracticeSession.session_id == session_id
                )
            )
            snapshot = result.scalar_one_or_none()
            return is_kb_lock_unbound_snapshot(snapshot)
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning(
            "Failed to evaluate presentation KB lock binding before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return False


def register_websocket_routes(app: FastAPI) -> None:
    """Mount WebSocket route modules on the app."""
    app.include_router(router, tags=["presentation-websocket"])
    app.include_router(sales_ws_router, tags=["sales-websocket"])
