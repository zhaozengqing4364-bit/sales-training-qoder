"""add supervisor score calibration table

Revision ID: 20260509_1200_038
Revises: 20260509_0900_037
Create Date: 2026-05-09 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_1200_038"
down_revision: str | None = "20260509_0900_037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supervisor_score_calibrations",
        sa.Column("calibration_id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("dimension", sa.String(length=120), nullable=False),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("supervisor_score", sa.Float(), nullable=True),
        sa.Column("calibration_label", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("calibrated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "calibration_label IN ('accurate', 'too_high', 'too_low', 'wrong_reason', 'missing_evidence')",
            name="ck_supervisor_score_calibration_label",
        ),
        sa.CheckConstraint(
            "ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)",
            name="ck_supervisor_score_calibration_ai_score",
        ),
        sa.CheckConstraint(
            "supervisor_score IS NULL OR (supervisor_score >= 0 AND supervisor_score <= 100)",
            name="ck_supervisor_score_calibration_supervisor_score",
        ),
        sa.ForeignKeyConstraint(
            ["calibrated_by_user_id"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["supervisor_reviews.review_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["practice_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("calibration_id"),
        sa.UniqueConstraint(
            "review_id",
            "dimension",
            name="uq_supervisor_score_calibration_review_dimension",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_score_calibrations_review_id",
        "supervisor_score_calibrations",
        ["review_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_score_calibrations_session_id",
        "supervisor_score_calibrations",
        ["session_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_score_calibrations_calibrated_by_user_id",
        "supervisor_score_calibrations",
        ["calibrated_by_user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_supervisor_score_calibrations_session_dimension",
        "supervisor_score_calibrations",
        ["session_id", "dimension"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_supervisor_score_calibrations_session_dimension",
        table_name="supervisor_score_calibrations",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_score_calibrations_calibrated_by_user_id",
        table_name="supervisor_score_calibrations",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_score_calibrations_session_id",
        table_name="supervisor_score_calibrations",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_score_calibrations_review_id",
        table_name="supervisor_score_calibrations",
        if_exists=True,
    )
    op.drop_table("supervisor_score_calibrations", if_exists=True)
