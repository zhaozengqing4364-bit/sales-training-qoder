from __future__ import annotations

import os

from common.db.models import User

DEFAULT_TRAINING_MANAGER_ROLES = {"support"}


def is_sales_trainer_admin(user: User) -> bool:
    return str(getattr(user, "role", "")).lower() == "admin"


def sales_trainer_manager_roles() -> set[str]:
    raw_value = os.getenv("SALES_TRAINER_MANAGER_ROLES", "")
    configured = {
        item.strip().lower()
        for item in raw_value.split(",")
        if item.strip()
    }
    return configured or set(DEFAULT_TRAINING_MANAGER_ROLES)


def is_sales_trainer_manager(user: User) -> bool:
    return str(getattr(user, "role", "")).lower() in sales_trainer_manager_roles()


def can_manage_sales_trainer(user: User) -> bool:
    return is_sales_trainer_admin(user) or is_sales_trainer_manager(user)


def team_scope_department(user: User) -> str | None:
    if is_sales_trainer_admin(user):
        return None
    if not is_sales_trainer_manager(user):
        return "__NO_ACCESS__"
    department = str(getattr(user, "department", "") or "").strip()
    return department or "__NO_DEPARTMENT__"
