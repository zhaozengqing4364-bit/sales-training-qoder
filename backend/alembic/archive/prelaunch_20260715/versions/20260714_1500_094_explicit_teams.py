"""Add explicit teams, memberships, and leader assignments.

Revision ID: 20260714_1500_094
Revises: 20260714_1400_093
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_1500_094"
down_revision: str | None = "20260714_1400_093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("team_id"),
    )
    op.create_index("ix_teams_code", "teams", ["code"], unique=True)
    op.create_index("ix_teams_is_active", "teams", ["is_active"])

    op.create_table(
        "team_memberships",
        sa.Column("membership_id", sa.String(36), nullable=False),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("membership_role", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "membership_role IN ('primary')", name="ck_team_membership_role"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("membership_id"),
    )
    op.create_index("ix_team_memberships_team_id", "team_memberships", ["team_id"])
    op.create_index("ix_team_memberships_user_id", "team_memberships", ["user_id"])
    op.create_index(
        "uq_team_memberships_active_primary_user",
        "team_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "effective_to IS NULL AND membership_role = 'primary'"
        ),
        sqlite_where=sa.text("effective_to IS NULL AND membership_role = 'primary'"),
    )

    op.create_table(
        "team_leader_assignments",
        sa.Column("assignment_id", sa.String(36), nullable=False),
        sa.Column("team_id", sa.String(36), nullable=False),
        sa.Column("leader_user_id", sa.String(36), nullable=False),
        sa.Column("assignment_role", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "assignment_role IN ('primary', 'proxy')",
            name="ck_team_leader_assignment_role",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["leader_user_id"], ["users.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index(
        "ix_team_leader_assignments_team_id", "team_leader_assignments", ["team_id"]
    )
    op.create_index(
        "ix_team_leader_assignments_leader_user_id",
        "team_leader_assignments",
        ["leader_user_id"],
    )
    op.create_index(
        "uq_team_leader_assignments_active_primary_team",
        "team_leader_assignments",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text(
            "effective_to IS NULL AND assignment_role = 'primary'"
        ),
        sqlite_where=sa.text("effective_to IS NULL AND assignment_role = 'primary'"),
    )
    op.create_index(
        "uq_team_leader_assignments_active_role",
        "team_leader_assignments",
        ["team_id", "leader_user_id", "assignment_role"],
        unique=True,
        postgresql_where=sa.text("effective_to IS NULL"),
        sqlite_where=sa.text("effective_to IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("team_leader_assignments")
    op.drop_table("team_memberships")
    op.drop_table("teams")
