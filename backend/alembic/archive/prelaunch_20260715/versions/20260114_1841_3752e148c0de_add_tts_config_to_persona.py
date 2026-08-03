"""add_tts_config_to_persona

Revision ID: 3752e148c0de
Revises: 003_add_user_role
Create Date: 2026-01-14 18:41:33.944220

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3752e148c0de'
down_revision: Union[str, None] = '003_add_user_role'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tts_config column to personas table."""
    op.add_column(
        'personas',
        sa.Column('tts_config', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    """Remove tts_config column from personas table."""
    op.drop_column('personas', 'tts_config')
