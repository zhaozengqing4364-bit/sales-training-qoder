"""add training task curriculum plan binding

Revision ID: 20260516_1100_065
Revises: 20260516_1000_064
Create Date: 2026-05-16 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_1100_065"
down_revision: str | None = "20260516_1000_064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_tasks",
        sa.Column("curriculum_plan_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "idx_training_tasks_curriculum_plan",
        "training_tasks",
        ["curriculum_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_training_tasks_curriculum_plan", table_name="training_tasks")
    op.drop_column("training_tasks", "curriculum_plan_id")
