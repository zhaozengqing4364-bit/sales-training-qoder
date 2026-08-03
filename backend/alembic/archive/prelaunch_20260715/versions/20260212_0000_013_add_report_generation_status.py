"""
Add report generation status to practice_sessions

Story 3.1: 会话结束自动生成训练报告

Revision ID: 013
Revises: 20260211_1200_012_support_role.py
Create Date: 2026-02-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260212_0000_013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add report generation status columns
    op.add_column(
        'practice_sessions',
        sa.Column('report_status', sa.String(20), nullable=False, server_default='pending')
    )
    op.add_column(
        'practice_sessions',
        sa.Column('report_generated_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'practice_sessions',
        sa.Column('report_error', sa.Text(), nullable=True)
    )

    # Add check constraint for report_status
    op.create_check_constraint(
        'ck_report_status',
        'practice_sessions',
        sa.text("report_status IN ('pending', 'processing', 'completed', 'failed')")
    )

    # Add index for report_status
    op.create_index(
        'idx_sessions_report_status',
        'practice_sessions',
        ['report_status']
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_sessions_report_status', table_name='practice_sessions')

    # Drop check constraint
    op.drop_constraint('ck_report_status', 'practice_sessions', type_='check')

    # Drop columns
    op.drop_column('practice_sessions', 'report_error')
    op.drop_column('practice_sessions', 'report_generated_at')
    op.drop_column('practice_sessions', 'report_status')
