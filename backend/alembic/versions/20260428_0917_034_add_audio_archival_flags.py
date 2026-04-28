"""add audio archival flags to practice sessions

Revision ID: 20260428_0917_034
Revises: 20260424_1106_w6
Create Date: 2026-04-28 09:17:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0917_034"
down_revision: str | None = "20260424_1106_w6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_sessions",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "practice_sessions",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_sessions", "archived_at")
    op.drop_column("practice_sessions", "archived")
