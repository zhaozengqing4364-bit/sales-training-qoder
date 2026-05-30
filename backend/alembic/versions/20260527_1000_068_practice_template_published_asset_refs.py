"""add practice template published asset refs

Revision ID: 20260527_1000_068
Revises: 20260518_0900_067
Create Date: 2026-05-27 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_1000_068"
down_revision: str | None = "20260518_0900_067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _published_asset_refs_column() -> sa.Column:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.Column(
            "published_asset_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        )
    return sa.Column(
        "published_asset_refs",
        sa.JSON(),
        nullable=False,
        server_default=sa.text("'{}'"),
    )


def upgrade() -> None:
    op.add_column(
        "practice_templates",
        sa.Column("situation_pack_code", sa.String(length=60), nullable=True),
    )
    op.add_column("practice_templates", _published_asset_refs_column())


def downgrade() -> None:
    op.drop_column("practice_templates", "published_asset_refs")
    op.drop_column("practice_templates", "situation_pack_code")
