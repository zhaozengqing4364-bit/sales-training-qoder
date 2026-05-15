"""add test bank import jobs table

Revision ID: 20260516_0900_063
Revises: 20260515_1100_062
Create Date: 2026-05-16 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_0900_063"
down_revision: str | None = "20260515_1100_062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_bank_import_jobs",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_test_bank_import_job_status",
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(
        "idx_test_bank_import_jobs_created",
        "test_bank_import_jobs",
        ["created_by", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_test_bank_import_jobs_created_by"),
        "test_bank_import_jobs",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_test_bank_import_jobs_status"),
        "test_bank_import_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_test_bank_import_jobs_status"), table_name="test_bank_import_jobs")
    op.drop_index(
        op.f("ix_test_bank_import_jobs_created_by"),
        table_name="test_bank_import_jobs",
    )
    op.drop_index("idx_test_bank_import_jobs_created", table_name="test_bank_import_jobs")
    op.drop_table("test_bank_import_jobs")
