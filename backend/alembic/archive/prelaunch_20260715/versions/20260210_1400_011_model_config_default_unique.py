"""Enforce single default model config per type

Revision ID: 011
Revises: 010
Create Date: 2026-02-10 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # Cleanup historical duplicates to avoid index creation failure.
    rows = connection.execute(
        sa.text(
            """
            SELECT id, model_type
            FROM model_configs
            WHERE is_default = true
            ORDER BY model_type, updated_at DESC, created_at DESC
            """
        )
    ).fetchall()

    kept_types: set[str] = set()
    for row in rows:
        if row.model_type in kept_types:
            connection.execute(
                sa.text("UPDATE model_configs SET is_default = 0 WHERE id = :id"),
                {"id": row.id},
            )
            continue
        kept_types.add(row.model_type)

    op.create_index(
        "uq_model_configs_default_per_type",
        "model_configs",
        ["model_type"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_configs_default_per_type", table_name="model_configs")
