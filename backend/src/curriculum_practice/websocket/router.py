from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, WebSocket

from common.config import settings
from common.db.models import PracticeSession
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from curriculum_practice.models import ExaminerAgent, QuestionItem
from curriculum_practice.websocket.examiner_runtime import (
    ExaminerRuntime,
    ExaminerWebSocketHandler,
    FrozenExamQuestion,
)

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


async def _reject(websocket: WebSocket, *, code: int, reason: str) -> None:
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


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

    runtime, failure_reason = await _build_runtime_from_session(resolved_session_id)
    if runtime is None:
        await _reject(
            websocket,
            code=4413,
            reason=failure_reason or "EXAMINER_RUNTIME_CONFIG_MISSING",
        )
        return

    handler = ExaminerWebSocketHandler(runtime)
    await handler.handle_connection(
        websocket,
        resolved_session_id,
        token,
        trace_id=trace_id,
    )


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
