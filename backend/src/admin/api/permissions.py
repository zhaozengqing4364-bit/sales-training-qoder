"""Fine-grained admin permission helpers backed by persisted role mappings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Final

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
TASK_RUNTIME_READ_PERMISSION: Final = "task_runtime.read"
TASK_RUNTIME_OPERATE_PERMISSION: Final = "task_runtime.operate"

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
            TASK_RUNTIME_READ_PERMISSION,
            TASK_RUNTIME_OPERATE_PERMISSION,
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


async def _insert_default_role_permission(
    db: AsyncSession,
    *,
    role: str,
    permission: str,
) -> bool:
    if permission not in DEFAULT_ADMIN_ROLE_PERMISSIONS.get(role, frozenset()):
        return False
    dialect_name = db.get_bind().dialect.name
    statement: Any
    if dialect_name == "postgresql":
        statement = postgresql_insert(AdminRolePermission)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(AdminRolePermission)
    else:  # pragma: no cover - production and tests use PostgreSQL/SQLite
        raise RuntimeError(f"不支持的权限存储数据库：{dialect_name}")
    await db.execute(
        statement.values(role=role, permission=permission).on_conflict_do_nothing(
            index_elements=["role", "permission"]
        )
    )
    await db.flush()
    return True


async def user_has_admin_permission(
    db: AsyncSession,
    user: User,
    permission: str,
) -> bool:
    role = admin_permission_role_for(getattr(user, "role", None))
    if not role:
        return False
    if await user_has_persisted_admin_permission(db, user, permission):
        return True
    return await _insert_default_role_permission(
        db,
        role=role,
        permission=permission,
    )


async def user_has_persisted_admin_permission(
    db: AsyncSession,
    user: User,
    permission: str,
) -> bool:
    """Read an exact persisted mapping without inferring defaults from a role."""

    role = admin_permission_role_for(getattr(user, "role", None))
    if not role:
        return False
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
