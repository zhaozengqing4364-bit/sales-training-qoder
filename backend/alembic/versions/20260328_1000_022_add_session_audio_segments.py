"""Add session_audio_segments table.

Revision ID: 20260328_1000_022
Revises: 20260326_1000_021
Create Date: 2026-03-28 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260328_1000_022"
down_revision: Union[str, None] = "20260326_1000_021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_audio_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("segment_sequence", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False, server_default="audio/webm"),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("upload_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "upload_status IN ('pending', 'uploaded', 'failed')",
            name="ck_audio_segment_upload_status",
        ),
        sa.UniqueConstraint(
            "session_id", "segment_sequence",
            name="uq_audio_segment_session_sequence",
        ),
    )
    op.create_index(
        "idx_audio_segments_session",
        "session_audio_segments",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_audio_segments_session", table_name="session_audio_segments")
    op.drop_table("session_audio_segments")
