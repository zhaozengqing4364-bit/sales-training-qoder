"""User-facing governed business-rule runtime endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import success_response
from common.business_rules.defaults import SALES_COMBINATIONS_RULESET_KEY
from common.business_rules.service import (
    BusinessRuleConfigService,
    BusinessRuleResolution,
)
from common.db.session import get_db

router = APIRouter(prefix="/business-rules", tags=["business-rules"])


def sales_combination_ruleset_payload(
    resolution: BusinessRuleResolution,
) -> dict[str, Any]:
    """Convert a governed rule resolution into the frontend sales-combination contract."""

    value = deepcopy(resolution.value)
    return {
        "rule_set_id": value.get("rule_set_id"),
        "version": value.get("version"),
        "status": "published" if resolution.status != "draft" else "draft",
        "effective_at": None,
        "combinations": value.get("combinations", []),
        "fallback_policy": value.get("fallback_policy", "client_default_v1"),
        "audit_summary": {
            "published_by": None,
            "published_at": None,
            "reason": resolution.fallback_reason,
            "trace_id": None,
        },
        "source": "server"
        if resolution.source.startswith("database")
        else "bundled_default",
        "fallback_reason": resolution.fallback_reason,
    }


@router.get("/sales-combinations/active")
async def get_active_sales_combinations(
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    resolution = await service.resolve_active_config(SALES_COMBINATIONS_RULESET_KEY)
    return success_response(sales_combination_ruleset_payload(resolution))
