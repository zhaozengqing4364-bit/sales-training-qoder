"""User-facing governed business-rule runtime endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import success_response
from common.auth.service import get_current_user
from common.business_rules.defaults import SALES_COMBINATION_RULES_KEY
from common.business_rules.service import (
    BusinessRuleConfigService,
    BusinessRuleResolution,
)
from common.db.models import User
from common.db.session import get_db

router = APIRouter(prefix="/business-rules", tags=["business-rules"])


def sales_combination_ruleset_payload(
    resolution: BusinessRuleResolution,
) -> dict[str, Any]:
    """Expose a frontend-stable sales-combination ruleset from governed config."""

    value = deepcopy(resolution.value)
    status = "published" if value.get("enabled") is not False else "disabled"
    if resolution.status in {"published", "disabled", "draft", "archived"}:
        status = str(resolution.status)

    payload = {
        "rule_set_id": value["rule_set_id"],
        "version": value["version"],
        "status": status,
        "effective_at": None,
        "combinations": value.get("combinations", []),
        "fallback_policy": value.get("fallback_policy", "client_default_v1"),
        "audit_summary": None,
        "source": resolution.source,
        "fallback_reason": resolution.fallback_reason,
        "config_id": resolution.config_id,
        "config_version": resolution.version,
    }
    return payload


@router.get("/sales-combinations/active")
async def get_active_sales_combination_ruleset(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the active sales training combination ruleset for learners/admins."""

    _ = current_user
    service = BusinessRuleConfigService(db)
    resolution = await service.resolve_active_config(SALES_COMBINATION_RULES_KEY)
    return success_response(sales_combination_ruleset_payload(resolution))
