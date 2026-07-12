"""Focused administration API for newcomer-training path orchestration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.orchestration.contracts import StrictModel, TrainingPathPayload
from sales_trainer.orchestration.errors import (
    NewcomerOrchestrationError,
    PathValidationError,
)
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService
from sales_trainer.permissions import (
    can_manage_newcomer_training_path,
    can_publish_newcomer_training_path,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)

admin_router = APIRouter(prefix="/admin/newcomer-training/path")


class DraftRequest(StrictModel):
    payload: TrainingPathPayload
    reason: str = Field(min_length=1, max_length=500)


class ReasonRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


def _forbidden() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response(
            "[ROLE_REQUIRED]", message="当前账号没有管理训练路径的权限。"
        ),
    )


def _error(exc: NewcomerOrchestrationError) -> JSONResponse:
    details = None
    if isinstance(exc, PathValidationError):
        details = [
            {
                "code": issue.code,
                "message": issue.message,
                "object_id": issue.object_id,
                "field_path": issue.field_path,
                "severity": issue.severity,
            }
            for issue in exc.issues
        ]
    content = error_response(exc.code, message=exc.message)
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=exc.status_code, content=content)


def _trace_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request.headers.get("x-trace-id")


@admin_router.get("/", response_model=None)
async def get_path(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        (await TrainingPathRevisionService(db).get_config()).model_dump()
    )


@admin_router.put("/draft", response_model=None)
async def save_draft(
    payload: DraftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        revision = await TrainingPathRevisionService(db).save_draft(
            payload=payload.payload,
            actor=current_user,
            reason=payload.reason,
            trace_id=_trace_id(request),
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(revision))


@admin_router.delete("/draft", response_model=None)
async def delete_draft(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    await TrainingPathRevisionService(db).delete_draft(
        actor=current_user, trace_id=_trace_id(request)
    )
    await db.commit()
    return success_response({"deleted": True})


@admin_router.post("/validate", response_model=None)
async def validate_draft(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await TrainingPathRevisionService(db).validate_draft()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(result.model_dump())


@admin_router.post("/publish", response_model=None)
async def publish(
    payload: ReasonRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_publish_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await TrainingPathRevisionService(db).publish(
            actor=current_user, reason=payload.reason, trace_id=_trace_id(request)
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(result.revision))


@admin_router.get("/revisions", response_model=None)
async def revisions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    rows = await TrainingPathRevisionService(db).list_revisions()
    return success_response(
        [SalesTrainerAssetRevisionService.snapshot(row) for row in rows]
    )


@admin_router.post("/revisions/{revision_id}/restore", response_model=None)
async def restore(
    revision_id: str,
    payload: ReasonRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        row = await TrainingPathRevisionService(db).restore_as_draft(
            revision_id=revision_id,
            actor=current_user,
            reason=payload.reason,
            trace_id=_trace_id(request),
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(row))


@admin_router.get("/activity-types", response_model=None)
async def activity_types(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        [
            {"type": key, "label": label}
            for key, label in (
                ("lesson", "内容学习"),
                ("quiz", "考试测验"),
                ("audio_assessment", "录音讲解"),
                ("realtime_roleplay", "实时对练"),
                ("ai_coach", "AI 教练"),
                ("assignment", "作业任务"),
            )
        ]
    )


__all__ = ["admin_router"]
