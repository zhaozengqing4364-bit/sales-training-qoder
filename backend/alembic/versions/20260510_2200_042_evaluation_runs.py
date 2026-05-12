"""add evaluation runs

Revision ID: 20260510_2200_042
Revises: 20260510_2130_041
Create Date: 2026-05-10 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2200_042"
down_revision: str | None = "20260510_2130_041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_evidence_reference", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_trace", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'non_evaluable', 'failed')",
            name="ck_evaluation_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("session_id", name="uq_evaluation_runs_session"),
    )
    op.create_index("ix_evaluation_runs_session_id", "evaluation_runs", ["session_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])
    op.create_index(
        "idx_evaluation_runs_session_status",
        "evaluation_runs",
        ["session_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_evaluation_runs_session_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_session_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
