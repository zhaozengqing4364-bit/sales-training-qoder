from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import (
    SalesTrainerUnitCreate,
    SalesTrainerUnitListResponse,
    SalesTrainerUnitResponse,
    SalesTrainerUnitUpdate,
)
from sales_trainer.services.unit_revision_service import (
    UnitRevisionService,
    UnitRevisionServiceError,
)
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService
from sales_trainer.unit_revision_schemas import (
    UnitRevisionListResponse,
    UnitRevisionResponse,
    UnitRollbackRequest,
)

newcomer_admin_unit_router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training-units"],
)
sales_trainer_admin_unit_revision_router = APIRouter(
    prefix="/admin/sales-trainer",
    tags=["admin-sales-trainer-unit-revisions"],
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


def _as_unit_response(payload: dict[str, Any]) -> dict[str, Any]:
    return SalesTrainerUnitResponse.model_validate(payload).model_dump()


@newcomer_admin_unit_router.get("/units", response_model=None)
async def list_newcomer_units(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    units, total = await service.list_units(include_archived=False)
    items = [_as_unit_response(await service.serialize_unit(unit)) for unit in units]
    return success_response(SalesTrainerUnitListResponse(items=items, total=total))


@newcomer_admin_unit_router.post("/units", response_model=None)
async def create_newcomer_unit(
    payload: SalesTrainerUnitCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    try:
        unit = await service.create_unit(payload, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(unit)))


@newcomer_admin_unit_router.put("/units/{unit_id}", response_model=None)
async def update_newcomer_unit(
    unit_id: str,
    payload: SalesTrainerUnitUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    try:
        updated = await service.update_unit(unit, payload, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(updated)))


@newcomer_admin_unit_router.post("/units/{unit_id}/publish", response_model=None)
async def publish_newcomer_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    try:
        published = await service.publish_unit(unit, actor=current_user)
    except SalesTrainerUnitError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(published)))


@newcomer_admin_unit_router.post("/units/{unit_id}/archive", response_model=None)
async def archive_newcomer_unit(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    archived = await service.archive_unit(unit, actor=current_user)
    return success_response(_as_unit_response(await service.serialize_unit(archived)))


@newcomer_admin_unit_router.get("/units/{unit_id}/revisions", response_model=None)
async def list_newcomer_unit_revisions(
    unit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    try:
        revisions = await UnitRevisionService(db).list_revisions(unit_id)
    except UnitRevisionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    items = [UnitRevisionResponse.model_validate(item).model_dump() for item in revisions]
    return success_response(UnitRevisionListResponse(items=items, total=len(items)))


@newcomer_admin_unit_router.post("/units/{unit_id}/rollback", response_model=None)
async def rollback_newcomer_unit(
    unit_id: str,
    payload: UnitRollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    service = UnitService(db)
    unit = await service.get_unit(unit_id)
    if unit is None:
        return _api_error("[SALES_TRAINER_UNIT_NOT_FOUND]", status_code=404)
    try:
        rolled_back = await UnitRevisionService(db).rollback_to_revision(
            unit,
            target_revision_id=payload.target_revision_id,
            reason=payload.reason,
            actor=current_user,
        )
    except UnitRevisionServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(_as_unit_response(await service.serialize_unit(rolled_back)))


sales_trainer_admin_unit_revision_router.add_api_route(
    "/units/{unit_id}/revisions",
    list_newcomer_unit_revisions,
    methods=["GET"],
    response_model=None,
)
sales_trainer_admin_unit_revision_router.add_api_route(
    "/units/{unit_id}/rollback",
    rollback_newcomer_unit,
    methods=["POST"],
    response_model=None,
)
