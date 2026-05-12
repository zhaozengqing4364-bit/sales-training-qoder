"""add admin action role permissions

Revision ID: 20260511_1030_050
Revises: 20260511_1015_049
Create Date: 2026-05-11 10:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_1030_050"
down_revision: str | None = "20260511_1015_049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("admin", "admin_settings.manage"),
    ("admin", "business_rule.publish"),
    ("admin", "config_audit.read"),
    ("admin", "config_bundle.disable"),
    ("admin", "config_bundle.draft"),
    ("admin", "config_bundle.preview"),
    ("admin", "config_bundle.publish"),
    ("admin", "config_bundle.read"),
    ("admin", "config_bundle.rollback"),
    ("admin", "config_bundle.validate"),
    ("admin", "release_verification.manage"),
    ("admin", "scoring_ruleset.dry_run"),
    ("admin", "scoring_ruleset.manage"),
    ("content_admin", "business_rule.publish"),
    ("content_admin", "config_audit.read"),
    ("content_admin", "config_bundle.disable"),
    ("content_admin", "config_bundle.draft"),
    ("content_admin", "config_bundle.preview"),
    ("content_admin", "config_bundle.publish"),
    ("content_admin", "config_bundle.read"),
    ("content_admin", "config_bundle.rollback"),
    ("content_admin", "config_bundle.validate"),
    ("content_admin", "scoring_ruleset.dry_run"),
    ("content_admin", "scoring_ruleset.manage"),
    ("operations", "business_rule.publish"),
    ("operations", "config_audit.read"),
    ("operations", "config_bundle.preview"),
    ("operations", "config_bundle.publish"),
    ("operations", "config_bundle.read"),
    ("operations", "config_bundle.rollback"),
    ("readonly_auditor", "config_audit.read"),
    ("support", "config_audit.read"),
)


def upgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('user', 'admin', 'support', 'content_admin', 'operations', 'readonly_auditor')",
    )
    op.create_table(
        "admin_role_permissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("permission", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'support', 'content_admin', 'operations', 'readonly_auditor')",
            name="ck_admin_role_permissions_role",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "role",
            "permission",
            name="uq_admin_role_permissions_role_permission",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_admin_role_permissions_role",
        "admin_role_permissions",
        ["role"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_admin_role_permissions_permission",
        "admin_role_permissions",
        ["permission"],
        if_not_exists=True,
    )
    op.create_index(
        "idx_admin_role_permissions_role_permission",
        "admin_role_permissions",
        ["role", "permission"],
        if_not_exists=True,
    )
    permissions_table = sa.table(
        "admin_role_permissions",
        sa.column("id", sa.String(length=36)),
        sa.column("role", sa.String(length=20)),
        sa.column("permission", sa.String(length=80)),
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": f"rbac-{index:03d}", "role": role, "permission": permission}
            for index, (role, permission) in enumerate(ROLE_PERMISSIONS, start=1)
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_admin_role_permissions_role_permission",
        table_name="admin_role_permissions",
        if_exists=True,
    )
    op.drop_index(
        "ix_admin_role_permissions_permission",
        table_name="admin_role_permissions",
        if_exists=True,
    )
    op.drop_index(
        "ix_admin_role_permissions_role",
        table_name="admin_role_permissions",
        if_exists=True,
    )
    op.drop_table("admin_role_permissions", if_exists=True)
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('user', 'admin', 'support')",
    )
