"""add governed business rule config tables

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
        "business_rule_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("default_value", sa.JSON(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("range_or_allowlist", sa.JSON(), nullable=False),
        sa.Column("read_path", sa.String(length=255), nullable=False),
        sa.Column("admin_entry", sa.String(length=255), nullable=False),
        sa.Column("permission", sa.String(length=80), nullable=False),
        sa.Column("audit_policy", sa.Text(), nullable=False),
        sa.Column("fallback_policy", sa.Text(), nullable=False),
        sa.Column("rollback_policy", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived', 'disabled')",
            name="ck_business_rule_config_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", "version", name="uq_business_rule_config_key_version"),
    )
    op.create_index("ix_business_rule_configs_domain", "business_rule_configs", ["domain"])
    op.create_index("ix_business_rule_configs_key", "business_rule_configs", ["key"])
    op.create_index("ix_business_rule_configs_status", "business_rule_configs", ["status"])
    op.create_index("ix_business_rule_configs_enabled", "business_rule_configs", ["enabled"])
    op.create_index(
        "idx_business_rule_configs_key_status_version",
        "business_rule_configs",
        ["key", "status", "version"],
    )
    op.create_index(
        "idx_business_rule_configs_domain_status",
        "business_rule_configs",
        ["domain", "status"],
    )

    op.create_table(
        "business_rule_config_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("config_id", sa.String(length=36), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("config_key", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("before_version", sa.Integer(), nullable=True),
        sa.Column("after_version", sa.Integer(), nullable=True),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('seed_default', 'create_draft', 'update_draft', 'validate', "
            "'preview', 'publish', 'rollback', 'disable', 'delete_draft')",
            name="ck_business_rule_audit_action",
        ),
        sa.ForeignKeyConstraint(
            ["config_id"],
            ["business_rule_configs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_config_id",
        "business_rule_config_audit_logs",
        ["config_id"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_domain",
        "business_rule_config_audit_logs",
        ["domain"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_config_key",
        "business_rule_config_audit_logs",
        ["config_key"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_action",
        "business_rule_config_audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_actor_id",
        "business_rule_config_audit_logs",
        ["actor_id"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_trace_id",
        "business_rule_config_audit_logs",
        ["trace_id"],
    )
    op.create_index(
        "ix_business_rule_config_audit_logs_created_at",
        "business_rule_config_audit_logs",
        ["created_at"],
    )
    op.create_index(
        "idx_business_rule_audit_key_created",
        "business_rule_config_audit_logs",
        ["config_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_business_rule_audit_key_created", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_created_at", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_trace_id", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_actor_id", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_action", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_config_key", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_domain", table_name="business_rule_config_audit_logs")
    op.drop_index("ix_business_rule_config_audit_logs_config_id", table_name="business_rule_config_audit_logs")
    op.drop_table("business_rule_config_audit_logs")

    op.drop_index("idx_business_rule_configs_domain_status", table_name="business_rule_configs")
    op.drop_index("idx_business_rule_configs_key_status_version", table_name="business_rule_configs")
    op.drop_index("ix_business_rule_configs_enabled", table_name="business_rule_configs")
    op.drop_index("ix_business_rule_configs_status", table_name="business_rule_configs")
    op.drop_index("ix_business_rule_configs_key", table_name="business_rule_configs")
    op.drop_index("ix_business_rule_configs_domain", table_name="business_rule_configs")
    op.drop_table("business_rule_configs")
