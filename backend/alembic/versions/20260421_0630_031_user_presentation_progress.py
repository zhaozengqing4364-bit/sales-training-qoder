"""add user presentation progress

Revision ID: 20260421_0630_031
Revises: 20260420_1030_030
Create Date: 2026-04-21 06:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260421_0630_031"
down_revision: str | None = "20260420_1030_030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_presentation_progress",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("presentation_id", sa.String(length=36), nullable=False),
        sa.Column("last_page_number", sa.Integer(), nullable=False),
        sa.Column("last_session_id", sa.String(length=36), nullable=True),
        sa.Column(
            "last_practice_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "last_page_number >= 1",
            name="ck_user_presentation_progress_page_positive",
        ),
        sa.ForeignKeyConstraint(
            ["last_session_id"],
            ["practice_sessions.session_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["presentation_id"],
            ["presentations.presentation_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "presentation_id"),
    )
    op.create_index(
        "idx_user_presentation_progress_user_updated",
        "user_presentation_progress",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_presentation_progress_last_session_id",
        "user_presentation_progress",
        ["last_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_presentation_progress_last_practice_at",
        "user_presentation_progress",
        ["last_practice_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_presentation_progress_last_practice_at",
        table_name="user_presentation_progress",
    )
    op.drop_index(
        "ix_user_presentation_progress_last_session_id",
        table_name="user_presentation_progress",
    )
    op.drop_index(
        "idx_user_presentation_progress_user_updated",
        table_name="user_presentation_progress",
    )
    op.drop_table("user_presentation_progress")
