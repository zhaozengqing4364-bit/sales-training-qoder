"""Canonical learner API for activity-orchestrated newcomer training."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id
from sales_trainer.orchestration.activities.ai_coach import AiCoachActivityHandler
from sales_trainer.orchestration.activities.assignment import AssignmentActivityHandler
from sales_trainer.orchestration.activities.audio_assessment import (
    AudioAssessmentActivityHandler,
)
from sales_trainer.orchestration.activities.lesson import LessonActivityHandler
from sales_trainer.orchestration.activities.quiz import QuizActivityHandler
from sales_trainer.orchestration.activities.realtime_roleplay import (
    RealtimeRoleplayActivityHandler,
)
from sales_trainer.orchestration.contracts import StrictModel
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.permissions import can_learn_newcomer_training_path
from sales_trainer.schemas import QuizAnswerSubmit
from sales_trainer.services.audio_submission_service import AudioSubmissionServiceError
from sales_trainer.services.effective_audio_training_config import (
    EffectiveAudioTrainingConfigError,
)
from sales_trainer.services.material_service import MaterialServiceError

learner_router = APIRouter(prefix="/newcomer-training")
logger = get_logger(__name__)

_TYPED_BUSINESS_ERRORS = (
    NewcomerOrchestrationError,
    AudioSubmissionServiceError,
    MaterialServiceError,
    EffectiveAudioTrainingConfigError,
)

_UNSAFE_CLIENT_MESSAGE_MARKERS = (
    "/tmp",
    "/home/",
    "/var/",
    "/usr/",
    "/etc/",
    "traceback",
    'file "',
    "secret",
    ".env",
    "password",
    "api_key",
    "access_key",
    "credentials not configured",
    "missing env vars",
    "tencent_cos_",
    "ali_oss_",
    "secret_id",
    "secret_key",
)

_SAFE_MESSAGE_BY_CODE = {
    "[COS_NOT_CONFIGURED]": "对象存储暂不可用，请稍后重试或联系管理员。",
    "[OSS_NOT_CONFIGURED]": "对象存储暂不可用，请稍后重试或联系管理员。",
    "[NEWCOMER_SERVICE_UNAVAILABLE]": "服务暂不可用，请稍后重试。",
    "[NEWCOMER_ACTIVITY_FAILED]": "训练操作失败，请稍后重试。",
    "[NEWCOMER_UPLOAD_FAILED]": "上传失败：请重新选择录音文件后重试。",
    "[NEWCOMER_REQUEST_INVALID]": "请求无效：请确认录音文件与页面信息后重试。",
    "[NEWCOMER_ACTIVITY_FORBIDDEN]": "当前没有权限完成该训练操作。",
}


class ClientTokenRequest(StrictModel):
    client_token: str = Field(min_length=1, max_length=100)


class QuizAttemptRequest(ClientTokenRequest):
    answers: list[QuizAnswerSubmit] = Field(min_length=1)


class AiCoachTurnRequest(ClientTokenRequest):
    answer: str = Field(min_length=1, max_length=10_000)


def _forbidden() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response("[ROLE_REQUIRED]", message="当前账号不能进入新人训练。"),
    )


def _looks_unsafe_client_message(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _UNSAFE_CLIENT_MESSAGE_MARKERS)


def _client_safe_business_message(code: str, message: str) -> str:
    """Keep actionable Chinese copy; redact secrets/paths/env dumps."""
    text = message.strip()
    if text and not _looks_unsafe_client_message(text):
        if any("\u4e00" <= ch <= "\u9fff" for ch in text):
            return text
        # Allow short non-Chinese codes only when already Chinese-safe above.
    return _SAFE_MESSAGE_BY_CODE.get(code, "训练操作失败，请稍后重试。")


def _typed_business_error(
    exc: Exception,
) -> tuple[str, str, int] | None:
    if isinstance(exc, _TYPED_BUSINESS_ERRORS):
        return (
            exc.code,
            _client_safe_business_message(exc.code, exc.message),
            int(exc.status_code),
        )
    code = getattr(exc, "code", None)
    message = getattr(exc, "message", None)
    status_code = getattr(exc, "status_code", None)
    if (
        isinstance(code, str)
        and code.startswith("[")
        and code.endswith("]")
        and isinstance(message, str)
        and message.strip()
        and isinstance(status_code, int)
        and 400 <= status_code < 600
    ):
        return code, _client_safe_business_message(code, message), status_code
    return None


def _classify_unexpected_error(exc: Exception) -> tuple[str, str, int]:
    """Map unexpected exceptions to safe learner-facing copy (no secrets/paths)."""
    if isinstance(exc, PermissionError):
        return (
            "[NEWCOMER_ACTIVITY_FORBIDDEN]",
            "当前没有权限完成该训练操作。",
            403,
        )
    if isinstance(exc, (FileNotFoundError, IsADirectoryError)):
        return (
            "[NEWCOMER_UPLOAD_FAILED]",
            "上传失败：录音文件无法读取，请重新选择文件后重试。",
            422,
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return (
            "[NEWCOMER_SERVICE_UNAVAILABLE]",
            "服务暂不可用，请稍后重试。",
            503,
        )
    if isinstance(exc, (ValidationError, TypeError, ValueError)):
        return (
            "[NEWCOMER_REQUEST_INVALID]",
            "请求无效：请确认录音文件与页面信息后重试。",
            422,
        )
    if isinstance(exc, SQLAlchemyError):
        return (
            "[NEWCOMER_SERVICE_UNAVAILABLE]",
            "服务暂不可用，请稍后重试。",
            503,
        )
    name = type(exc).__name__.lower()
    if "multipart" in name or "upload" in name:
        return (
            "[NEWCOMER_UPLOAD_FAILED]",
            "上传失败：请重新选择录音文件后重试。",
            422,
        )
    return (
        "[NEWCOMER_ACTIVITY_FAILED]",
        "训练操作失败，请稍后重试。",
        500,
    )


def _error(exc: Exception) -> JSONResponse:
    typed = _typed_business_error(exc)
    if typed is not None:
        code, message, status = typed
        raw_message = str(getattr(exc, "message", "") or "")
        if raw_message and _looks_unsafe_client_message(raw_message):
            logger.warning(
                "newcomer_learner_business_message_redacted",
                error_type=type(exc).__name__,
                error_code=code,
                trace_id=get_trace_id(),
                exception_message=raw_message[:500],
            )
        return JSONResponse(
            status_code=status,
            content=error_response(code, message=message),
        )

    code, message, status = _classify_unexpected_error(exc)
    trace_id = get_trace_id()
    logger.error(
        "newcomer_learner_activity_failed",
        error_type=type(exc).__name__,
        error_code=code,
        trace_id=trace_id,
        exception_message=str(exc)[:500],
        exc_info=True,
    )
    return JSONResponse(
        status_code=status,
        content=error_response(code, message=message, trace_id=trace_id),
    )


async def _detail(db: AsyncSession, user: User, activity_id: str) -> dict[str, Any]:
    return success_response(
        (
            await NewcomerJourneyService(db).activity_detail(
                learner=user, activity_id=activity_id
            )
        ).model_dump()
    )


@learner_router.get("/journey", response_model=None)
async def journey(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await NewcomerJourneyService(db).get_or_create_for_learner(
            learner=current_user
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(result.model_dump())


@learner_router.get("/modules/{module_id}", response_model=None)
async def module_detail(
    module_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await NewcomerJourneyService(db).module_detail(
            learner=current_user, module_id=module_id
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(result.model_dump())


@learner_router.get("/activities/{activity_id}", response_model=None)
async def activity_detail(
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await _detail(db, current_user, activity_id)
        await db.commit()
        return result
    except NewcomerOrchestrationError as exc:
        return _error(exc)


@learner_router.post(
    "/activities/{activity_id}/lesson/chapters/{chapter_id}/complete",
    response_model=None,
)
async def complete_lesson_chapter(
    activity_id: str,
    chapter_id: str,
    payload: ClientTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        await LessonActivityHandler(db).mark_chapter_complete(
            context,
            chapter_id=chapter_id,
            actor=current_user,
            client_token=payload.client_token,
        )
        await db.commit()
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


@learner_router.post("/activities/{activity_id}/lesson/confirm", response_model=None)
async def confirm_lesson(
    activity_id: str,
    payload: ClientTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        await LessonActivityHandler(db).confirm(
            context, actor=current_user, client_token=payload.client_token
        )
        await db.commit()
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


@learner_router.post("/activities/{activity_id}/quiz/attempts", response_model=None)
async def submit_quiz(
    activity_id: str,
    payload: QuizAttemptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        await QuizActivityHandler(db).submit(
            context,
            answers=payload.answers,
            client_token=payload.client_token,
            actor=current_user,
        )
        await db.commit()
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


@learner_router.post("/activities/{activity_id}/audio/submissions", response_model=None)
async def submit_audio(
    activity_id: str,
    client_token: str = Form(...),
    confirmed_material_version_id: str | None = Form(None),
    confirmed_scoring_rubric_revision_id: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        await AudioAssessmentActivityHandler(db).submit_file(
            context,
            file=file,
            confirmed_material_version_id=confirmed_material_version_id,
            confirmed_scoring_rubric_revision_id=(
                confirmed_scoring_rubric_revision_id
            ),
            client_token=client_token,
            actor=current_user,
        )
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


@learner_router.post("/activities/{activity_id}/realtime/sessions", response_model=None)
async def start_realtime(
    activity_id: str,
    payload: ClientTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        start_result = await RealtimeRoleplayActivityHandler(db).start_session(
            context, actor=current_user, client_token=payload.client_token
        )
        return success_response(
            {
                "session_id": start_result["session_id"],
                "detail": (
                    await NewcomerJourneyService(db).activity_detail(
                        learner=current_user, activity_id=activity_id
                    )
                ).model_dump(),
            }
        )
    except Exception as exc:
        return _error(exc)


@learner_router.post("/activities/{activity_id}/ai-coach/sessions", response_model=None)
async def start_ai_coach(
    activity_id: str,
    payload: ClientTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        _, session = await AiCoachActivityHandler(db).start_session(
            context, actor=current_user, client_token=payload.client_token
        )
        await db.commit()
        return success_response(
            {
                "session_id": str(session.session_id),
                "first_question": str(
                    cast(dict[str, Any], session.coach_state or {}).get(
                        "current_question"
                    )
                    or ""
                ),
                "detail": (
                    await NewcomerJourneyService(db).activity_detail(
                        learner=current_user, activity_id=activity_id
                    )
                ).model_dump(),
            }
        )
    except Exception as exc:
        return _error(exc)


@learner_router.post(
    "/activities/{activity_id}/ai-coach/sessions/{session_id}/turns",
    response_model=None,
)
async def submit_ai_coach_turn(
    activity_id: str,
    session_id: str,
    payload: AiCoachTurnRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        if context.activity.type != "ai_coach":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_TYPE_MISMATCH]", "当前任务不是 AI 辅导。", 422
            )
        state = await AiCoachActivityHandler(db).submit_turn(
            context,
            session_id=session_id,
            actor=current_user,
            answer=payload.answer,
            client_token=payload.client_token,
        )
        return success_response(
            {
                **state,
                "detail": (
                    await NewcomerJourneyService(db).activity_detail(
                        learner=current_user, activity_id=activity_id
                    )
                ).model_dump(),
            }
        )
    except Exception as exc:
        return _error(exc)


@learner_router.post(
    "/activities/{activity_id}/ai-coach/sessions/{session_id}/turns/stream",
    response_model=None,
)
async def stream_ai_coach_turn(
    activity_id: str,
    session_id: str,
    payload: AiCoachTurnRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()

    async def events() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'started'}, ensure_ascii=False)}\n\n"
        try:
            context = await NewcomerJourneyService(db).context_for_activity(
                learner=current_user, activity_id=activity_id
            )
            state = await AiCoachActivityHandler(db).submit_turn(
                context,
                session_id=session_id,
                actor=current_user,
                answer=payload.answer,
                client_token=payload.client_token,
            )
            detail = await NewcomerJourneyService(db).activity_detail(
                learner=current_user, activity_id=activity_id
            )
            yield f"data: {json.dumps({'type': 'result', **state, 'detail': detail.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(getattr(exc, 'message', 'AI 教练暂时无法反馈，请重试。'))}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@learner_router.post("/activities/{activity_id}/assignments", response_model=None)
async def submit_assignment(
    activity_id: str,
    client_token: str = Form(...),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_learn_newcomer_training_path(current_user):
        return _forbidden()
    try:
        context = await NewcomerJourneyService(db).context_for_activity(
            learner=current_user, activity_id=activity_id
        )
        await AssignmentActivityHandler(db).submit(
            context, text=text, file=file, client_token=client_token, actor=current_user
        )
        await db.commit()
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


__all__ = ["learner_router"]
