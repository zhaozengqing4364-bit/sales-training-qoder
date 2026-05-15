"""add learner learning progress table

Revision ID: 20260515_1000_061
Revises: 20260515_1000_060
Create Date: 2026-05-15 10:00:01.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_1000_061"
down_revision: str | None = "20260515_1000_060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_progress",
        sa.Column("progress_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("learning_content_id", sa.String(36), nullable=False),
        sa.Column("chapter_id", sa.String(36), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["learning_content_id"],
            ["learning_contents.learning_content_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["learning_chapters.chapter_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("progress_id"),
        sa.UniqueConstraint(
            "user_id",
            "learning_content_id",
            "chapter_id",
            name="uq_learning_progress_user_content_chapter",
        ),
    )
    op.create_index(
        "idx_learning_progress_user_content",
        "learning_progress",
        ["user_id", "learning_content_id"],
        unique=False,
    )
    op.create_index(op.f("ix_learning_progress_user_id"), "learning_progress", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_learning_progress_learning_content_id"),
        "learning_progress",
        ["learning_content_id"],
        unique=False,
    )
    op.create_index(op.f("ix_learning_progress_chapter_id"), "learning_progress", ["chapter_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_progress_chapter_id"), table_name="learning_progress")
    op.drop_index(
        op.f("ix_learning_progress_learning_content_id"),
        table_name="learning_progress",
    )
    op.drop_index(op.f("ix_learning_progress_user_id"), table_name="learning_progress")
    op.drop_index("idx_learning_progress_user_content", table_name="learning_progress")
    op.drop_table("learning_progress")
