"""Fine-grained admin permission helpers.

Current persisted roles are intentionally not expanded here. The existing
``admin`` role remains the compatibility superuser while this helper gives new
high-risk admin operations a named permission boundary for future role rollout.
"""

from __future__ import annotations

from typing import Final

from fastapi import Depends

from common.auth.service import get_current_admin_user
from common.db.models import User

BUSINESS_RULE_PUBLISH_PERMISSION: Final = "business_rule.publish"
RELEASE_VERIFICATION_MANAGE_PERMISSION: Final = "release_verification.manage"
ADMIN_SETTINGS_MANAGE_PERMISSION: Final = "admin_settings.manage"
SCORING_RULESET_MANAGE_PERMISSION: Final = "scoring_ruleset.manage"

ADMIN_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    "admin": frozenset(
        {
            BUSINESS_RULE_PUBLISH_PERMISSION,
            RELEASE_VERIFICATION_MANAGE_PERMISSION,
            ADMIN_SETTINGS_MANAGE_PERMISSION,
            SCORING_RULESET_MANAGE_PERMISSION,
        }
    ),
    # Documented target roles. They cannot be persisted until the User.role
    # database constraint is widened by a future migration.
    "content_admin": frozenset(
        {
            BUSINESS_RULE_PUBLISH_PERMISSION,
            SCORING_RULESET_MANAGE_PERMISSION,
        }
    ),
    "operations": frozenset({BUSINESS_RULE_PUBLISH_PERMISSION}),
    "support": frozenset(),
    "readonly_auditor": frozenset(),
}


def user_has_admin_permission(user: User, permission: str) -> bool:
    role = str(getattr(user, "role", "") or "").strip().lower()
    return permission in ADMIN_ROLE_PERMISSIONS.get(role, frozenset())


def require_admin_permission(permission: str):
    async def checker(current_user: User = Depends(get_current_admin_user)) -> User:
        if not user_has_admin_permission(current_user, permission):
            # get_current_admin_user already preserves the published [ROLE_REQUIRED]
            # contract for non-admin users. This branch is for future narrowed roles.
            from common.auth.service import _raise_auth_http_error

            _raise_auth_http_error(
                status_code=403,
                error_code="[PERMISSION_REQUIRED]",
                message=f"当前账号缺少权限：{permission}。",
            )
        return current_user

    return checker
