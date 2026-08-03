"""Fix business etiquette question generation prompt seed.

Revision ID: 20260616_086
Revises: 20260615_085
Create Date: 2026-06-16 00:00:00.000000
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260616_086"
down_revision: str | None = "20260615_085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BUSINESS_ETIQUETTE_QUESTION_PURPOSE = "business_etiquette_question_generation"
LEGACY_AI_COACH_QUESTION_PROMPT_NAME = "新人训练路径商务技巧 AI 教练题目生成 v1"
QUESTION_PROMPT_NAME = "商务礼仪题目草稿生成 v1"
QUESTION_PROMPT_TEMPLATE = """你是商务礼仪新人训练题目草稿生成器。请严格基于章节原文生成题目，不要编造教材外知识。

训练包：{{ training_pack_key }}
训练包版本：{{ training_pack_revision_no }}
文章标题：{{ book_title }}
当前章节：第 {{ chapter_order }} 章 {{ chapter_title }}
章节 ID：{{ chapter_id }}

【章节原文】
{{ chapter_content }}

【能力点】
{{ capabilities_json }}

【能力点 key】
{{ capability_keys_json }}

【本次要求】
- 生成数量：{{ draft_count }}
- 允许题型：{{ question_types_json }}
- 语言：{{ language }}
- 审核规则：{{ review_policy }}
- 操作原因：{{ reason }}

【输出要求】
只输出合法 JSON，不要输出 Markdown，不要输出解释性正文。JSON 必须满足以下 schema：
{{ output_schema }}

每道题必须：
1. 明确引用章节原文或 source_excerpt。
2. 单选题必须有 options 和 correct_answer。
3. 多选题必须有 options 和 correct_answers。
4. 简答题必须有 reference_answer。
5. capability_keys 只能使用上方能力点 key。"""
QUESTION_PROMPT_VARIABLES = [
    "training_pack_key",
    "training_pack_revision_no",
    "book_title",
    "chapter_order",
    "chapter_title",
    "chapter_id",
    "chapter_content",
    "capabilities_json",
    "capability_keys_json",
    "draft_count",
    "question_types_json",
    "language",
    "review_policy",
    "reason",
    "output_schema",
]


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def _json_expr(dialect_name: str) -> str:
    if dialect_name == "postgresql":
        return "CAST(:variables AS JSONB)"
    return ":variables"


def _id_expr(dialect_name: str) -> str:
    if dialect_name == "postgresql":
        return "CAST(:id AS uuid)"
    return ":id"


def _upsert_question_prompt() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    variable_expr = _json_expr(dialect_name)
    variables = json.dumps(QUESTION_PROMPT_VARIABLES, ensure_ascii=False)

    bind.execute(
        sa.text(
            f"""
            UPDATE prompt_templates
            SET
                name = :name,
                prompt_type = 'scoring',
                business_purpose = :purpose,
                category = 'business_etiquette',
                template = :template,
                variables = {variable_expr},
                is_active = true,
                is_default = false,
                is_system = true,
                updated_at = CURRENT_TIMESTAMP
            WHERE business_purpose = :purpose
              AND (
                name = :legacy_name
                OR template LIKE :interaction_marker
                OR template LIKE :allowed_interaction_marker
              )
            """
        ),
        {
            "name": QUESTION_PROMPT_NAME,
            "purpose": BUSINESS_ETIQUETTE_QUESTION_PURPOSE,
            "template": QUESTION_PROMPT_TEMPLATE,
            "variables": variables,
            "legacy_name": LEGACY_AI_COACH_QUESTION_PROMPT_NAME,
            "interaction_marker": "%ai_coach_interaction_v1%",
            "allowed_interaction_marker": "%allowed_interaction_types%",
        },
    )

    existing = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM prompt_templates
            WHERE business_purpose = :purpose
              AND is_active = true
              AND template NOT LIKE :interaction_marker
            """
        ),
        {
            "purpose": BUSINESS_ETIQUETTE_QUESTION_PURPOSE,
            "interaction_marker": "%ai_coach_interaction_v1%",
        },
    ).scalar()
    if int(existing or 0) > 0:
        return

    bind.execute(
        sa.text(
            f"""
            INSERT INTO prompt_templates (
                id, name, prompt_type, business_purpose, category, template, variables,
                is_active, is_default, is_system
            )
            VALUES (
                {_id_expr(dialect_name)}, :name, 'scoring', :purpose,
                'business_etiquette', :template, {variable_expr},
                true, false, true
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "name": QUESTION_PROMPT_NAME,
            "purpose": BUSINESS_ETIQUETTE_QUESTION_PURPOSE,
            "template": QUESTION_PROMPT_TEMPLATE,
            "variables": variables,
        },
    )


def upgrade() -> None:
    if not _table_exists("prompt_templates"):
        return
    if not _column_exists("prompt_templates", "business_purpose"):
        return
    _upsert_question_prompt()


def downgrade() -> None:
    # Data repair is intentionally non-destructive on downgrade. Removing the
    # corrected system template would reintroduce the broken operator path.
    return
