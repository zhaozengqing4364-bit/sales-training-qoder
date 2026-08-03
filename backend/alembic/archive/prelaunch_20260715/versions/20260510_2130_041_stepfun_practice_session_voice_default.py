"""default practice session voice mode to stepfun

Revision ID: 20260510_2130_041
Revises: 20260510_0900_040
Create Date: 2026-05-10 21:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2130_041"
down_revision: str | None = "20260510_0900_040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Change only the future DB default; preserve existing row values."""
    op.alter_column(
        "practice_sessions",
        "voice_mode",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="stepfun_realtime",
    )


def downgrade() -> None:
    """Restore the previous future DB default without rewriting existing rows."""
    op.alter_column(
        "practice_sessions",
        "voice_mode",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        server_default="legacy",
    )
