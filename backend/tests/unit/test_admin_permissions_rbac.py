from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from admin.api.permissions import (
    ADMIN_SETTINGS_MANAGE_PERMISSION,
    CONFIG_ASSET_IMPORT_PERMISSION,
    CONFIG_AUDIT_READ_PERMISSION,
    CONFIG_BUNDLE_PUBLISH_PERMISSION,
    TASK_RUNTIME_OPERATE_PERMISSION,
    TASK_RUNTIME_READ_PERMISSION,
    user_has_admin_permission,
)
from common.db.models import AdminRolePermission, User


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


@pytest.mark.asyncio
async def test_existing_permission_rows_do_not_block_new_default_permission_seed(
    test_db,
) -> None:
    test_db.add(AdminRolePermission(role="support", permission="config_audit.read"))
    await test_db.flush()

    admin = _user("admin")
    assert await user_has_admin_permission(
        test_db,
        admin,
        TASK_RUNTIME_READ_PERMISSION,
    )
    assert await user_has_admin_permission(
        test_db,
        admin,
        TASK_RUNTIME_OPERATE_PERMISSION,
    )


@pytest.mark.asyncio
async def test_concurrent_default_permission_seed_is_conflict_safe(test_engine) -> None:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    admin = _user("admin")

    async def check_permission() -> bool:
        async with factory() as session:
            allowed = await user_has_admin_permission(
                session,
                admin,
                TASK_RUNTIME_READ_PERMISSION,
            )
            await session.commit()
            return allowed

    assert await asyncio.gather(check_permission(), check_permission()) == [True, True]
    async with factory() as session:
        count = (
            await session.execute(
                select(func.count(AdminRolePermission.id)).where(
                    AdminRolePermission.role == "admin",
                    AdminRolePermission.permission == TASK_RUNTIME_READ_PERMISSION,
                )
            )
        ).scalar_one()
    assert count == 1
