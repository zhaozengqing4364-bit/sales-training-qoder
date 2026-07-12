"""Add newcomer training enrollment and unified activity attempt persistence.

Revision ID: 20260712_1300_092
Revises: 20260707_1200_091
Create Date: 2026-07-12 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_1300_092"
down_revision: str | None = "20260707_1200_091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "newcomer_training_enrollments",
        sa.Column("enrollment_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("path_id", sa.String(length=80), nullable=False),
        sa.Column("path_revision_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_newcomer_training_enrollment_status",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["path_revision_id"],
            ["sales_trainer_asset_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("enrollment_id"),
    )
    op.create_index(
        "ix_newcomer_training_enrollments_learner_id",
        "newcomer_training_enrollments",
        ["learner_id"],
    )
    op.create_index(
        "ix_newcomer_training_enrollments_path_revision_id",
        "newcomer_training_enrollments",
        ["path_revision_id"],
    )
    op.create_index(
        "ix_newcomer_training_enrollments_status",
        "newcomer_training_enrollments",
        ["status"],
    )
    op.create_index(
        "uq_newcomer_training_active_enrollment",
        "newcomer_training_enrollments",
        ["learner_id", "path_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "newcomer_training_activity_attempts",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("enrollment_id", sa.String(length=36), nullable=False),
        sa.Column("path_revision_id", sa.String(length=36), nullable=False),
        sa.Column("activity_id", sa.String(length=80), nullable=False),
        sa.Column("activity_type", sa.String(length=40), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("max_score", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("evidence_type", sa.String(length=50), nullable=True),
        sa.Column("evidence_id", sa.String(length=120), nullable=True),
        sa.Column("client_token", sa.String(length=100), nullable=False),
        sa.Column("activity_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_no >= 1", name="ck_newcomer_training_attempt_no"),
        sa.CheckConstraint(
            "activity_type IN ('lesson', 'quiz', 'audio_assessment', "
            "'realtime_roleplay', 'ai_coach', 'assignment')",
            name="ck_newcomer_training_activity_type",
        ),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'submitted', 'completed', 'failed')",
            name="ck_newcomer_training_attempt_status",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["newcomer_training_enrollments.enrollment_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["path_revision_id"],
            ["sales_trainer_asset_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "enrollment_id",
            "activity_id",
            "attempt_no",
            name="uq_newcomer_training_activity_attempt_no",
        ),
    )
    for column in ("enrollment_id", "path_revision_id", "activity_id", "activity_type", "status"):
        op.create_index(
            f"ix_newcomer_training_activity_attempts_{column}",
            "newcomer_training_activity_attempts",
            [column],
        )
    op.create_index(
        "uq_newcomer_training_attempt_client_token",
        "newcomer_training_activity_attempts",
        ["client_token"],
        unique=True,
    )
    op.create_index(
        "idx_newcomer_training_attempt_evidence",
        "newcomer_training_activity_attempts",
        ["evidence_type", "evidence_id"],
    )


def downgrade() -> None:
    op.drop_table("newcomer_training_activity_attempts")
    op.drop_table("newcomer_training_enrollments")
