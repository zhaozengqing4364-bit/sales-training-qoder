"""Add voice runtime profile and agent voice policy tables

Revision ID: 010
Revises: 009
Create Date: 2026-02-10 11:00:00.000000
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(column.get("name") == column_name for column in columns)


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(index.get("name") == index_name for index in indexes)


def _constraint_exists(bind: sa.Connection, constraint_name: str) -> bool:
    dialect = bind.dialect.name
    if dialect == "postgresql":
        row = bind.execute(
            sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
            {"name": constraint_name},
        ).fetchone()
        return row is not None
    return False


def upgrade() -> None:
    """Create runtime policy tables and session snapshot columns."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "voice_runtime_profiles"):
        op.create_table(
            "voice_runtime_profiles",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("voice_mode", sa.String(length=32), nullable=False, server_default="stepfun_realtime"),
            sa.Column("model_name", sa.String(length=100), nullable=False, server_default="step-audio-2"),
            sa.Column("voice_name", sa.String(length=100), nullable=False, server_default="qingchunshaonv"),
            sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
            sa.Column("input_audio_format", sa.String(length=20), nullable=False, server_default="pcm16"),
            sa.Column("output_audio_format", sa.String(length=20), nullable=False, server_default="pcm16"),
            sa.Column("output_sample_rate", sa.Integer(), nullable=False, server_default="24000"),
            sa.Column("turn_detection", sa.String(length=32), nullable=True),
            sa.Column("system_instruction_template", sa.Text(), nullable=True),
            sa.Column("tool_policy", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("name", name="uq_voice_runtime_profile_name"),
            sa.CheckConstraint(
                "voice_mode IN ('legacy', 'stepfun_realtime')",
                name="ck_voice_runtime_profile_mode",
            ),
            sa.CheckConstraint(
                "temperature >= 0 AND temperature <= 2",
                name="ck_voice_runtime_profile_temperature",
            ),
            sa.CheckConstraint(
                "output_sample_rate > 0",
                name="ck_voice_runtime_profile_sample_rate",
            ),
        )
        inspector = sa.inspect(bind)

    if not _index_exists(inspector, "voice_runtime_profiles", "idx_voice_runtime_profiles_default"):
        op.create_index("idx_voice_runtime_profiles_default", "voice_runtime_profiles", ["is_default"])
    if not _index_exists(inspector, "voice_runtime_profiles", "idx_voice_runtime_profiles_active"):
        op.create_index("idx_voice_runtime_profiles_active", "voice_runtime_profiles", ["is_active"])
    if not _index_exists(inspector, "voice_runtime_profiles", "idx_voice_runtime_profiles_mode"):
        op.create_index("idx_voice_runtime_profiles_mode", "voice_runtime_profiles", ["voice_mode"])

    if not _table_exists(inspector, "agent_voice_policies"):
        op.create_table(
            "agent_voice_policies",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("agent_id", sa.String(length=36), nullable=False),
            sa.Column("runtime_profile_id", sa.String(length=36), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("voice_mode_override", sa.String(length=32), nullable=True),
            sa.Column("model_override", sa.String(length=100), nullable=True),
            sa.Column("voice_override", sa.String(length=100), nullable=True),
            sa.Column("temperature_override", sa.Float(), nullable=True),
            sa.Column("instructions_override", sa.Text(), nullable=True),
            sa.Column("tool_policy_override", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["runtime_profile_id"], ["voice_runtime_profiles.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("agent_id", name="uq_agent_voice_policy_agent_id"),
            sa.CheckConstraint(
                "voice_mode_override IS NULL OR voice_mode_override IN ('legacy', 'stepfun_realtime')",
                name="ck_agent_voice_policy_mode",
            ),
            sa.CheckConstraint(
                "temperature_override IS NULL OR (temperature_override >= 0 AND temperature_override <= 2)",
                name="ck_agent_voice_policy_temperature",
            ),
        )
        inspector = sa.inspect(bind)

    if not _index_exists(inspector, "agent_voice_policies", "idx_agent_voice_policy_agent"):
        op.create_index("idx_agent_voice_policy_agent", "agent_voice_policies", ["agent_id"])
    if not _index_exists(inspector, "agent_voice_policies", "idx_agent_voice_policy_profile"):
        op.create_index("idx_agent_voice_policy_profile", "agent_voice_policies", ["runtime_profile_id"])

    if not _column_exists(inspector, "practice_sessions", "voice_mode"):
        op.add_column(
            "practice_sessions",
            sa.Column("voice_mode", sa.String(length=32), nullable=False, server_default="legacy"),
        )
        inspector = sa.inspect(bind)
    if not _column_exists(inspector, "practice_sessions", "voice_runtime_profile_id"):
        op.add_column(
            "practice_sessions",
            sa.Column("voice_runtime_profile_id", sa.String(length=36), nullable=True),
        )
        inspector = sa.inspect(bind)
    if not _column_exists(inspector, "practice_sessions", "voice_policy_snapshot"):
        op.add_column(
            "practice_sessions",
            sa.Column("voice_policy_snapshot", sa.JSON(), nullable=True),
        )
        inspector = sa.inspect(bind)

    if not _constraint_exists(bind, "ck_session_voice_mode"):
        op.create_check_constraint(
            "ck_session_voice_mode",
            "practice_sessions",
            "voice_mode IN ('legacy', 'stepfun_realtime')",
        )
    if not _constraint_exists(bind, "fk_practice_sessions_voice_profile"):
        op.create_foreign_key(
            "fk_practice_sessions_voice_profile",
            "practice_sessions",
            "voice_runtime_profiles",
            ["voice_runtime_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _index_exists(inspector, "practice_sessions", "idx_sessions_voice_mode"):
        op.create_index("idx_sessions_voice_mode", "practice_sessions", ["voice_mode"])
    if not _index_exists(inspector, "practice_sessions", "idx_sessions_voice_profile"):
        op.create_index("idx_sessions_voice_profile", "practice_sessions", ["voice_runtime_profile_id"])

    default_profile_table = sa.table(
        "voice_runtime_profiles",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("voice_mode", sa.String),
        sa.column("model_name", sa.String),
        sa.column("voice_name", sa.String),
        sa.column("temperature", sa.Float),
        sa.column("input_audio_format", sa.String),
        sa.column("output_audio_format", sa.String),
        sa.column("output_sample_rate", sa.Integer),
        sa.column("turn_detection", sa.String),
        sa.column("system_instruction_template", sa.Text),
        sa.column("tool_policy", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    has_default_profile = bind.execute(
        sa.text("SELECT 1 FROM voice_runtime_profiles WHERE is_default = true LIMIT 1")
    ).fetchone()
    if not has_default_profile:
        now = datetime.now(timezone.utc)
        op.bulk_insert(
            default_profile_table,
            [
                {
                    "id": str(uuid.uuid4()),
                    "name": "系统默认 Realtime",
                    "description": "默认端到端语音配置，可用于全局回退",
                    "is_default": True,
                    "is_active": True,
                    "voice_mode": "stepfun_realtime",
                    "model_name": "step-audio-2",
                    "voice_name": "qingchunshaonv",
                    "temperature": 0.7,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "output_sample_rate": 24000,
                    "turn_detection": None,
                    "system_instruction_template": "",
                    "tool_policy": {
                        "enable_web_search": False,
                        "web_search_top_k": 5,
                        "web_search_timeout_seconds": 3,
                        "enable_internal_retrieval": True,
                        "retrieval_priority": "kb_first",
                        "retrieval_top_k": 5,
                        "retrieval_similarity_threshold": 0.65,
                        "strict_instruction_following": True,
                        "require_grounding": True,
                    },
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def downgrade() -> None:
    """Drop runtime policy structures."""
    op.drop_index("idx_sessions_voice_profile", table_name="practice_sessions")
    op.drop_index("idx_sessions_voice_mode", table_name="practice_sessions")
    op.drop_constraint("fk_practice_sessions_voice_profile", "practice_sessions", type_="foreignkey")
    op.drop_constraint("ck_session_voice_mode", "practice_sessions", type_="check")
    op.drop_column("practice_sessions", "voice_policy_snapshot")
    op.drop_column("practice_sessions", "voice_runtime_profile_id")
    op.drop_column("practice_sessions", "voice_mode")

    op.drop_index("idx_agent_voice_policy_profile", table_name="agent_voice_policies")
    op.drop_index("idx_agent_voice_policy_agent", table_name="agent_voice_policies")
    op.drop_table("agent_voice_policies")

    op.drop_index("idx_voice_runtime_profiles_mode", table_name="voice_runtime_profiles")
    op.drop_index("idx_voice_runtime_profiles_active", table_name="voice_runtime_profiles")
    op.drop_index("idx_voice_runtime_profiles_default", table_name="voice_runtime_profiles")
    op.drop_table("voice_runtime_profiles")
