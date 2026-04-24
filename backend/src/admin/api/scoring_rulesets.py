"""Admin scoring ruleset CRUD, publish/rollback, and dry-run APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db
from common.effectiveness.scoring_rulesets import (
    ScoringRulesetDefinition,
    ScoringRulesetService,
)
from common.monitoring.logger import get_trace_id

router = APIRouter(
    prefix="/admin/scoring-rulesets",
    tags=["admin-scoring-rulesets"],
)

_ERROR_MESSAGES = {
    "[SCORING_RULESET_NOT_FOUND]": "评分规则集不存在。",
    "[SCORING_RULESET_VERSION_EXISTS]": "该训练类型下的评分规则版本已存在。",
    "[SCORING_RULESET_SCENARIO_MISMATCH]": "评分规则集训练类型不一致。",
    "[SCORING_RULESET_ACTIVE_IMMUTABLE]": "已发布且启用的评分规则集不可直接修改。",
    "[SCORING_RULESET_ROLLBACK_TARGET_NOT_PUBLISHED]": "只能回滚到已发布过的评分规则集。",
    "[SCORING_RULESET_DRY_RUN_CANDIDATE_REQUIRED]": "dry-run 必须提供候选规则集。",
    "[SESSION_EVIDENCE_FAILED]": "无法读取会话证据，dry-run 失败。",
}


class ScoringRulesetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_type: str = Field(..., pattern="^(sales|presentation)$")
    version: str = Field(..., min_length=1, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    definition: ScoringRulesetDefinition


class ScoringRulesetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    definition: ScoringRulesetDefinition | None = None


class ScoringRulesetReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class ScoringRulesetDryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=80)
    candidate_ruleset_id: str | None = Field(default=None, max_length=80)
    candidate_definition: ScoringRulesetDefinition | None = None


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "trace_id": get_trace_id()}


def _api_error(
    error_code: str,
    *,
    status_code: int = 400,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(
            error_code,
            message=message or _ERROR_MESSAGES.get(error_code, error_code),
        ),
    )


def _error_code(exc: Exception) -> str:
    message = str(exc)
    if message.startswith("[") and "]" in message:
        return message.split("]", 1)[0] + "]"
    return "[SCORING_RULESET_INVALID]"


@router.get("")
async def list_scoring_rulesets(
    scenario_type: str | None = Query(default=None, pattern="^(sales|presentation)$"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = ScoringRulesetService(db)
    items = await service.list_rulesets(scenario_type=scenario_type)
    return _success(
        {
            "items": [item.to_dict() for item in items],
            "total": len(items),
            "actor_id": str(current_user.user_id),
        }
    )


@router.get("/active")
async def get_active_scoring_ruleset(
    scenario_type: str = Query(..., pattern="^(sales|presentation)$"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    service = ScoringRulesetService(db)
    active = await service.get_active_or_default(scenario_type)
    data = active.to_dict()
    data["actor_id"] = str(current_user.user_id)
    return _success(data)


@router.post("")
async def create_scoring_ruleset(
    payload: ScoringRulesetCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScoringRulesetService(db)
    try:
        created = await service.create_ruleset(
            scenario_type=payload.scenario_type,
            version=payload.version,
            display_name=payload.display_name,
            description=payload.description,
            definition=payload.definition,
            actor=current_user,
        )
        await db.commit()
        return _success(created.to_dict())
    except ValueError as exc:
        await db.rollback()
        return _api_error(_error_code(exc), status_code=400)
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[SCORING_RULESET_CREATE_FAILED]",
            message="Failed to create scoring ruleset",
            exc=exc,
        )


@router.put("/{ruleset_id}")
async def update_scoring_ruleset(
    ruleset_id: str,
    payload: ScoringRulesetUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScoringRulesetService(db)
    try:
        updated = await service.update_ruleset(
            ruleset_id=ruleset_id,
            actor=current_user,
            display_name=payload.display_name,
            description=payload.description,
            definition=payload.definition,
        )
        await db.commit()
        return _success(updated.to_dict())
    except ValueError as exc:
        await db.rollback()
        code = _error_code(exc)
        return _api_error(
            code,
            status_code=404 if code == "[SCORING_RULESET_NOT_FOUND]" else 400,
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[SCORING_RULESET_UPDATE_FAILED]",
            message="Failed to update scoring ruleset",
            exc=exc,
        )


@router.post("/{ruleset_id}/publish")
async def publish_scoring_ruleset(
    ruleset_id: str,
    payload: ScoringRulesetReasonRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScoringRulesetService(db)
    try:
        published = await service.publish_ruleset(
            ruleset_id=ruleset_id,
            actor=current_user,
            reason=payload.reason if payload else None,
        )
        await db.commit()
        return _success(published.to_dict())
    except ValueError as exc:
        await db.rollback()
        code = _error_code(exc)
        return _api_error(
            code,
            status_code=404 if code == "[SCORING_RULESET_NOT_FOUND]" else 400,
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[SCORING_RULESET_PUBLISH_FAILED]",
            message="Failed to publish scoring ruleset",
            exc=exc,
        )


@router.post("/{ruleset_id}/rollback")
async def rollback_scoring_ruleset(
    ruleset_id: str,
    payload: ScoringRulesetReasonRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScoringRulesetService(db)
    try:
        rolled_back = await service.rollback_to_ruleset(
            ruleset_id=ruleset_id,
            actor=current_user,
            reason=payload.reason if payload else None,
        )
        await db.commit()
        return _success(rolled_back.to_dict())
    except ValueError as exc:
        await db.rollback()
        code = _error_code(exc)
        return _api_error(
            code,
            status_code=404 if code == "[SCORING_RULESET_NOT_FOUND]" else 400,
        )
    except SQLAlchemyError as exc:
        await db.rollback()
        return build_server_error(
            "[SCORING_RULESET_ROLLBACK_FAILED]",
            message="Failed to rollback scoring ruleset",
            exc=exc,
        )


@router.post("/dry-run")
async def dry_run_scoring_ruleset(
    payload: ScoringRulesetDryRunRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScoringRulesetService(db)
    try:
        result = await service.dry_run_session(
            session_id=payload.session_id,
            candidate_ruleset_id=payload.candidate_ruleset_id,
            candidate_definition=payload.candidate_definition,
        )
        result["actor_id"] = str(current_user.user_id)
        return _success(result)
    except ValueError as exc:
        code = _error_code(exc)
        return _api_error(
            code,
            status_code=404
            if code in {"[SCORING_RULESET_NOT_FOUND]", "[SESSION_NOT_FOUND]"}
            else 400,
        )
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SCORING_RULESET_DRY_RUN_FAILED]",
            message="Failed to dry-run scoring ruleset",
            exc=exc,
        )
