from __future__ import annotations

from common.db.models import User

CURRICULUM_TEMPLATE_MANAGE_PERMISSION = "curriculum.template.manage"
CURRICULUM_TEMPLATE_PUBLISH_PERMISSION = "curriculum.template.publish"


def can_manage_practice_templates(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"
