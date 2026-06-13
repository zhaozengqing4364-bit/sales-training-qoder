from __future__ import annotations

import os
from typing import Final

from common.db.models import User

SUPER_ADMIN_ROLES: Final = {"admin", "super_admin"}
CONTENT_ADMIN_ROLES: Final = {"content_admin", "newcomer_content_admin"}
TRAINING_LEAD_ROLES: Final = {"support", "training_lead", "training_manager"}
OPS_ROLES: Final = {"ops", "operator", "operations", "sre"}
DEFAULT_TRAINING_MANAGER_ROLES: Final = set(TRAINING_LEAD_ROLES)
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


def _role(user: User) -> str:
    return str(getattr(user, "role", "")).lower()


def is_sales_trainer_admin(user: User) -> bool:
    return _role(user) in SUPER_ADMIN_ROLES


def sales_trainer_manager_roles() -> set[str]:
    raw_value = os.getenv("SALES_TRAINER_MANAGER_ROLES", "")
    configured = {
        item.strip().lower()
        for item in raw_value.split(",")
        if item.strip()
    }
    return configured or set(DEFAULT_TRAINING_MANAGER_ROLES)


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
    return (
        is_sales_trainer_admin(user)
        or is_sales_trainer_manager(user)
        or is_sales_trainer_ops(user)
    )


def can_view_sales_trainer_settings(user: User) -> bool:
    return can_view_sales_trainer_logs(user)


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
