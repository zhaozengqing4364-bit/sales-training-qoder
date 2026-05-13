"""add voice fields to role profiles

Revision ID: 20260513_1000_059
Revises: 20260513_0900_056
Create Date: 2026-05-13 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_1000_059"
down_revision: str | None = "20260513_0900_056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("role_profiles", sa.Column("voice_id", sa.String(64), nullable=True))
    op.add_column(
        "role_profiles", sa.Column("voice_sample_url", sa.String(512), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("role_profiles", "voice_sample_url")
    op.drop_column("role_profiles", "voice_id")
