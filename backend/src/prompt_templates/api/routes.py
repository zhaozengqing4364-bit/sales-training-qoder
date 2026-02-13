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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import get_db
from common.monitoring.logger import get_logger
from prompt_templates.models import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptRenderRequest,
    PromptRenderResponse,
    ScenarioPrompt,
    ScenarioPromptCreate,
    PromptType,
)
from prompt_templates.service import PromptTemplateService

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["prompt-templates"])
logger = get_logger(__name__)


def get_prompt_service(
    db: AsyncSession = Depends(get_db),
) -> PromptTemplateService:
    """Dependency to get prompt template service."""
    return PromptTemplateService(db_session=db)


def _raise_prompt_http_error(
    *,
    status_code: int,
    error_code: str,
    message: str,
    exc: Exception | None = None,
) -> None:
    if exc is not None:
        logger.error(
            "Prompt API request failed",
            error_code=error_code,
            status_code=status_code,
            error=str(exc),
        )
    raise HTTPException(
        status_code=status_code,
        detail={
            "error": error_code,
            "message": message,
        },
    )


@router.get("", response_model=list[PromptTemplate])
async def list_prompt_templates(
    prompt_type: PromptType | None = Query(None, description="Filter by prompt type"),
    category: str | None = Query(None, description="Filter by category"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Skip N items"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> list[PromptTemplate]:
    """List prompt templates with optional filtering."""
    try:
        return await service.list_templates(
            prompt_type=prompt_type,
            category=category,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=500,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.get("/by-scenario/{scenario_type}", response_model=PromptTemplate | None)
async def get_template_for_scenario(
    scenario_type: str,
    prompt_type: str,
    scenario_id: str | None = None,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate | None:
    """Get the best matching template for a scenario."""
    try:
        return await service.get_template_for_scenario(
            prompt_type=prompt_type,
            scenario_type=scenario_type,
            scenario_id=scenario_id,
        )
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=500,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.post("", response_model=PromptTemplate, status_code=201)
async def create_prompt_template(
    data: PromptTemplateCreate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Create a new prompt template."""
    try:
        return await service.create_template(data)
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


@router.get("/{template_id}", response_model=PromptTemplate)
async def get_prompt_template(
    template_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Get a prompt template by ID."""
    try:
        template = await service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail={"error": "[PROMPT_TEMPLATE_NOT_FOUND]", "message": "模板不存在"},
            )
        return template
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=500,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据异常，请联系管理员。",
            exc=exc,
        )


@router.put("/{template_id}", response_model=PromptTemplate)
async def update_prompt_template(
    template_id: UUID,
    data: PromptTemplateUpdate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Update a prompt template."""
    try:
        template = await service.update_template(template_id, data)
        if not template:
            raise HTTPException(
                status_code=404,
                detail={"error": "[PROMPT_TEMPLATE_NOT_FOUND]", "message": "模板不存在"},
            )
        return template
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


@router.delete("/{template_id}", status_code=204)
async def delete_prompt_template(
    template_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete (deactivate) a prompt template."""
    try:
        success = await service.delete_template(template_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={"error": "[PROMPT_TEMPLATE_NOT_FOUND]", "message": "模板不存在"},
            )
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@router.post("/{template_id}/render", response_model=PromptRenderResponse)
async def render_prompt_template(
    template_id: UUID,
    request: PromptRenderRequest,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptRenderResponse:
    """Render a prompt template with variables."""
    # Ensure template_id in path matches request
    if request.template_id != template_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "[PROMPT_TEMPLATE_ID_MISMATCH]",
                "message": "路径中的模板ID与请求体不一致",
            },
        )
    try:
        return await service.render_prompt(request)
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[PROMPT_RENDER_FAILED]",
            message="提示词渲染失败，请检查变量配置。",
            exc=exc,
        )


@router.post("/{template_id}/set-default", response_model=PromptTemplate)
async def set_default_template(
    template_id: UUID,
    prompt_type: PromptType,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Set a template as the default for its type."""
    try:
        success = await service.set_default_template(template_id, prompt_type)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={"error": "[PROMPT_TEMPLATE_NOT_FOUND]", "message": "模板不存在"},
            )

        template = await service.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail={"error": "[PROMPT_TEMPLATE_NOT_FOUND]", "message": "模板不存在"},
            )
        return template
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[PROMPT_DATA_INVALID]",
            message="提示词数据无效，请检查后重试。",
            exc=exc,
        )


# Scenario Prompt Assignment Routes
scenario_router = APIRouter(prefix="/api/v1/scenario-prompts", tags=["scenario-prompts"])


@scenario_router.get("", response_model=list[ScenarioPrompt])
async def list_scenario_prompts(
    scenario_type: str | None = Query(None, description="Filter by scenario type"),
    prompt_type: str | None = Query(None, description="Filter by prompt type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> list[ScenarioPrompt]:
    """List scenario prompt assignments with optional filtering."""
    try:
        return await service.list_scenario_prompts(
            scenario_type=scenario_type,
            prompt_type=prompt_type,
            is_active=is_active,
        )
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@scenario_router.post("", response_model=ScenarioPrompt, status_code=201)
async def create_scenario_prompt(
    data: ScenarioPromptCreate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Create a scenario prompt assignment."""
    try:
        return await service.assign_template_to_scenario(data)
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[SCENARIO_PROMPT_INVALID]",
            message="场景提示词配置无效，请检查后重试。",
            exc=exc,
        )


@scenario_router.get("/{assignment_id}", response_model=ScenarioPrompt)
async def get_scenario_prompt(
    assignment_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Get a scenario prompt assignment by ID."""
    try:
        assignment = await service.get_scenario_prompt(assignment_id)
        if not assignment:
            raise HTTPException(
                status_code=404,
                detail={"error": "[SCENARIO_PROMPT_NOT_FOUND]", "message": "场景提示词绑定不存在"},
            )
        return assignment
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )


@scenario_router.put("/{assignment_id}", response_model=ScenarioPrompt)
async def update_scenario_prompt(
    assignment_id: UUID,
    is_active: bool | None = Query(None, description="New active status"),
    template_id: UUID | None = Query(None, description="New template ID"),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Update a scenario prompt assignment."""
    try:
        assignment = await service.update_scenario_prompt(
            assignment_id=assignment_id,
            is_active=is_active,
            template_id=template_id,
        )
        if not assignment:
            raise HTTPException(
                status_code=404,
                detail={"error": "[SCENARIO_PROMPT_NOT_FOUND]", "message": "场景提示词绑定不存在"},
            )
        return assignment
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
    except ValueError as exc:
        _raise_prompt_http_error(
            status_code=400,
            error_code="[SCENARIO_PROMPT_INVALID]",
            message="场景提示词配置无效，请检查后重试。",
            exc=exc,
        )


@scenario_router.delete("/{assignment_id}", status_code=204)
async def delete_scenario_prompt(
    assignment_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete a scenario prompt assignment."""
    try:
        success = await service.delete_scenario_prompt(assignment_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={"error": "[SCENARIO_PROMPT_NOT_FOUND]", "message": "场景提示词绑定不存在"},
            )
    except SQLAlchemyError as exc:
        _raise_prompt_http_error(
            status_code=503,
            error_code="[PROMPT_DB_UNAVAILABLE]",
            message="提示词服务暂不可用，请稍后重试。",
            exc=exc,
        )
