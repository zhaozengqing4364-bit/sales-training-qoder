"""add training report snapshots

Revision ID: 20260510_2215_043
Revises: 20260510_2200_042
Create Date: 2026-05-10 22:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2215_043"
down_revision: str | None = "20260510_2200_042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_report_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=36), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("ruleset_source", sa.String(length=80), nullable=False),
        sa.Column("ruleset_version", sa.String(length=80), nullable=False),
        sa.Column("score_basis", sa.String(length=120), nullable=False),
        sa.Column("evidence_completeness", sa.JSON(), nullable=False),
        sa.Column("non_evaluable_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.run_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("session_id", name="uq_training_report_snapshots_session"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            name="uq_training_report_snapshots_evaluation_run",
        ),
    )
    op.create_index(
        "ix_training_report_snapshots_session_id",
        "training_report_snapshots",
        ["session_id"],
    )
    op.create_index(
        "ix_training_report_snapshots_evaluation_run_id",
        "training_report_snapshots",
        ["evaluation_run_id"],
    )
    op.create_index(
        "idx_training_report_snapshots_session_generated",
        "training_report_snapshots",
        ["session_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_training_report_snapshots_session_generated",
        table_name="training_report_snapshots",
    )
    op.drop_index(
        "ix_training_report_snapshots_evaluation_run_id",
        table_name="training_report_snapshots",
    )
    op.drop_index(
        "ix_training_report_snapshots_session_id",
        table_name="training_report_snapshots",
    )
    op.drop_table("training_report_snapshots")
