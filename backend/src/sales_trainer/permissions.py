from __future__ import annotations

import os
from typing import Final

from common.db.models import User

SUPER_ADMIN_ROLES: Final = {"admin", "super_admin"}
CONTENT_ADMIN_ROLES: Final = {"content_admin", "newcomer_content_admin"}
TRAINING_LEAD_ROLES: Final = {"support", "training_lead", "training_manager"}
OPS_ROLES: Final = {"ops", "operator", "operations", "sre"}
DEFAULT_TRAINING_MANAGER_ROLES: Final = set(TRAINING_LEAD_ROLES)


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


def team_scope_department(user: User) -> str | None:
    if is_sales_trainer_admin(user):
        return None
    if is_sales_trainer_ops(user):
        return None
    if not is_sales_trainer_manager(user):
        return "__NO_ACCESS__"
    department = str(getattr(user, "department", "") or "").strip()
    return department or "__NO_DEPARTMENT__"
