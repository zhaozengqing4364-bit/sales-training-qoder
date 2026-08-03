"""add case item and role profile assets

Revision ID: 20260512_1200_055
Revises: 20260512_1100_054
Create Date: 2026-05-12 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_1200_055"
down_revision: str | None = "20260512_1100_054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_items",
        sa.Column("case_item_id", sa.String(length=36), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=False),
        sa.Column("company_profile", sa.Text(), nullable=False),
        sa.Column("customer_role", sa.String(length=120), nullable=False),
        sa.Column("pain_points", sa.JSON(), nullable=False),
        sa.Column("objections", sa.JSON(), nullable=False),
        sa.Column("hidden_information", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("allowed_disclosure_policy", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_case_item_status",
        ),
        sa.PrimaryKeyConstraint("case_item_id"),
    )
    op.create_table(
        "role_profiles",
        sa.Column("role_profile_id", sa.String(length=36), nullable=False),
        sa.Column("role_type", sa.String(length=40), nullable=False),
        sa.Column("role_name", sa.String(length=160), nullable=False),
        sa.Column("persona_ref", sa.String(length=36), nullable=True),
        sa.Column("communication_style", sa.Text(), nullable=False),
        sa.Column("pressure_level", sa.String(length=20), nullable=False),
        sa.Column("knowledge_boundary", sa.JSON(), nullable=False),
        sa.Column("behavior_rules", sa.JSON(), nullable=False),
        sa.Column("voice_style_hint", sa.String(length=300), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role_type IN ('customer')",
            name="ck_role_profile_role_type",
        ),
        sa.CheckConstraint(
            "pressure_level IN ('low', 'medium', 'high')",
            name="ck_role_profile_pressure_level",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_role_profile_status",
        ),
        sa.PrimaryKeyConstraint("role_profile_id"),
    )
    op.create_index("ix_case_items_status", "case_items", ["status"], if_not_exists=True)
    op.create_index(
        "idx_case_items_status_updated",
        "case_items",
        ["status", "updated_at"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_role_profiles_status", "role_profiles", ["status"], if_not_exists=True
    )
    op.create_index(
        "ix_role_profiles_persona_ref",
        "role_profiles",
        ["persona_ref"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_role_profiles_status_updated",
        "role_profiles",
        ["status", "updated_at"],
        if_not_exists=True,
    )
    op.add_column(
        "practice_templates",
        sa.Column("case_item_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "practice_templates",
        sa.Column("role_profile_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_practice_templates_case_item_id",
        "practice_templates",
        ["case_item_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_practice_templates_role_profile_id",
        "practice_templates",
        ["role_profile_id"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_practice_templates_role_profile_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_index(
        "ix_practice_templates_case_item_id",
        table_name="practice_templates",
        if_exists=True,
    )
    op.drop_column("practice_templates", "role_profile_id")
    op.drop_column("practice_templates", "case_item_id")
    op.drop_index(
        "idx_role_profiles_status_updated", table_name="role_profiles", if_exists=True
    )
    op.drop_index(
        "ix_role_profiles_persona_ref", table_name="role_profiles", if_exists=True
    )
    op.drop_index("ix_role_profiles_status", table_name="role_profiles", if_exists=True)
    op.drop_index(
        "idx_case_items_status_updated", table_name="case_items", if_exists=True
    )
    op.drop_index("ix_case_items_status", table_name="case_items", if_exists=True)
    op.drop_table("role_profiles")
    op.drop_table("case_items")
