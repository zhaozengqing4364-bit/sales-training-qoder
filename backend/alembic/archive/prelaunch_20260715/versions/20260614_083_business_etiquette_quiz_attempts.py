"""Add business etiquette unit quiz attempts

Revision ID: 20260614_083
Revises: 20260614_082
Create Date: 2026-06-14 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_083"
down_revision: str | None = "20260614_082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("sales_trainer_business_etiquette_quiz_attempts"):
        return

    op.create_table(
        "sales_trainer_business_etiquette_quiz_attempts",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("training_pack_key", sa.String(length=80), nullable=False),
        sa.Column("learning_unit_key", sa.String(length=80), nullable=False),
        sa.Column("learning_unit_title", sa.String(length=120), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("path_revision_id", sa.String(length=36), nullable=True),
        sa.Column("path_revision_no", sa.Integer(), nullable=True),
        sa.Column("training_pack_revision_id", sa.String(length=36), nullable=True),
        sa.Column("training_pack_revision_no", sa.Integer(), nullable=True),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("question_snapshots", sa.JSON(), nullable=False),
        sa.Column("answers_snapshot", sa.JSON(), nullable=False),
        sa.Column("capability_scores", sa.JSON(), nullable=False),
        sa.Column("weak_capability_keys", sa.JSON(), nullable=False),
        sa.Column("recommended_chapter_orders", sa.JSON(), nullable=False),
        sa.Column("total_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("max_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('submitted', 'scored', 'failed')",
            name="ck_business_etiquette_quiz_attempt_status",
        ),
        sa.ForeignKeyConstraint(
            ["path_revision_id"],
            ["sales_trainer_asset_revisions.revision_id"],
        ),
        sa.ForeignKeyConstraint(
            ["training_pack_revision_id"],
            ["sales_trainer_asset_revisions.revision_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    for index_name, columns in (
        (
            "ix_business_etiquette_quiz_attempt_training_pack_key",
            ["training_pack_key"],
        ),
        (
            "ix_business_etiquette_quiz_attempt_learning_unit_key",
            ["learning_unit_key"],
        ),
        ("ix_business_etiquette_quiz_attempt_user_id", ["user_id"]),
        ("ix_business_etiquette_quiz_attempt_path_revision_id", ["path_revision_id"]),
        (
            "ix_business_etiquette_quiz_attempt_pack_revision_id",
            ["training_pack_revision_id"],
        ),
    ):
        op.create_index(
            index_name,
            "sales_trainer_business_etiquette_quiz_attempts",
            columns,
        )
    op.create_index(
        "idx_business_etiquette_quiz_attempt_user_unit",
        "sales_trainer_business_etiquette_quiz_attempts",
        ["user_id", "learning_unit_key", "submitted_at"],
    )


def downgrade() -> None:
    if _table_exists("sales_trainer_business_etiquette_quiz_attempts"):
        op.drop_table("sales_trainer_business_etiquette_quiz_attempts")
