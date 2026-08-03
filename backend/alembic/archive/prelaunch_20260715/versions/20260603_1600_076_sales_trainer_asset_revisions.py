"""add sales trainer asset revisions

Revision ID: 20260603_1600_076
Revises: 20260603_1000_075
Create Date: 2026-06-03 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260603_1600_076"
down_revision: str | None = "20260603_1000_075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("sales_trainer_asset_revisions"):
        op.create_table(
            "sales_trainer_asset_revisions",
            sa.Column("revision_id", sa.String(length=36), nullable=False),
            sa.Column("resource_type", sa.String(length=80), nullable=False),
            sa.Column("logical_id", sa.String(length=120), nullable=False),
            sa.Column("revision_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="working"),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("payload_hash", sa.String(length=128), nullable=False),
            sa.Column(
                "change_class",
                sa.String(length=40),
                nullable=False,
                server_default="semantic",
            ),
            sa.Column("source_revision_id", sa.String(length=36), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(length=100), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("published_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('working', 'published', 'archived')",
                name="ck_sales_trainer_asset_revision_status",
            ),
            sa.CheckConstraint(
                "change_class IN ('non_semantic', 'semantic', 'binding', 'scoring_high_risk')",
                name="ck_sales_trainer_asset_revision_change_class",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["published_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(
                ["source_revision_id"],
                ["sales_trainer_asset_revisions.revision_id"],
            ),
            sa.PrimaryKeyConstraint("revision_id"),
            sa.UniqueConstraint(
                "resource_type",
                "logical_id",
                "revision_no",
                name="uq_sales_trainer_asset_revision_no",
            ),
        )
    if not _table_exists("sales_trainer_asset_active_revisions"):
        op.create_table(
            "sales_trainer_asset_active_revisions",
            sa.Column("active_ref_id", sa.String(length=36), nullable=False),
            sa.Column("resource_type", sa.String(length=80), nullable=False),
            sa.Column("logical_id", sa.String(length=120), nullable=False),
            sa.Column("active_revision_id", sa.String(length=36), nullable=False),
            sa.Column("activated_by", sa.String(length=36), nullable=True),
            sa.Column("activation_reason", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(length=100), nullable=True),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["active_revision_id"],
                ["sales_trainer_asset_revisions.revision_id"],
            ),
            sa.ForeignKeyConstraint(["activated_by"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("active_ref_id"),
            sa.UniqueConstraint(
                "resource_type",
                "logical_id",
                name="uq_sales_trainer_asset_active_ref",
            ),
        )
    for index_name, table_name, columns in (
        (
            "idx_sales_trainer_asset_revisions_lookup",
            "sales_trainer_asset_revisions",
            ["resource_type", "logical_id", "status", "revision_no"],
        ),
        (
            "idx_sales_trainer_asset_active_lookup",
            "sales_trainer_asset_active_revisions",
            ["resource_type", "logical_id"],
        ),
    ):
        if not _index_exists(table_name, index_name):
            op.create_index(index_name, table_name, columns)
    if not _column_exists("sales_trainer_quiz_attempts", "paper_revision_id"):
        op.add_column(
            "sales_trainer_quiz_attempts",
            sa.Column("paper_revision_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_sales_trainer_quiz_attempts_paper_revision",
            "sales_trainer_quiz_attempts",
            "sales_trainer_asset_revisions",
            ["paper_revision_id"],
            ["revision_id"],
        )
        op.create_index(
            "ix_sales_trainer_quiz_attempts_paper_revision_id",
            "sales_trainer_quiz_attempts",
            ["paper_revision_id"],
        )


def downgrade() -> None:
    if _column_exists("sales_trainer_quiz_attempts", "paper_revision_id"):
        op.drop_index(
            "ix_sales_trainer_quiz_attempts_paper_revision_id",
            table_name="sales_trainer_quiz_attempts",
        )
        op.drop_constraint(
            "fk_sales_trainer_quiz_attempts_paper_revision",
            "sales_trainer_quiz_attempts",
            type_="foreignkey",
        )
        op.drop_column("sales_trainer_quiz_attempts", "paper_revision_id")
    if _table_exists("sales_trainer_asset_active_revisions"):
        op.drop_table("sales_trainer_asset_active_revisions")
    if _table_exists("sales_trainer_asset_revisions"):
        op.drop_table("sales_trainer_asset_revisions")
