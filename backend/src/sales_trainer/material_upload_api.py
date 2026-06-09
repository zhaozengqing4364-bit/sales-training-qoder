from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from sales_trainer.permissions import can_manage_sales_trainer
from sales_trainer.schemas import SalesTrainerMaterialVersionResponse
from sales_trainer.services.material_service import (
    MaterialServiceError,
    SalesTrainerMaterialService,
    serialize_material_version,
)
from sales_trainer.services.material_upload_service import (
    SalesTrainerMaterialUploadService,
)

sales_trainer_admin_material_upload_router = APIRouter(
    prefix="/admin/sales-trainer",
    tags=["admin-sales-trainer-materials"],
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


@sales_trainer_admin_material_upload_router.post(
    "/materials/{material_id}/versions/upload",
    response_model=None,
)
async def admin_upload_material_version(
    material_id: str,
    version_label: str = Form(..., min_length=1, max_length=80),
    title: str = Form(..., min_length=1, max_length=200),
    release_notes: str | None = Form(None, max_length=4000),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if error := _require_manager(current_user):
        return error
    material_service = SalesTrainerMaterialService(db)
    material = await material_service.get_material(material_id)
    if material is None:
        return _api_error("[SALES_TRAINER_MATERIAL_NOT_FOUND]", status_code=404)
    try:
        version = await SalesTrainerMaterialUploadService(db).upload_version_file(
            material,
            file=file,
            version_label=version_label,
            title=title,
            release_notes=release_notes,
            actor=current_user,
        )
    except MaterialServiceError as exc:
        return _api_error(exc.code, status_code=exc.status_code, message=exc.message)
    return success_response(
        SalesTrainerMaterialVersionResponse.model_validate(
            serialize_material_version(version)
        ).model_dump()
    )
