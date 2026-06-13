"""Add phase 2 sales trainer record pagination indexes

Revision ID: 20260612_1400_081_phase2_indexes
Revises: 20260609_1300_080_ai_proactive
Create Date: 2026-06-12 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_1400_081_phase2_indexes"
down_revision: str | None = "20260609_1300_080_ai_proactive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _index_exists(
        "sales_trainer_audio_submissions",
        "idx_sales_trainer_audio_created_id",
    ):
        op.create_index(
            "idx_sales_trainer_audio_created_id",
            "sales_trainer_audio_submissions",
            ["created_at", "submission_id"],
        )
    if not _index_exists(
        "sales_trainer_quiz_attempts",
        "idx_sales_trainer_quiz_attempt_submitted_id",
    ):
        op.create_index(
            "idx_sales_trainer_quiz_attempt_submitted_id",
            "sales_trainer_quiz_attempts",
            ["submitted_at", "attempt_id"],
        )
    if not _index_exists(
        "sales_trainer_ai_coach_sessions",
        "idx_sales_trainer_ai_coach_sessions_created_id",
    ):
        op.create_index(
            "idx_sales_trainer_ai_coach_sessions_created_id",
            "sales_trainer_ai_coach_sessions",
            ["created_at", "session_id"],
        )


def downgrade() -> None:
    for table_name, index_name in (
        (
            "sales_trainer_ai_coach_sessions",
            "idx_sales_trainer_ai_coach_sessions_created_id",
        ),
        (
            "sales_trainer_quiz_attempts",
            "idx_sales_trainer_quiz_attempt_submitted_id",
        ),
        ("sales_trainer_audio_submissions", "idx_sales_trainer_audio_created_id"),
    ):
        if _index_exists(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
