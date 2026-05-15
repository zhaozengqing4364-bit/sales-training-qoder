"""add test bank category and question tables

Revision ID: 20260515_1100_062
Revises: 20260515_1000_061
Create Date: 2026-05-15 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_1100_062"
down_revision: str | None = "20260515_1000_061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_categories",
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("order_index >= 1", name="ck_question_category_order_index"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["question_categories.category_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("category_id"),
    )
    op.create_index(
        "idx_question_categories_parent_order",
        "question_categories",
        ["parent_id", "order_index"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_categories_parent_id"),
        "question_categories",
        ["parent_id"],
        unique=False,
    )

    op.create_table(
        "question_items",
        sa.Column("question_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=True),
        sa.Column("scoring_criteria", sa.JSON(), nullable=False),
        sa.Column("scoring_dimensions", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("safety_flagged", sa.Boolean(), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_question_item_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_question_item_status",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["question_categories.category_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("question_id"),
    )
    op.create_index(
        "idx_question_items_category_status",
        "question_items",
        ["category_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_question_items_status_updated",
        "question_items",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_items_category_id"),
        "question_items",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_items_department"),
        "question_items",
        ["department"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_items_difficulty"),
        "question_items",
        ["difficulty"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_items_status"),
        "question_items",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_question_items_status"), table_name="question_items")
    op.drop_index(op.f("ix_question_items_difficulty"), table_name="question_items")
    op.drop_index(op.f("ix_question_items_department"), table_name="question_items")
    op.drop_index(op.f("ix_question_items_category_id"), table_name="question_items")
    op.drop_index("idx_question_items_status_updated", table_name="question_items")
    op.drop_index("idx_question_items_category_status", table_name="question_items")
    op.drop_table("question_items")
    op.drop_index(
        op.f("ix_question_categories_parent_id"),
        table_name="question_categories",
    )
    op.drop_index(
        "idx_question_categories_parent_order",
        table_name="question_categories",
    )
    op.drop_table("question_categories")
