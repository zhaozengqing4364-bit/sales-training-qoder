"""add learning content lecture tables

Revision ID: 20260515_1000_060
Revises: 20260513_1000_059
Create Date: 2026-05-15 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_1000_060"
down_revision: str | None = "20260513_1000_059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_contents",
        sa.Column("learning_content_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(120), nullable=True),
        sa.Column("source", sa.String(300), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("safety_flagged", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_learning_content_status",
        ),
        sa.PrimaryKeyConstraint("learning_content_id"),
    )
    op.create_index(
        "idx_learning_contents_status_updated",
        "learning_contents",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_contents_status"),
        "learning_contents",
        ["status"],
        unique=False,
    )

    op.create_table(
        "learning_chapters",
        sa.Column("chapter_id", sa.String(36), nullable=False),
        sa.Column("learning_content_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("order_index >= 1", name="ck_learning_chapter_order_index"),
        sa.ForeignKeyConstraint(
            ["learning_content_id"],
            ["learning_contents.learning_content_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chapter_id"),
        sa.UniqueConstraint(
            "learning_content_id",
            "order_index",
            name="uq_learning_chapters_content_order",
        ),
    )
    op.create_index(
        "idx_learning_chapters_content_order",
        "learning_chapters",
        ["learning_content_id", "order_index"],
        unique=False,
    )
    op.create_index(
        op.f("ix_learning_chapters_learning_content_id"),
        "learning_chapters",
        ["learning_content_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_learning_chapters_learning_content_id"),
        table_name="learning_chapters",
    )
    op.drop_index("idx_learning_chapters_content_order", table_name="learning_chapters")
    op.drop_table("learning_chapters")
    op.drop_index(op.f("ix_learning_contents_status"), table_name="learning_contents")
    op.drop_index("idx_learning_contents_status_updated", table_name="learning_contents")
    op.drop_table("learning_contents")
