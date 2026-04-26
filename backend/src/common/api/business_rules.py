"""User-facing governed business-rule endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.business_rules.defaults import SALES_COMBINATION_RULES_KEY
from common.business_rules.service import (
    BusinessRuleConfigService,
    BusinessRuleResolution,
)
from common.business_rules.validators import BusinessRuleValidationError
from common.db.models import User
from common.db.session import get_db

router = APIRouter(prefix="/business-rules", tags=["business-rules"])


def sales_combination_ruleset_payload(
    resolution: BusinessRuleResolution,
) -> dict[str, Any]:
    """Map governed config resolution to the frontend sales-combination contract."""

    value = deepcopy(resolution.value)
    return {
        "rule_set_id": value.get("rule_set_id"),
        "version": value.get("version"),
        "status": resolution.status or "published",
        "effective_at": None,
        "fallback_policy": value.get("fallback_policy", "client_default_v1"),
        "combinations": value.get("combinations", []),
        "source": resolution.source,
        "fallback_reason": resolution.fallback_reason,
        "audit_summary": None,
    }


def _business_rule_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, KeyError):
        code = "[BUSINESS_RULE_KEY_UNSUPPORTED]"
    elif isinstance(exc, BusinessRuleValidationError):
        code = "[BUSINESS_RULE_SCHEMA_INVALID]"
    else:
        code = "[BUSINESS_RULE_OPERATION_FAILED]"
    return JSONResponse(
        status_code=400,
        content=error_response(code, message=str(exc)),
    )


@router.get("/sales-combinations/active")
async def get_active_sales_combinations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the active sales training combinations from governed configuration."""

    _ = current_user
    service = BusinessRuleConfigService(db)
    try:
        resolution = await service.resolve_active_config(SALES_COMBINATION_RULES_KEY)
        return success_response(sales_combination_ruleset_payload(resolution))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        return _business_rule_error(exc)
