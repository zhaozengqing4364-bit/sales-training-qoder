"""Bulk account provisioning transport endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from admin.services.provisioning import ProvisioningError, ProvisioningService
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db

router = APIRouter(prefix="/admin/user-provisioning", tags=["admin-user-provisioning"])


class ProvisioningPreviewRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=2_000_000)
    source_name: str = Field(default="accounts.csv", max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=120)


class TeamOverride(BaseModel):
    name: str | None = None
    primary_leader_email: str | None = None


class ProvisioningConfirmRequest(BaseModel):
    team_overrides: dict[str, TeamOverride] = Field(default_factory=dict)
    retry_team_codes: list[str] | None = None


def _error(exc: ProvisioningError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.code, "message": exc.message},
    )


@router.post("/preview", response_model=None)
async def preview_provisioning(
    payload: ProvisioningPreviewRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await ProvisioningService(db).preview(
            csv_text=payload.csv_text,
            source_name=payload.source_name,
            idempotency_key=payload.idempotency_key,
            actor=current_user,
        )
    except ProvisioningError as exc:
        await db.rollback()
        return _error(exc)
    return {"success": True, "data": result}


@router.get("/{batch_id}", response_model=None)
async def get_provisioning_batch(
    batch_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    del current_user
    try:
        result = await ProvisioningService(db).get_batch(batch_id)
    except ProvisioningError as exc:
        return _error(exc)
    return {"success": True, "data": result}


@router.post("/{batch_id}/confirm", response_model=None)
async def confirm_provisioning(
    batch_id: str,
    payload: ProvisioningConfirmRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    try:
        result = await ProvisioningService(db).confirm(
            batch_id=batch_id,
            actor=current_user,
            team_overrides={
                code.strip().lower(): override.model_dump(exclude_none=True)
                for code, override in payload.team_overrides.items()
            },
            retry_team_codes={code.strip().lower() for code in payload.retry_team_codes}
            if payload.retry_team_codes is not None
            else None,
        )
    except ProvisioningError as exc:
        await db.rollback()
        return _error(exc)
    response = JSONResponse(content={"success": True, "data": result})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/{batch_id}/reset-credentials")
async def reset_provisioning_credentials(
    batch_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ProvisioningService(db).reset_credentials(
            batch_id=batch_id, actor=current_user
        )
    except ProvisioningError as exc:
        await db.rollback()
        return _error(exc)
    response = JSONResponse(content={"success": True, "data": result})
    response.headers["Cache-Control"] = "no-store"
    return response
