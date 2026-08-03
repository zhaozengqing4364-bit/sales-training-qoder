"""add situation packs head projection table

Revision ID: 20260527_1100_069
Revises: 20260527_1000_068
Create Date: 2026-05-27 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_1100_069"
down_revision: str | None = "20260527_1000_068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _json_object_default() -> sa.TextClause:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def _json_array_default(value: str) -> sa.TextClause:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return sa.text(f"'{value}'::jsonb")
    return sa.text(f"'{value}'")


def upgrade() -> None:
    json_type = _json_type()
    op.create_table(
        "situation_packs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "version",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
        sa.Column("content_hash", sa.String(length=80), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "relationship_context",
            json_type,
            nullable=False,
            server_default=_json_object_default(),
        ),
        sa.Column(
            "visible_information_scope",
            json_type,
            nullable=False,
            server_default=_json_object_default(),
        ),
        sa.Column(
            "forbidden_claim_patterns",
            json_type,
            nullable=False,
            server_default=_json_array_default("[]"),
        ),
        sa.Column(
            "forbidden_topic_codes",
            json_type,
            nullable=False,
            server_default=_json_array_default("[]"),
        ),
        sa.Column(
            "forbidden_stage_codes",
            json_type,
            nullable=False,
            server_default=_json_array_default("[]"),
        ),
        sa.Column(
            "conflict_response_strategy",
            sa.String(length=40),
            nullable=True,
            server_default=sa.text("'neutral_clarification'"),
        ),
        sa.Column(
            "behavior_rules_for_prompt_only",
            json_type,
            nullable=False,
            server_default=_json_array_default("[]"),
        ),
        sa.Column(
            "disclosure_policy",
            json_type,
            nullable=False,
            server_default=_json_object_default(),
        ),
        sa.Column(
            "runtime_violation_policy",
            json_type,
            nullable=False,
            server_default=_json_object_default(),
        ),
        sa.Column(
            "compatible_practice_modes",
            json_type,
            nullable=False,
            server_default=_json_array_default('["customer_roleplay"]'),
        ),
        sa.Column(
            "compatible_scenario_types",
            json_type,
            nullable=False,
            server_default=_json_array_default('["sales"]'),
        ),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
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
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_situation_pack_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_situation_packs_code"),
    )
    op.create_index(
        "idx_situation_packs_status",
        "situation_packs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_situation_packs_code",
        "situation_packs",
        ["code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_situation_packs_code", table_name="situation_packs")
    op.drop_index("idx_situation_packs_status", table_name="situation_packs")
    op.drop_table("situation_packs")
