from __future__ import annotations

import pytest

from admin.api.permissions import (
    ADMIN_SETTINGS_MANAGE_PERMISSION,
    CONFIG_ASSET_IMPORT_PERMISSION,
    CONFIG_AUDIT_READ_PERMISSION,
    CONFIG_BUNDLE_PUBLISH_PERMISSION,
    user_has_admin_permission,
)
from common.db.models import User


def _user(role: str) -> User:
    return User(
        user_id=f"user-{role}",
        wechat_user_id=f"wechat-{role}",
        name=role,
        email=f"{role}@example.com",
        role=role,
    )


@pytest.mark.asyncio
async def test_role_aliases_use_canonical_admin_permission_rows(test_db) -> None:
    assert await user_has_admin_permission(
        test_db,
        _user("super_admin"),
        ADMIN_SETTINGS_MANAGE_PERMISSION,
    )
    assert await user_has_admin_permission(
        test_db,
        _user("newcomer_content_admin"),
        CONFIG_ASSET_IMPORT_PERMISSION,
    )
    assert await user_has_admin_permission(
        test_db,
        _user("ops"),
        CONFIG_BUNDLE_PUBLISH_PERMISSION,
    )
    assert await user_has_admin_permission(
        test_db,
        _user("operator"),
        CONFIG_BUNDLE_PUBLISH_PERMISSION,
    )
    assert await user_has_admin_permission(
        test_db,
        _user("sre"),
        CONFIG_BUNDLE_PUBLISH_PERMISSION,
    )


@pytest.mark.asyncio
async def test_readonly_and_operations_aliases_do_not_expand_to_admin(test_db) -> None:
    assert await user_has_admin_permission(
        test_db,
        _user("readonly_auditor"),
        CONFIG_AUDIT_READ_PERMISSION,
    )
    assert not await user_has_admin_permission(
        test_db,
        _user("readonly_auditor"),
        ADMIN_SETTINGS_MANAGE_PERMISSION,
    )
    assert not await user_has_admin_permission(
        test_db,
        _user("ops"),
        ADMIN_SETTINGS_MANAGE_PERMISSION,
    )
