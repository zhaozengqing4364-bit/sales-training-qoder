"""Merge heads

Revision ID: f0afc3841ba3
Revises: 005, 006
Create Date: 2026-02-04 16:56:46.444644

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0afc3841ba3'
down_revision: Union[str, None] = ('005', '006')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
