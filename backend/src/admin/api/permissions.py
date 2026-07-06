"""Fine-grained admin permission helpers backed by persisted role mappings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.roles import (
    ROLE_ADMIN,
    ROLE_CONTENT_ADMIN,
    ROLE_OPERATIONS,
    ROLE_READONLY_AUDITOR,
    ROLE_SUPPORT,
    admin_permission_role_for,
)
from common.auth.service import get_current_user
from common.db.models import AdminRolePermission, User
from common.db.session import get_db

BUSINESS_RULE_PUBLISH_PERMISSION: Final = "business_rule.publish"
RELEASE_VERIFICATION_MANAGE_PERMISSION: Final = "release_verification.manage"
ADMIN_SETTINGS_MANAGE_PERMISSION: Final = "admin_settings.manage"
SCORING_RULESET_MANAGE_PERMISSION: Final = "scoring_ruleset.manage"
CONFIG_BUNDLE_READ_PERMISSION: Final = "config_bundle.read"
CONFIG_BUNDLE_DRAFT_PERMISSION: Final = "config_bundle.draft"
CONFIG_BUNDLE_VALIDATE_PERMISSION: Final = "config_bundle.validate"
CONFIG_BUNDLE_PREVIEW_PERMISSION: Final = "config_bundle.preview"
CONFIG_BUNDLE_PUBLISH_PERMISSION: Final = "config_bundle.publish"
CONFIG_BUNDLE_ROLLBACK_PERMISSION: Final = "config_bundle.rollback"
CONFIG_BUNDLE_DISABLE_PERMISSION: Final = "config_bundle.disable"
CONFIG_AUDIT_READ_PERMISSION: Final = "config_audit.read"
CONFIG_ASSET_EXPORT_PERMISSION: Final = "config_asset.export"
CONFIG_ASSET_IMPORT_PERMISSION: Final = "config_asset.import"
SCORING_RULESET_DRY_RUN_PERMISSION: Final = "scoring_ruleset.dry_run"

DEFAULT_ADMIN_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    ROLE_ADMIN: frozenset(
        {
            BUSINESS_RULE_PUBLISH_PERMISSION,
            RELEASE_VERIFICATION_MANAGE_PERMISSION,
            ADMIN_SETTINGS_MANAGE_PERMISSION,
            SCORING_RULESET_MANAGE_PERMISSION,
            CONFIG_BUNDLE_READ_PERMISSION,
            CONFIG_BUNDLE_DRAFT_PERMISSION,
            CONFIG_BUNDLE_VALIDATE_PERMISSION,
            CONFIG_BUNDLE_PREVIEW_PERMISSION,
            CONFIG_BUNDLE_PUBLISH_PERMISSION,
            CONFIG_BUNDLE_ROLLBACK_PERMISSION,
            CONFIG_BUNDLE_DISABLE_PERMISSION,
            CONFIG_AUDIT_READ_PERMISSION,
            CONFIG_ASSET_EXPORT_PERMISSION,
            CONFIG_ASSET_IMPORT_PERMISSION,
            SCORING_RULESET_DRY_RUN_PERMISSION,
        }
    ),
    ROLE_CONTENT_ADMIN: frozenset(
        {
            BUSINESS_RULE_PUBLISH_PERMISSION,
            SCORING_RULESET_MANAGE_PERMISSION,
            CONFIG_BUNDLE_READ_PERMISSION,
            CONFIG_BUNDLE_DRAFT_PERMISSION,
            CONFIG_BUNDLE_VALIDATE_PERMISSION,
            CONFIG_BUNDLE_PREVIEW_PERMISSION,
            CONFIG_BUNDLE_PUBLISH_PERMISSION,
            CONFIG_BUNDLE_ROLLBACK_PERMISSION,
            CONFIG_BUNDLE_DISABLE_PERMISSION,
            CONFIG_AUDIT_READ_PERMISSION,
            CONFIG_ASSET_EXPORT_PERMISSION,
            CONFIG_ASSET_IMPORT_PERMISSION,
            SCORING_RULESET_DRY_RUN_PERMISSION,
        }
    ),
    ROLE_OPERATIONS: frozenset(
        {
            BUSINESS_RULE_PUBLISH_PERMISSION,
            CONFIG_BUNDLE_READ_PERMISSION,
            CONFIG_BUNDLE_PREVIEW_PERMISSION,
            CONFIG_BUNDLE_PUBLISH_PERMISSION,
            CONFIG_BUNDLE_ROLLBACK_PERMISSION,
            CONFIG_AUDIT_READ_PERMISSION,
        }
    ),
    ROLE_SUPPORT: frozenset({CONFIG_AUDIT_READ_PERMISSION}),
    ROLE_READONLY_AUDITOR: frozenset({CONFIG_AUDIT_READ_PERMISSION}),
}


async def _ensure_default_role_permissions(db: AsyncSession) -> None:
    result = await db.execute(select(AdminRolePermission.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for role, permissions in DEFAULT_ADMIN_ROLE_PERMISSIONS.items():
        for permission in permissions:
            db.add(AdminRolePermission(role=role, permission=permission))
    await db.flush()


async def user_has_admin_permission(
    db: AsyncSession,
    user: User,
    permission: str,
) -> bool:
    role = admin_permission_role_for(getattr(user, "role", None))
    if not role:
        return False
    await _ensure_default_role_permissions(db)
    result = await db.execute(
        select(AdminRolePermission.id)
        .where(AdminRolePermission.role == role)
        .where(AdminRolePermission.permission == permission)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def require_admin_permission(permission: str) -> Callable[..., Awaitable[User]]:
    async def checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if not await user_has_admin_permission(db, current_user, permission):
            from common.auth.service import _raise_auth_http_error

            _raise_auth_http_error(
                status_code=403,
                error_code="[PERMISSION_REQUIRED]",
                message=f"当前账号缺少权限：{permission}。",
            )
        return current_user

    return checker
