"""Add append-only sales trainer roleplay observations.

Revision ID: 20260702_1530_089
Revises: 20260702_1100_088
Create Date: 2026-07-02 15:30:00.000000
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260702_1530_089"
down_revision: str | None = "20260702_1100_088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "sales_trainer_roleplay_observations"
_ALLOW_DESTRUCTIVE_DOWNGRADE_ENV = (
    "ALLOW_SALES_TRAINER_ROLEPLAY_OBSERVATION_DESTRUCTIVE_DOWNGRADE"
)


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table(_TABLE_NAME):
        op.create_table(
            _TABLE_NAME,
            sa.Column("observation_id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("source_record_id", sa.String(length=36), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("evaluator_status", sa.String(length=20), nullable=False),
            sa.Column("dimensions", sa.JSON(), nullable=False),
            sa.Column("signals", sa.JSON(), nullable=False),
            sa.Column("error", sa.JSON(), nullable=True),
            sa.Column("payload_hash", sa.String(length=128), nullable=False),
            sa.Column("trace_id", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "source IN ('heuristic', 'llm_evaluator')",
                name="ck_sales_trainer_roleplay_observation_source",
            ),
            sa.CheckConstraint(
                "evaluator_status IN ('pending', 'completed', 'failed', 'ignored')",
                name="ck_sales_trainer_roleplay_observation_status",
            ),
            sa.CheckConstraint(
                "turn_index >= 0",
                name="ck_sales_trainer_roleplay_observation_turn_index",
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["practice_sessions.session_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("observation_id"),
            sa.UniqueConstraint(
                "source_record_id",
                "source",
                "turn_index",
                "payload_hash",
                name="uq_sales_trainer_roleplay_observation_dedupe",
            ),
        )
    _create_index_if_missing(
        "ix_sales_trainer_roleplay_observations_session_id",
        _TABLE_NAME,
        ["session_id"],
    )
    _create_index_if_missing(
        "ix_sales_trainer_roleplay_observations_source_record_id",
        _TABLE_NAME,
        ["source_record_id"],
    )
    _create_index_if_missing(
        "ix_sales_trainer_roleplay_observations_source",
        _TABLE_NAME,
        ["source"],
    )
    _create_index_if_missing(
        "ix_sales_trainer_roleplay_observations_evaluator_status",
        _TABLE_NAME,
        ["evaluator_status"],
    )
    _create_index_if_missing(
        "idx_sales_trainer_roleplay_observation_session_turn",
        _TABLE_NAME,
        ["session_id", "turn_index", "created_at"],
    )
    _create_index_if_missing(
        "idx_sales_trainer_roleplay_observation_session_source_status",
        _TABLE_NAME,
        ["session_id", "source", "evaluator_status", "created_at"],
    )


def downgrade() -> None:
    if not inspect(op.get_bind()).has_table(_TABLE_NAME):
        return
    _guard_destructive_downgrade()
    _drop_index_if_exists(
        "idx_sales_trainer_roleplay_observation_session_source_status",
        table_name=_TABLE_NAME,
    )
    _drop_index_if_exists(
        "idx_sales_trainer_roleplay_observation_session_turn",
        table_name=_TABLE_NAME,
    )
    _drop_index_if_exists(
        "ix_sales_trainer_roleplay_observations_evaluator_status",
        table_name=_TABLE_NAME,
    )
    _drop_index_if_exists(
        "ix_sales_trainer_roleplay_observations_source",
        table_name=_TABLE_NAME,
    )
    _drop_index_if_exists(
        "ix_sales_trainer_roleplay_observations_source_record_id",
        table_name=_TABLE_NAME,
    )
    _drop_index_if_exists(
        "ix_sales_trainer_roleplay_observations_session_id",
        table_name=_TABLE_NAME,
    )
    op.drop_table(_TABLE_NAME)


def _guard_destructive_downgrade() -> None:
    row_count = op.get_bind().execute(
        sa.text(f"SELECT COUNT(*) FROM {_TABLE_NAME}")
    ).scalar_one()
    if row_count == 0:
        return
    if os.getenv(_ALLOW_DESTRUCTIVE_DOWNGRADE_ENV) == "1":
        return
    raise RuntimeError(
        "Refusing to drop non-empty sales trainer roleplay observations. "
        "This sidecar is append-only audit data; disable the observation sink "
        "or hide the read endpoint for business rollback. Export/approve data "
        "loss first, then rerun with "
        f"{_ALLOW_DESTRUCTIVE_DOWNGRADE_ENV}=1 if destructive downgrade is intended."
    )


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    bind = op.get_bind()
    existing_indexes = {
        item.get("name") for item in inspect(bind).get_indexes(table_name)
    }
    if index_name in existing_indexes:
        return
    op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_exists(index_name: str, *, table_name: str) -> None:
    existing_indexes = {
        item.get("name") for item in inspect(op.get_bind()).get_indexes(table_name)
    }
    if index_name not in existing_indexes:
        return
    op.drop_index(index_name, table_name=table_name)
