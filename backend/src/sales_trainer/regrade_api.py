from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.permissions import (
    can_regrade_sales_trainer_history,
    team_scope_department,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.regrade_schemas import (
    RegradePreviewRequest,
    RegradePreviewResponse,
    RegradeRunRequest,
    RegradeRunResponse,
)
from sales_trainer.services.audio_regrade_calculator import AudioRegradePreview
from sales_trainer.services.audio_regrade_service import (
    SalesTrainerAudioRegradeService,
    SalesTrainerAudioRegradeServiceError,
)
from sales_trainer.services.regrade_service import (
    QuizRegradePreview,
    SalesTrainerRegradeService,
    SalesTrainerRegradeServiceError,
)

sales_trainer_admin_regrade_router = APIRouter(
    prefix="/admin/sales-trainer/regrades",
    tags=["admin-sales-trainer-regrades"],
)
newcomer_admin_regrade_router = APIRouter(
    prefix="/admin/newcomer-training/regrades",
    tags=["admin-newcomer-training-regrades"],
)


def _api_error(
    code: str,
    *,
    status_code: int,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message),
    )


def _require_regrade_permission(user: User) -> JSONResponse | None:
    if can_regrade_sales_trainer_history(user):
        return None
    return _api_error(
        "[ROLE_REQUIRED]",
        status_code=403,
        message="当前账号无权重新评分历史记录。",
    )


def _team_scope(user: User) -> str | None:
    return cast(str | None, team_scope_department(user))


async def preview_quiz_attempt_regrade(
    attempt_id: str,
    payload: RegradePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_regrade_permission(current_user):
        return error
    service = SalesTrainerRegradeService(db)
    try:
        preview = await service.preview_quiz_attempt(
            attempt_id,
            target_revision_id=payload.target_revision_id,
            viewer=current_user,
            team_department=_team_scope(current_user),
        )
    except SalesTrainerRegradeServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        RegradePreviewResponse.model_validate(_preview_payload(preview)).model_dump()
    )


async def run_quiz_attempt_regrade(
    attempt_id: str,
    payload: RegradeRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_regrade_permission(current_user):
        return error
    service = SalesTrainerRegradeService(db)
    try:
        run = await service.run_quiz_attempt_regrade(
            attempt_id,
            target_revision_id=payload.target_revision_id,
            reason=payload.reason,
            actor=current_user,
            team_department=_team_scope(current_user),
        )
    except SalesTrainerRegradeServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        RegradeRunResponse.model_validate(_run_payload(run)).model_dump()
    )


async def preview_audio_submission_regrade(
    submission_id: str,
    payload: RegradePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_regrade_permission(current_user):
        return error
    service = SalesTrainerAudioRegradeService(db)
    try:
        preview = await service.preview_audio_submission(
            submission_id,
            target_revision_id=payload.target_revision_id,
            viewer=current_user,
            team_department=_team_scope(current_user),
        )
    except SalesTrainerAudioRegradeServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        RegradePreviewResponse.model_validate(_preview_payload(preview)).model_dump()
    )


async def run_audio_submission_regrade(
    submission_id: str,
    payload: RegradeRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_regrade_permission(current_user):
        return error
    service = SalesTrainerAudioRegradeService(db)
    try:
        run = await service.run_audio_submission_regrade(
            submission_id,
            target_revision_id=payload.target_revision_id,
            reason=payload.reason,
            actor=current_user,
            team_department=_team_scope(current_user),
        )
    except SalesTrainerAudioRegradeServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        RegradeRunResponse.model_validate(_run_payload(run)).model_dump()
    )


def _preview_payload(
    preview: QuizRegradePreview | AudioRegradePreview,
) -> dict[str, Any]:
    return {
        "target_type": preview.target_type,
        "target_id": preview.target_id,
        "target_revision_id": preview.target_revision_id,
        "impact_scope": preview.impact_scope,
        "before_snapshot": preview.before_snapshot,
        "after_snapshot": preview.after_snapshot,
    }


def _run_payload(run: SalesTrainerRegradeRun) -> dict[str, Any]:
    return {
        "regrade_run_id": run.run_id,
        "target_type": run.target_type,
        "target_id": run.target_id,
        "target_revision_id": run.target_revision_id,
        "status": run.status,
        "reason": run.reason,
        "impact_scope": run.impact_scope_json,
        "before_snapshot": run.before_snapshot_json,
        "after_snapshot": run.after_snapshot_json,
        "trace_id": run.trace_id,
        "created_at": run.created_at,
    }


for router in (sales_trainer_admin_regrade_router, newcomer_admin_regrade_router):
    router.add_api_route(
        "/quiz-attempts/{attempt_id}/preview",
        preview_quiz_attempt_regrade,
        methods=["POST"],
        response_model=None,
    )
    router.add_api_route(
        "/quiz-attempts/{attempt_id}/run",
        run_quiz_attempt_regrade,
        methods=["POST"],
        response_model=None,
    )
    router.add_api_route(
        "/audio-submissions/{submission_id}/preview",
        preview_audio_submission_regrade,
        methods=["POST"],
        response_model=None,
    )
    router.add_api_route(
        "/audio-submissions/{submission_id}/run",
        run_audio_submission_regrade,
        methods=["POST"],
        response_model=None,
    )
