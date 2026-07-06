from __future__ import annotations

from sqlalchemy import CheckConstraint

from common.auth.roles import (
    ADMIN_PERMISSION_ROLE_VALUES,
    ROLE_ADMIN,
    ROLE_CONTENT_ADMIN,
    ROLE_NEWCOMER_CONTENT_ADMIN,
    ROLE_OPERATIONS,
    ROLE_OPERATOR,
    ROLE_OPS,
    ROLE_READONLY_AUDITOR,
    ROLE_SRE,
    ROLE_SUPER_ADMIN,
    USER_ROLE_VALUES,
    admin_permission_role_check_sql,
    admin_permission_role_for,
    is_platform_admin_role,
    normalize_role,
    role_matches_allowed,
    user_role_check_sql,
)
from common.db.models import AdminRolePermission, User


def _check_constraint_sql(model: type, name: str) -> str:
    for constraint in model.__table__.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == name:
            return str(constraint.sqltext)
    raise AssertionError(f"{model.__name__}.{name} constraint not found")


def test_user_role_constraint_uses_central_role_vocabulary() -> None:
    sql = _check_constraint_sql(User, "ck_user_role")

    assert sql == user_role_check_sql()
    for role in USER_ROLE_VALUES:
        assert f"'{role}'" in sql


def test_user_role_column_fits_longest_central_role() -> None:
    role_length = User.__table__.c.role.type.length

    assert role_length is not None
    assert role_length >= max(len(role) for role in USER_ROLE_VALUES)
    assert len(ROLE_NEWCOMER_CONTENT_ADMIN) <= role_length


def test_admin_permission_role_constraint_uses_canonical_permission_roles() -> None:
    sql = _check_constraint_sql(
        AdminRolePermission,
        "ck_admin_role_permissions_role",
    )

    assert sql == admin_permission_role_check_sql()
    for role in ADMIN_PERMISSION_ROLE_VALUES:
        assert f"'{role}'" in sql
    assert f"'{ROLE_SUPER_ADMIN}'" not in sql
    assert f"'{ROLE_NEWCOMER_CONTENT_ADMIN}'" not in sql
    assert f"'{ROLE_OPS}'" not in sql


def test_admin_permission_aliases_resolve_to_canonical_roles() -> None:
    assert admin_permission_role_for(ROLE_SUPER_ADMIN) == ROLE_ADMIN
    assert admin_permission_role_for(ROLE_NEWCOMER_CONTENT_ADMIN) == ROLE_CONTENT_ADMIN
    assert admin_permission_role_for(ROLE_OPS) == ROLE_OPERATIONS
    assert admin_permission_role_for(ROLE_OPERATOR) == ROLE_OPERATIONS
    assert admin_permission_role_for(ROLE_SRE) == ROLE_OPERATIONS
    assert admin_permission_role_for(ROLE_READONLY_AUDITOR) == ROLE_READONLY_AUDITOR


def test_role_normalization_and_platform_admin_predicate() -> None:
    assert normalize_role(" Super_Admin ") == ROLE_SUPER_ADMIN
    assert normalize_role(None) == "user"
    assert is_platform_admin_role(" ADMIN ")
    assert is_platform_admin_role(ROLE_SUPER_ADMIN)
    assert not is_platform_admin_role(ROLE_CONTENT_ADMIN)


def test_role_matches_allowed_expands_canonical_admin_content_and_ops_groups() -> None:
    assert role_matches_allowed(ROLE_SUPER_ADMIN, [ROLE_ADMIN, "user"])
    assert role_matches_allowed(ROLE_NEWCOMER_CONTENT_ADMIN, [ROLE_CONTENT_ADMIN])
    assert role_matches_allowed(ROLE_OPS, [ROLE_OPERATIONS])
    assert role_matches_allowed(ROLE_OPERATOR, [ROLE_OPERATIONS])
    assert role_matches_allowed(ROLE_SRE, [ROLE_OPERATIONS])
    assert not role_matches_allowed(ROLE_READONLY_AUDITOR, [ROLE_ADMIN])
