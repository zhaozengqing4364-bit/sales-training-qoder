"""Add durable bulk provisioning batches.

Revision ID: 20260714_1600_095
Revises: 20260714_1500_094
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_1600_095"
down_revision: str | None = "20260714_1500_094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisioning_batches",
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('previewed', 'processing', 'completed', 'partially_completed', 'failed')",
            name="ck_provisioning_batch_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("batch_id"),
    )
    op.create_index(
        "ix_provisioning_batches_idempotency_key",
        "provisioning_batches",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_provisioning_batches_status", "provisioning_batches", ["status"]
    )

    op.create_table(
        "provisioning_team_executions",
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("team_code", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_provisioning_team_execution_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["provisioning_batches.batch_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("execution_id"),
        sa.UniqueConstraint(
            "batch_id", "team_code", name="uq_provisioning_team_execution"
        ),
    )
    op.create_index(
        "ix_provisioning_team_executions_batch_id",
        "provisioning_team_executions",
        ["batch_id"],
    )

    op.create_table(
        "provisioning_rows",
        sa.Column("row_id", sa.String(36), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("team_code", sa.String(80), nullable=False),
        sa.Column("team_name", sa.String(160), nullable=True),
        sa.Column("primary_leader_email", sa.String(255), nullable=True),
        sa.Column("employee_number", sa.String(80), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.CheckConstraint(
            "status IN ('valid', 'invalid', 'created', 'failed', 'skipped')",
            name="ck_provisioning_row_status",
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["provisioning_batches.batch_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint(
            "batch_id", "row_number", name="uq_provisioning_batch_row_number"
        ),
    )
    op.create_index("ix_provisioning_rows_batch_id", "provisioning_rows", ["batch_id"])
    op.create_index(
        "ix_provisioning_rows_team_code", "provisioning_rows", ["team_code"]
    )


def downgrade() -> None:
    op.drop_table("provisioning_rows")
    op.drop_table("provisioning_team_executions")
    op.drop_table("provisioning_batches")
