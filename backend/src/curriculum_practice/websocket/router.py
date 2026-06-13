from __future__ import annotations

import uuid
from typing import NamedTuple

from fastapi import APIRouter, Query, WebSocket
from jwt import InvalidTokenError as JWTError
from sqlalchemy import select

from common.auth.service import resolve_websocket_token, verify_token
from common.config import settings
from common.db.models import PracticeSession, User
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from common.services.runtime_gate import RuntimeAdmissionDecision, RuntimeGate
from common.services.session_runtime_lifecycle_hooks import mark_session_runtime_failed
from common.websocket.session_manager import get_session_manager
from curriculum_practice.services.examiner_report_service import (
    ExaminerReportService,
    examiner_report_frontend_path,
)
from curriculum_practice.services.runtime_gate_contributor import (
    register_curriculum_practice_runtime_gate_contributors,
)
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    ExaminerWebSocketHandler,
)


class _AuthUser(NamedTuple):
    user_id: str
    role: str
    is_active: bool

logger = get_logger(__name__)
router = APIRouter()
register_curriculum_practice_runtime_gate_contributors()


@router.websocket("/ws/curriculum/examiner")
async def examiner_websocket(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    token: str = Query(""),
    trace_id: str = Query(""),
) -> None:
    await _handle_examiner_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        trace_id=trace_id,
    )


@router.websocket("/ws/curriculum/examiner/{session_id}")
async def examiner_websocket_with_path(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(""),
    trace_id: str = Query(""),
) -> None:
    await _handle_examiner_websocket(
        websocket=websocket,
        session_id=session_id,
        token=token,
        trace_id=trace_id,
    )


def _parse_session_id(session_id: str | None) -> str | None:
    candidate = (session_id or "").strip()
    if not candidate:
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


def _extract_user_id_from_payload(payload: dict) -> str | None:
    sub = payload.get("sub")
    if isinstance(sub, str) and sub:
        return sub
    user_id_val = payload.get("user_id")
    if isinstance(user_id_val, str) and user_id_val:
        return user_id_val
    return None


async def _reject(
    websocket: WebSocket,
    *,
    code: int,
    reason: str,
    session_id: str | None = None,
    mark_runtime_failed: bool = True,
) -> None:
    if session_id and mark_runtime_failed:
        await mark_session_runtime_failed(
            session_id,
            failure_code=reason,
            source="examiner_websocket_reject",
        )
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


async def _reject_admission(
    websocket: WebSocket,
    decision: RuntimeAdmissionDecision,
    *,
    session_id: str,
) -> None:
    reason = decision.close_reason or decision.code or "EXAMINER_RUNTIME_CONFIG_MISSING"
    if decision.mark_runtime_failed:
        await mark_session_runtime_failed(
            session_id,
            failure_code=reason,
            source="examiner_websocket_reject",
        )
    await websocket.accept()
    await websocket.close(code=decision.close_code or 4413, reason=reason)


async def _resolve_authenticated_user(user_id: str) -> _AuthUser | None:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.user_id, User.role, User.is_active).where(
                    User.user_id == user_id
                )
            )
            row = result.one_or_none()
            if row is None:
                return None
            return _AuthUser(
                user_id=str(row.user_id),
                role=str(row.role or ""),
                is_active=bool(row.is_active),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve authenticated user for examiner websocket",
            user_id=user_id,
            error=str(exc),
        )
        return None


async def _resolve_examiner_session_owner_id(
    session_id: str,
) -> tuple[str | None, bool]:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(PracticeSession.user_id).where(
                    PracticeSession.session_id == session_id
                )
            )
            owner_id = result.scalar_one_or_none()
            return (str(owner_id) if owner_id else None, True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to resolve examiner session owner before websocket connect",
            session_id=session_id,
            error=str(exc),
        )
        return (None, False)


