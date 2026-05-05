"""Admin API - Presentation AI policy management."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import success_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_logger
from presentation_coach.services.presentation_ai_policy_service import (
    PresentationAIPolicyService,
)

logger = get_logger(__name__)

ScopeType = Literal["global", "scenario", "presentation"]


class PolicyScopePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeType = "global"
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> PolicyScopePayload:
        if self.scope_type == "global":
            self.scope_id = None
            return self
        if not self.scope_id or not self.scope_id.strip():
            raise ValueError("scope_id is required for scenario/presentation scope")
        self.scope_id = self.scope_id.strip()
        return self


class PolicyUpsertPayload(PolicyScopePayload):
    enabled: bool | None = None
    prompt_config: dict[str, Any] | None = None
    rule_config: dict[str, Any] | None = None
    fallback_config: dict[str, Any] | None = None


class PolicyPreviewPayload(PolicyScopePayload):
    transcript: str = Field(..., min_length=1, max_length=5000)
    required_points: list[str] = Field(default_factory=list)
    forbidden_words: list[Any] = Field(default_factory=list)


router = APIRouter(
    prefix="/presentation-ai",
    tags=["presentation-ai"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/policy", response_model=None)
async def get_scope_policy(
    scope_type: ScopeType = Query(default="global"),
    scope_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = PresentationAIPolicyService(db)
    data = await service.get_scope_policy(scope_type=scope_type, scope_id=scope_id)
    return success_response(data)


@router.put("/policy", response_model=None)
async def upsert_scope_policy(
    payload: PolicyUpsertPayload,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    service = PresentationAIPolicyService(db)
    updates = payload.model_dump(
        exclude={"scope_type", "scope_id"},
        exclude_none=True,
    )
    try:
        data = await service.upsert_scope_policy(
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            payload=updates,
            updated_by=str(current_user.user_id),
        )
        await db.commit()
        return success_response(data)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"[{exc}]") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error(f"Failed to upsert presentation AI policy: {exc}")
        return build_server_error(
            "[PRESENTATION_AI_POLICY_UPSERT_FAILED]",
            message="Failed to upsert presentation AI policy",
            exc=exc,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )


@router.post("/policy/preview", response_model=None)
async def preview_scope_policy(
    payload: PolicyPreviewPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = PresentationAIPolicyService(db)

    scenario_id = payload.scope_id if payload.scope_type == "scenario" else None
    presentation_id = payload.scope_id if payload.scope_type == "presentation" else None

    data = await service.preview_policy_decision(
        transcript=payload.transcript,
        required_points=payload.required_points,
        forbidden_words=payload.forbidden_words,
        scenario_id=scenario_id,
        presentation_id=presentation_id,
    )
    return success_response(data)


@router.get("/policy/effective", response_model=None)
async def get_effective_policy(
    session_id: str | None = Query(default=None),
    scenario_id: str | None = Query(default=None),
    presentation_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = PresentationAIPolicyService(db)

    if session_id:
        policy_result = await service.resolve_effective_policy_for_session_result(
            session_id=session_id
        )
        if not policy_result.is_success:
            raise HTTPException(
                status_code=404,
                detail=policy_result.fallback or "[SESSION_NOT_FOUND]",
            )
        return success_response(policy_result.value)

    data = await service.resolve_effective_policy(
        scenario_id=scenario_id,
        presentation_id=presentation_id,
    )
    return success_response(data)
