"""enforce single active password reset token per user

Revision ID: 028_reset_single_active_token
Revises: 027_reset_lifecycle_delivery
Create Date: 2026-04-12 03:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "028_reset_single_active_token"
down_revision: Union[str, None] = "027_reset_lifecycle_delivery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE_TOKEN_WHERE = sa.text("used_at IS NULL AND invalidated_at IS NULL")


def upgrade() -> None:
    op.create_index(
        "uq_password_reset_tokens_single_active_user",
        "password_reset_tokens",
        ["user_id"],
        unique=True,
        sqlite_where=_ACTIVE_TOKEN_WHERE,
        postgresql_where=_ACTIVE_TOKEN_WHERE,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_password_reset_tokens_single_active_user",
        table_name="password_reset_tokens",
    )
