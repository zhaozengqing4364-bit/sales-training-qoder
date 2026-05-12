"""add training tasks

Revision ID: 20260511_0900_045
Revises: 20260510_2230_044
Create Date: 2026-05-11 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0900_045"
down_revision: str | None = "20260510_2230_044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_tasks",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("assignee_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_type", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("focus_intent", sa.String(length=120), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_criteria", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=50), server_default="manual", nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="assigned", nullable=False
        ),
        sa.Column("resulting_session_id", sa.String(length=36), nullable=True),
        sa.Column("before_after_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scenario_type IN ('sales', 'presentation')",
            name="ck_training_tasks_scenario_type",
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed', 'expired', 'cancelled')",
            name="ck_training_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resulting_session_id"],
            ["practice_sessions.session_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_training_tasks_status", "training_tasks", ["status"])
    op.create_index(
        "ix_training_tasks_resulting_session_id",
        "training_tasks",
        ["resulting_session_id"],
    )
    op.create_index(
        "idx_training_tasks_assignee_status",
        "training_tasks",
        ["assignee_id", "status"],
    )
    op.create_index("idx_training_tasks_due_date", "training_tasks", ["due_date"])
    op.create_index("idx_training_tasks_created_at", "training_tasks", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_training_tasks_created_at", table_name="training_tasks")
    op.drop_index("idx_training_tasks_due_date", table_name="training_tasks")
    op.drop_index("idx_training_tasks_assignee_status", table_name="training_tasks")
    op.drop_index("ix_training_tasks_resulting_session_id", table_name="training_tasks")
    op.drop_index("ix_training_tasks_status", table_name="training_tasks")
    op.drop_table("training_tasks")
