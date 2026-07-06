"""
Persona API - Admin endpoints for Persona management

Implements CRUD operations and duplication for Personas.

References:
- Requirements: R3 (Persona Management)
- Design: Section 5 (Persona Service)
- API Contract: docs/api-contract/personas.md
"""

from __future__ import annotations

import json
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.server_error import build_server_error
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
from ..services.industry_pack_contract import build_persona_industry_pack_contract
from ..services.persona_service import PersonaService

logger = get_logger(__name__)

admin_router = APIRouter(prefix="/admin/personas", tags=["admin-personas"])


def _raise_persona_service_error(
    result_fallback: str | None, *, not_found_status: int = 404
) -> None:
    fallback = str(result_fallback or "")
    if fallback.startswith("{"):
        try:
            payload = json.loads(fallback)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("error") == (
            "[PERSONA_POLICY_VALIDATION_FAILED]"
        ):
            raise HTTPException(status_code=400, detail=payload)
    if fallback == "[PERSONA_NOT_FOUND]":
        raise HTTPException(status_code=not_found_status, detail=fallback)
    raise HTTPException(status_code=400, detail=fallback)


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


@admin_router.post("", response_model=dict)
async def create_persona(
    request: CreatePersonaRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new Persona - R3.1"""
    service = PersonaService(db)
    result = await service.create(request, user_id=cast(str, current_user.user_id))

    if not result.is_success:
        _raise_persona_service_error(result.fallback)

    persona = cast(Any, result.value)
    commit_error = await commit_or_500(db, "create_persona")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": PersonaCreateResponse(
            id=persona.id,
            name=persona.name,
            status=persona.status,
            created_at=persona.created_at,
        ).model_dump(),
    }


@admin_router.get("", response_model=dict)
async def list_personas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None),
    difficulty: str | None = Query(None),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get paginated Persona list - R3.2"""
    service = PersonaService(db)
    items, total = await service.list(
        page=page,
        page_size=page_size,
        category=category,
        difficulty=difficulty,
        status=status,
    )

    return {
        "success": True,
        "data": PersonaListResponse(
            personas=items, total=total, page=page, page_size=page_size
        ).model_dump(),
    }


@admin_router.get("/industry-pack-contract", response_model=dict)
async def get_persona_industry_pack_contract(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Expose persona/customer-pressure/knowledge ownership for industry-pack composition."""
    del current_user
    return {
        "success": True,
        "data": build_persona_industry_pack_contract(),
    }


@admin_router.get("/policy-health", response_model=dict)
async def get_persona_policy_health(
    sample_limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Audit persona_policy consistency for governance dashboards."""
    del current_user
    service = PersonaService(db)
    report = await service.audit_policy_health(sample_limit=sample_limit)
    return {
        "success": True,
        "data": report,
    }


@admin_router.get("/{persona_id}", response_model=dict)
async def get_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get Persona details - R3.3"""
    service = PersonaService(db)
    result = await service.get_by_id(persona_id)

    if not result.is_success:
        _raise_persona_service_error(result.fallback, not_found_status=404)

    persona = result.value
    return {
        "success": True,
        "data": PersonaResponse.model_validate(persona).model_dump(),
    }


@admin_router.put("/{persona_id}", response_model=dict)
async def update_persona(
    persona_id: str,
    request: UpdatePersonaRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update Persona - R3.4"""
    service = PersonaService(db)
    result = await service.update(persona_id, request)

    if not result.is_success:
        _raise_persona_service_error(result.fallback, not_found_status=404)

    persona = result.value
    commit_error = await commit_or_500(db, "update_persona")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": PersonaResponse.model_validate(persona).model_dump(),
    }


@admin_router.delete("/{persona_id}", response_model=dict)
async def delete_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete Persona - R3.5"""
    service = PersonaService(db)
    result = await service.delete(persona_id)

    if not result.is_success:
        if result.fallback == "[PERSONA_IN_USE]":
            raise HTTPException(
                status_code=400,
                detail="Persona is linked to agents and cannot be deleted",
            )
        raise HTTPException(status_code=404, detail=result.fallback)

    commit_error = await commit_or_500(db, "delete_persona")
    if commit_error is not None:
        return commit_error
    return {"success": True, "data": {"deleted": True}}


@admin_router.post("/{persona_id}/duplicate", response_model=dict)
async def duplicate_persona(
    persona_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Duplicate Persona - R3.6"""
    service = PersonaService(db)
    result = await service.duplicate(
        persona_id, user_id=cast(str, current_user.user_id)
    )

    if not result.is_success:
        _raise_persona_service_error(result.fallback, not_found_status=404)

    persona = cast(Any, result.value)
    commit_error = await commit_or_500(db, "duplicate_persona")
    if commit_error is not None:
        return commit_error
    return {
        "success": True,
        "data": PersonaCreateResponse(
            id=persona.id,
            name=persona.name,
            status=persona.status,
            created_at=persona.created_at,
        ).model_dump(),
    }
