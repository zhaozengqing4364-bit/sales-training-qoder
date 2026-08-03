"""Staged Evaluation Migration

Creates tables for staged evaluation system:
- staged_evaluation_results: Stores evaluation results for each stage
- comprehensive_reports: Stores final comprehensive reports

Revision ID: 006_staged_evaluation
Revises: 005
Create Date: 2026-02-04 09:00:00.000000

Requirements: C1 - Create staged evaluation database tables
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "3752e148c0de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create staged_evaluation_results and comprehensive_reports tables."""

    # 1. Create staged_evaluation_results table
    op.create_table(
        "staged_evaluation_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("stage_number", sa.Integer, nullable=False),
        sa.Column("start_turn", sa.Integer, nullable=False),
        sa.Column("end_turn", sa.Integer, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("strengths", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("weaknesses", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("key_insights", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("improvement_suggestions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("stage_summary", sa.Text(), nullable=True),
        sa.Column("comparison_with_previous", postgresql.JSONB(), nullable=True),
        sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cost_tokens", sa.Integer, nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
    )
    op.create_index(
        "idx_staged_eval_session", "staged_evaluation_results", ["session_id"]
    )
    op.create_index(
        "idx_staged_eval_stage", "staged_evaluation_results", ["session_id", "stage_number"], unique=True
    )

    # 2. Create comprehensive_reports table
    op.create_table(
        "comprehensive_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(36), nullable=False, unique=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("total_stages", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_turns", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_assessment", sa.Text(), nullable=True),
        sa.Column("key_strengths", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("priority_improvements", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("trend_summary", sa.Text(), nullable=True),
        sa.Column("personalized_advice", sa.Text(), nullable=True),
        sa.Column("practice_recommendations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("estimated_skill_level", sa.String(20), nullable=True),
        sa.Column("trend_analysis", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("score_timeline", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "idx_comprehensive_reports_session", "comprehensive_reports", ["session_id"], unique=True
    )


def downgrade() -> None:
    """Drop staged_evaluation_results and comprehensive_reports tables."""

    # Drop comprehensive_reports first (no dependencies)
    op.drop_index("idx_comprehensive_reports_session", table_name="comprehensive_reports")
    op.drop_table("comprehensive_reports")

    # Drop staged_evaluation_results
    op.drop_index("idx_staged_eval_stage", table_name="staged_evaluation_results")
    op.drop_index("idx_staged_eval_session", table_name="staged_evaluation_results")
    op.drop_table("staged_evaluation_results")
