from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import (
    NewcomerPathConfigActionRequest,
    NewcomerPathConfigResponse,
    NewcomerPathConfigSaveRequest,
    NewcomerPathRevisionListResponse,
    NewcomerPathRevisionSummary,
)
from sales_trainer.services.path_config_models import SalesTrainerPathConfigError
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService

newcomer_admin_path_config_router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training-path-config"],
)


def _api_error(
    code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
    trace_id: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(code, message=message or code, trace_id=trace_id),
    )


def _require_manager(user: User) -> JSONResponse | None:
    if can_manage_sales_trainer(user):
        return None
    return _api_error("[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足。")


@newcomer_admin_path_config_router.get("/path-config", response_model=None)
async def get_path_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        payload = await SalesTrainerPathConfigService(db).get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(NewcomerPathConfigResponse.model_validate(payload).model_dump())


@newcomer_admin_path_config_router.put("/path-config", response_model=None)
async def save_path_config(
    payload: NewcomerPathConfigSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        await service.save_config(payload, actor=current_user, trace_id=trace_id)
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.post("/path-config/publish", response_model=None)
async def publish_path_config(
    payload: NewcomerPathConfigActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        await service.publish_config(
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )


@newcomer_admin_path_config_router.get("/path-config/revisions", response_model=None)
async def list_path_config_revisions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        revisions = await SalesTrainerPathConfigService(db).list_revisions()
    except SalesTrainerPathConfigError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [
        NewcomerPathRevisionSummary.model_validate(item).model_dump()
        for item in revisions
    ]
    return success_response(
        NewcomerPathRevisionListResponse(items=items, total=len(items))
    )


@newcomer_admin_path_config_router.post("/path-config/rollback", response_model=None)
async def rollback_path_config(
    payload: NewcomerPathConfigActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    if not payload.revision_id:
        return _api_error(
            "[NEWCOMER_PATH_REVISION_REQUIRED]",
            status_code=422,
            message="请选择要回滚的新人训练路径历史版本。",
        )
    service = SalesTrainerPathConfigService(db)
    trace_id = get_trace_id()
    try:
        await service.rollback_config(
            revision_id=payload.revision_id,
            actor=current_user,
            reason=payload.reason,
            trace_id=trace_id,
        )
        response = await service.get_config()
    except SalesTrainerPathConfigError as exc:
        return _api_error(
            exc.code,
            status_code=exc.status_code,
            message=exc.message,
            trace_id=trace_id,
        )
    return success_response(
        NewcomerPathConfigResponse.model_validate(response).model_dump(),
        trace_id=trace_id,
    )
