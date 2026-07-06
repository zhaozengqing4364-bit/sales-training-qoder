from __future__ import annotations

from typing import Final

from common.auth.roles import PLATFORM_ADMIN_ROLES, normalize_role
from common.db.models import User

PROMPT_TEMPLATE_ADMIN_ROLES: Final = PLATFORM_ADMIN_ROLES


def can_manage_prompt_templates(user: User) -> bool:
    return normalize_role(getattr(user, "role", None), default="") in PROMPT_TEMPLATE_ADMIN_ROLES