async def _handle_examiner_websocket(
    *,
    websocket: WebSocket,
    session_id: str | None,
    token: str,
    trace_id: str,
) -> None:
    if not settings.CURRICULUM_EXAMINER_ENABLED:
        logger.warning("Rejected examiner websocket because feature flag is disabled")
        await _reject(websocket, code=4404, reason="CURRICULUM_EXAMINER_DISABLED")
        return

    resolved_session_id = _parse_session_id(session_id)
    if resolved_session_id is None:
        await _reject(websocket, code=4400, reason="INVALID_SESSION_ID")
        return

    token = resolve_websocket_token(
        query_token=token,
        authorization_header=websocket.headers.get("authorization", ""),
        cookie_header=websocket.headers.get("cookie", ""),
    )
    try:
        payload = verify_token(token)
        user_id = _extract_user_id_from_payload(payload)
    except (JWTError, RuntimeError, ValueError, OSError):
        logger.warning(
            "Failed to resolve examiner websocket user from token",
            session_id=resolved_session_id,
        )
        user_id = None

    if user_id is None:
        await _reject(
            websocket,
            code=4001,
            reason="Unauthorized",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
        )
        return

    auth_user = await _resolve_authenticated_user(user_id)
    if auth_user is None or not auth_user.is_active:
        await _reject(
            websocket,
            code=4001,
            reason="Unauthorized",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
        )
        return

    session_owner_id, owner_lookup_ok = await _resolve_examiner_session_owner_id(
        resolved_session_id
    )
    if not owner_lookup_ok:
        await _reject(
            websocket,
            code=4003,
            reason="ACCESS_DENIED",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
        )
        return
    if (
        session_owner_id
        and session_owner_id != auth_user.user_id
        and auth_user.role != "admin"
    ):
        logger.warning(
            "Rejected examiner websocket due to owner mismatch",
            session_id=resolved_session_id,
            request_user_id=auth_user.user_id,
            session_owner_id=session_owner_id,
        )
        await _reject(
            websocket,
            code=4003,
            reason="ACCESS_DENIED",
            session_id=resolved_session_id,
            mark_runtime_failed=False,
        )
        return

    admission = await _resolve_examiner_admission_decision(resolved_session_id)
    if admission is not None and not admission.allowed:
        await _reject_admission(
            websocket,
            admission,
            session_id=resolved_session_id,
        )
        return

    runtime, failure_reason = await _build_runtime_from_session(resolved_session_id)
    if runtime is None:
        await _reject(
            websocket,
            code=4413,
            reason=failure_reason or "EXAMINER_RUNTIME_CONFIG_MISSING",
            session_id=resolved_session_id,
        )
        return

    handler = ExaminerWebSocketHandler(runtime)
    session_manager = get_session_manager()
    await session_manager.register_session(
        resolved_session_id, handler, user_id=auth_user.user_id
    )
    try:
        await handler.handle_connection(
            websocket,
            resolved_session_id,
            token,
            trace_id=trace_id,
        )
    finally:
        await session_manager.unregister_session(resolved_session_id, reason="connection_closed")


async def _build_runtime_from_session(
    session_id: str,
) -> tuple[ExaminerRuntime | None, str | None]:
    async with AsyncSessionLocal() as db:
        return await RuntimeGate(db).build_examiner_runtime(
            session_id,
            completion_writer=_mark_examiner_report_completed,
        )


async def _resolve_examiner_admission_decision(
    session_id: str,
) -> RuntimeAdmissionDecision | None:
    async with AsyncSessionLocal() as db:
        return await RuntimeGate(db).admit_session(
            session_id,
            expected_runtime_type="examiner",
        )


async def _mark_examiner_report_completed(
    *,
    session_id: str,
    answers: list[dict[str, object]],
    reason: str,
) -> str:
    async with AsyncSessionLocal() as db:
        report_service = ExaminerReportService(db)
        persist_result = await report_service.persist_completion_report(
            session_id=session_id,
            answers=[item for item in answers if isinstance(item, dict)],
            reason=reason,
        )
        if not persist_result.is_success:
            logger.warning(
                "Failed to persist examiner report payload",
                session_id=session_id,
                fallback=persist_result.fallback,
            )
    return examiner_report_frontend_path(session_id)
