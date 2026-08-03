"""Expand users.role for centralized RBAC vocabulary.

Revision ID: 20260706_1200_090
Revises: 20260702_1530_089
Create Date: 2026-07-06 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260706_1200_090"
down_revision: str | None = "20260702_1530_089"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=20),
            type_=sa.String(length=32),
            existing_nullable=False,
            existing_server_default=sa.text("'user'"),
        )


def downgrade() -> None:
    long_role_count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM users WHERE length(role) > 20")
    ).scalar_one()
    if long_role_count:
        raise RuntimeError(
            "Refusing to shrink users.role to 20 while rows contain longer "
            "central RBAC roles. Reassign those users first, then retry downgrade."
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(length=32),
            type_=sa.String(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'user'"),
        )
