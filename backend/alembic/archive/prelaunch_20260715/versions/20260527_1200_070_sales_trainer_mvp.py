"""add sales trainer MVP tables

Revision ID: 20260527_1200_070
Revises: 20260527_1100_069
Create Date: 2026-05-27 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_1200_070"
down_revision: str | None = "20260527_1100_069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    json_type = _json_type()
    op.create_table(
        "sales_trainer_units",
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_type", sa.String(length=30), nullable=False),
        sa.Column("config", json_type, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "unit_type IN ('quiz', 'audio_scoring')",
            name="ck_sales_trainer_unit_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_unit_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("unit_id"),
    )
    op.create_index(
        "idx_sales_trainer_units_status_updated",
        "sales_trainer_units",
        ["status", "updated_at"],
    )
    op.create_index("ix_sales_trainer_units_status", "sales_trainer_units", ["status"])
    op.create_index(
        "ix_sales_trainer_units_unit_type", "sales_trainer_units", ["unit_type"]
    )

    op.create_table(
        "sales_trainer_unit_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("order_index >= 1", name="ck_sales_trainer_question_order"),
        sa.CheckConstraint("points > 0", name="ck_sales_trainer_question_points"),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["question_items.question_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["sales_trainer_units.unit_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_id", "question_id", name="uq_sales_trainer_unit_question"),
    )
    op.create_index(
        "idx_sales_trainer_unit_questions_order",
        "sales_trainer_unit_questions",
        ["unit_id", "order_index"],
    )
    op.create_index(
        "ix_sales_trainer_unit_questions_question_id",
        "sales_trainer_unit_questions",
        ["question_id"],
    )
    op.create_index(
        "ix_sales_trainer_unit_questions_unit_id",
        "sales_trainer_unit_questions",
        ["unit_id"],
    )

    op.create_table(
        "sales_trainer_quiz_attempts",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("total_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("max_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('submitted', 'scored', 'failed')",
            name="ck_sales_trainer_quiz_status",
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["sales_trainer_units.unit_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index(
        "idx_sales_trainer_quiz_attempt_user",
        "sales_trainer_quiz_attempts",
        ["user_id", "submitted_at"],
    )
    op.create_index(
        "ix_sales_trainer_quiz_attempts_status",
        "sales_trainer_quiz_attempts",
        ["status"],
    )
    op.create_index(
        "ix_sales_trainer_quiz_attempts_unit_id",
        "sales_trainer_quiz_attempts",
        ["unit_id"],
    )

    op.create_table(
        "sales_trainer_quiz_answers",
        sa.Column("answer_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("question_type", sa.String(length=30), nullable=False),
        sa.Column("answer_payload", json_type, nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["sales_trainer_quiz_attempts.attempt_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["question_id"], ["question_items.question_id"]),
        sa.PrimaryKeyConstraint("answer_id"),
    )
    op.create_index(
        "ix_sales_trainer_quiz_answers_attempt_id",
        "sales_trainer_quiz_answers",
        ["attempt_id"],
    )
    op.create_index(
        "ix_sales_trainer_quiz_answers_question_id",
        "sales_trainer_quiz_answers",
        ["question_id"],
    )

    op.create_table(
        "sales_trainer_audio_score_prompts",
        sa.Column("prompt_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("scoring_template", sa.Text(), nullable=False),
        sa.Column("output_schema", json_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_prompt_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("prompt_id"),
    )
    op.create_index(
        "idx_sales_trainer_prompts_status",
        "sales_trainer_audio_score_prompts",
        ["status", "updated_at"],
    )
    op.create_index(
        "ix_sales_trainer_audio_score_prompts_status",
        "sales_trainer_audio_score_prompts",
        ["status"],
    )

    op.create_table(
        "sales_trainer_audio_submissions",
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("source_page", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('uploaded', 'transcribing', 'transcribed', "
            "'transcription_failed', 'scoring', 'scored', 'scoring_failed')",
            name="ck_sales_trainer_audio_status",
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["sales_trainer_units.unit_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("submission_id"),
    )
    op.create_index(
        "idx_sales_trainer_audio_user_created",
        "sales_trainer_audio_submissions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_sales_trainer_audio_submissions_status",
        "sales_trainer_audio_submissions",
        ["status"],
    )
    op.create_index(
        "ix_sales_trainer_audio_submissions_unit_id",
        "sales_trainer_audio_submissions",
        ["unit_id"],
    )

    op.create_table(
        "sales_trainer_audio_transcripts",
        sa.Column("transcript_id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("raw_payload", json_type, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["sales_trainer_audio_submissions.submission_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("transcript_id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(
        "ix_sales_trainer_audio_transcripts_submission_id",
        "sales_trainer_audio_transcripts",
        ["submission_id"],
        unique=True,
    )

    op.create_table(
        "sales_trainer_audio_score_results",
        sa.Column("score_id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_id", sa.String(length=36), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("prompt_hash", sa.String(length=128), nullable=False),
        sa.Column("deucate_model", sa.String(length=100), nullable=True),
        sa.Column("transcript_snapshot", sa.Text(), nullable=True),
        sa.Column("total_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", json_type, nullable=False),
        sa.Column("improvements", json_type, nullable=False),
        sa.Column("dimension_scores", json_type, nullable=False),
        sa.Column("raw_response", json_type, nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["sales_trainer_audio_score_prompts.prompt_id"],
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["sales_trainer_audio_submissions.submission_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("score_id"),
    )
    op.create_index(
        "ix_sales_trainer_audio_score_results_prompt_id",
        "sales_trainer_audio_score_results",
        ["prompt_id"],
    )
    op.create_index(
        "ix_sales_trainer_audio_score_results_submission_id",
        "sales_trainer_audio_score_results",
        ["submission_id"],
    )

    op.create_table(
        "sales_trainer_operation_logs",
        sa.Column("log_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(
        "idx_sales_trainer_operation_actor",
        "sales_trainer_operation_logs",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "idx_sales_trainer_operation_target",
        "sales_trainer_operation_logs",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_sales_trainer_operation_logs_action",
        "sales_trainer_operation_logs",
        ["action"],
    )
    op.create_index(
        "ix_sales_trainer_operation_logs_actor_id",
        "sales_trainer_operation_logs",
        ["actor_id"],
    )
    op.create_index(
        "ix_sales_trainer_operation_logs_target_id",
        "sales_trainer_operation_logs",
        ["target_id"],
    )
    op.create_index(
        "ix_sales_trainer_operation_logs_target_type",
        "sales_trainer_operation_logs",
        ["target_type"],
    )


def downgrade() -> None:
    op.drop_table("sales_trainer_operation_logs")
    op.drop_table("sales_trainer_audio_score_results")
    op.drop_table("sales_trainer_audio_transcripts")
    op.drop_table("sales_trainer_audio_submissions")
    op.drop_table("sales_trainer_audio_score_prompts")
    op.drop_table("sales_trainer_quiz_answers")
    op.drop_table("sales_trainer_quiz_attempts")
    op.drop_table("sales_trainer_unit_questions")
    op.drop_table("sales_trainer_units")
