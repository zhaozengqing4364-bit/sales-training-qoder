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
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger, get_trace_id

from ..schemas import (
    AgentPersonaListResponse,
    AgentPersonaResponse,
    CreateAgentPersonaRequest,
    UpdateAgentPersonaRequest,
)
from ..services.agent_persona_service import AgentPersonaService

logger = get_logger(__name__)

admin_router = APIRouter(prefix="/admin/agents", tags=["admin-agent-personas"])


async def commit_or_500(db: AsyncSession, action: str) -> JSONResponse | None:
    """Persist transaction and return normalized 500 response on failure."""
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[DB_COMMIT_FAILED]",
            message="Database commit failed",
            exc=exc,
            action=action,
        )
    return None


def error_response(error_code: str, status_code: int = 400) -> JSONResponse:
    """Create unified error response with trace_id."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_code,
            "message": error_code,
            "trace_id": get_trace_id(),
        },
    )


@admin_router.post("/{agent_id}/personas", response_model=dict)
async def add_persona_to_agent(
    agent_id: str,
    request: CreateAgentPersonaRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a Persona to an Agent - R4.1"""
    service = AgentPersonaService(db)
    result = await service.add_persona(agent_id, request)

    if not result.is_success:
        if result.fallback == "[AGENT_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Agent not found")
        if result.fallback == "[AGENT_ARCHIVED]":
            return error_response("[AGENT_ARCHIVED]", status_code=400)
        if result.fallback == "[PERSONA_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Persona not found")
        if result.fallback == "[PERSONA_INACTIVE]":
            return error_response("[PERSONA_INACTIVE]", status_code=400)
        if result.fallback == "[PERSONA_ALREADY_LINKED]":
            raise HTTPException(status_code=400, detail="Persona already linked to this agent")
        raise HTTPException(status_code=400, detail=result.fallback)

    link = result.value
    commit_error = await commit_or_500(db, "add_persona_to_agent")
    if commit_error is not None:
        return commit_error
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
    current_user: User = Depends(get_current_admin_user),
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
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update Agent-Persona association - R4.3"""
    service = AgentPersonaService(db)
    result = await service.update_link(agent_id, persona_id, request)

    if not result.is_success:
        if result.fallback == "[AGENT_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Agent not found")
        if result.fallback == "[PERSONA_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Persona not found")
        if result.fallback == "[LINK_NOT_FOUND]":
            raise HTTPException(status_code=404, detail="Link not found")
        if result.fallback == "[AGENT_ARCHIVED]":
            return error_response("[AGENT_ARCHIVED]", status_code=400)
        if result.fallback == "[PERSONA_INACTIVE]":
            return error_response("[PERSONA_INACTIVE]", status_code=400)
        raise HTTPException(status_code=400, detail=result.fallback)

    link = result.value
    commit_error = await commit_or_500(db, "update_agent_persona")
    if commit_error is not None:
        return commit_error
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
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Remove Persona from Agent - R4.4"""
    service = AgentPersonaService(db)
    result = await service.remove_persona(agent_id, persona_id)

    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)

    commit_error = await commit_or_500(db, "remove_persona_from_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": {"removed": True}
    }
