"""Read-only admin governance inventory surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from common.api.response import success_response
from common.auth.service import get_current_admin_user
from common.db.models import User

from .security_inventory import (
    ADMIN_PERMISSION_POSITIVE_CONTROL,
    ADMIN_ROUTE_PERMISSION_MATRIX,
    ADMIN_SUPPORT_BACKEND_ONLY_FIELDS,
    ADMIN_SUPPORT_DIAGNOSTIC_ALLOWLIST,
    ADMIN_SUPPORT_LOG_REDACTION_GUIDANCE,
    ADMIN_SUPPORT_LOG_VISIBLE_FIELDS,
    FIX_FIRST_ADMIN_ROUTE_FAMILIES,
    M021_QUALITY_EVENT_ADMIN_SUPPORT_PREREQUISITE,
)

router = APIRouter(
    prefix="/governance",
    tags=["admin-governance"],
    dependencies=[Depends(get_current_admin_user)],
)

SETTINGS_GOVERNANCE_BACKLOG: tuple[dict[str, Any], ...] = (
    {
        "surface": "general",
        "label": "常规设置",
        "status": "persisted",
        "missing_capabilities": (),
        "fallback_policy": "managed by /api/v1/admin/settings/general with bundled safe defaults",
    },
    {
        "surface": "security",
        "label": "安全与访问",
        "status": "persisted",
        "missing_capabilities": (
            "runtime enforcement remains code-owned until each security policy is explicitly wired",
        ),
        "fallback_policy": "managed by /api/v1/admin/settings/security; runtime security baseline stays code-owned",
    },
    {
        "surface": "notifications",
        "label": "通知设置",
        "status": "persisted",
        "missing_capabilities": (
            "delivered notification jobs must explicitly consume the governed config before enabling new sends",
        ),
        "fallback_policy": "managed by /api/v1/admin/settings/notifications with disabled-state metadata",
    },
    {
        "surface": "models",
        "label": "模型配置",
        "status": "persisted",
        "missing_capabilities": (),
        "fallback_policy": "managed by /api/v1/admin/model-configs with admin guard",
    },
)


def _permission_entry_payload(entry: Any) -> dict[str, Any]:
    return {
        "route_family": entry.route_family,
        "auth_surface": entry.auth_surface,
        "routes": list(entry.routes),
        "allowed_roles": list(entry.allowed_roles),
        "non_admin_deny_path": entry.non_admin_deny_path,
        "current_evidence": list(entry.current_evidence),
        "risk": entry.risk,
        "priority": entry.priority,
        "rationale": entry.rationale,
    }


@router.get("/permissions-matrix")
async def get_permissions_matrix(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    _ = current_user
    items = [_permission_entry_payload(entry) for entry in ADMIN_ROUTE_PERMISSION_MATRIX]
    return success_response(
        {
            "items": items,
            "total": len(items),
            "fix_first_route_families": list(FIX_FIRST_ADMIN_ROUTE_FAMILIES),
            "positive_control_route_families": list(ADMIN_PERMISSION_POSITIVE_CONTROL),
            "support_log_redaction": {
                "visible_fields": list(ADMIN_SUPPORT_LOG_VISIBLE_FIELDS),
                "diagnostic_allowlist": list(ADMIN_SUPPORT_DIAGNOSTIC_ALLOWLIST),
                "backend_only_fields": list(ADMIN_SUPPORT_BACKEND_ONLY_FIELDS),
                "guidance": ADMIN_SUPPORT_LOG_REDACTION_GUIDANCE,
                "quality_event_prerequisite": M021_QUALITY_EVENT_ADMIN_SUPPORT_PREREQUISITE,
            },
        }
    )


@router.get("/settings-backlog")
async def get_settings_governance_backlog(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    _ = current_user
    return success_response(
        {
            "items": [dict(item) for item in SETTINGS_GOVERNANCE_BACKLOG],
            "total": len(SETTINGS_GOVERNANCE_BACKLOG),
            "policy": (
                "Admin settings are governed through BusinessRuleConfig-backed "
                "/api/v1/admin/settings/{surface} APIs with defaults, validation, "
                "audit logs, and rollback. Runtime consumers must opt in explicitly."
            ),
        }
    )
