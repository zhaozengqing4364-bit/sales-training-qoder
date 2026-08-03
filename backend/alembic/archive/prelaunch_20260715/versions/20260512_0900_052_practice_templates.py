"""add practice templates

Revision ID: 20260512_0900_052
Revises: 20260511_1045_051
Create Date: 2026-05-12 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_0900_052"
down_revision: str | None = "20260511_1045_051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_templates",
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario_type", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("persona_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_profile_id", sa.String(length=36), nullable=False),
        sa.Column("voice_mode", sa.String(length=32), nullable=False),
        sa.Column("scoring_ruleset_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_refs", sa.JSON(), nullable=False),
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
            "scenario_type IN ('sales', 'presentation')",
            name="ck_practice_template_scenario_type",
        ),
        sa.CheckConstraint(
            "mode IN ('learning', 'expert_qa', 'examiner', 'customer_roleplay', 'mixed_path')",
            name="ck_practice_template_mode",
        ),
        sa.CheckConstraint(
            "voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_practice_template_voice_mode",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_practice_template_status",
        ),
        sa.PrimaryKeyConstraint("template_id"),
    )
    op.create_index(
        "ix_practice_templates_scenario_type",
        "practice_templates",
        ["scenario_type"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_agent_id",
        "practice_templates",
        ["agent_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_persona_id",
        "practice_templates",
        ["persona_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_runtime_profile_id",
        "practice_templates",
        ["runtime_profile_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_scoring_ruleset_id",
        "practice_templates",
        ["scoring_ruleset_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_status",
        "practice_templates",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_practice_templates_status_updated",
        "practice_templates",
        ["status", "updated_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_practice_templates_status_updated",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_status", table_name="practice_templates", if_exists=True
    )
    op.drop_index(
        "ix_practice_templates_scoring_ruleset_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_runtime_profile_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_persona_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_agent_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_scenario_type",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_table("practice_templates")
