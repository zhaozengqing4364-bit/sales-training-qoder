"""add evaluation run config binding

Revision ID: 20260511_1000_048
Revises: 20260511_0930_047
Create Date: 2026-05-11 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_1000_048"
down_revision: str | None = "20260511_0930_047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("config_bundle_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("config_version_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_runs_config_bundle_id",
        "evaluation_runs",
        "config_bundles",
        ["config_bundle_id"],
        ["bundle_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evaluation_runs_config_version_id",
        "evaluation_runs",
        "config_versions",
        ["config_version_id"],
        ["version_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_evaluation_runs_config_bundle_id",
        "evaluation_runs",
        ["config_bundle_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_evaluation_runs_config_version_id",
        "evaluation_runs",
        ["config_version_id"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_evaluation_runs_config_binding",
        "evaluation_runs",
        ["config_bundle_id", "config_version_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_evaluation_runs_config_binding",
        table_name="evaluation_runs",
        if_exists=True,
    )
    op.drop_index(
        "ix_evaluation_runs_config_version_id",
        table_name="evaluation_runs",
        if_exists=True,
    )
    op.drop_index(
        "ix_evaluation_runs_config_bundle_id",
        table_name="evaluation_runs",
        if_exists=True,
    )
    op.drop_constraint(
        "fk_evaluation_runs_config_version_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_runs_config_bundle_id",
        "evaluation_runs",
        type_="foreignkey",
    )
    op.drop_column("evaluation_runs", "config_version_id")
    op.drop_column("evaluation_runs", "config_bundle_id")
