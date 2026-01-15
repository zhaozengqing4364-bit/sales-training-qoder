"""
Agent-Persona Association API

Manages the relationship between Agents and Personas.

References:
- Requirements: R4 (Agent-Persona Association)
- Design: Section 15 (AgentPersona)
- API Contract: docs/api-contract/personas.md
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger

from ..schemas import (
    AgentPersonaListResponse,
    AgentPersonaResponse,
    CreateAgentPersonaRequest,
    UpdateAgentPersonaRequest,
)
from ..services.agent_persona_service import AgentPersonaService

logger = get_logger(__name__)

admin_router = APIRouter(prefix="/admin/agents", tags=["admin-agent-personas"])


@admin_router.post("/{agent_id}/personas", response_model=dict)
async def add_persona_to_agent(
    agent_id: str,
    request: CreateAgentPersonaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a Persona to an Agent - R4.1"""
    service = AgentPersonaService(db)
    result = await service.add_persona(agent_id, request)
    
    if not result.is_success:
        if result.fallback == "[AGENT_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Agent not found")
        if result.fallback == "[PERSONA_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Persona not found")
        if result.fallback == "[PERSONA_ALREADY_LINKED]":
            raise HTTPException(status_code=400, detail="Persona already linked to this agent")
        raise HTTPException(status_code=400, detail=result.fallback)
    
    link = result.value
    return {
        "success": True,
        "data": AgentPersonaResponse(
            id=link.id,
            agent_id=link.agent_id,
            persona_id=link.persona_id,
            display_order=link.display_order,
            is_default=link.is_default,
            override_config=link.override_config,
            created_at=link.created_at
        ).model_dump()
    }


@admin_router.get("/{agent_id}/personas", response_model=dict)
async def list_agent_personas(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get all Personas linked to an Agent - R4.2"""
    service = AgentPersonaService(db)
    result = await service.list_personas(agent_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    return {
        "success": True,
        "data": AgentPersonaListResponse(
            personas=[item.model_dump() for item in result.value]
        ).model_dump()
    }


@admin_router.put("/{agent_id}/personas/{persona_id}", response_model=dict)
async def update_agent_persona(
    agent_id: str,
    persona_id: str,
    request: UpdateAgentPersonaRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update Agent-Persona association - R4.3"""
    service = AgentPersonaService(db)
    result = await service.update_link(agent_id, persona_id, request)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    link = result.value
    return {
        "success": True,
        "data": AgentPersonaResponse(
            id=link.id,
            agent_id=link.agent_id,
            persona_id=link.persona_id,
            display_order=link.display_order,
            is_default=link.is_default,
            override_config=link.override_config,
            created_at=link.created_at
        ).model_dump()
    }


@admin_router.delete("/{agent_id}/personas/{persona_id}", response_model=dict)
async def remove_persona_from_agent(
    agent_id: str,
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Remove Persona from Agent - R4.4"""
    service = AgentPersonaService(db)
    result = await service.remove_persona(agent_id, persona_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    return {
        "success": True,
        "data": {"removed": True}
    }
