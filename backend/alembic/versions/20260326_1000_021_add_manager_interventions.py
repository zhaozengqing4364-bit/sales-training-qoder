"""Add manager interventions table.

Revision ID: 20260326_1000_021
Revises: 20260317_2310_020
Create Date: 2026-03-26 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260326_1000_021"
down_revision: Union[str, None] = "20260317_2310_020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manager_interventions",
        sa.Column("intervention_id", sa.String(length=36), nullable=False),
        sa.Column("manager_user_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("issue_family", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("due_state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "reminder_status",
            sa.String(length=20),
            nullable=False,
            server_default="not_sent",
        ),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolving_session_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "due_state IN ('pending', 'due', 'resolved')",
            name="ck_manager_intervention_due_state",
        ),
        sa.CheckConstraint(
            "reminder_status IN ('not_sent', 'sent')",
            name="ck_manager_intervention_reminder_status",
        ),
        sa.CheckConstraint(
            "(resolving_session_id IS NULL AND due_state IN ('pending', 'due')) OR "
            "(resolving_session_id IS NOT NULL AND due_state = 'resolved')",
            name="ck_manager_intervention_resolution_state",
        ),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["resolving_session_id"], ["practice_sessions.session_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("intervention_id"),
    )
    op.create_index(
        "idx_manager_interventions_user_created",
        "manager_interventions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_manager_interventions_manager_created",
        "manager_interventions",
        ["manager_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_created_at"),
        "manager_interventions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_due_state"),
        "manager_interventions",
        ["due_state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_issue_family"),
        "manager_interventions",
        ["issue_family"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_manager_user_id"),
        "manager_interventions",
        ["manager_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_resolving_session_id"),
        "manager_interventions",
        ["resolving_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_manager_interventions_user_id"),
        "manager_interventions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_manager_interventions_user_id"), table_name="manager_interventions")
    op.drop_index(
        op.f("ix_manager_interventions_resolving_session_id"),
        table_name="manager_interventions",
    )
    op.drop_index(
        op.f("ix_manager_interventions_manager_user_id"),
        table_name="manager_interventions",
    )
    op.drop_index(op.f("ix_manager_interventions_issue_family"), table_name="manager_interventions")
    op.drop_index(op.f("ix_manager_interventions_due_state"), table_name="manager_interventions")
    op.drop_index(op.f("ix_manager_interventions_created_at"), table_name="manager_interventions")
    op.drop_index(
        "idx_manager_interventions_manager_created",
        table_name="manager_interventions",
    )
    op.drop_index(
        "idx_manager_interventions_user_created",
        table_name="manager_interventions",
    )
    op.drop_table("manager_interventions")
