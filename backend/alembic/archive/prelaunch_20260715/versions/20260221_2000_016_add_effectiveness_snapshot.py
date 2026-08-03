"""Add effectiveness_snapshot to practice_sessions

Revision ID: 20260221_2000_016
Revises: 20260216_0100_015
Create Date: 2026-02-21 20:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260221_2000_016"
down_revision: Union[str, None] = "20260216_0100_015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(column.get("name") == column_name for column in columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "practice_sessions", "effectiveness_snapshot"):
        op.add_column(
            "practice_sessions",
            sa.Column("effectiveness_snapshot", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _column_exists(inspector, "practice_sessions", "effectiveness_snapshot"):
        op.drop_column("practice_sessions", "effectiveness_snapshot")
