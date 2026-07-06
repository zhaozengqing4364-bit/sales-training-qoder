"""Switch default StepFun realtime model to stepaudio-2.5-realtime.

Revision ID: 20260702_1100_088
Revises: 20260629_0215_087
Create Date: 2026-07-02 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_1100_088"
down_revision: str | None = "20260629_0215_087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "voice_runtime_profiles"
_COLUMN_NAME = "model_name"
_VOICE_MODE = "stepfun_realtime"
_OLD_MODEL = "step-audio-2.3"
_NEW_MODEL = "stepaudio-2.5-realtime"


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
    _update_default_stepfun_profiles(from_model=_OLD_MODEL, to_model=_NEW_MODEL)


def downgrade() -> None:
    _set_server_default(_OLD_MODEL)
    # Downgrade is intentionally value-guarded rather than provenance-aware:
    # Alembic has no per-row marker for rows touched by upgrade. Rows already
    # moved to a different model after upgrade are preserved; operators who
    # intentionally keep stepaudio-2.5 should use provider registry rollback
    # rather than a schema/config downgrade.
    _update_default_stepfun_profiles(from_model=_NEW_MODEL, to_model=_OLD_MODEL)


def _update_default_stepfun_profiles(*, from_model: str, to_model: str) -> None:
    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :to_model
            WHERE is_default = true
              AND voice_mode = :voice_mode
              AND model_name = :from_model
            """
        ).bindparams(
            to_model=to_model,
            voice_mode=_VOICE_MODE,
            from_model=from_model,
        )
    )
