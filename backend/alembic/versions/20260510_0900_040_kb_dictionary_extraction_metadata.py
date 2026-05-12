"""add kb dictionary extraction metadata

Revision ID: 20260510_0900_040
Revises: 20260509_1300_039
Create Date: 2026-05-10 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0900_040"
down_revision: str | None = "20260509_1300_039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_dictionary_entries",
        sa.Column("extraction_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_dictionary_entries", "extraction_metadata")
