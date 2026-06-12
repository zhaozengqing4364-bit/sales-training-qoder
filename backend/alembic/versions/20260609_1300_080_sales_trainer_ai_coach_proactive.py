"""Add proactive AI coach state and action audit

Revision ID: 20260609_1300_080_ai_proactive
Revises: 20260609_1200_079_ai_chat
Create Date: 2026-06-09 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260609_1300_080_ai_proactive"
down_revision: str | None = "20260609_1200_079_ai_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _column_exists("sales_trainer_ai_coach_sessions", "coach_state"):
        op.add_column(
            "sales_trainer_ai_coach_sessions",
            sa.Column(
                "coach_state",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )
    if not _table_exists("sales_trainer_ai_coach_coach_actions"):
        op.create_table(
            "sales_trainer_ai_coach_coach_actions",
            sa.Column("action_id", sa.String(36), primary_key=True),
            sa.Column(
                "session_id",
                sa.String(36),
                sa.ForeignKey(
                    "sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"
                ),
                nullable=False,
                index=True,
            ),
            sa.Column("trigger_type", sa.String(40), nullable=False),
            sa.Column(
                "trigger_event_id",
                sa.String(36),
                sa.ForeignKey(
                    "sales_trainer_ai_coach_ui_events.event_id", ondelete="SET NULL"
                ),
                nullable=True,
                index=True,
            ),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="generated"
            ),
            sa.Column("state_before", sa.JSON(), nullable=False),
            sa.Column("state_after", sa.JSON(), nullable=False),
            sa.Column(
                "assistant_message_id",
                sa.String(36),
                sa.ForeignKey(
                    "sales_trainer_ai_coach_chat_messages.message_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
                index=True,
            ),
            sa.Column("error_code", sa.String(120), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "trigger_type IN ('session_start', 'user_message', 'event_answer')",
                name="ck_sales_trainer_ai_coach_action_trigger_type",
            ),
            sa.CheckConstraint(
                "action IN ("
                "'continue_drill', 'increase_difficulty', 'remediate', "
                "'switch_scenario', 'summarize', 'ask_user_choice', 'end_session'"
                ")",
                name="ck_sales_trainer_ai_coach_action",
            ),
            sa.CheckConstraint(
                "status IN ('generated', 'skipped', 'failed')",
                name="ck_sales_trainer_ai_coach_action_status",
            ),
        )
    if not _index_exists(
        "sales_trainer_ai_coach_coach_actions",
        "idx_sales_trainer_ai_coach_actions_session",
    ):
        op.create_index(
            "idx_sales_trainer_ai_coach_actions_session",
            "sales_trainer_ai_coach_coach_actions",
            ["session_id", "created_at"],
        )


def downgrade() -> None:
    if _table_exists("sales_trainer_ai_coach_coach_actions"):
        op.drop_table("sales_trainer_ai_coach_coach_actions")
    if _column_exists("sales_trainer_ai_coach_sessions", "coach_state"):
        op.drop_column("sales_trainer_ai_coach_sessions", "coach_state")
