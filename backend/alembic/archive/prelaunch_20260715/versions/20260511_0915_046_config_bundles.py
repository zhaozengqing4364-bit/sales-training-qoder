"""add config bundle read-only registry tables

Revision ID: 20260511_0915_046
Revises: 20260511_0900_045
Create Date: 2026-05-11 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0915_046"
down_revision: str | None = "20260511_0900_045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "config_bundles",
        sa.Column("bundle_id", sa.String(length=36), nullable=False),
        sa.Column("bundle_key", sa.String(length=160), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("adapter_key", sa.String(length=120), nullable=False),
        sa.Column("legacy_domain", sa.String(length=120), nullable=True),
        sa.Column("read_path", sa.String(length=255), nullable=False),
        sa.Column("admin_entry", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
            "domain IN ('business_rules', 'scoring', 'model', 'knowledge', 'voice_runtime', 'ai_analysis')",
            name="ck_config_bundle_domain",
        ),
        sa.PrimaryKeyConstraint("bundle_id"),
        sa.UniqueConstraint("bundle_key", name="uq_config_bundles_bundle_key"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundles_bundle_key",
        "config_bundles",
        ["bundle_key"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundles_domain",
        "config_bundles",
        ["domain"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundles_adapter_key",
        "config_bundles",
        ["adapter_key"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_bundles_enabled",
        "config_bundles",
        ["enabled"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_config_bundles_domain_enabled",
        "config_bundles",
        ["domain", "enabled"],
        if_not_exists=True,
    )

    op.create_table(
        "config_versions",
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("bundle_id", sa.String(length=36), nullable=False),
        sa.Column("source_config_id", sa.String(length=36), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=True),
        sa.Column("version_label", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'rolled_back', 'archived', 'disabled', 'default')",
            name="ck_config_version_status",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["config_bundles.bundle_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("version_id"),
        sa.UniqueConstraint(
            "bundle_id",
            "source_config_id",
            name="uq_config_versions_bundle_source",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_versions_bundle_id",
        "config_versions",
        ["bundle_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_versions_source_config_id",
        "config_versions",
        ["source_config_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_config_versions_status",
        "config_versions",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_config_versions_bundle_status",
        "config_versions",
        ["bundle_id", "status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_config_versions_bundle_status", table_name="config_versions", if_exists=True)
    op.drop_index("ix_config_versions_status", table_name="config_versions", if_exists=True)
    op.drop_index("ix_config_versions_source_config_id", table_name="config_versions", if_exists=True)
    op.drop_index("ix_config_versions_bundle_id", table_name="config_versions", if_exists=True)
    op.drop_table("config_versions", if_exists=True)

    op.drop_index("idx_config_bundles_domain_enabled", table_name="config_bundles", if_exists=True)
    op.drop_index("ix_config_bundles_enabled", table_name="config_bundles", if_exists=True)
    op.drop_index("ix_config_bundles_adapter_key", table_name="config_bundles", if_exists=True)
    op.drop_index("ix_config_bundles_domain", table_name="config_bundles", if_exists=True)
    op.drop_index("ix_config_bundles_bundle_key", table_name="config_bundles", if_exists=True)
    op.drop_table("config_bundles", if_exists=True)
