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
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.db.session import get_db_session
from src.common.error_handling.result import Result
from src.prompt_templates.models import (
    PromptTemplate,
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptRenderRequest,
    PromptRenderResponse,
    ScenarioPrompt,
    ScenarioPromptCreate,
    PromptType,
)
from src.prompt_templates.service import PromptTemplateService

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["prompt-templates"])


def get_prompt_service(
    db: AsyncSession = Depends(get_db_session),
) -> PromptTemplateService:
    """Dependency to get prompt template service."""
    return PromptTemplateService(db_session=db)


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
    return await service.list_templates(
        prompt_type=prompt_type,
        category=category,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PromptTemplate, status_code=201)
async def create_prompt_template(
    data: PromptTemplateCreate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Create a new prompt template."""
    return await service.create_template(data)


@router.get("/{template_id}", response_model=PromptTemplate)
async def get_prompt_template(
    template_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Get a prompt template by ID."""
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}", response_model=PromptTemplate)
async def update_prompt_template(
    template_id: UUID,
    data: PromptTemplateUpdate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Update a prompt template."""
    template = await service.update_template(template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_prompt_template(
    template_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete (deactivate) a prompt template."""
    success = await service.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")


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
            detail="Template ID in path does not match request body",
        )
    return await service.render_prompt(request)


@router.post("/{template_id}/set-default", response_model=PromptTemplate)
async def set_default_template(
    template_id: UUID,
    prompt_type: PromptType,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate:
    """Set a template as the default for its type."""
    success = await service.set_default_template(template_id, prompt_type)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    # Return the updated template
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/by-scenario/{scenario_type}", response_model=PromptTemplate | None)
async def get_template_for_scenario(
    scenario_type: str,
    prompt_type: str,
    scenario_id: str | None = None,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> PromptTemplate | None:
    """Get the best matching template for a scenario."""
    return await service.get_template_for_scenario(
        prompt_type=prompt_type,
        scenario_type=scenario_type,
        scenario_id=scenario_id,
    )


# Scenario Prompt Assignment Routes
scenario_router = APIRouter(prefix="/api/v1/scenario-prompts", tags=["scenario-prompts"])


@scenario_router.get("", response_model=list[ScenarioPrompt])
async def list_scenario_prompts(
    scenario_type: str | None = Query(None),
    prompt_type: str | None = Query(None),
    service: PromptTemplateService = Depends(get_prompt_service),
) -> list[ScenarioPrompt]:
    """List scenario prompt assignments."""
    # TODO: Implement list_scenario_prompts in service
    return []


@scenario_router.post("", response_model=ScenarioPrompt, status_code=201)
async def create_scenario_prompt(
    data: ScenarioPromptCreate,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> ScenarioPrompt:
    """Create a scenario prompt assignment."""
    return await service.assign_template_to_scenario(data)


@scenario_router.delete("/{assignment_id}", status_code=204)
async def delete_scenario_prompt(
    assignment_id: UUID,
    service: PromptTemplateService = Depends(get_prompt_service),
) -> None:
    """Delete a scenario prompt assignment."""
    # TODO: Implement delete in service
    pass
