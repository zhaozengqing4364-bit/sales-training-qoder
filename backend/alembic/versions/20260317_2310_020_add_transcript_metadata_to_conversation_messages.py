"""Add transcript metadata to conversation messages.

Revision ID: 20260317_2310_020
Revises: 20260317_2200_019
Create Date: 2026-03-17 23:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260317_2310_020"
down_revision: Union[str, None] = "20260317_2200_019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_messages") as batch_op:
        batch_op.add_column(sa.Column("transcript_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversation_messages") as batch_op:
        batch_op.drop_column("transcript_metadata")
