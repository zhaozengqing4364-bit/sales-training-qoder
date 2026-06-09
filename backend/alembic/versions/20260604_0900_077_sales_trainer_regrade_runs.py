from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_0900_077"
down_revision: str | None = "20260603_1600_076"
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
    if not _table_exists("sales_trainer_regrade_runs"):
        op.create_table(
            "sales_trainer_regrade_runs",
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("target_type", sa.String(length=40), nullable=False),
            sa.Column("target_id", sa.String(length=36), nullable=False),
            sa.Column("target_revision_id", sa.String(length=36), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="completed",
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("impact_scope", sa.JSON(), nullable=False),
            sa.Column("before_snapshot", sa.JSON(), nullable=False),
            sa.Column("after_snapshot", sa.JSON(), nullable=False),
            sa.Column("trace_id", sa.String(length=100), nullable=False),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "target_type IN ('quiz_attempt', 'audio_submission')",
                name="ck_sales_trainer_regrade_target_type",
            ),
            sa.CheckConstraint(
                "status IN ('completed', 'failed')",
                name="ck_sales_trainer_regrade_status",
            ),
            sa.ForeignKeyConstraint(
                ["target_revision_id"],
                ["sales_trainer_asset_revisions.revision_id"],
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("run_id"),
        )
    for index_name, columns in (
        (
            "ix_sales_trainer_regrade_runs_target_type",
            ["target_type"],
        ),
        (
            "ix_sales_trainer_regrade_runs_target_id",
            ["target_id"],
        ),
        (
            "ix_sales_trainer_regrade_runs_target_revision_id",
            ["target_revision_id"],
        ),
        (
            "ix_sales_trainer_regrade_runs_status",
            ["status"],
        ),
        (
            "ix_sales_trainer_regrade_runs_trace_id",
            ["trace_id"],
        ),
        (
            "idx_sales_trainer_regrade_target",
            ["target_type", "target_id", "created_at"],
        ),
    ):
        if not _index_exists("sales_trainer_regrade_runs", index_name):
            op.create_index(index_name, "sales_trainer_regrade_runs", columns)


def downgrade() -> None:
    if _table_exists("sales_trainer_regrade_runs"):
        op.drop_table("sales_trainer_regrade_runs")
