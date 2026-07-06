"""Central role vocabulary and RBAC compatibility mapping."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

ROLE_USER: Final = "user"
ROLE_ADMIN: Final = "admin"
ROLE_SUPER_ADMIN: Final = "super_admin"
ROLE_SUPPORT: Final = "support"
ROLE_TRAINING_LEAD: Final = "training_lead"
ROLE_TRAINING_MANAGER: Final = "training_manager"
ROLE_CONTENT_ADMIN: Final = "content_admin"
ROLE_NEWCOMER_CONTENT_ADMIN: Final = "newcomer_content_admin"
ROLE_OPERATIONS: Final = "operations"
ROLE_OPS: Final = "ops"
ROLE_OPERATOR: Final = "operator"
ROLE_SRE: Final = "sre"
ROLE_READONLY_AUDITOR: Final = "readonly_auditor"
ROLE_LEARNER: Final = "learner"

USER_ROLE_VALUES: Final[tuple[str, ...]] = (
    ROLE_USER,
    ROLE_ADMIN,
    ROLE_SUPER_ADMIN,
    ROLE_SUPPORT,
    ROLE_TRAINING_LEAD,
    ROLE_TRAINING_MANAGER,
    ROLE_CONTENT_ADMIN,
    ROLE_NEWCOMER_CONTENT_ADMIN,
    ROLE_OPERATIONS,
    ROLE_OPS,
    ROLE_OPERATOR,
    ROLE_SRE,
    ROLE_READONLY_AUDITOR,
)

ADMIN_PERMISSION_ROLE_VALUES: Final[tuple[str, ...]] = (
    ROLE_ADMIN,
    ROLE_SUPPORT,
    ROLE_CONTENT_ADMIN,
    ROLE_OPERATIONS,
    ROLE_READONLY_AUDITOR,
)

PLATFORM_ADMIN_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_ADMIN, ROLE_SUPER_ADMIN}
)
CONTENT_ADMIN_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_CONTENT_ADMIN, ROLE_NEWCOMER_CONTENT_ADMIN}
)
TRAINING_MANAGER_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_SUPPORT, ROLE_TRAINING_LEAD, ROLE_TRAINING_MANAGER}
)
OPERATIONS_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_OPERATIONS, ROLE_OPS, ROLE_OPERATOR, ROLE_SRE}
)
READONLY_AUDITOR_ROLES: Final[frozenset[str]] = frozenset({ROLE_READONLY_AUDITOR})
SALES_TRAINER_ADMIN_CONSOLE_ROLES: Final[frozenset[str]] = frozenset(
    PLATFORM_ADMIN_ROLES
    | CONTENT_ADMIN_ROLES
    | TRAINING_MANAGER_ROLES
    | OPERATIONS_ROLES
)
SALES_TRAINER_LEARNER_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_USER, ROLE_LEARNER}
)

ADMIN_PERMISSION_ROLE_ALIASES: Final[dict[str, str]] = {
    ROLE_SUPER_ADMIN: ROLE_ADMIN,
    ROLE_NEWCOMER_CONTENT_ADMIN: ROLE_CONTENT_ADMIN,
    ROLE_OPS: ROLE_OPERATIONS,
    ROLE_OPERATOR: ROLE_OPERATIONS,
    ROLE_SRE: ROLE_OPERATIONS,
}


def normalize_role(value: object, *, default: str = ROLE_USER) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized:
            return normalized
    return default


def is_platform_admin_role(value: object) -> bool:
    return normalize_role(value) in PLATFORM_ADMIN_ROLES


def admin_permission_role_for(value: object) -> str:
    role = normalize_role(value, default="")
    return ADMIN_PERMISSION_ROLE_ALIASES.get(role, role)


def role_matches_allowed(value: object, allowed_roles: Iterable[str]) -> bool:
    role = normalize_role(value, default="")
    if not role:
        return False

    allowed: set[str] = set()
    for allowed_role in allowed_roles:
        normalized_allowed_role = normalize_role(allowed_role, default="")
        if normalized_allowed_role:
            allowed.add(normalized_allowed_role)
    if role in allowed:
        return True
    if ROLE_ADMIN in allowed and role in PLATFORM_ADMIN_ROLES:
        return True
    if ROLE_CONTENT_ADMIN in allowed and role in CONTENT_ADMIN_ROLES:
        return True
    if ROLE_OPERATIONS in allowed and role in OPERATIONS_ROLES:
        return True
    return False


def role_check_sql(column_name: str, roles: Iterable[str]) -> str:
    values = ", ".join(f"'{role}'" for role in roles)
    return f"{column_name} IN ({values})"


def user_role_check_sql(column_name: str = "role") -> str:
    return role_check_sql(column_name, USER_ROLE_VALUES)


def admin_permission_role_check_sql(column_name: str = "role") -> str:
    return role_check_sql(column_name, ADMIN_PERMISSION_ROLE_VALUES)
