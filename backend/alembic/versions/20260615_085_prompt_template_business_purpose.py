"""Add business purpose to prompt templates.

Revision ID: 20260615_085
Revises: 20260615_084
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_085"
down_revision: str | None = "20260615_084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AI_COACH_CONVERSATION_PURPOSE = "ai_coach_conversation_generation"
BUSINESS_ETIQUETTE_QUESTION_PURPOSE = "business_etiquette_question_generation"
BUSINESS_PROMPT_CATEGORIES = (
    "business_etiquette",
    "sales_trainer_ai_coach",
    "sales_trainer",
)
QUESTION_KEYWORDS = ("题目生成", "题目草稿", "试题生成", "question")
CONVERSATION_KEYWORDS = ("对话教练", "互动卡片", "chatbot", "教练回复")


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes("prompt_templates"))


def _contains_any_sql(column_sql: str, keywords: tuple[str, ...], prefix: str) -> tuple[str, dict[str, str]]:
    clauses: list[str] = []
    params: dict[str, str] = {}
    for index, keyword in enumerate(keywords):
        key = f"{prefix}_{index}"
        clauses.append(f"lower(COALESCE({column_sql}, '')) LIKE :{key}")
        params[key] = f"%{keyword.lower()}%"
    return "(" + " OR ".join(clauses) + ")", params


def _backfill_business_purpose() -> None:
    bind = op.get_bind()
    text_match, text_params = _contains_any_sql(
        "name || ' ' || prompt_type || ' ' || category || ' ' || template",
        CONVERSATION_KEYWORDS,
        "conversation_keyword",
    )
    bind.execute(
        sa.text(
            f"""
            UPDATE prompt_templates
            SET business_purpose = :purpose, updated_at = CURRENT_TIMESTAMP
            WHERE business_purpose IS NULL
              AND category = 'sales_trainer_ai_coach'
              AND {text_match}
            """
        ),
        {"purpose": AI_COACH_CONVERSATION_PURPOSE, **text_params},
    )

    question_match, question_params = _contains_any_sql(
        "name || ' ' || prompt_type || ' ' || category || ' ' || template",
        QUESTION_KEYWORDS,
        "question_keyword",
    )
    excluded_match, excluded_params = _contains_any_sql(
        "name || ' ' || prompt_type || ' ' || category || ' ' || template",
        CONVERSATION_KEYWORDS,
        "excluded_keyword",
    )
    bind.execute(
        sa.text(
            f"""
            UPDATE prompt_templates
            SET business_purpose = :purpose, updated_at = CURRENT_TIMESTAMP
            WHERE business_purpose IS NULL
              AND category IN :categories
              AND {question_match}
              AND NOT {excluded_match}
            """
        ).bindparams(sa.bindparam("categories", expanding=True)),
        {
            "purpose": BUSINESS_ETIQUETTE_QUESTION_PURPOSE,
            "categories": BUSINESS_PROMPT_CATEGORIES,
            **question_params,
            **excluded_params,
        },
    )


def upgrade() -> None:
    if not _column_exists("prompt_templates", "business_purpose"):
        op.add_column(
            "prompt_templates",
            sa.Column("business_purpose", sa.String(length=100), nullable=True),
        )
    if not _index_exists("idx_prompt_templates_business_purpose"):
        op.create_index(
            "idx_prompt_templates_business_purpose",
            "prompt_templates",
            ["business_purpose"],
        )
    _backfill_business_purpose()


def downgrade() -> None:
    if _index_exists("idx_prompt_templates_business_purpose"):
        op.drop_index("idx_prompt_templates_business_purpose", table_name="prompt_templates")
    if _column_exists("prompt_templates", "business_purpose"):
        op.drop_column("prompt_templates", "business_purpose")
