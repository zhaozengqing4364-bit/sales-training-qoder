"""add report trigger diagnostics

Revision ID: 20260510_2230_044
Revises: 20260510_2215_043
Create Date: 2026-05-10 22:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2230_044"
down_revision: str | None = "20260510_2215_043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_sessions",
        sa.Column("report_status_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "practice_sessions",
        sa.Column("report_retryable", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "practice_sessions",
        sa.Column("report_trace_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_sessions", "report_trace_id")
    op.drop_column("practice_sessions", "report_retryable")
    op.drop_column("practice_sessions", "report_status_updated_at")
