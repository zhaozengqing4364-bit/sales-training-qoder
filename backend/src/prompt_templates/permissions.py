from __future__ import annotations

from typing import Final

from common.db.models import User

PROMPT_TEMPLATE_ADMIN_ROLES: Final = {"admin", "super_admin"}


def can_manage_prompt_templates(user: User) -> bool:
    return str(getattr(user, "role", "")).lower() in PROMPT_TEMPLATE_ADMIN_ROLES
