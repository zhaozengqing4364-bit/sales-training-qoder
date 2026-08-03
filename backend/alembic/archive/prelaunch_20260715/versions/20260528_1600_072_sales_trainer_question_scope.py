"""add usage scope for sales trainer question bank

Revision ID: 20260528_1600_072
Revises: 20260528_1500_071
Create Date: 2026-05-28 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_1600_072"
down_revision: str | None = "20260528_1500_071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


QUESTION_CATEGORIES_TABLE = "question_categories"
QUESTION_ITEMS_TABLE = "question_items"
DEFAULT_SALES_TRAINER_CATEGORY_ID = "sales-trainer-default"


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _column_exists(QUESTION_CATEGORIES_TABLE, "usage_scope"):
        op.add_column(
            QUESTION_CATEGORIES_TABLE,
            sa.Column(
                "usage_scope",
                sa.String(length=50),
                nullable=False,
                server_default="general",
            ),
        )
    if not _column_exists(QUESTION_ITEMS_TABLE, "usage_scope"):
        op.add_column(
            QUESTION_ITEMS_TABLE,
            sa.Column(
                "usage_scope",
                sa.String(length=50),
                nullable=False,
                server_default="general",
            ),
        )

    if not _index_exists(QUESTION_CATEGORIES_TABLE, "idx_question_categories_scope_parent"):
        op.create_index(
            "idx_question_categories_scope_parent",
            QUESTION_CATEGORIES_TABLE,
            ["usage_scope", "parent_id", "order_index"],
        )
    if not _index_exists(QUESTION_ITEMS_TABLE, "idx_question_items_scope_status"):
        op.create_index(
            "idx_question_items_scope_status",
            QUESTION_ITEMS_TABLE,
            ["usage_scope", "status"],
        )
    if not _index_exists(QUESTION_ITEMS_TABLE, "idx_question_items_scope_category"):
        op.create_index(
            "idx_question_items_scope_category",
            QUESTION_ITEMS_TABLE,
            ["usage_scope", "category_id"],
        )

    op.execute(
        sa.text(
            """
            INSERT INTO question_categories
                (category_id, parent_id, name, description, usage_scope, order_index, created_at, updated_at)
            SELECT
                :category_id,
                NULL,
                '销售训练题库',
                '销售训练专用题目分类。',
                'sales_trainer',
                1,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM question_categories WHERE category_id = :category_id
            )
            """
        ).bindparams(category_id=DEFAULT_SALES_TRAINER_CATEGORY_ID)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM question_categories WHERE category_id = :category_id"
        ).bindparams(category_id=DEFAULT_SALES_TRAINER_CATEGORY_ID)
    )
    if _index_exists(QUESTION_ITEMS_TABLE, "idx_question_items_scope_category"):
        op.drop_index("idx_question_items_scope_category", table_name=QUESTION_ITEMS_TABLE)
    if _index_exists(QUESTION_ITEMS_TABLE, "idx_question_items_scope_status"):
        op.drop_index("idx_question_items_scope_status", table_name=QUESTION_ITEMS_TABLE)
    if _index_exists(QUESTION_CATEGORIES_TABLE, "idx_question_categories_scope_parent"):
        op.drop_index(
            "idx_question_categories_scope_parent",
            table_name=QUESTION_CATEGORIES_TABLE,
        )
    if _column_exists(QUESTION_ITEMS_TABLE, "usage_scope"):
        op.drop_column(QUESTION_ITEMS_TABLE, "usage_scope")
    if _column_exists(QUESTION_CATEGORIES_TABLE, "usage_scope"):
        op.drop_column(QUESTION_CATEGORIES_TABLE, "usage_scope")
