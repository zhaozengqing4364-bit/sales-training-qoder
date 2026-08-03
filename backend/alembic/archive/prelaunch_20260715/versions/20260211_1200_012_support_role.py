"""Allow support role in users table

Revision ID: 012
Revises: 011
Create Date: 2026-02-11 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('user', 'admin', 'support')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_role", "users", type_="check")
    op.create_check_constraint(
        "ck_user_role",
        "users",
        "role IN ('user', 'admin')",
    )
