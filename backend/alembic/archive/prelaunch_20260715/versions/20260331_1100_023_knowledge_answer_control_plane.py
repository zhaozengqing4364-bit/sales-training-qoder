"""Add knowledge answer control plane and audit tables.

Revision ID: 20260331_1100_023
Revises: 20260328_1000_022
Create Date: 2026-03-31 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260331_1100_023"
down_revision: Union[str, None] = "20260328_1000_022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_config_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_knowledge_config_version_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_name"),
    )
    op.create_index(
        "idx_knowledge_config_versions_status",
        "knowledge_config_versions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "knowledge_query_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=False),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rewrite_strategy", sa.String(length=50), nullable=False),
        sa.Column("max_rewrite_queries", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "stop_after_first_success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_query_profile_version_key",
        ),
    )
    op.create_index(
        "idx_knowledge_query_profiles_profile_key",
        "knowledge_query_profiles",
        ["profile_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_query_profiles_config_version_id"),
        "knowledge_query_profiles",
        ["config_version_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_intent_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=False),
        sa.Column("intent_key", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("match_type", sa.String(length=50), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_knowledge_intent_rules_intent_key",
        "knowledge_intent_rules",
        ["intent_key"],
        unique=False,
    )
    op.create_index(
        "idx_knowledge_intent_rules_priority",
        "knowledge_intent_rules",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_intent_rules_config_version_id"),
        "knowledge_intent_rules",
        ["config_version_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_entity_aliases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_entity", sa.String(length=255), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_knowledge_entity_alias_confidence",
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "config_version_id",
            "alias",
            name="uq_knowledge_entity_alias_version_alias",
        ),
    )
    op.create_index(
        "idx_knowledge_entity_aliases_canonical_entity",
        "knowledge_entity_aliases",
        ["canonical_entity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_entity_aliases_config_version_id"),
        "knowledge_entity_aliases",
        ["config_version_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_ranking_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=False),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("title_exact_boost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("entity_match_boost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("doc_type_weights_json", sa.JSON(), nullable=False),
        sa.Column("section_weights_json", sa.JSON(), nullable=False),
        sa.Column("min_pass_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("min_pass_score_keyword", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_ranking_profile_version_key",
        ),
    )
    op.create_index(
        "idx_knowledge_ranking_profiles_profile_key",
        "knowledge_ranking_profiles",
        ["profile_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_ranking_profiles_config_version_id"),
        "knowledge_ranking_profiles",
        ["config_version_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_answerability_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=False),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("required_slots_json", sa.JSON(), nullable=False),
        sa.Column("optional_slots_json", sa.JSON(), nullable=False),
        sa.Column("sufficient_threshold", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("partial_threshold", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "config_version_id",
            "profile_key",
            name="uq_knowledge_answerability_profile_version_key",
        ),
    )
    op.create_index(
        "idx_knowledge_answerability_profiles_profile_key",
        "knowledge_answerability_profiles",
        ["profile_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_answerability_profiles_config_version_id"),
        "knowledge_answerability_profiles",
        ["config_version_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_answer_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("config_version_id", sa.String(length=36), nullable=True),
        sa.Column("entrypoint", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("answerability", sa.String(length=20), nullable=False, server_default="insufficient"),
        sa.Column("final_status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("blocked_reason", sa.String(length=100), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("retrieval_summary_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "answerability IN ('sufficient', 'partial', 'insufficient', 'blocked')",
            name="ck_knowledge_answer_run_answerability",
        ),
        sa.CheckConstraint(
            "final_status IN ('completed', 'blocked', 'failed')",
            name="ck_knowledge_answer_run_final_status",
        ),
        sa.ForeignKeyConstraint(["config_version_id"], ["knowledge_config_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["practice_sessions.session_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_knowledge_answer_runs_session_created",
        "knowledge_answer_runs",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_answer_runs_config_version_id"),
        "knowledge_answer_runs",
        ["config_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_answer_runs_session_id"),
        "knowledge_answer_runs",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_answer_run_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("answer_run_id", sa.String(length=36), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed', 'skipped')",
            name="ck_knowledge_answer_run_step_status",
        ),
        sa.ForeignKeyConstraint(["answer_run_id"], ["knowledge_answer_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "answer_run_id",
            "step_order",
            name="uq_knowledge_answer_run_steps_order",
        ),
    )
    op.create_index(
        "idx_knowledge_answer_run_steps_run",
        "knowledge_answer_run_steps",
        ["answer_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_answer_run_steps_answer_run_id"),
        "knowledge_answer_run_steps",
        ["answer_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_answer_run_steps_answer_run_id"),
        table_name="knowledge_answer_run_steps",
    )
    op.drop_index(
        "idx_knowledge_answer_run_steps_run",
        table_name="knowledge_answer_run_steps",
    )
    op.drop_table("knowledge_answer_run_steps")

    op.drop_index(
        op.f("ix_knowledge_answer_runs_session_id"),
        table_name="knowledge_answer_runs",
    )
    op.drop_index(
        op.f("ix_knowledge_answer_runs_config_version_id"),
        table_name="knowledge_answer_runs",
    )
    op.drop_index(
        "idx_knowledge_answer_runs_session_created",
        table_name="knowledge_answer_runs",
    )
    op.drop_table("knowledge_answer_runs")

    op.drop_index(
        op.f("ix_knowledge_answerability_profiles_config_version_id"),
        table_name="knowledge_answerability_profiles",
    )
    op.drop_index(
        "idx_knowledge_answerability_profiles_profile_key",
        table_name="knowledge_answerability_profiles",
    )
    op.drop_table("knowledge_answerability_profiles")

    op.drop_index(
        op.f("ix_knowledge_ranking_profiles_config_version_id"),
        table_name="knowledge_ranking_profiles",
    )
    op.drop_index(
        "idx_knowledge_ranking_profiles_profile_key",
        table_name="knowledge_ranking_profiles",
    )
    op.drop_table("knowledge_ranking_profiles")

    op.drop_index(
        op.f("ix_knowledge_entity_aliases_config_version_id"),
        table_name="knowledge_entity_aliases",
    )
    op.drop_index(
        "idx_knowledge_entity_aliases_canonical_entity",
        table_name="knowledge_entity_aliases",
    )
    op.drop_table("knowledge_entity_aliases")

    op.drop_index(
        op.f("ix_knowledge_intent_rules_config_version_id"),
        table_name="knowledge_intent_rules",
    )
    op.drop_index(
        "idx_knowledge_intent_rules_priority",
        table_name="knowledge_intent_rules",
    )
    op.drop_index(
        "idx_knowledge_intent_rules_intent_key",
        table_name="knowledge_intent_rules",
    )
    op.drop_table("knowledge_intent_rules")

    op.drop_index(
        op.f("ix_knowledge_query_profiles_config_version_id"),
        table_name="knowledge_query_profiles",
    )
    op.drop_index(
        "idx_knowledge_query_profiles_profile_key",
        table_name="knowledge_query_profiles",
    )
    op.drop_table("knowledge_query_profiles")

    op.drop_index(
        "idx_knowledge_config_versions_status",
        table_name="knowledge_config_versions",
    )
    op.drop_table("knowledge_config_versions")
