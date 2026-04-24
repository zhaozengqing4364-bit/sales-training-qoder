"""add highlight review persistence and share audit tables

Revision ID: 20260424_1106_w6
Revises: 20260421_0645_032
Create Date: 2026-04-24 11:06:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260424_1106_w6"
down_revision: str | None = "20260421_0645_032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "highlight_reviews",
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=40),
            nullable=False,
            server_default="highlight_review_v1",
        ),
        sa.Column("title", sa.String(length=160), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["session_id"], ["practice_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint(
            "user_id", "session_id", name="uq_highlight_reviews_user_session"
        ),
    )
    op.create_index(
        "idx_highlight_reviews_user_updated",
        "highlight_reviews",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_highlight_reviews_session",
        "highlight_reviews",
        ["session_id"],
        unique=False,
    )

    op.create_table(
        "highlight_review_items",
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content_excerpt", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("stage_name", sa.String(length=80), nullable=True),
        sa.Column("issue_label", sa.String(length=80), nullable=True),
        sa.Column("suggested_response", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_highlight_review_item_role",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["conversation_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["highlight_reviews.review_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("item_id"),
        sa.UniqueConstraint(
            "review_id",
            "message_id",
            name="uq_highlight_review_items_review_message",
        ),
    )
    op.create_index(
        "idx_highlight_review_items_review",
        "highlight_review_items",
        ["review_id"],
        unique=False,
    )
    op.create_index(
        "idx_highlight_review_items_message",
        "highlight_review_items",
        ["message_id"],
        unique=False,
    )

    op.create_table(
        "highlight_review_shares",
        sa.Column("share_id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="wecom",
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "consent_granted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("ttl_days", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("revoked_reason", sa.String(length=200), nullable=True),
        sa.Column("desensitization_version", sa.String(length=50), nullable=False),
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
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "channel IN ('wecom')",
            name="ck_highlight_review_share_channel",
        ),
        sa.CheckConstraint("ttl_days BETWEEN 1 AND 90", name="ck_highlight_share_ttl"),
        sa.ForeignKeyConstraint(
            ["review_id"], ["highlight_reviews.review_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("share_id"),
    )
    op.create_index(
        op.f("ix_highlight_review_shares_token_hash"),
        "highlight_review_shares",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_highlight_review_shares_expires_at"),
        "highlight_review_shares",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_highlight_review_shares_revoked_at"),
        "highlight_review_shares",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        "idx_highlight_review_shares_review",
        "highlight_review_shares",
        ["review_id"],
        unique=False,
    )
    op.create_index(
        "idx_highlight_review_shares_user",
        "highlight_review_shares",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "highlight_review_share_access_logs",
        sa.Column("log_id", sa.String(length=36), nullable=False),
        sa.Column("share_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("viewer_label", sa.String(length=120), nullable=True),
        sa.Column("client_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'accessed', 'revoked', 'denied')",
            name="ck_highlight_share_access_event_type",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'blocked')",
            name="ck_highlight_share_access_status",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["share_id"], ["highlight_review_shares.share_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(
        "idx_highlight_share_access_logs_share",
        "highlight_review_share_access_logs",
        ["share_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_highlight_share_access_logs_actor",
        "highlight_review_share_access_logs",
        ["actor_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_highlight_share_access_logs_actor",
        table_name="highlight_review_share_access_logs",
    )
    op.drop_index(
        "idx_highlight_share_access_logs_share",
        table_name="highlight_review_share_access_logs",
    )
    op.drop_table("highlight_review_share_access_logs")

    op.drop_index("idx_highlight_review_shares_user", table_name="highlight_review_shares")
    op.drop_index("idx_highlight_review_shares_review", table_name="highlight_review_shares")
    op.drop_index(
        op.f("ix_highlight_review_shares_revoked_at"),
        table_name="highlight_review_shares",
    )
    op.drop_index(
        op.f("ix_highlight_review_shares_expires_at"),
        table_name="highlight_review_shares",
    )
    op.drop_index(
        op.f("ix_highlight_review_shares_token_hash"),
        table_name="highlight_review_shares",
    )
    op.drop_table("highlight_review_shares")

    op.drop_index(
        "idx_highlight_review_items_message", table_name="highlight_review_items"
    )
    op.drop_index(
        "idx_highlight_review_items_review", table_name="highlight_review_items"
    )
    op.drop_table("highlight_review_items")

    op.drop_index("idx_highlight_reviews_session", table_name="highlight_reviews")
    op.drop_index("idx_highlight_reviews_user_updated", table_name="highlight_reviews")
    op.drop_table("highlight_reviews")
