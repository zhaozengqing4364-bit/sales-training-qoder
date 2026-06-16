from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import (
    BusinessEtiquetteAiCoachProgressResponse,
    BusinessEtiquetteCapabilityActionRequest,
    BusinessEtiquetteCapabilitySnapshotResponse,
    BusinessEtiquetteCapabilitySnapshotSaveRequest,
    BusinessEtiquetteImportResponse,
    BusinessEtiquetteLearningUnitsResponse,
    BusinessEtiquetteQuestionDraftApproveRequest,
    BusinessEtiquetteQuestionDraftGenerateRequest,
    BusinessEtiquetteQuestionDraftGenerateResponse,
    BusinessEtiquetteQuestionDraftListResponse,
    BusinessEtiquetteQuestionDraftRejectRequest,
    BusinessEtiquetteQuestionDraftResponse,
    BusinessEtiquetteQuestionDraftUpdateRequest,
    BusinessEtiquetteReleaseImpactResponse,
    BusinessEtiquetteReleasePublishRequest,
    BusinessEtiquetteReleasePublishResponse,
    BusinessEtiquetteRetrainingAssignmentRequest,
    BusinessEtiquetteRetrainingAssignmentResponse,
    BusinessEtiquetteRetrainingStartRequest,
    BusinessEtiquetteUnitQuizAttemptCreate,
    BusinessEtiquetteUnitQuizAttemptListResponse,
    BusinessEtiquetteUnitQuizAttemptResponse,
    BusinessEtiquetteUnitQuizResponse,
)
from sales_trainer.services.business_etiquette_ai_coach_progress_service import (
    BusinessEtiquetteAiCoachProgressService,
    BusinessEtiquetteAiCoachProgressServiceError,
)
from sales_trainer.services.business_etiquette_capability_service import (
    BusinessEtiquetteCapabilityService,
    BusinessEtiquetteCapabilityServiceError,
)
from sales_trainer.services.business_etiquette_import_service import (
    BusinessEtiquetteImportService,
    BusinessEtiquetteImportServiceError,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BusinessEtiquetteLearningService,
    BusinessEtiquetteLearningServiceError,
)
from sales_trainer.services.business_etiquette_question_draft_service import (
    BusinessEtiquetteQuestionDraftService,
    BusinessEtiquetteQuestionDraftServiceError,
)
from sales_trainer.services.business_etiquette_quiz_service import (
    BusinessEtiquetteQuizService,
    BusinessEtiquetteQuizServiceError,
)
from sales_trainer.services.business_etiquette_release_service import (
    BusinessEtiquetteReleaseService,
    BusinessEtiquetteReleaseServiceError,
)

business_etiquette_router = APIRouter(
    prefix="/newcomer-training/business-etiquette",
    tags=["newcomer-training-business-etiquette"],
)
business_etiquette_admin_router = APIRouter(
    prefix="/admin/newcomer-training/business-etiquette",
    tags=["admin-newcomer-training-business-etiquette"],
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code),
    )


def _require_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


@business_etiquette_router.get("/learning-units", response_model=None)
async def get_business_etiquette_learning_units(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await BusinessEtiquetteLearningService(db).get_learning_units(
            user_id=str(current_user.user_id),
        )
    except BusinessEtiquetteLearningServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteLearningUnitsResponse.model_validate(result).model_dump()
    )


@business_etiquette_router.get(
    "/learning-units/{unit_key}/quiz",
    response_model=None,
)
async def get_business_etiquette_unit_quiz(
    unit_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await BusinessEtiquetteQuizService(db).get_unit_quiz(
            unit_key,
            user_id=str(current_user.user_id),
        )
    except BusinessEtiquetteQuizServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteUnitQuizResponse.model_validate(result).model_dump(
            mode="json"
        )
    )


@business_etiquette_router.post(
    "/learning-units/{unit_key}/quiz-attempts",
    response_model=None,
)
async def submit_business_etiquette_unit_quiz_attempt(
    unit_key: str,
    payload: BusinessEtiquetteUnitQuizAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await BusinessEtiquetteQuizService(db).submit_attempt(
            unit_key,
            payload,
            actor=current_user,
        )
    except BusinessEtiquetteQuizServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteUnitQuizAttemptResponse.model_validate(result).model_dump(
            mode="json"
        )
    )


@business_etiquette_router.get(
    "/learning-units/{unit_key}/quiz-attempts",
    response_model=None,
)
async def list_my_business_etiquette_unit_quiz_attempts(
    unit_key: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await BusinessEtiquetteQuizService(db).list_attempts(
            user_id=str(current_user.user_id),
            learning_unit_key=unit_key,
            limit=limit,
            offset=offset,
        )
    except BusinessEtiquetteQuizServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteUnitQuizAttemptListResponse.model_validate(
            result
        ).model_dump(mode="json")
    )


