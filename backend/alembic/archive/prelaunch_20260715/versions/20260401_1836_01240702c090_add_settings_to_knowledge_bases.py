"""add_settings_to_knowledge_bases

Revision ID: 01240702c090
Revises: 20260331_1100_023
Create Date: 2026-04-01 18:36:09.047868

"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '01240702c090'
down_revision: Union[str, None] = '20260331_1100_023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_bases ADD COLUMN IF NOT EXISTS settings TEXT")


def downgrade() -> None:
    op.drop_column("knowledge_bases", "settings")
