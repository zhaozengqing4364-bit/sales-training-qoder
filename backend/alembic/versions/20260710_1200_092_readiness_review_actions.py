"""Add canonical append-only readiness review actions.

Revision ID: 20260710_1200_092
Revises: 20260707_1200_091
Create Date: 2026-07-10 12:00:00.000000

The historical sales trainer operation log remains intact. New readiness
decisions use a dedicated table with actor-scoped idempotency and an audit-log
reference; downgrade removes only this additive table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260710_1200_092"
down_revision: str | None = "20260707_1200_091"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_NAME = "sales_trainer_readiness_review_actions"


def upgrade() -> None:
    bind = op.get_bind()
    if _TABLE_NAME in inspect(bind).get_table_names():
        return

    op.create_table(
        _TABLE_NAME,
        sa.Column("action_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("capability_keys", sa.JSON(), nullable=False),
        sa.Column("source_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("retraining_task", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("expected_previous_action_id", sa.String(length=36), nullable=True),
        sa.Column("audit_log_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approve', 'require_retraining', 'mark_manual_follow_up')",
            name="ck_readiness_review_decision",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("action_id"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_readiness_review_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_sales_trainer_readiness_review_actions_actor_id",
        _TABLE_NAME,
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        "ix_sales_trainer_readiness_review_actions_audit_log_id",
        _TABLE_NAME,
        ["audit_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_sales_trainer_readiness_review_actions_learner_id",
        _TABLE_NAME,
        ["learner_id"],
        unique=False,
    )
    op.create_index(
        "idx_readiness_review_learner_created",
        _TABLE_NAME,
        ["learner_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE_NAME not in inspect(bind).get_table_names():
        return
    op.drop_table(_TABLE_NAME)
