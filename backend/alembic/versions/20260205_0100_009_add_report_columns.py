"""Add missing columns to staged_evaluation_results and comprehensive_reports

Adds columns needed by the evaluation service code that were not in the
original migration 006:
- staged_evaluation_results: suggestions, summary, created_at
- comprehensive_reports: overall_score, dimension_scores, stage_summaries,
  key_improvements, detailed_feedback, recommendations, comparison_to_baseline

Revision ID: 009
Revises: 008
Create Date: 2026-02-05 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to evaluation tables."""

    # Add missing columns to staged_evaluation_results
    op.add_column(
        "staged_evaluation_results",
        sa.Column("suggestions", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "staged_evaluation_results",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "staged_evaluation_results",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    # Add missing columns to comprehensive_reports
    op.add_column(
        "comprehensive_reports",
        sa.Column("overall_score", sa.Float(), nullable=True, server_default="0"),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("dimension_scores", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("stage_summaries", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("key_improvements", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("detailed_feedback", sa.Text(), nullable=True),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("recommendations", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "comprehensive_reports",
        sa.Column("comparison_to_baseline", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove added columns."""

    # Remove from comprehensive_reports
    op.drop_column("comprehensive_reports", "comparison_to_baseline")
    op.drop_column("comprehensive_reports", "recommendations")
    op.drop_column("comprehensive_reports", "detailed_feedback")
    op.drop_column("comprehensive_reports", "key_improvements")
    op.drop_column("comprehensive_reports", "stage_summaries")
    op.drop_column("comprehensive_reports", "dimension_scores")
    op.drop_column("comprehensive_reports", "overall_score")

    # Remove from staged_evaluation_results
    op.drop_column("staged_evaluation_results", "created_at")
    op.drop_column("staged_evaluation_results", "summary")
    op.drop_column("staged_evaluation_results", "suggestions")
