"""
Prompt Templates API Routes

Requirements: B8 - Implement prompt template management API

Endpoints:
- GET /api/v1/prompt-templates - List templates
- POST /api/v1/prompt-templates - Create template
- GET /api/v1/prompt-templates/{id} - Get template
- PUT /api/v1/prompt-templates/{id} - Update template
- DELETE /api/v1/prompt-templates/{id} - Delete template
- POST /api/v1/prompt-templates/{id}/render - Render template
- GET /api/v1/scenario-prompts - List scenario assignments
- POST /api/v1/scenario-prompts - Create scenario assignment
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger
from prompt_templates.models import (
    ALLOWED_PROMPT_TYPE_VALUES,
    PromptRenderRequest,
    PromptRenderResponse,
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateGovernanceRollbackResponse,
    PromptTemplateQuarantineResult,
    PromptTemplateUpdate,
    PromptType,
    ScenarioPrompt,
    ScenarioPromptCreate,
)
from prompt_templates.service import (
    SALES_PROMPT_SCOPE_ALLOWED_TYPES,
    PromptTemplateService,
)



def _is_admin(user: User) -> bool:
    return str(getattr(user, "role", "")).lower() == "admin"


def _prompt_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    exc: Exception | None = None,
) -> JSONResponse:
    if status_code >= 500:
        return build_server_error(
            error_code,
            status_code=status_code,
            message=message,
            exc=exc,
            source="prompt_templates_api",
        )

    log_method = logger.warning if status_code >= 400 else logger.info
    if exc is not None:
        log_method(
            "Prompt API request failed",
            error_code=error_code,
            status_code=status_code,
            error=str(exc),
        )

    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message),
    )


def _require_prompt_admin_or_error(current_user: User) -> JSONResponse | None:
    if _is_admin(current_user):
        return None
    return _prompt_error_response(
        status_code=403,
        error_code="[PROMPT_TEMPLATE_EDIT_ADMIN_ONLY]",
        message="仅管理员可访问提示词治理接口。",
    )


router = APIRouter(
    prefix="/api/v1/prompt-templates",
    tags=["prompt-templates"],
)
logger = get_logger(__name__)

HTTP_500_INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
HTTP_503_SERVICE_UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE

# M016/S02/T01 error-contract inventory:
# - 4xx branches in this route family already converge on FastAPI detail={error,message}.
# - 5xx / infra failures go through build_server_error(...) and therefore return the shared
#   Result-style envelope {success:false,error,message,trace_id} at the top level.
# - This makes prompt templates the smallest backend seam to reuse in T02, while also showing
#   the remaining envelope drift between detail-wrapped 4xx responses and top-level 5xx failures.


def get_prompt_service(
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateService:
    """Dependency to get prompt template service."""
    return PromptTemplateService(db_session=db)


def _scope_violation_response(exc: ValueError) -> JSONResponse:
    return _prompt_error_response(
        status_code=400,
        error_code="[PROMPT_SCOPE_VIOLATION]",
        message=str(exc),
        exc=exc,
    )


def _parse_template_id_or_error(
    template_id: str,
) -> tuple[UUID | None, JSONResponse | None]:
    normalized = str(template_id or "").strip()
    if not normalized or normalized.lower() in {"undefined", "null"}:
        return None, _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_TEMPLATE_ID_INVALID]",
            message="模板ID无效，请检查请求参数。",
        )
    try:
        return UUID(normalized), None
    except ValueError as exc:
        return None, _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_TEMPLATE_ID_INVALID]",
            message="模板ID无效，请检查请求参数。",
            exc=exc,
        )


@router.get("", response_model=list[PromptTemplate])
async def list_prompt_templates(
    prompt_type: PromptType | None = Query(None, description="Filter by prompt type"),
    category: str | None = Query(None, description="Filter by category"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Skip N items"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> list[PromptTemplate]:
    """List prompt templates with optional filtering."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        return await service.list_templates(
            prompt_type=prompt_type,
            category=category,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        if str(exc).startswith("[PROMPT_SCOPE_VIOLATION]"):
            return _scope_violation_response(exc)
        return _prompt_error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.get("/by-scenario/{scenario_type}", response_model=PromptTemplate | None)
