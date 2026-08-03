"""add learner profile and runtime bindings

Revision ID: 20260516_1000_064
Revises: 20260516_0900_063
Create Date: 2026-05-16 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_1000_064"
down_revision: str | None = "20260516_0900_063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "practice_templates",
        sa.Column("learning_content_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "practice_templates",
        sa.Column("examiner_agent_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "practice_templates",
        sa.Column("target_learner_level", sa.String(20), nullable=True),
    )
    op.add_column(
        "practice_templates",
        sa.Column("timeout_config", sa.JSON(), nullable=True),
    )
    op.create_index(
        op.f("ix_practice_templates_learning_content_id"),
        "practice_templates",
        ["learning_content_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_templates_examiner_agent_id"),
        "practice_templates",
        ["examiner_agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_practice_templates_target_learner_level"),
        "practice_templates",
        ["target_learner_level"],
        unique=False,
    )

    op.create_table(
        "learner_profiles",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("self_assessed_level", sa.String(20), nullable=True),
        sa.Column("admin_overridden_level", sa.String(20), nullable=True),
        sa.Column("effective_level", sa.String(20), nullable=False),
        sa.Column("self_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overridden_by", sa.String(36), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(self_assessed_level IS NULL OR self_assessed_level IN ('conservative', 'beginner', 'intermediate', 'advanced'))",
            name="ck_learner_profile_self_assessed_level",
        ),
        sa.CheckConstraint(
            "(admin_overridden_level IS NULL OR admin_overridden_level IN ('conservative', 'beginner', 'intermediate', 'advanced'))",
            name="ck_learner_profile_admin_overridden_level",
        ),
        sa.CheckConstraint(
            "effective_level IN ('conservative', 'beginner', 'intermediate', 'advanced')",
            name="ck_learner_profile_effective_level",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "idx_learner_profiles_effective_level",
        "learner_profiles",
        ["effective_level"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_learner_profiles_effective_level", table_name="learner_profiles")
    op.drop_table("learner_profiles")
    op.drop_index(
        op.f("ix_practice_templates_target_learner_level"),
        table_name="practice_templates",
    )
    op.drop_index(
        op.f("ix_practice_templates_examiner_agent_id"),
        table_name="practice_templates",
    )
    op.drop_index(
        op.f("ix_practice_templates_learning_content_id"),
        table_name="practice_templates",
    )
    op.drop_column("practice_templates", "timeout_config")
    op.drop_column("practice_templates", "target_learner_level")
    op.drop_column("practice_templates", "examiner_agent_id")
    op.drop_column("practice_templates", "learning_content_id")
