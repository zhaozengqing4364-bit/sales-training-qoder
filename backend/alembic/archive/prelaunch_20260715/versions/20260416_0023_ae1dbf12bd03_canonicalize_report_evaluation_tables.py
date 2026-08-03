"""canonicalize report evaluation tables

Revision ID: ae1dbf12bd03
Revises: 20260413_1040_029
Create Date: 2026-04-16 00:23:42.487345

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "ae1dbf12bd03"
down_revision: Union[str, None] = "20260413_1040_029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STAGED_TABLE = "staged_evaluation_results"
STAGED_CANONICAL_TABLE = "staged_evaluation_results__canonical"
STAGED_LEGACY_TABLE = "staged_evaluation_results__legacy"

REPORT_TABLE = "comprehensive_reports"
REPORT_CANONICAL_TABLE = "comprehensive_reports__canonical"
REPORT_LEGACY_TABLE = "comprehensive_reports__legacy"


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _drop_table_if_exists(table_name: str) -> None:
    op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}"'))


def _jsonb_type() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def _json_expr(
    columns: set[str], primary: str, *, fallback: str | None = None, default: str
) -> str:
    candidates = [name for name in (primary, fallback) if name and name in columns]
    if not candidates:
        return f"'{default}'::jsonb"
    casted = ", ".join(f"{name}::jsonb" for name in candidates)
    return f"COALESCE({casted}, '{default}'::jsonb)"


def _text_expr(
    columns: set[str],
    primary: str,
    *,
    fallback: str | None = None,
    default_sql: str = "NULL",
) -> str:
    candidates = [name for name in (primary, fallback) if name and name in columns]
    if not candidates:
        return default_sql
    combined = ", ".join(candidates)
    return f"COALESCE({combined}, {default_sql})"


def _timestamp_expr(
    columns: set[str], primary: str, *, fallback: str | None = None
) -> str:
    candidates = [name for name in (primary, fallback) if name and name in columns]
    if not candidates:
        return "CURRENT_TIMESTAMP"
    casted = ", ".join(f"{name}::timestamptz" for name in candidates)
    return f"COALESCE({casted}, CURRENT_TIMESTAMP)"


def _float_expr(columns: set[str], primary: str, *, default: str = "0") -> str:
    if primary not in columns:
        return default
    return f"COALESCE({primary}, {default})"


def _require_columns(table_name: str, columns: set[str], required: set[str]) -> None:
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(
            f"{table_name} is missing required source columns: {', '.join(missing)}"
        )


def _canonicalize_staged_evaluation_results() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, STAGED_TABLE)

    _drop_table_if_exists(STAGED_CANONICAL_TABLE)
    op.create_table(
        STAGED_CANONICAL_TABLE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "scores",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "strengths",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "weaknesses",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "suggestions",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    if columns:
        _require_columns(
            STAGED_TABLE,
            columns,
            {"id", "session_id", "stage_number", "start_turn", "end_turn"},
        )
        op.execute(
            sa.text(
                f"""
                INSERT INTO {STAGED_CANONICAL_TABLE} (
                    id,
                    session_id,
                    stage_number,
                    start_turn,
                    end_turn,
                    created_at,
                    scores,
                    strengths,
                    weaknesses,
                    suggestions,
                    summary
                )
                SELECT
                    COALESCE(id::text, substr(md5(random()::text || clock_timestamp()::text), 1, 36)),
                    session_id::text,
                    stage_number,
                    COALESCE(start_turn, 0),
                    COALESCE(end_turn, 0),
                    {_timestamp_expr(columns, "created_at", fallback="timestamp")},
                    {_json_expr(columns, "scores", default="{}")},
                    {_json_expr(columns, "strengths", default="[]")},
                    {_json_expr(columns, "weaknesses", default="[]")},
                    {_json_expr(columns, "suggestions", fallback="improvement_suggestions", default="[]")},
                    {_text_expr(columns, "summary", fallback="stage_summary")}
                FROM {STAGED_TABLE}
                """
            )
        )
        op.drop_table(STAGED_TABLE)

    op.rename_table(STAGED_CANONICAL_TABLE, STAGED_TABLE)
    op.create_index(
        "idx_staged_eval_session", STAGED_TABLE, ["session_id"], unique=False
    )
    op.create_index(
        "idx_staged_eval_stage",
        STAGED_TABLE,
        ["session_id", "stage_number"],
        unique=True,
    )


def _canonicalize_comprehensive_reports() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, REPORT_TABLE)

    _drop_table_if_exists(REPORT_CANONICAL_TABLE)
    op.create_table(
        REPORT_CANONICAL_TABLE,
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "overall_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "dimension_scores",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "stage_summaries",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "key_strengths",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "key_improvements",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("detailed_feedback", sa.Text(), nullable=True),
        sa.Column(
            "recommendations",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )

    if columns:
        _require_columns(REPORT_TABLE, columns, {"session_id"})
        op.execute(
            sa.text(
                f"""
                INSERT INTO {REPORT_CANONICAL_TABLE} (
                    session_id,
                    created_at,
                    overall_score,
                    dimension_scores,
                    stage_summaries,
                    key_strengths,
                    key_improvements,
                    detailed_feedback,
                    recommendations
                )
                SELECT
                    session_id::text,
                    {_timestamp_expr(columns, "created_at", fallback="generated_at")},
                    {_float_expr(columns, "overall_score")},
                    {_json_expr(columns, "dimension_scores", default="[]")},
                    {_json_expr(columns, "stage_summaries", default="[]")},
                    {_json_expr(columns, "key_strengths", default="[]")},
                    {_json_expr(columns, "key_improvements", fallback="priority_improvements", default="[]")},
                    {_text_expr(columns, "detailed_feedback", fallback="overall_assessment")},
                    {_json_expr(columns, "recommendations", fallback="practice_recommendations", default="[]")}
                FROM {REPORT_TABLE}
                """
            )
        )
        op.drop_table(REPORT_TABLE)

    op.rename_table(REPORT_CANONICAL_TABLE, REPORT_TABLE)


def _downgrade_staged_evaluation_results() -> None:
    columns = _column_names(op.get_bind(), STAGED_TABLE)

    _drop_table_if_exists(STAGED_LEGACY_TABLE)
    op.create_table(
        STAGED_LEGACY_TABLE,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("start_turn", sa.Integer(), nullable=False),
        sa.Column("end_turn", sa.Integer(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "scores",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "strengths",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "weaknesses",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "key_insights",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "improvement_suggestions",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("stage_summary", sa.Text(), nullable=True),
        sa.Column("comparison_with_previous", _jsonb_type(), nullable=True),
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("cost_tokens", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "suggestions",
            _jsonb_type(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    if columns:
        _require_columns(
            STAGED_TABLE,
            columns,
            {
                "session_id",
                "stage_number",
                "start_turn",
                "end_turn",
                "created_at",
                "scores",
                "strengths",
                "weaknesses",
                "suggestions",
                "summary",
            },
        )
        op.execute(
            sa.text(
                f"""
                INSERT INTO {STAGED_LEGACY_TABLE} (
                    id,
                    session_id,
                    stage_number,
                    start_turn,
                    end_turn,
                    timestamp,
                    scores,
                    strengths,
                    weaknesses,
                    key_insights,
                    improvement_suggestions,
                    stage_summary,
                    comparison_with_previous,
                    is_fallback,
                    cost_tokens,
                    processing_time_ms,
                    suggestions,
                    summary,
                    created_at
                )
                SELECT
                    gen_random_uuid(),
                    session_id::text,
                    stage_number,
                    start_turn,
                    end_turn,
                    created_at,
                    scores::jsonb,
                    strengths::jsonb,
                    weaknesses::jsonb,
                    '[]'::jsonb,
                    suggestions::jsonb,
                    summary,
                    NULL::jsonb,
                    false,
                    NULL::integer,
                    NULL::integer,
                    suggestions::jsonb,
                    summary,
                    created_at
                FROM {STAGED_TABLE}
                """
            )
        )
        op.drop_index("idx_staged_eval_stage", table_name=STAGED_TABLE)
        op.drop_index("idx_staged_eval_session", table_name=STAGED_TABLE)
        op.drop_table(STAGED_TABLE)

    op.rename_table(STAGED_LEGACY_TABLE, STAGED_TABLE)
    op.create_index(
        "idx_staged_eval_session", STAGED_TABLE, ["session_id"], unique=False
    )
    op.create_index(
        "idx_staged_eval_stage",
        STAGED_TABLE,
        ["session_id", "stage_number"],
        unique=True,
    )


def _downgrade_comprehensive_reports() -> None:
    columns = _column_names(op.get_bind(), REPORT_TABLE)

    _drop_table_if_exists(REPORT_LEGACY_TABLE)
    op.create_table(
        REPORT_LEGACY_TABLE,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "total_stages",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_turns",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("overall_assessment", sa.Text(), nullable=True),
        sa.Column(
            "key_strengths",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "priority_improvements",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("trend_summary", sa.Text(), nullable=True),
        sa.Column("personalized_advice", sa.Text(), nullable=True),
        sa.Column(
            "practice_recommendations",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("estimated_skill_level", sa.String(length=20), nullable=True),
        sa.Column(
            "trend_analysis",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "score_timeline",
            _jsonb_type(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "overall_score",
            sa.Float(),
            nullable=True,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "dimension_scores",
            _jsonb_type(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "stage_summaries",
            _jsonb_type(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "key_improvements",
            _jsonb_type(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("detailed_feedback", sa.Text(), nullable=True),
        sa.Column(
            "recommendations",
            _jsonb_type(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("comparison_to_baseline", _jsonb_type(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_comprehensive_reports_session_id"),
    )

    if columns:
        _require_columns(
            REPORT_TABLE,
            columns,
            {
                "session_id",
                "created_at",
                "overall_score",
                "dimension_scores",
                "stage_summaries",
                "key_strengths",
                "key_improvements",
                "detailed_feedback",
                "recommendations",
            },
        )
        op.execute(
            sa.text(
                f"""
                INSERT INTO {REPORT_LEGACY_TABLE} (
                    id,
                    session_id,
                    generated_at,
                    total_stages,
                    total_turns,
                    overall_assessment,
                    key_strengths,
                    priority_improvements,
                    trend_summary,
                    personalized_advice,
                    practice_recommendations,
                    estimated_skill_level,
                    trend_analysis,
                    score_timeline,
                    is_fallback,
                    overall_score,
                    dimension_scores,
                    stage_summaries,
                    key_improvements,
                    detailed_feedback,
                    recommendations,
                    comparison_to_baseline
                )
                SELECT
                    gen_random_uuid(),
                    session_id::text,
                    created_at,
                    jsonb_array_length(stage_summaries::jsonb),
                    0,
                    detailed_feedback,
                    key_strengths::jsonb,
                    key_improvements::jsonb,
                    NULL::text,
                    NULL::text,
                    recommendations::jsonb,
                    NULL::varchar(20),
                    '[]'::jsonb,
                    '[]'::jsonb,
                    false,
                    overall_score,
                    dimension_scores::jsonb,
                    stage_summaries::jsonb,
                    key_improvements::jsonb,
                    detailed_feedback,
                    recommendations::jsonb,
                    NULL::jsonb
                FROM {REPORT_TABLE}
                """
            )
        )
        op.drop_table(REPORT_TABLE)

    op.rename_table(REPORT_LEGACY_TABLE, REPORT_TABLE)
    op.create_index(
        "idx_comprehensive_reports_session",
        REPORT_TABLE,
        ["session_id"],
        unique=True,
    )


def upgrade() -> None:
    _canonicalize_staged_evaluation_results()
    _canonicalize_comprehensive_reports()


def downgrade() -> None:
    _downgrade_staged_evaluation_results()
    _downgrade_comprehensive_reports()
