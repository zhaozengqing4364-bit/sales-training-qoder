"""add growth infrastructure tables

Revision ID: 20260421_0645_032
Revises: 20260421_0630_031
Create Date: 2026-04-21 06:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260421_0645_032"
down_revision: str | None = "20260421_0630_031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "achievements",
        sa.Column("achievement_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon_key", sa.String(length=60), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("achievement_id"),
        sa.UniqueConstraint("code"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_achievements_code",
        "achievements",
        ["code"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_achievements_enabled",
        "achievements",
        ["enabled"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("action_label", sa.String(length=80), nullable=True),
        sa.Column("action_path", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=160), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('system', 'tip', 'reminder', 'achievement', 'ai_coach')",
            name="ck_notification_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_type",
        "notifications",
        ["type"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_source",
        "notifications",
        ["source"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_expires_at",
        "notifications",
        ["expires_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_notifications_user_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "user_goals",
        sa.Column("goal_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_type", sa.String(length=40), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            "goal_type IN ('weekly_sessions', 'monthly_presentations')",
            name="ck_user_goal_type",
        ),
        sa.CheckConstraint(
            "period IN ('weekly', 'monthly')", name="ck_user_goal_period"
        ),
        sa.CheckConstraint("target_count > 0", name="ck_user_goal_target_positive"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("goal_id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_goals_user_id",
        "user_goals",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_goals_is_active",
        "user_goals",
        ["is_active"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_user_goals_user_active",
        "user_goals",
        ["user_id", "is_active"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("achievement_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["achievement_id"], ["achievements.achievement_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["practice_sessions.session_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "achievement_id", name="uq_user_achievements_user_achievement"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_achievements_user_id",
        "user_achievements",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_achievements_achievement_id",
        "user_achievements",
        ["achievement_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_achievements_session_id",
        "user_achievements",
        ["session_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_achievements_unlocked_at",
        "user_achievements",
        ["unlocked_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_user_achievements_user_unlocked",
        "user_achievements",
        ["user_id", "unlocked_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_achievements_user_unlocked",
        table_name="user_achievements",
        if_exists=True,
    )
    op.drop_index(
        "ix_user_achievements_unlocked_at",
        table_name="user_achievements",
        if_exists=True,
    )
    op.drop_index(
        "ix_user_achievements_session_id",
        table_name="user_achievements",
        if_exists=True,
    )
    op.drop_index(
        "ix_user_achievements_achievement_id",
        table_name="user_achievements",
        if_exists=True,
    )
    op.drop_index(
        "ix_user_achievements_user_id", table_name="user_achievements", if_exists=True
    )
    op.drop_table("user_achievements", if_exists=True)

    op.drop_index("idx_user_goals_user_active", table_name="user_goals", if_exists=True)
    op.drop_index("ix_user_goals_is_active", table_name="user_goals", if_exists=True)
    op.drop_index("ix_user_goals_user_id", table_name="user_goals", if_exists=True)
    op.drop_table("user_goals", if_exists=True)

    op.drop_index(
        "idx_notifications_user_read_created",
        table_name="notifications",
        if_exists=True,
    )
    op.drop_index(
        "ix_notifications_created_at", table_name="notifications", if_exists=True
    )
    op.drop_index(
        "ix_notifications_expires_at", table_name="notifications", if_exists=True
    )
    op.drop_index(
        "ix_notifications_is_read", table_name="notifications", if_exists=True
    )
    op.drop_index("ix_notifications_source", table_name="notifications", if_exists=True)
    op.drop_index("ix_notifications_type", table_name="notifications", if_exists=True)
    op.drop_index(
        "ix_notifications_user_id", table_name="notifications", if_exists=True
    )
    op.drop_table("notifications", if_exists=True)

    op.drop_index("ix_achievements_enabled", table_name="achievements", if_exists=True)
    op.drop_index("ix_achievements_code", table_name="achievements", if_exists=True)
    op.drop_table("achievements", if_exists=True)
