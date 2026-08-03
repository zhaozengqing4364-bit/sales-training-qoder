"""add knowledge base dictionary entries

Revision ID: 20260509_1300_039
Revises: 20260509_1200_038
Create Date: 2026-05-09 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_1300_039"
down_revision: str | None = "20260509_1200_038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_dictionary_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_term", sa.String(length=255), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("term_type", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="95"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_knowledge_dictionary_entry_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_knowledge_dictionary_entry_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_base_id",
            "canonical_term",
            name="uq_knowledge_dictionary_entry_kb_canonical",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "idx_knowledge_dictionary_entries_kb",
        "knowledge_dictionary_entries",
        ["knowledge_base_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_knowledge_dictionary_entries_status",
        "knowledge_dictionary_entries",
        ["status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_knowledge_dictionary_entries_status",
        table_name="knowledge_dictionary_entries",
        if_exists=True,
    )
    op.drop_index(
        "idx_knowledge_dictionary_entries_kb",
        table_name="knowledge_dictionary_entries",
        if_exists=True,
    )
    op.drop_table("knowledge_dictionary_entries", if_exists=True)
