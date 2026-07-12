from __future__ import annotations

import os
from functools import lru_cache
from typing import Final

from common.auth.roles import (
    CONTENT_ADMIN_ROLES,
    OPERATIONS_ROLES,
    PLATFORM_ADMIN_ROLES,
    SALES_TRAINER_LEARNER_ROLES,
    TRAINING_MANAGER_ROLES,
    normalize_role,
)
from common.db.models import User
from common.monitoring.logger import get_logger

SUPER_ADMIN_ROLES: Final = PLATFORM_ADMIN_ROLES
TRAINING_LEAD_ROLES: Final = TRAINING_MANAGER_ROLES
OPS_ROLES: Final = OPERATIONS_ROLES
DEFAULT_TRAINING_MANAGER_ROLES: Final = set(TRAINING_LEAD_ROLES)
ALLOWED_TRAINING_MANAGER_ROLES: Final = frozenset(TRAINING_LEAD_ROLES)
SALES_TRAINER_ADMIN_CAPABILITY_KEYS: Final = (
    "admin_full_access",
    "manage_content",
    "manage_questions",
    "manage_modules",
    "manage_prompts",
    "view_records",
    "view_global_records",
    "retry_jobs",
    "regrade_history",
    "view_logs",
    "view_settings",
)

logger = get_logger(__name__)


def _role(user: User) -> str:
    return normalize_role(getattr(user, "role", None), default="")


def is_sales_trainer_admin(user: User) -> bool:
    return _role(user) in SUPER_ADMIN_ROLES


@lru_cache(maxsize=8)
def _resolve_sales_trainer_manager_roles(raw_value: str) -> frozenset[str]:
    configured = {item.strip().lower() for item in raw_value.split(",") if item.strip()}
    if not configured:
        return frozenset(DEFAULT_TRAINING_MANAGER_ROLES)

    allowed = configured & ALLOWED_TRAINING_MANAGER_ROLES
    invalid = sorted(configured - ALLOWED_TRAINING_MANAGER_ROLES)
    if invalid:
        logger.warning(
            "sales_trainer_manager_roles_invalid",
            configured_roles=sorted(configured),
            invalid_roles=invalid,
            effective_roles=sorted(allowed),
            fallback_to_default=False,
        )
    if allowed:
        return frozenset(allowed)
    return frozenset()


def sales_trainer_manager_roles() -> set[str]:
    raw_value = os.getenv("SALES_TRAINER_MANAGER_ROLES", "")
    return set(_resolve_sales_trainer_manager_roles(raw_value))


def is_sales_trainer_manager(user: User) -> bool:
    return _role(user) in sales_trainer_manager_roles()


def is_sales_trainer_content_admin(user: User) -> bool:
    return _role(user) in CONTENT_ADMIN_ROLES


def is_sales_trainer_ops(user: User) -> bool:
    return _role(user) in OPS_ROLES


def can_manage_sales_trainer(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_content_admin(user)


def can_manage_sales_trainer_questions(user: User) -> bool:
    return can_manage_sales_trainer(user) or is_sales_trainer_manager(user)


def can_manage_sales_trainer_modules(user: User) -> bool:
    """管理模块开关、入口文案、轮数等配置。"""
    return is_sales_trainer_admin(user) or is_sales_trainer_content_admin(user)


def can_manage_sales_trainer_prompts(user: User) -> bool:
    """管理 prompt 绑定、评分规则、掌握阈值等高风险训练规则。"""
    return is_sales_trainer_admin(user)


def can_view_sales_trainer_records(user: User) -> bool:
    return (
        is_sales_trainer_admin(user)
        or is_sales_trainer_manager(user)
        or is_sales_trainer_ops(user)
    )


def can_view_sales_trainer_global_records(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_ops(user)


def can_retry_sales_trainer_jobs(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_ops(user)


def can_regrade_sales_trainer_history(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_ops(user)


def can_view_sales_trainer_logs(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_ops(user)


def can_view_sales_trainer_settings(user: User) -> bool:
    return can_view_sales_trainer_logs(user)


def can_enter_sales_trainer_learning_path(user: User) -> bool:
    # getattr returns None for unset Column defaults on transient objects;
    # treat None as active so unit-constructed users behave as expected.
    is_active = getattr(user, "is_active", True)
    if is_active is False:
        return False
    # Platform admins may enter the learner path for development, debugging,
    # and product acceptance without needing a separate learner account.
    # They remain subject to per-user progress isolation in the journey.
    if is_sales_trainer_admin(user):
        return True
    return _role(user) in SALES_TRAINER_LEARNER_ROLES


def can_enter_sales_trainer_realtime(user: User) -> bool:
    return can_enter_sales_trainer_learning_path(user)


def can_manage_newcomer_training_path(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_content_admin(user)


def can_publish_newcomer_training_path(user: User) -> bool:
    return is_sales_trainer_admin(user)


def can_learn_newcomer_training_path(user: User) -> bool:
    return can_enter_sales_trainer_learning_path(user)


def team_scope_department(user: User) -> str | None:
    if is_sales_trainer_admin(user):
        return None
    if is_sales_trainer_ops(user):
        return None
    if not is_sales_trainer_manager(user):
        return "__NO_ACCESS__"
    department = str(getattr(user, "department", "") or "").strip()
    return department or "__NO_DEPARTMENT__"


def sales_trainer_admin_role_label(role: str) -> str:
    if role in SUPER_ADMIN_ROLES:
        return "超级管理员"
    if role in CONTENT_ADMIN_ROLES:
        return "内容管理员"
    if role in sales_trainer_manager_roles():
        return "培训负责人"
    if role in OPS_ROLES:
        return "运维人员"
    return "普通用户"


def sales_trainer_admin_capability_projection(user: User) -> dict[str, object]:
    role = _role(user)
    capabilities = {
        "admin_full_access": is_sales_trainer_admin(user),
        "manage_content": can_manage_sales_trainer(user),
        "manage_questions": can_manage_sales_trainer_questions(user),
        "manage_modules": can_manage_sales_trainer_modules(user),
        "manage_prompts": can_manage_sales_trainer_prompts(user),
        "view_records": can_view_sales_trainer_records(user),
        "view_global_records": can_view_sales_trainer_global_records(user),
        "retry_jobs": can_retry_sales_trainer_jobs(user),
        "regrade_history": can_regrade_sales_trainer_history(user),
        "view_logs": can_view_sales_trainer_logs(user),
        "view_settings": can_view_sales_trainer_settings(user),
    }
    return {
        "role": role,
        "role_label": sales_trainer_admin_role_label(role),
        "capabilities": capabilities,
        "capability_keys": [
            key for key in SALES_TRAINER_ADMIN_CAPABILITY_KEYS if capabilities[key]
        ],
    }
