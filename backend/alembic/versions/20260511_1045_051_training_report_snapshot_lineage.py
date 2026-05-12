"""add training report snapshot config lineage

Revision ID: 20260511_1045_051
Revises: 20260511_1030_050
Create Date: 2026-05-11 10:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_1045_051"
down_revision: str | None = "20260511_1030_050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_report_snapshots",
        sa.Column("config_bundle_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "training_report_snapshots",
        sa.Column("config_bundle_snapshot", sa.JSON(), nullable=True),
    )
    op.create_foreign_key(
        "fk_training_report_snapshots_config_bundle_id",
        "training_report_snapshots",
        "config_bundles",
        ["config_bundle_id"],
        ["bundle_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_training_report_snapshots_config_bundle_id",
        "training_report_snapshots",
        ["config_bundle_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_report_snapshots_config_bundle_id",
        table_name="training_report_snapshots",
        if_exists=True,
    )
    op.drop_constraint(
        "fk_training_report_snapshots_config_bundle_id",
        "training_report_snapshots",
        type_="foreignkey",
    )
    op.drop_column("training_report_snapshots", "config_bundle_snapshot")
    op.drop_column("training_report_snapshots", "config_bundle_id")