async def get_template_for_scenario(
    scenario_type: str,
    prompt_type: str,
    scenario_id: str | None = None,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate | None:
    """Get the best matching template for a scenario."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        return await service.get_template_for_scenario(
            prompt_type=prompt_type,
            scenario_type=scenario_type,
            scenario_id=scenario_id,
        )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.post("", response_model=PromptTemplate, status_code=201)
async def create_prompt_template(
    data: PromptTemplateCreate,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Create a new prompt template."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        return await service.create_template(payload, actor=current_user)
    except ValidationError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_TEMPLATE_VALIDATION_FAILED]",
            message="提示词模板校验失败：variables 必须是字符串数组，prompt_type 必须属于允许类型。",
            exc=exc,
        )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


@router.get("/{template_id}", response_model=PromptTemplate)
async def get_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Get a prompt template by ID."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    template_uuid, parse_error = _parse_template_id_or_error(template_id)
    if parse_error is not None:
        return parse_error
    assert template_uuid is not None

    try:
        template = await service.get_template(template_uuid)
        if not template:
            return _prompt_error_response(
                status_code=404,
                error_code="[PROMPT_TEMPLATE_NOT_FOUND]",
                message="模板不存在",
            )
        return template
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.put("/{template_id}", response_model=PromptTemplate)
async def update_prompt_template(
    template_id: str,
    data: PromptTemplateUpdate,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Update a prompt template."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    template_uuid, parse_error = _parse_template_id_or_error(template_id)
    if parse_error is not None:
        return parse_error
    assert template_uuid is not None

    try:
        template = await service.update_template(template_uuid, payload, actor=current_user)
        if not template:
            return _prompt_error_response(
                status_code=404,
                error_code="[PROMPT_TEMPLATE_NOT_FOUND]",
                message="模板不存在",
            )
        return template
    except ValidationError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_TEMPLATE_VALIDATION_FAILED]",
            message="提示词模板校验失败：variables 必须是字符串数组，prompt_type 必须属于允许类型。",
            exc=exc,
        )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


@router.delete("/{template_id}", status_code=204)
async def delete_prompt_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete (deactivate) a prompt template."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    template_uuid, parse_error = _parse_template_id_or_error(template_id)
    if parse_error is not None:
        return parse_error
    assert template_uuid is not None

    try:
        success = await service.delete_template(template_uuid, actor=current_user)
        if not success:
            return _prompt_error_response(
                status_code=404,
                error_code="[PROMPT_TEMPLATE_NOT_FOUND]",
                message="模板不存在",
            )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@router.post("/{template_id}/render", response_model=PromptRenderResponse)
async def render_prompt_template(
    template_id: str,
    request: PromptRenderRequest,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptRenderResponse:
    """Render a prompt template with variables."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    template_uuid, parse_error = _parse_template_id_or_error(template_id)
    if parse_error is not None:
        return parse_error
    assert template_uuid is not None

    # Ensure template_id in path matches request
    if request.template_id != template_uuid:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_TEMPLATE_ID_MISMATCH]",
            message="路径中的模板ID与请求体不一致",
        )
    try:
        return await service.render_prompt(request)
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_RENDER_FAILED]",
            message="提示词渲染失败，请检查变量配置。",
            exc=exc,
        )


