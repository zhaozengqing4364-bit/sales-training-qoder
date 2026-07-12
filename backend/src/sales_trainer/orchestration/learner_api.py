"""Canonical learner API for activity-orchestrated newcomer training."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
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

learner_router = APIRouter(prefix="/newcomer-training")


class ClientTokenRequest(StrictModel):
    client_token: str = Field(min_length=1, max_length=100)


class QuizAttemptRequest(ClientTokenRequest):
    answers: list[QuizAnswerSubmit] = Field(min_length=1)


def _forbidden() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response("[ROLE_REQUIRED]", message="当前账号不能进入新人训练。"),
    )


def _error(exc: Exception) -> JSONResponse:
    code = str(getattr(exc, "code", "[NEWCOMER_ACTIVITY_FAILED]"))
    message = str(getattr(exc, "message", "训练操作失败，请重试。"))
    status = int(getattr(exc, "status_code", 400))
    return JSONResponse(
        status_code=status, content=error_response(code, message=message)
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
        return await _detail(db, current_user, activity_id)
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
        await RealtimeRoleplayActivityHandler(db).start(
            context, actor=current_user, client_token=payload.client_token
        )
        return await _detail(db, current_user, activity_id)
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
        await AiCoachActivityHandler(db).start(
            context, actor=current_user, client_token=payload.client_token
        )
        await db.commit()
        return await _detail(db, current_user, activity_id)
    except Exception as exc:
        return _error(exc)


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
