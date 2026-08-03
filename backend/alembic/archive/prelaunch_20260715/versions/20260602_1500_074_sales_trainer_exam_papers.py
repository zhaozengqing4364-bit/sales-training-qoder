"""add sales trainer exam papers

Revision ID: 20260602_1500_074
Revises: 20260601_1000_073
Create Date: 2026-06-02 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260602_1500_074"
down_revision: str | None = "20260601_1000_073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("sales_trainer_exam_papers"):
        op.create_table(
            "sales_trainer_exam_papers",
            sa.Column("paper_id", sa.String(length=36), nullable=False),
            sa.Column("paper_key", sa.String(length=120), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "module_key",
                sa.String(length=80),
                nullable=False,
                server_default="business_skills",
            ),
            sa.Column("unit_id", sa.String(length=36), nullable=False),
            sa.Column("pass_threshold", sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="draft",
            ),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'published', 'archived')",
                name="ck_sales_trainer_exam_paper_status",
            ),
            sa.CheckConstraint(
                "pass_threshold IS NULL OR pass_threshold >= 0",
                name="ck_sales_trainer_exam_paper_pass_threshold",
            ),
            sa.ForeignKeyConstraint(
                ["unit_id"],
                ["sales_trainer_units.unit_id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("paper_id"),
            sa.UniqueConstraint("paper_key"),
        )
    for index_name, columns in (
        ("ix_sales_trainer_exam_papers_paper_key", ["paper_key"]),
        ("ix_sales_trainer_exam_papers_module_key", ["module_key"]),
        ("ix_sales_trainer_exam_papers_unit_id", ["unit_id"]),
        ("ix_sales_trainer_exam_papers_status", ["status"]),
        (
            "idx_sales_trainer_exam_papers_module_status",
            ["module_key", "status", "updated_at"],
        ),
    ):
        if not _index_exists("sales_trainer_exam_papers", index_name):
            op.create_index(index_name, "sales_trainer_exam_papers", columns)


def downgrade() -> None:
    if _table_exists("sales_trainer_exam_papers"):
        op.drop_table("sales_trainer_exam_papers")
