"""Add managed user credential lifecycle fields.

Revision ID: 20260714_1400_093
Revises: 20260712_1300_092
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_1400_093"
down_revision: str | None = "20260712_1300_092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    duplicate_emails = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT lower(email) AS normalized_email, count(*) AS duplicate_count "
                "FROM users WHERE email IS NOT NULL "
                "GROUP BY lower(email) HAVING count(*) > 1"
            )
        )
        .fetchall()
    )
    if duplicate_emails:
        raise RuntimeError(
            "Cannot enforce case-insensitive user email uniqueness; "
            f"resolve {len(duplicate_emails)} normalized email conflict(s) first."
        )

    op.add_column(
        "users",
        sa.Column(
            "credential_status",
            sa.String(length=24),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "temporary_password_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "credential_version", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    op.create_check_constraint(
        "ck_users_credential_status",
        "users",
        "credential_status IN ('active', 'temporary', 'reset_required')",
    )
    op.create_index(
        "ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_constraint("ck_users_credential_status", "users", type_="check")
    op.drop_column("users", "credential_version")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "temporary_password_expires_at")
    op.drop_column("users", "credential_status")
