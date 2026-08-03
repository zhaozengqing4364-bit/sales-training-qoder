"""Add model_configs table for AI service configuration

Revision ID: 002_model_configs
Revises: 001
Create Date: 2026-01-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_model_configs'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create model_configs table
    op.create_table(
        'model_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('model_type', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False),
        sa.Column('extra_config', sa.JSON(), server_default='{}'),
        sa.Column('is_default', sa.Boolean(), server_default='false', index=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', index=True),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('last_test_status', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),

        # Constraints
        sa.UniqueConstraint('model_type', 'provider', 'model_name', name='uq_model_config_type_provider_model'),
        sa.CheckConstraint(
            "model_type IN ('llm', 'embedding', 'asr', 'tts')",
            name='ck_model_config_type'
        ),
        sa.CheckConstraint(
            "provider IN ('openai', 'azure', 'alibaba', 'anthropic', 'local')",
            name='ck_model_config_provider'
        ),
        sa.CheckConstraint(
            "last_test_status IS NULL OR last_test_status IN ('success', 'failed')",
            name='ck_model_config_test_status'
        ),
    )

    # Create indexes
    op.create_index('idx_model_configs_type', 'model_configs', ['model_type'])
    op.create_index('idx_model_configs_type_default', 'model_configs', ['model_type', 'is_default'])
    op.create_index('idx_model_configs_active', 'model_configs', ['is_active'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_model_configs_active', table_name='model_configs')
    op.drop_index('idx_model_configs_type_default', table_name='model_configs')
    op.drop_index('idx_model_configs_type', table_name='model_configs')

    # Drop table
    op.drop_table('model_configs')
