"""Switch default StepFun realtime model to step-audio-2.3.

Revision ID: 20260629_0215_087
Revises: 20260616_086
Create Date: 2026-06-29 02:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260629_0215_087"
down_revision: str | None = "20260616_086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "voice_runtime_profiles"
_COLUMN_NAME = "model_name"
_OLD_MODELS = ("step-audio-2", "step-audio-r1.1")
_NEW_MODEL = "step-audio-2.3"
_ROLLBACK_MODEL = "step-audio-2"


def _set_server_default(model_name: str) -> None:
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.alter_column(
            _COLUMN_NAME,
            existing_type=sa.String(length=100),
            existing_nullable=False,
            server_default=model_name,
        )


def upgrade() -> None:
    _set_server_default(_NEW_MODEL)

    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :new_model
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
              AND model_name IN :old_models
            """
        ).bindparams(
            sa.bindparam("old_models", expanding=True),
            new_model=_NEW_MODEL,
            old_models=_OLD_MODELS,
        )
    )


def downgrade() -> None:
    _set_server_default(_ROLLBACK_MODEL)

    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :rollback_model
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
              AND model_name = :new_model
            """
        ).bindparams(new_model=_NEW_MODEL, rollback_model=_ROLLBACK_MODEL)
    )
