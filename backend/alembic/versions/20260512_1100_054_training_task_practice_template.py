"""bind training tasks to practice templates

Revision ID: 20260512_1100_054
Revises: 20260512_1000_053
Create Date: 2026-05-12 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_1100_054"
down_revision: str | None = "20260512_1000_053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_tasks",
        sa.Column("practice_template_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_training_tasks_practice_template_id",
        "training_tasks",
        "practice_templates",
        ["practice_template_id"],
        ["template_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_training_tasks_practice_template",
        "training_tasks",
        ["practice_template_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_training_tasks_practice_template",
        table_name="training_tasks",
        if_exists=True,
    )
    op.drop_constraint(
        "fk_training_tasks_practice_template_id",
        "training_tasks",
        type_="foreignkey",
    )
    op.drop_column("training_tasks", "practice_template_id")
