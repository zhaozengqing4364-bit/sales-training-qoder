"""
Persona API - Admin endpoints for Persona management

Implements CRUD operations and duplication for Personas.

References:
- Requirements: R3 (Persona Management)
- Design: Section 5 (Persona Service)
- API Contract: docs/api-contract/personas.md
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger

from ..schemas import (
    CreatePersonaRequest,
    PersonaCreateResponse,
    PersonaListResponse,
    PersonaResponse,
    UpdatePersonaRequest,
)
from ..services.persona_service import PersonaService

logger = get_logger(__name__)

admin_router = APIRouter(prefix="/admin/personas", tags=["admin-personas"])


async def commit_or_500(db: AsyncSession, action: str) -> None:
    """Persist transaction and convert DB failures to HTTP 500."""
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Database commit failed during {action}: {exc}")
        raise HTTPException(status_code=500, detail="[DB_COMMIT_FAILED]") from exc


@admin_router.post("", response_model=dict)
async def create_persona(
    request: CreatePersonaRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new Persona - R3.1"""
    service = PersonaService(db)
    result = await service.create(request, user_id=current_user.user_id)
    
    if not result.is_success:
        raise HTTPException(status_code=400, detail=result.fallback)
    
    persona = result.value
    await commit_or_500(db, "create_persona")
    return {
        "success": True,
        "data": PersonaCreateResponse(
            id=persona.id,
            name=persona.name,
            status=persona.status,
            created_at=persona.created_at
        ).model_dump()
    }


@admin_router.get("", response_model=dict)
async def list_personas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    difficulty: str | None = Query(None),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get paginated Persona list - R3.2"""
    service = PersonaService(db)
    items, total = await service.list(
        page=page,
        page_size=page_size,
        category=category,
        difficulty=difficulty,
        status=status
    )
    
    return {
        "success": True,
        "data": PersonaListResponse(
            personas=items,
            total=total,
            page=page,
            page_size=page_size
        ).model_dump()
    }


@admin_router.get("/{persona_id}", response_model=dict)
async def get_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get Persona details - R3.3"""
    service = PersonaService(db)
    result = await service.get_by_id(persona_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    persona = result.value
    return {
        "success": True,
        "data": PersonaResponse.model_validate(persona).model_dump()
    }


@admin_router.put("/{persona_id}", response_model=dict)
async def update_persona(
    persona_id: str,
    request: UpdatePersonaRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update Persona - R3.4"""
    service = PersonaService(db)
    result = await service.update(persona_id, request)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    persona = result.value
    await commit_or_500(db, "update_persona")
    return {
        "success": True,
        "data": PersonaResponse.model_validate(persona).model_dump()
    }


@admin_router.delete("/{persona_id}", response_model=dict)
async def delete_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Delete Persona - R3.5"""
    service = PersonaService(db)
    result = await service.delete(persona_id)
    
    if not result.is_success:
        if result.fallback == "[PERSONA_IN_USE]":
            raise HTTPException(
                status_code=400,
                detail="Persona is linked to agents and cannot be deleted"
            )
        raise HTTPException(status_code=404, detail=result.fallback)
    
    await commit_or_500(db, "delete_persona")
    return {
        "success": True,
        "data": {"deleted": True}
    }


@admin_router.post("/{persona_id}/duplicate", response_model=dict)
async def duplicate_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Duplicate Persona - R3.6"""
    service = PersonaService(db)
    result = await service.duplicate(persona_id, user_id=current_user.user_id)
    
    if not result.is_success:
        raise HTTPException(status_code=404, detail=result.fallback)
    
    persona = result.value
    await commit_or_500(db, "duplicate_persona")
    return {
        "success": True,
        "data": PersonaCreateResponse(
            id=persona.id,
            name=persona.name,
            status=persona.status,
            created_at=persona.created_at
        ).model_dump()
    }