@router.post("/{template_id}/set-default", response_model=PromptTemplate)
async def set_default_template(
    template_id: str,
    prompt_type: PromptType,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Set a template as the default for its type."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    template_uuid, parse_error = _parse_template_id_or_error(template_id)
    if parse_error is not None:
        return parse_error
    assert template_uuid is not None

    try:
        success = await service.set_default_template(
            template_uuid,
            prompt_type,
            actor=current_user,
        )
        if not success:
            return _prompt_error_response(
                status_code=404,
                error_code="[PROMPT_TEMPLATE_NOT_FOUND]",
                message="模板不存在",
            )

        template = await service.get_template(template_uuid)
        if not template:
            return _prompt_error_response(
                status_code=404,
                error_code="[PROMPT_TEMPLATE_NOT_FOUND]",
                message="模板不存在",
            )
        return template
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        return _prompt_error_response(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


# Scenario Prompt Assignment Routes
scenario_router = APIRouter(
    prefix="/api/v1/scenario-prompts",
    tags=["scenario-prompts"],
)


@scenario_router.get("", response_model=list[ScenarioPrompt])
async def list_scenario_prompts(
    scenario_type: str | None = Query(None, description="Filter by scenario type"),
    prompt_type: str | None = Query(None, description="Filter by prompt type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> list[ScenarioPrompt]:
    """List scenario prompt assignments with optional filtering."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        return await service.list_scenario_prompts(
            scenario_type=scenario_type,
            prompt_type=prompt_type,
            is_active=is_active,
        )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@scenario_router.post("", response_model=ScenarioPrompt, status_code=201)
async def create_scenario_prompt(
    data: ScenarioPromptCreate,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Create a scenario prompt assignment."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        return await service.assign_template_to_scenario(data, actor=current_user)
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        if str(exc).startswith("[PROMPT_SCOPE_VIOLATION]"):
            return _scope_violation_response(exc)
        return _prompt_error_response(
            status_code=400,
            error_code="[SCENARIO_PROMPT_INVALID]",
            message="场景提示词配置无效，请检查后重试。",
            exc=exc,
        )


@scenario_router.get("/{assignment_id}", response_model=ScenarioPrompt)
async def get_scenario_prompt(
    assignment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Get a scenario prompt assignment by ID."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        assignment = await service.get_scenario_prompt(assignment_id)
        if not assignment:
            return _prompt_error_response(
                status_code=404,
                error_code="[SCENARIO_PROMPT_NOT_FOUND]",
                message="场景提示词绑定不存在",
            )
        return assignment
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@scenario_router.put("/{assignment_id}", response_model=ScenarioPrompt)
async def update_scenario_prompt(
    assignment_id: UUID,
    is_active: bool | None = Query(None, description="New active status"),
    template_id: UUID | None = Query(None, description="New template ID"),
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Update a scenario prompt assignment."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        assignment = await service.update_scenario_prompt(
            assignment_id=assignment_id,
            is_active=is_active,
            template_id=template_id,
            actor=current_user,
        )
        if not assignment:
            return _prompt_error_response(
                status_code=404,
                error_code="[SCENARIO_PROMPT_NOT_FOUND]",
                message="场景提示词绑定不存在",
            )
        return assignment
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        if str(exc).startswith("[PROMPT_SCOPE_VIOLATION]"):
            return _scope_violation_response(exc)
        return _prompt_error_response(
            status_code=400,
            error_code="[SCENARIO_PROMPT_INVALID]",
            message="场景提示词配置无效，请检查后重试。",
            exc=exc,
        )


@scenario_router.delete("/{assignment_id}", status_code=204)
async def delete_scenario_prompt(
    assignment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete a scenario prompt assignment."""
    admin_error = _require_prompt_admin_or_error(current_user)
    if admin_error is not None:
        return admin_error

    try:
        success = await service.delete_scenario_prompt(
            assignment_id,
            actor=current_user,
        )
        if not success:
            return _prompt_error_response(
                status_code=404,
                error_code="[SCENARIO_PROMPT_NOT_FOUND]",
                message="场景提示词绑定不存在",
            )
    except SQLAlchemyError as exc:
        return _prompt_error_response(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
