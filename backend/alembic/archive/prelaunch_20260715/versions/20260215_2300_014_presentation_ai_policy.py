"""Add presentation AI policy table

Revision ID: 20260215_2300_014
Revises: 20260212_0000_013
Create Date: 2026-02-15 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260215_2300_014"
down_revision: Union[str, None] = "20260212_0000_013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "presentation_ai_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("prompt_config", sa.JSON(), nullable=False),
        sa.Column("rule_config", sa.JSON(), nullable=False),
        sa.Column("fallback_config", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "scope_type IN ('global', 'scenario', 'presentation')",
            name="ck_presentation_ai_policy_scope_type",
        ),
        sa.CheckConstraint(
            "((scope_type = 'global' AND scope_id IS NULL) OR "
            "(scope_type IN ('scenario', 'presentation') AND scope_id IS NOT NULL))",
            name="ck_presentation_ai_policy_scope_id",
        ),
        sa.UniqueConstraint(
            "scope_type",
            "scope_id",
            name="uq_presentation_ai_policy_scope",
        ),
    )
    op.create_index(
        "idx_presentation_ai_policy_scope",
        "presentation_ai_policies",
        ["scope_type", "scope_id"],
    )
    op.create_index(
        "idx_presentation_ai_policy_enabled",
        "presentation_ai_policies",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_presentation_ai_policy_enabled",
        table_name="presentation_ai_policies",
    )
    op.drop_index(
        "idx_presentation_ai_policy_scope",
        table_name="presentation_ai_policies",
    )
    op.drop_table("presentation_ai_policies")
