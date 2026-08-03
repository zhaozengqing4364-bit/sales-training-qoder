"""Expand user roles for newcomer training RBAC

Revision ID: 20260603_1000_075
Revises: 20260602_1500_074
Create Date: 2026-06-03 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260603_1000_075"
down_revision: str | None = "20260602_1500_074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE_CHECK = (
    "role IN ('user', 'admin', 'super_admin', 'support', 'training_lead', "
    "'training_manager', 'content_admin', 'newcomer_content_admin', "
    "'operations', 'ops', 'operator', 'sre', 'readonly_auditor')"
)


def upgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        USER_ROLE_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('user', 'admin', 'support', 'content_admin', 'operations', 'readonly_auditor')",
    )
