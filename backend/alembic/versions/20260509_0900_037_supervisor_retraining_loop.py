"""add supervisor review and retraining task tables

Revision ID: 20260509_0900_037
Revises: 20260501_0400_036
Create Date: 2026-05-09 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0900_037"
down_revision: str | None = "20260501_0400_036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supervisor_reviews",
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("trainee_user_id", sa.String(length=36), nullable=False),
        sa.Column("supervisor_user_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("readiness_status", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "required_retraining",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
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
            "decision IN ('pending', 'approved', 'rejected', 'needs_retraining')",
            name="ck_supervisor_review_decision",
        ),
        sa.CheckConstraint(
            "readiness_status IN ('not_ready', 'shadow_only', 'ready_for_trial', 'approved')",
            name="ck_supervisor_review_readiness_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["practice_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supervisor_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trainee_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("session_id", name="uq_supervisor_review_session"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_reviews_session_id",
        "supervisor_reviews",
        ["session_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_reviews_trainee_user_id",
        "supervisor_reviews",
        ["trainee_user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_reviews_supervisor_user_id",
        "supervisor_reviews",
        ["supervisor_user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_supervisor_reviews_decision",
        "supervisor_reviews",
        ["decision"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_supervisor_reviews_trainee_decision",
        "supervisor_reviews",
        ["trainee_user_id", "decision"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_supervisor_reviews_supervisor_created",
        "supervisor_reviews",
        ["supervisor_user_id", "created_at"],
        if_not_exists=True,
    )

    op.create_table(
        "retraining_tasks",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_session_id", sa.String(length=36), nullable=False),
        sa.Column("source_review_id", sa.String(length=36), nullable=False),
        sa.Column("skill_dimension", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completed_session_id", sa.String(length=36), nullable=True),
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
            "status IN ('todo', 'in_progress', 'completed', 'cancelled')",
            name="ck_retraining_task_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_session_id"],
            ["practice_sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_review_id"],
            ["supervisor_reviews.review_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["completed_session_id"],
            ["practice_sessions.session_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("task_id"),
        sa.UniqueConstraint(
            "source_review_id",
            "skill_dimension",
            name="uq_retraining_task_review_dimension",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_retraining_tasks_user_id",
        "retraining_tasks",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_retraining_tasks_source_session_id",
        "retraining_tasks",
        ["source_session_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_retraining_tasks_source_review_id",
        "retraining_tasks",
        ["source_review_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_retraining_tasks_status",
        "retraining_tasks",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_retraining_tasks_completed_session_id",
        "retraining_tasks",
        ["completed_session_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_retraining_tasks_user_status",
        "retraining_tasks",
        ["user_id", "status"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_retraining_tasks_source_completed",
        "retraining_tasks",
        ["source_session_id", "completed_session_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_retraining_tasks_source_completed",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "idx_retraining_tasks_user_status",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_completed_session_id",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_status",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_source_review_id",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_source_session_id",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_index(
        "ix_retraining_tasks_user_id",
        table_name="retraining_tasks",
        if_exists=True,
    )
    op.drop_table("retraining_tasks", if_exists=True)

    op.drop_index(
        "idx_supervisor_reviews_supervisor_created",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_index(
        "idx_supervisor_reviews_trainee_decision",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_reviews_decision",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_reviews_supervisor_user_id",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_reviews_trainee_user_id",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_index(
        "ix_supervisor_reviews_session_id",
        table_name="supervisor_reviews",
        if_exists=True,
    )
    op.drop_table("supervisor_reviews", if_exists=True)
