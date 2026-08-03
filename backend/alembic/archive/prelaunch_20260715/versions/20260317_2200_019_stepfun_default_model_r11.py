"""Switch default StepFun realtime model to step-audio-r1.1

Revision ID: 20260317_2200_019
Revises: 20260314_1200_018
Create Date: 2026-03-17 22:00:00.000000
"""

from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260317_2200_019"
down_revision: Union[str, None] = "20260314_1200_018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = "voice_runtime_profiles"
_COLUMN_NAME = "model_name"
_OLD_MODEL = "step-audio-2"
_NEW_MODEL = "step-audio-r1.1"


def _normalize_tool_policy(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _backfill_default_runtime_tool_policy() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, tool_policy
            FROM voice_runtime_profiles
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
            """
        )
    ).fetchall()

    for row in rows:
        tool_policy = _normalize_tool_policy(row.tool_policy)
        tool_policy.setdefault("kb_lock_mode", "coach_mode")
        tool_policy.setdefault("max_questions_per_turn", 1)
        tool_policy.setdefault("retrieval_enable_rerank", True)
        tool_policy.setdefault("retrieval_rerank_top_k", 8)
        bind.execute(
            sa.text(
                """
                UPDATE voice_runtime_profiles
                SET tool_policy = :tool_policy
                WHERE id = :profile_id
                """
            ).bindparams(
                profile_id=row.id,
                tool_policy=json.dumps(tool_policy, ensure_ascii=False),
            )
        )


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
              AND model_name = :old_model
            """
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )
    _backfill_default_runtime_tool_policy()


def downgrade() -> None:
    _set_server_default(_OLD_MODEL)

    op.execute(
        sa.text(
            """
            UPDATE voice_runtime_profiles
            SET model_name = :old_model
            WHERE is_default = true
              AND voice_mode = 'stepfun_realtime'
              AND model_name = :new_model
            """
        ).bindparams(new_model=_NEW_MODEL, old_model=_OLD_MODEL)
    )
