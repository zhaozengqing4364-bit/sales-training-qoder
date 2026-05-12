from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from curriculum_practice.permissions import can_manage_practice_templates
from curriculum_practice.schemas import (
    PracticeTemplateCreate,
    PracticeTemplateListResponse,
    PracticeTemplateUpdate,
)
from curriculum_practice.services.practice_templates import (
    PracticeTemplateService,
    published_ref,
    serialize_template,
)

router = APIRouter(
    prefix="/admin/curriculum-practice/templates", tags=["admin-curriculum-practice"]
)


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


def _api_error(
    error_code: str, *, status_code: int = 400, message: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message or error_code),
    )


def _require_admin(current_user: User) -> JSONResponse | None:
    if can_manage_practice_templates(current_user):
        return None
    return _api_error(
        "[ROLE_REQUIRED]", status_code=403, message="当前账号权限不足，无法执行该操作。"
    )


@router.get("", response_model=None)
async def list_practice_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    items = await service.list_templates()
    payload = PracticeTemplateListResponse(
        items=[serialize_template(item) for item in items],
        total=len(items),
    )
    return _success(payload)


@router.post("", response_model=None)
async def create_practice_template(
    payload: PracticeTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    try:
        template = await service.create_template(
            payload, actor_id=str(current_user.user_id)
        )
        return _success(serialize_template(template))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_CREATE_FAILED]",
            message="PracticeTemplate 创建失败。",
            exc=exc,
        )


@router.put("/{template_id}", response_model=None)
async def update_practice_template(
    template_id: str,
    payload: PracticeTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _api_error(
            "[PRACTICE_TEMPLATE_NOT_FOUND]",
            status_code=404,
            message="PracticeTemplate 不存在。",
        )
    try:
        updated = await service.update_template(
            template, payload, actor_id=str(current_user.user_id)
        )
        return _success(serialize_template(updated))
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_UPDATE_FAILED]",
            message="PracticeTemplate 更新失败。",
            exc=exc,
        )


@router.post("/{template_id}/publish", response_model=None)
async def publish_practice_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    admin_error = _require_admin(current_user)
    if admin_error is not None:
        return admin_error
    service = PracticeTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        return _api_error(
            "[PRACTICE_TEMPLATE_NOT_FOUND]",
            status_code=404,
            message="PracticeTemplate 不存在。",
        )
    try:
        published, decision = await service.publish_template(
            template, actor_id=str(current_user.user_id)
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[PRACTICE_TEMPLATE_PUBLISH_FAILED]",
            message="PracticeTemplate 发布失败。",
            exc=exc,
        )
    if published is None:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "[PRACTICE_TEMPLATE_PUBLISH_GATE_FAILED]",
                message="PracticeTemplate 发布门禁未通过。",
            )
            | {
                "details": {
                    "gate_results": [item.model_dump() for item in decision.results]
                }
            },
        )
    data = serialize_template(published).model_dump()
    data["published_ref"] = published_ref(published).model_dump()
    return _success(data)
