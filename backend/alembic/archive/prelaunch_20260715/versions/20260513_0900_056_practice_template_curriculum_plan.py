"""add curriculum plan fields to practice templates

Revision ID: 20260513_0900_056
Revises: 20260512_1200_055
Create Date: 2026-05-13 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0900_056"
down_revision: str | None = "20260512_1200_055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_templates",
        sa.Column("curriculum_plan", sa.JSON(), nullable=True),
    )
    op.add_column(
        "practice_templates",
        sa.Column("max_stage_duration_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_templates", "max_stage_duration_seconds")
    op.drop_column("practice_templates", "curriculum_plan")
