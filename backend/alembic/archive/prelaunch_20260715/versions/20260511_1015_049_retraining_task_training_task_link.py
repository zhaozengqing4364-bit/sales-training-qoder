"""link retraining tasks to training tasks

Revision ID: 20260511_1015_049
Revises: 20260511_1000_048
Create Date: 2026-05-11 10:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_1015_049"
down_revision: str | None = "20260511_1000_048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retraining_tasks",
        sa.Column("training_task_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_retraining_tasks_training_task_id",
        "retraining_tasks",
        "training_tasks",
        ["training_task_id"],
        ["task_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_retraining_tasks_training_task_id",
        "retraining_tasks",
        ["training_task_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_retraining_tasks_training_status",
        "retraining_tasks",
        ["training_task_id", "status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_retraining_tasks_training_status",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_training_task_id",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_constraint(
        "fk_retraining_tasks_training_task_id",
        "retraining_tasks",
        type_="foreignkey",
    )
    op.drop_column("retraining_tasks", "training_task_id")
