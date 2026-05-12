"""add practice session curriculum snapshot fields

Revision ID: 20260512_1000_053
Revises: 20260512_0900_052
Create Date: 2026-05-12 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_1000_053"
down_revision: str | None = "20260512_0900_052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_sessions",
        sa.Column("practice_template_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "practice_sessions",
        sa.Column("curriculum_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "practice_sessions",
        sa.Column("runtime_state", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_practice_sessions_practice_template_id",
        "practice_sessions",
        "practice_templates",
        ["practice_template_id"],
        ["template_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_sessions_practice_template",
        "practice_sessions",
        ["practice_template_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_sessions_practice_template",
        table_name="practice_sessions",
        if_exists=True,
    )
    op.drop_constraint(
        "fk_practice_sessions_practice_template_id",
        "practice_sessions",
        type_="foreignkey",
    )
    op.drop_column("practice_sessions", "runtime_state")
    op.drop_column("practice_sessions", "curriculum_snapshot")
    op.drop_column("practice_sessions", "practice_template_id")
