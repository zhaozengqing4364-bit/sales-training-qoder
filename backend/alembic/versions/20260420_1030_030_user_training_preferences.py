"""add user training preferences

Revision ID: 20260420_1030_030
Revises: ae1dbf12bd03
Create Date: 2026-04-20 10:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260420_1030_030"
down_revision: str | None = "ae1dbf12bd03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_training_preferences",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("voice_mode", sa.String(length=32), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("persona_id", sa.String(length=36), nullable=True),
        sa.Column("presentation_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "voice_mode IS NULL OR voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_user_training_preferences_voice_mode",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_training_preferences")
