"""Add composite index for practice_sessions performance optimization

Creates a composite index on (status, start_time) for practice_sessions table
to optimize common query patterns filtering by status and time range.

Revision ID: 008
Revises: f0afc3841ba3
Create Date: 2026-02-04 19:00:00.000000

Requirements: Code Review Fix - Phase 4 Performance Optimization
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "f0afc3841ba3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index on practice_sessions (status, start_time)."""

    # Create composite index for common query pattern:
    # select().where(PracticeSession.status == "completed")
    #        .where(PracticeSession.start_time >= cutoff)
    op.create_index(
        "idx_sessions_status_start_time",
        "practice_sessions",
        ["status", "start_time"],
    )


def downgrade() -> None:
    """Remove composite index on practice_sessions (status, start_time)."""

    op.drop_index("idx_sessions_status_start_time", table_name="practice_sessions")
