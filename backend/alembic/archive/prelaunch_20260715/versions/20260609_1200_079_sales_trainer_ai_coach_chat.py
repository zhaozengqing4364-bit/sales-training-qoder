"""Add AI coach chat messages and UI events

Revision ID: 20260609_1200_079_ai_chat
Revises: 20260609_1100_078b_ai_fields
Create Date: 2026-06-09 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260609_1200_079_ai_chat"
down_revision: str | None = "20260609_1100_078b_ai_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales_trainer_ai_coach_chat_messages",
        sa.Column("message_id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey(
                "sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_sales_trainer_ai_coach_chat_message_role",
        ),
        sa.UniqueConstraint(
            "session_id",
            "order_index",
            name="uq_sales_trainer_ai_coach_chat_message_order",
        ),
    )
    op.create_index(
        "idx_sales_trainer_ai_coach_chat_messages_session",
        "sales_trainer_ai_coach_chat_messages",
        ["session_id", "order_index"],
    )

    op.create_table(
        "sales_trainer_ai_coach_ui_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey(
                "sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey(
                "sales_trainer_ai_coach_chat_messages.message_id",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("answer_payload", sa.JSON, nullable=True),
        sa.Column("score_result", sa.JSON, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'assistant_text', 'quiz_card', 'quiz_result', "
            "'explanation_card', 'summary_card', 'followup_prompt'"
            ")",
            name="ck_sales_trainer_ai_coach_ui_event_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'scored', 'failed')",
            name="ck_sales_trainer_ai_coach_ui_event_status",
        ),
        sa.UniqueConstraint(
            "message_id",
            "order_index",
            name="uq_sales_trainer_ai_coach_ui_event_message_order",
        ),
    )
    op.create_index(
        "idx_sales_trainer_ai_coach_ui_events_session",
        "sales_trainer_ai_coach_ui_events",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("sales_trainer_ai_coach_ui_events")
    op.drop_table("sales_trainer_ai_coach_chat_messages")
