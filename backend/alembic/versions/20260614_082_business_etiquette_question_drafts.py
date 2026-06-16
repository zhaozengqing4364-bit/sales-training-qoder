"""Add business etiquette AI question drafts

Revision ID: 20260614_082
Revises: 20260612_1400_081_phase2_indexes
Create Date: 2026-06-14 10:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_082"
down_revision: str | None = "20260612_1400_081_phase2_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("sales_trainer_business_etiquette_question_drafts"):
        return

    op.create_table(
        "sales_trainer_business_etiquette_question_drafts",
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("training_pack_key", sa.String(length=80), nullable=False),
        sa.Column("training_pack_revision_id", sa.String(length=36), nullable=True),
        sa.Column("training_pack_revision_no", sa.Integer(), nullable=True),
        sa.Column("learning_content_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_order", sa.Integer(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("question_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_answer", sa.String(length=50), nullable=True),
        sa.Column("correct_answers", sa.JSON(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("capability_keys", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_template_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_contract_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_contract_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_rendered_hash", sa.String(length=64), nullable=False),
        sa.Column("model_config", sa.JSON(), nullable=False),
        sa.Column("raw_generation", sa.JSON(), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "question_type IN ('single_choice', 'multiple_choice', 'short_answer')",
            name="ck_business_etiquette_question_draft_type",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_business_etiquette_question_draft_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'converted')",
            name="ck_business_etiquette_question_draft_status",
        ),
        sa.CheckConstraint(
            "chapter_order >= 1",
            name="ck_business_etiquette_question_draft_chapter_order",
        ),
        sa.ForeignKeyConstraint(
            ["chapter_id"],
            ["learning_chapters.chapter_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["learning_content_id"],
            ["learning_contents.learning_content_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["question_items.question_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["training_pack_revision_id"],
            ["sales_trainer_asset_revisions.revision_id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("draft_id"),
    )
    for index_name, columns in (
        ("ix_sales_trainer_business_etiquette_question_drafts_batch_id", ["batch_id"]),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_chapter_id",
            ["chapter_id"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_difficulty",
            ["difficulty"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_learning_content_id",
            ["learning_content_id"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_prompt_contract_hash",
            ["prompt_contract_hash"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_prompt_template_id",
            ["prompt_template_id"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_question_id",
            ["question_id"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_question_type",
            ["question_type"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_status",
            ["status"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_training_pack_key",
            ["training_pack_key"],
        ),
        (
            "ix_sales_trainer_business_etiquette_question_drafts_revision_id",
            ["training_pack_revision_id"],
        ),
    ):
        op.create_index(
            index_name,
            "sales_trainer_business_etiquette_question_drafts",
            columns,
        )
    op.create_index(
        "idx_business_etiquette_question_drafts_filter",
        "sales_trainer_business_etiquette_question_drafts",
        ["training_pack_key", "status", "question_type", "created_at"],
    )


def downgrade() -> None:
    if _table_exists("sales_trainer_business_etiquette_question_drafts"):
        op.drop_table("sales_trainer_business_etiquette_question_drafts")
