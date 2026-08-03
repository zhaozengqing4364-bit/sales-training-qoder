"""Add sales_trainer_ai_coach_sessions and sales_trainer_ai_coach_turns tables

Revision ID: 20260609_1000_078_ai_coach
Revises: 20260604_0900_077
Create Date: 2026-06-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260609_1000_078_ai_coach"
down_revision: str | None = "20260604_0900_077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales_trainer_ai_coach_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("module_key", sa.String(80), nullable=False, index=True),
        sa.Column("path_key", sa.String(80), nullable=True, index=True),
        sa.Column(
            "path_revision_id",
            sa.String(36),
            sa.ForeignKey("sales_trainer_asset_revisions.revision_id"),
            nullable=True,
        ),
        sa.Column("path_revision_no", sa.Integer, nullable=True),
        sa.Column("article_snapshot", sa.JSON, nullable=False, default=dict),
        sa.Column("path_config_snapshot", sa.JSON, nullable=False, default=dict),
        sa.Column("prompt_template_id", sa.String(36), nullable=True),
        sa.Column("prompt_revision_id", sa.String(36), nullable=True),
        sa.Column("prompt_contract_hash", sa.String(128), nullable=True),
        sa.Column("config_snapshot", sa.JSON, nullable=False, default=dict),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="in_progress",
            server_default="in_progress",
        ),
        sa.Column(
            "mastery_state",
            sa.String(20),
            nullable=True,
        ),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
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
            onupdate=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_sales_trainer_ai_coach_session_status",
        ),
        sa.CheckConstraint(
            "mastery_state IS NULL OR mastery_state IN ('mastered', 'not_mastered')",
            name="ck_sales_trainer_ai_coach_session_mastery",
        ),
        sa.Index(
            "idx_sales_trainer_ai_coach_sessions_user_status",
            "user_id",
            "status",
        ),
        sa.Index(
            "idx_sales_trainer_ai_coach_sessions_module_created",
            "module_key",
            "created_at",
        ),
    )

    op.create_table(
        "sales_trainer_ai_coach_turns",
        sa.Column("turn_id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey(
                "sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("turn_number", sa.Integer, nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("user_answer", sa.Text, nullable=False),
        sa.Column("ai_feedback", sa.Text, nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("missed_points", sa.JSON, nullable=False, default=list),
        sa.Column("next_question", sa.Text, nullable=True),
        sa.Column("raw_model_output", sa.JSON, nullable=True),
        sa.Column("validated_output", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "turn_number >= 1", name="ck_sales_trainer_ai_coach_turn_number"
        ),
        sa.UniqueConstraint(
            "session_id",
            "turn_number",
            name="uq_sales_trainer_ai_coach_turn_session_number",
        ),
        sa.Index(
            "idx_sales_trainer_ai_coach_turns_session",
            "session_id",
            "turn_number",
        ),
    )


def downgrade() -> None:
    op.drop_table("sales_trainer_ai_coach_turns")
    op.drop_table("sales_trainer_ai_coach_sessions")