@business_etiquette_router.get("/ai-coach/progress", response_model=None)
async def get_business_etiquette_ai_coach_progress(
    session_id: str = Query(..., min_length=1, max_length=36),
    unit_key: str | None = Query(None, min_length=1, max_length=80),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await BusinessEtiquetteAiCoachProgressService(db).get_progress(
            session_id=session_id,
            user_id=str(current_user.user_id),
            unit_key=unit_key,
        )
    except BusinessEtiquetteAiCoachProgressServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteAiCoachProgressResponse.model_validate(result).model_dump(
            mode="json"
        )
    )


@business_etiquette_router.post("/retraining-sessions", response_model=None)
async def start_business_etiquette_retraining_session(
    payload: BusinessEtiquetteRetrainingStartRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    trace_id = get_trace_id()
    try:
        session_id = await BusinessEtiquetteReleaseService(
            db
        ).start_voluntary_retraining(
            actor=current_user,
            reason=payload.reason if payload else None,
            trace_id=trace_id,
        )
    except BusinessEtiquetteReleaseServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response({"session_id": session_id}, trace_id=trace_id)


@business_etiquette_admin_router.post("/imports", response_model=None)
async def import_business_etiquette_markdown(
    training_pack_key: str | None = Form(None, min_length=1, max_length=80),
    allow_overwrite_draft: bool | None = Form(None),
    reason: str | None = Form(None, max_length=500),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    file_bytes = await file.read()
    try:
        result = await BusinessEtiquetteImportService(db).import_markdown(
            file_bytes=file_bytes,
            source_filename=file.filename or "",
            content_type=file.content_type,
            actor=current_user,
            training_pack_key=training_pack_key,
            allow_overwrite_draft=allow_overwrite_draft,
            reason=reason,
            trace_id=trace_id,
        )
    except BusinessEtiquetteImportServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteImportResponse.model_validate(result).model_dump(),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.get("/release-impact", response_model=None)
async def preview_business_etiquette_release_impact(
    training_pack_key: str | None = Query(None, min_length=1, max_length=80),
    target_revision_id: str | None = Query(None, min_length=1, max_length=36),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        result = await BusinessEtiquetteReleaseService(db).preview_release_impact(
            training_pack_key=training_pack_key,
            target_revision_id=target_revision_id,
        )
    except BusinessEtiquetteReleaseServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteReleaseImpactResponse.model_validate(result).model_dump(
            mode="json"
        )
    )


@business_etiquette_admin_router.post("/release", response_model=None)
async def publish_business_etiquette_release(
    payload: BusinessEtiquetteReleasePublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteReleaseService(db).publish_release(
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteReleaseServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteReleasePublishResponse.model_validate(result).model_dump(
            mode="json"
        ),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.post(
    "/retraining-assignments",
    response_model=None,
)
async def assign_business_etiquette_retraining(
    payload: BusinessEtiquetteRetrainingAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteReleaseService(db).assign_retraining(
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteReleaseServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteRetrainingAssignmentResponse.model_validate(
            result
        ).model_dump(mode="json"),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.get("/capabilities", response_model=None)
async def get_business_etiquette_capabilities(
    training_pack_key: str | None = Query(None, min_length=1, max_length=80),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        result = await BusinessEtiquetteCapabilityService(db).get_snapshot(
            training_pack_key=training_pack_key,
        )
    except BusinessEtiquetteCapabilityServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteCapabilitySnapshotResponse.model_validate(
            result
        ).model_dump(mode="json")
    )


@business_etiquette_admin_router.put("/capabilities", response_model=None)
async def save_business_etiquette_capabilities(
    payload: BusinessEtiquetteCapabilitySnapshotSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteCapabilityService(db).save_snapshot(
            capabilities=list(payload.capabilities),
            chapter_bindings=list(payload.chapter_bindings),
            actor=current_user,
            training_pack_key=payload.training_pack_key,
            reason=payload.reason,
            trace_id=trace_id,
        )
    except BusinessEtiquetteCapabilityServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteCapabilitySnapshotResponse.model_validate(
            result
        ).model_dump(mode="json"),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.post(
    "/capabilities/{capability_key}/publish",
    response_model=None,
)
async def publish_business_etiquette_capability(
    capability_key: str,
    payload: BusinessEtiquetteCapabilityActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _update_business_etiquette_capability_status(
        capability_key=capability_key,
        status="published",
        payload=payload,
        current_user=current_user,
        db=db,
    )


@business_etiquette_admin_router.post(
    "/capabilities/{capability_key}/archive",
    response_model=None,
)
async def archive_business_etiquette_capability(
    capability_key: str,
    payload: BusinessEtiquetteCapabilityActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    return await _update_business_etiquette_capability_status(
        capability_key=capability_key,
        status="archived",
        payload=payload,
        current_user=current_user,
        db=db,
    )


@business_etiquette_admin_router.post("/question-drafts/generate", response_model=None)
async def generate_business_etiquette_question_drafts(
    payload: BusinessEtiquetteQuestionDraftGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteQuestionDraftService(db).generate_drafts(
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteQuestionDraftServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteQuestionDraftGenerateResponse.model_validate(
            result
        ).model_dump(mode="json", by_alias=True),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.get("/question-drafts", response_model=None)
async def list_business_etiquette_question_drafts(
    training_pack_key: str | None = Query(None, min_length=1, max_length=80),
    chapter_order: int | None = Query(None, ge=1, le=100),
    question_type: str | None = Query(None, min_length=1, max_length=30),
    status: str | None = Query(None, min_length=1, max_length=30),
    capability_key: str | None = Query(None, min_length=1, max_length=80),
    batch_id: str | None = Query(None, min_length=1, max_length=36),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        result = await BusinessEtiquetteQuestionDraftService(db).list_drafts(
            training_pack_key=training_pack_key,
            chapter_order=chapter_order,
            question_type=question_type,
            status=status,
            capability_key=capability_key,
            batch_id=batch_id,
            limit=limit,
            offset=offset,
        )
    except BusinessEtiquetteQuestionDraftServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteQuestionDraftListResponse.model_validate(
            result
        ).model_dump(mode="json", by_alias=True)
    )


@business_etiquette_admin_router.put(
    "/question-drafts/{draft_id}",
    response_model=None,
)
async def update_business_etiquette_question_draft(
    draft_id: str,
    payload: BusinessEtiquetteQuestionDraftUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteQuestionDraftService(db).update_draft(
            draft_id,
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteQuestionDraftServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteQuestionDraftResponse.model_validate(result).model_dump(
            mode="json",
            by_alias=True,
        ),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.post(
    "/question-drafts/{draft_id}/approve",
    response_model=None,
)
async def approve_business_etiquette_question_draft(
    draft_id: str,
    payload: BusinessEtiquetteQuestionDraftApproveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteQuestionDraftService(db).approve_draft(
            draft_id,
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteQuestionDraftServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteQuestionDraftResponse.model_validate(result).model_dump(
            mode="json",
            by_alias=True,
        ),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.post(
    "/question-drafts/{draft_id}/reject",
    response_model=None,
)
async def reject_business_etiquette_question_draft(
    draft_id: str,
    payload: BusinessEtiquetteQuestionDraftRejectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteQuestionDraftService(db).reject_draft(
            draft_id,
            payload,
            actor=current_user,
            trace_id=trace_id,
        )
    except BusinessEtiquetteQuestionDraftServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteQuestionDraftResponse.model_validate(result).model_dump(
            mode="json",
            by_alias=True,
        ),
        trace_id=trace_id,
    )


@business_etiquette_admin_router.get(
    "/learning-units/{unit_key}/quiz-preview",
    response_model=None,
)
async def preview_business_etiquette_unit_quiz(
    unit_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        result = await BusinessEtiquetteQuizService(db).preview_unit_quiz(unit_key)
    except BusinessEtiquetteQuizServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteUnitQuizResponse.model_validate(result).model_dump(
            mode="json"
        )
    )


@business_etiquette_admin_router.get("/quiz-attempts", response_model=None)
async def list_business_etiquette_quiz_attempts(
    user_id: str | None = Query(None, min_length=1, max_length=36),
    learning_unit_key: str | None = Query(None, min_length=1, max_length=80),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        result = await BusinessEtiquetteQuizService(db).list_attempts(
            user_id=user_id,
            learning_unit_key=learning_unit_key,
            limit=limit,
            offset=offset,
        )
    except BusinessEtiquetteQuizServiceError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteUnitQuizAttemptListResponse.model_validate(
            result
        ).model_dump(mode="json")
    )


async def _update_business_etiquette_capability_status(
    *,
    capability_key: str,
    status: str,
    payload: BusinessEtiquetteCapabilityActionRequest | None,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    trace_id = get_trace_id()
    try:
        result = await BusinessEtiquetteCapabilityService(
            db
        ).update_capability_status(
            capability_key=capability_key,
            status="published" if status == "published" else "archived",
            actor=current_user,
            training_pack_key=payload.training_pack_key if payload else None,
            reason=payload.reason if payload else None,
            trace_id=trace_id,
        )
    except BusinessEtiquetteCapabilityServiceError as exc:
        await db.rollback()
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
    return success_response(
        BusinessEtiquetteCapabilitySnapshotResponse.model_validate(
            result
        ).model_dump(mode="json"),
        trace_id=trace_id,
    )
