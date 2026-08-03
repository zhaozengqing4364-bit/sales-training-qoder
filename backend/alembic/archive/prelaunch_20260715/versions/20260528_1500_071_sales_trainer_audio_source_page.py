"""repair sales trainer audio columns

Revision ID: 20260528_1500_071
Revises: 20260527_1200_070
Create Date: 2026-05-28 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_1500_071"
down_revision: str | None = "20260527_1200_070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SUBMISSIONS_TABLE = "sales_trainer_audio_submissions"
SCORE_RESULTS_TABLE = "sales_trainer_audio_score_results"


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _column_exists(SUBMISSIONS_TABLE, "source_page"):
        op.add_column(
            SUBMISSIONS_TABLE,
            sa.Column("source_page", sa.String(length=100), nullable=True),
        )
    if not _column_exists(SCORE_RESULTS_TABLE, "transcript_snapshot"):
        op.add_column(
            SCORE_RESULTS_TABLE,
            sa.Column("transcript_snapshot", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists(SCORE_RESULTS_TABLE, "transcript_snapshot"):
        op.drop_column(SCORE_RESULTS_TABLE, "transcript_snapshot")
    if _column_exists(SUBMISSIONS_TABLE, "source_page"):
        op.drop_column(SUBMISSIONS_TABLE, "source_page")
