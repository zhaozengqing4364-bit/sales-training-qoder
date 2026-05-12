"""add config bundle lifecycle audit logs

Revision ID: 20260511_0930_047
Revises: 20260511_0915_046
Create Date: 2026-05-11 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0930_047"
down_revision: str | None = "20260511_0915_046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "config_bundle_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bundle_key", sa.String(length=160), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=True),
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
            "action IN ('create_draft', 'validate', 'preview', 'publish', 'rollback', 'disable')",
            name="ck_config_bundle_audit_action",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["config_versions.version_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_bundle_key",
        "config_bundle_audit_logs",
        ["bundle_key"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_version_id",
        "config_bundle_audit_logs",
        ["version_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_action",
        "config_bundle_audit_logs",
        ["action"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_actor_id",
        "config_bundle_audit_logs",
        ["actor_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_trace_id",
        "config_bundle_audit_logs",
        ["trace_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundle_audit_logs_created_at",
        "config_bundle_audit_logs",
        ["created_at"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_config_bundle_audit_key_created",
        "config_bundle_audit_logs",
        ["bundle_key", "created_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_config_bundle_audit_key_created",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_created_at",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_trace_id",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_actor_id",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_action",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_version_id",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_index(
        "ix_config_bundle_audit_logs_bundle_key",
        table_name="config_bundle_audit_logs",
        if_exists=True,
    )
    op.drop_table("config_bundle_audit_logs", if_exists=True)
