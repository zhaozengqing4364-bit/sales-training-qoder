"""
Agent API - Admin and User endpoints for Agent management

Implements CRUD operations for Agents with lifecycle management.

References:
- Requirements: R1, R2 (Agent Management)
- Design: Section 4 (Agent Service)
- API Contract: docs/api-contract/agents.md
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user, get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger

from ..schemas import (
    AgentCreateResponse,
    AgentListItem,
    AgentListResponse,
    AgentPublishResponse,
    AgentResponse,
    AgentUserResponse,
    CreateAgentRequest,
    PersonaUserListItem,
    UpdateAgentRequest,
)
from ..services.agent_service import AgentService
from ..services.industry_pack_contract import build_agent_industry_pack_contract

logger = get_logger(__name__)

# Admin router for /api/v1/admin/agents
admin_router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])

# User router for /api/v1/agents
user_router = APIRouter(prefix="/agents", tags=["agents"])


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


# =============================================================================
# Admin API Endpoints - R1
# =============================================================================


@admin_router.post("", response_model=dict)
async def create_agent(
    request: CreateAgentRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Create a new Agent with draft status
    
    Requirements: R1.1
    """
    service = AgentService(db)
    result = await service.create(request, user_id=current_user.user_id)
    
    if not result.is_success:
        raise HTTPException(status_code=400, detail=result.fallback)
    
    agent = result.value
    commit_error = await commit_or_500(db, "create_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": AgentCreateResponse(
            id=agent.id,
            name=agent.name,
            status=agent.status,
            created_at=agent.created_at
        ).model_dump()
    }


@admin_router.get("", response_model=dict)
async def list_agents_admin(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get paginated Agent list (admin view)
    
    Requirements: R1.2
    """
    service = AgentService(db)
    items, total = await service.list(
        page=page,
        page_size=page_size,
        category=category,
        status=status,
        admin=True
    )
    
    return {
        "success": True,
        "data": AgentListResponse(
            agents=items,
            total=total,
            page=page,
            page_size=page_size
        ).model_dump()
    }


@admin_router.get("/industry-pack-contract", response_model=dict)
async def get_industry_pack_contract(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Expose the composed industry-pack authority on top of existing admin entrypoints."""
    del current_user
    return {
        "success": True,
        "data": build_agent_industry_pack_contract(),
    }


@admin_router.get("/{agent_id}", response_model=dict)
async def get_agent_admin(
    agent_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get Agent details (admin view with system_prompt)
    
    Requirements: R1.3
    """
    service = AgentService(db)
    result = await service.get_by_id(agent_id, admin=True)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    agent = result.value
    return {
        "success": True,
        "data": AgentResponse.model_validate(agent).model_dump()
    }


@admin_router.put("/{agent_id}", response_model=dict)
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Update Agent (partial update)
    
    Requirements: R1.4
    """
    service = AgentService(db)
    result = await service.update(agent_id, request)
    
    if not result.is_success:
        if result.fallback == "[AGENT_CATEGORY_RESTRICTED]":
            raise HTTPException(status_code=400, detail=result.fallback)
        if str(result.fallback).startswith("[FIELD_DEPRECATED_PERSONA_CENTERED]"):
            raise HTTPException(status_code=400, detail=result.fallback)
        raise HTTPException(status_code=404, detail=result.fallback)
    
    agent = result.value
    commit_error = await commit_or_500(db, "update_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": {
            "id": agent.id,
            "name": agent.name,
            "updated_at": agent.updated_at.isoformat()
        }
    }


@admin_router.delete("/{agent_id}", response_model=dict)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Delete Agent (fails if has associated sessions)
    
    Requirements: R1.7
    """
    service = AgentService(db)
    result = await service.delete(agent_id)
    
    if not result.is_success:
        if result.fallback == "[AGENT_CANNOT_DELETE]":
            raise HTTPException(
                status_code=400, 
                detail="Agent has associated sessions and cannot be deleted"
            )
        raise HTTPException(status_code=404, detail=result.fallback)
    
    commit_error = await commit_or_500(db, "delete_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": {"deleted": True}
    }


@admin_router.post("/{agent_id}/publish", response_model=dict)
async def publish_agent(
    agent_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Publish Agent (draft -> published)
    
    Requirements: R1.5
    """
    service = AgentService(db)
    result = await service.publish(agent_id)
    
    if not result.is_success:
        if result.fallback == "[AGENT_ALREADY_PUBLISHED]":
            raise HTTPException(status_code=400, detail="Agent is already published")
        raise HTTPException(status_code=404, detail=result.fallback)
    
    agent = result.value
    commit_error = await commit_or_500(db, "publish_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": AgentPublishResponse(
            id=agent.id,
            status=agent.status,
            published_at=agent.published_at
        ).model_dump()
    }


@admin_router.post("/{agent_id}/archive", response_model=dict)
async def archive_agent(
    agent_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Archive Agent
    
    Requirements: R1.6
    """
    service = AgentService(db)
    result = await service.archive(agent_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    agent = result.value
    commit_error = await commit_or_500(db, "archive_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": {
            "id": agent.id,
            "status": agent.status
        }
    }


@admin_router.post("/{agent_id}/unpublish", response_model=dict)
async def unpublish_agent(
    agent_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Unpublish Agent (revert to draft status)
    """
    service = AgentService(db)
    result = await service.unpublish(agent_id)
    
    if not result.is_success:
        if result.fallback == "[AGENT_ALREADY_DRAFT]":
            raise HTTPException(status_code=400, detail="Agent is already in draft status")
        raise HTTPException(status_code=404, detail=result.fallback)
    
    agent = result.value
    commit_error = await commit_or_500(db, "unpublish_agent")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": {
            "id": agent.id,
            "status": agent.status
        }
    }


# =============================================================================
# User API Endpoints - R2
# =============================================================================


@user_router.get("", response_model=dict)
async def list_agents_user(
    category: str | None = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get published Agent list (user view)
    
    Requirements: R2.1
    """
    service = AgentService(db)
    items, total = await service.list(
        page=1,
        page_size=100,  # Return all published agents
        category=category,
        admin=False  # Only published
    )
    
    return {
        "success": True,
        "data": {
            "agents": [item.model_dump() for item in items],
            "total": total
        }
    }


@user_router.get("/{agent_id}", response_model=dict)
async def get_agent_user(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get Agent details (user view without system_prompt)
    
    Requirements: R2.2
    """
    service = AgentService(db)
    result = await service.get_by_id(agent_id, admin=False)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    # Result is already AgentUserResponse for non-admin
    agent_response = result.value
    return {
        "success": True,
        "data": agent_response.model_dump() if hasattr(agent_response, 'model_dump') else agent_response
    }


@user_router.get("/{agent_id}/personas", response_model=dict)
async def get_agent_personas(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get Personas associated with an Agent (user view)
    
    Requirements: R2.3
    """
    service = AgentService(db)
    result = await service.get_personas(agent_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    personas = result.value
    return {
        "success": True,
        "data": {
            "personas": [p.model_dump() for p in personas]
        }
    }


# Combined router for registration
router = APIRouter()
router.include_router(admin_router)
router.include_router(user_router)
