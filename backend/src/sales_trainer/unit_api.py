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
from sales_trainer.schemas import SalesTrainerUnitResponse
from sales_trainer.services.unit_revision_service import (
    UnitRevisionService,
    UnitRevisionServiceError,
)
from sales_trainer.services.unit_service import UnitService
from sales_trainer.unit_revision_schemas import (
    UnitRevisionListResponse,
    UnitRevisionResponse,
    UnitRollbackRequest,
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


async def list_unit_revisions(
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


async def rollback_unit_revision(
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
    list_unit_revisions,
    methods=["GET"],
    response_model=None,
)
sales_trainer_admin_unit_revision_router.add_api_route(
    "/units/{unit_id}/rollback",
    rollback_unit_revision,
    methods=["POST"],
    response_model=None,
)
