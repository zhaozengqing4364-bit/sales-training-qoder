"""add scoring ruleset governance tables

Revision ID: 20260424_1100_033
Revises: 20260421_0645_032
Create Date: 2026-04-24 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_1100_033"
down_revision: str | None = "20260421_0645_032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoring_rulesets",
        sa.Column("ruleset_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_type", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            "scenario_type IN ('sales', 'presentation')",
            name="ck_scoring_ruleset_scenario_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_scoring_ruleset_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["published_by"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("ruleset_id"),
        sa.UniqueConstraint(
            "scenario_type",
            "version",
            name="uq_scoring_ruleset_scenario_version",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_scoring_rulesets_scenario_type",
        "scoring_rulesets",
        ["scenario_type"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_scoring_rulesets_is_active",
        "scoring_rulesets",
        ["is_active"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_scoring_rulesets_status",
        "scoring_rulesets",
        ["status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_scoring_rulesets_scenario_active",
        "scoring_rulesets",
        ["scenario_type", "is_active"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_scoring_rulesets_scenario_active",
        table_name="scoring_rulesets",
        if_exists=True,
    )
    op.drop_index(
        "ix_scoring_rulesets_status", table_name="scoring_rulesets", if_exists=True
    )
    op.drop_index(
        "ix_scoring_rulesets_is_active", table_name="scoring_rulesets", if_exists=True
    )
    op.drop_index(
        "ix_scoring_rulesets_scenario_type",
        table_name="scoring_rulesets",
        if_exists=True,
    )
    op.drop_table("scoring_rulesets", if_exists=True)
