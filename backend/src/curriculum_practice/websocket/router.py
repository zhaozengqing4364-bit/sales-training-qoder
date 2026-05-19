from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from fastapi import APIRouter, Query, WebSocket
from jwt import InvalidTokenError as JWTError
from sqlalchemy import select

from common.auth.service import resolve_websocket_token, verify_token
from common.config import settings
from common.db.models import PracticeSession, User
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from common.websocket.session_manager import get_session_manager
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    ExaminerWebSocketHandler,
    FrozenExamQuestion,
)


class _AuthUser(NamedTuple):
    user_id: str
    role: str
    is_active: bool

logger = get_logger(__name__)
router = APIRouter()


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


async def _reject(websocket: WebSocket, *, code: int, reason: str) -> None:
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


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
        await _reject(websocket, code=4001, reason="Unauthorized")
        return

    auth_user = await _resolve_authenticated_user(user_id)
    if auth_user is None or not auth_user.is_active:
        await _reject(websocket, code=4001, reason="Unauthorized")
        return

    session_owner_id, owner_lookup_ok = await _resolve_examiner_session_owner_id(
        resolved_session_id
    )
    if not owner_lookup_ok:
        await _reject(websocket, code=4003, reason="ACCESS_DENIED")
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
        await _reject(websocket, code=4003, reason="ACCESS_DENIED")
        return

    runtime, failure_reason = await _build_runtime_from_session(resolved_session_id)
    if runtime is None:
        await _reject(
            websocket,
            code=4413,
            reason=failure_reason or "EXAMINER_RUNTIME_CONFIG_MISSING",
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
    try:
        async with AsyncSessionLocal() as db:
            session = await db.get(PracticeSession, session_id)
            if session is None or not isinstance(session.curriculum_snapshot, dict):
                return None, "EXAMINER_RUNTIME_SNAPSHOT_MISSING"

            content_assets = session.curriculum_snapshot.get("content_assets")
            if not isinstance(content_assets, list):
                return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

            examiner_ref = _first_asset_ref(content_assets, "examiner_agent")
            if examiner_ref is None:
                return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

            agent = await db.get(ExaminerAgent, str(examiner_ref["asset_id"]))
            if agent is None or getattr(agent, "status", None) != "published":
                return None, "EXAMINER_RUNTIME_CONFIG_MISSING"
            if not _asset_matches_ref(agent, examiner_ref):
                return None, "EXAMINER_RUNTIME_SNAPSHOT_STALE"

            questions: list[FrozenExamQuestion] = []
            question_refs = _asset_refs(content_assets, "question_item")
            if not question_refs:
                return None, "EXAMINER_RUNTIME_CONFIG_MISSING"

            for question_ref in question_refs:
                question = await db.get(QuestionItem, str(question_ref["asset_id"]))
                if (
                    question is None
                    or getattr(question, "status", None) != "published"
                    or bool(getattr(question, "safety_flagged", False))
                ):
                    return None, "EXAMINER_RUNTIME_CONFIG_MISSING"
                if not _asset_matches_ref(question, question_ref):
                    return None, "EXAMINER_RUNTIME_SNAPSHOT_STALE"
                questions.append(
                    FrozenExamQuestion(
                        question_id=str(question.question_id),
                        title=str(question.title),
                        stem=str(question.stem),
                        reference_answer=getattr(question, "reference_answer", None),
                        scoring_criteria=dict(question.scoring_criteria or {}),
                    )
                )

            return (
                ExaminerRuntime(
                    session_id=session_id,
                    examiner_agent_id=str(agent.examiner_agent_id),
                    timeout_seconds=_timeout_seconds(agent.timeout_config),
                    questions=questions,
                    completion_writer=_mark_examiner_report_completed,
                ),
                None,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to build examiner runtime from session",
            session_id=session_id,
            error_type=type(exc).__name__,
        )
        return None, "EXAMINER_RUNTIME_CONFIG_MISSING"


def _timeout_seconds(config: object) -> int:
    if not isinstance(config, dict):
        return 0
    try:
        return max(0, int(config.get("max_seconds") or 0))
    except (TypeError, ValueError):
        return 0


async def _mark_examiner_report_completed(
    *,
    session_id: str,
    answers: list[dict[str, object]],
    reason: str,
) -> str:
    del answers, reason
    async with AsyncSessionLocal() as db:
        session = await db.get(PracticeSession, session_id)
        if session is not None and getattr(session, "report_status", None) != "completed":
            now = datetime.now(UTC)
            session.report_status = "completed"
            session.report_status_updated_at = now
            session.report_retryable = False
            session.report_generated_at = now
            session.report_error = None
            await db.commit()
    return f"/api/v1/evaluation/sessions/{session_id}/report"


def _asset_refs(content_assets: list[object], asset_type: str) -> list[dict[str, object]]:
    return [
        asset
        for asset in content_assets
        if isinstance(asset, dict)
        and asset.get("asset_type") == asset_type
        and isinstance(asset.get("asset_id"), str)
    ]


def _first_asset_ref(
    content_assets: list[object], asset_type: str
) -> dict[str, object] | None:
    refs = _asset_refs(content_assets, asset_type)
    return refs[0] if refs else None


def _asset_matches_ref(asset: object, ref: dict[str, object]) -> bool:
    return str(getattr(asset, "content_hash", "")) == str(
        ref.get("hash")
    ) and _as_int(getattr(asset, "version", 0)) == _as_int(ref.get("version"))


def _as_int(value: object) -> int:
    if not isinstance(value, int | str):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
