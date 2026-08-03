"""add examiner agents

Revision ID: 20260516_1200_066
Revises: 20260516_1100_065
Create Date: 2026-05-16 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_1200_066"
down_revision: str | None = "20260516_1100_065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "examiner_agents",
        sa.Column("examiner_agent_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("question_source_ids", sa.JSON(), nullable=False),
        sa.Column("learner_level_strategy", sa.JSON(), nullable=False),
        sa.Column("scoring_policy_id", sa.String(length=36), nullable=False),
        sa.Column("timeout_config", sa.JSON(), nullable=False),
        sa.Column("safety_config", sa.JSON(), nullable=False),
        sa.Column("prompt_config", sa.JSON(), nullable=False),
        sa.Column("simulation_config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_examiner_agent_status",
        ),
        sa.PrimaryKeyConstraint("examiner_agent_id"),
    )
    op.create_index(
        "idx_examiner_agents_status_updated",
        "examiner_agents",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_examiner_agents_scoring_policy_id"),
        "examiner_agents",
        ["scoring_policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_examiner_agents_status"),
        "examiner_agents",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_examiner_agents_status"), table_name="examiner_agents")
    op.drop_index(
        op.f("ix_examiner_agents_scoring_policy_id"), table_name="examiner_agents"
    )
    op.drop_index("idx_examiner_agents_status_updated", table_name="examiner_agents")
    op.drop_table("examiner_agents")
