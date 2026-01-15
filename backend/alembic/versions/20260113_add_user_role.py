"""Add role field to users table

Revision ID: 003_add_user_role
Revises: 002_model_configs
Create Date: 2026-01-13

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '003_add_user_role'
down_revision = '002_model_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column with default value 'user'
    op.add_column('users', sa.Column('role', sa.String(20), nullable=False, server_default='user'))

    # Add check constraint for role values
    op.create_check_constraint(
        'ck_user_role',
        'users',
        "role IN ('user', 'admin')"
    )


def downgrade() -> None:
    # Remove check constraint
    op.drop_constraint('ck_user_role', 'users', type_='check')

    # Remove role column
    op.drop_column('users', 'role')
