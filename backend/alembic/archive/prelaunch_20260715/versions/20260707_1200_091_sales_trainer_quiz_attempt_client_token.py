"""Add client_token idempotency column to sales_trainer_quiz_attempts.

Revision ID: 20260707_1200_091
Revises: 20260706_1200_090
Create Date: 2026-07-07 12:00:00.000000

向做题提交表加入 client_token 幂等键：
- 列 nullable，向后兼容旧数据与无 token 提交；
- 部分唯一索引（WHERE client_token IS NOT NULL）保证同一 token 重复提交
  只生成一条 attempt，避免重复判分。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260707_1200_091"
down_revision: str | None = "20260706_1200_090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "sales_trainer_quiz_attempts"
_COLUMN_NAME = "client_token"
_UNIQUE_INDEX_NAME = "uq_sales_trainer_quiz_attempt_client_token"


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        col["name"] for col in inspect(bind).get_columns(_TABLE_NAME)
    }
    if _COLUMN_NAME not in existing_columns:
        op.add_column(
            _TABLE_NAME,
            sa.Column(_COLUMN_NAME, sa.String(length=100), nullable=True),
        )

    existing_indexes = {
        item.get("name") for item in inspect(bind).get_indexes(_TABLE_NAME)
    }
    if _UNIQUE_INDEX_NAME not in existing_indexes:
        # 部分唯一索引：仅当 client_token 非空时强制唯一，兼容旧数据与无 token 提交。
        op.create_index(
            _UNIQUE_INDEX_NAME,
            _TABLE_NAME,
            [_COLUMN_NAME],
            unique=True,
            postgresql_where=sa.text(f"{_COLUMN_NAME} IS NOT NULL"),
        )


def downgrade() -> None:
    existing_indexes = {
        item.get("name") for item in inspect(op.get_bind()).get_indexes(_TABLE_NAME)
    }
    if _UNIQUE_INDEX_NAME in existing_indexes:
        op.drop_index(_UNIQUE_INDEX_NAME, table_name=_TABLE_NAME)

    existing_columns = {
        col["name"] for col in inspect(op.get_bind()).get_columns(_TABLE_NAME)
    }
    if _COLUMN_NAME in existing_columns:
        op.drop_column(_TABLE_NAME, _COLUMN_NAME)
