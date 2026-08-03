"""Prompt template governance constraints and data repair.

Revision ID: 20260615_084
Revises: 20260614_083
Create Date: 2026-06-15 00:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260615_084"
down_revision: str | None = "20260614_083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ALLOWED_PROMPT_TYPES = {
    "summary",
    "system",
    "system_prompt",
    "extraction",
    "scoring",
    "realtime_scoring",
    "stage",
    "fuzzy_detection",
    "interruption",
    "tracking",
    "welcome",
    "evaluation",
    "report",
}


SYSTEM_TEMPLATE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Sales Conversation Summary": {
        "name": "销售对话总结",
        "template": (
            "请分析这段销售对话，并输出结构化总结。\n\n"
            "**客户人格**：{persona}\n"
            "**总轮次**：{turn_count}\n\n"
            "**对话记录**：\n{transcript}\n\n"
            "**过程指标**：\n"
            "- AI 打断用户次数：{bot_interruptions}\n"
            "- 模糊表达命中次数：{vagueness_count}\n"
            "- 平均挑战等级：{avg_challenge}/5\n\n"
            "{format_instructions}\n\n"
            "请客观评价销售人员表现，保留输出格式要求。"
        ),
    },
    "Default Sales Persona": {
        "name": "默认销售客户人格",
        "template": (
            "你是一位有挑战性的销售对话客户。你保持怀疑，会提出尖锐但真实的问题。"
            "回答应简洁、自然，并符合真实客户沟通方式。"
        ),
    },
    "PPT Point Extraction": {
        "name": "PPT 要点提取",
        "template": (
            "请分析这页 PPT，并识别演讲时必须覆盖的要点。\n\n"
            "**页面标题**：{title}\n\n"
            "**页面内容**：\n{content}\n\n"
            "**页面上下文**：这是一页 {page_context} 类型页面。\n\n"
            "你的任务：\n"
            "1. 识别 3-5 个演讲时必须覆盖的关键表达点\n"
            "2. 识别应被提到的关键概念\n"
            "3. 定义这一页的讲解成功标准\n\n"
            "{format_instructions}\n\n"
            "请输出可执行、具体的演讲要点。"
        ),
    },
    "Realtime Scoring Rules": {
        "name": "销售实时评分规则",
        "template": (
            "从 5 个维度评价用户表现：专业度、沟通技巧、销售流程、异议处理、成交能力。\n\n"
            "评分规则：\n"
            "- 专业度：关注数据、证据、研究、统计、报告，避免空泛表达。\n"
            "- 沟通技巧：鼓励使用“您”“请问”“理解”“明白”“感谢”等礼貌表达，避免负面话术。\n"
            "- 销售流程：关注“需求”“方案”“价值”“优势”“下一步”等关键词。\n"
            "- 异议处理：关注“理解您的顾虑”“确实”“同时”“不过”等承接表达。\n"
            "- 成交能力：关注“合作”“开始”“签约”“确认”“行动”等推进词。"
        ),
    },
    "Sales Stage Definition": {
        "name": "销售阶段定义",
        "template": (
            "请根据对话识别当前销售阶段。\n\n"
            "阶段定义：\n"
            "1. opening - 开场破冰（关键词：你好、介绍、了解、认识）\n"
            "2. discovery - 需求挖掘（关键词：需求、问题、痛点、挑战、目标）\n"
            "3. presentation - 方案呈现（关键词：方案、产品、功能、价值、优势）\n"
            "4. objection - 异议处理（关键词：但是、担心、价格、竞品、考虑）\n"
            "5. closing - 促成成交（关键词：合作、签约、下一步、决定、购买）"
        ),
    },
    "Fuzzy Detection - Uncertain": {
        "name": "销售不确定表达检测",
        "template": "不确定表达词：大概、可能、也许、应该、估计、好像。\n\n建议：请给出具体数据或明确表态。",
    },
    "Fuzzy Detection - Filler": {
        "name": "销售填充词检测",
        "template": "填充词：嗯、那个、就是说、然后、这个。\n\n建议：减少填充词，保持表达流畅。",
    },
    "Fuzzy Detection - Vague Number": {
        "name": "销售模糊数字检测",
        "template": "模糊数字词：差不多、左右、大约、大致、基本上。\n\n建议：请给出精确数值或具体范围。",
    },
    "Interruption Detection Rules": {
        "name": "PPT 打断判断规则",
        "template": (
            "打断触发条件：\n"
            "1. 命中当前上下文中的禁用词\n"
            "2. 遗漏必须讲到的关键点\n"
            "3. 出现类似“太笼统了”的模糊表达\n\n"
            "动作：用具体反馈打断用户，并说明需要修正的点。"
        ),
    },
    "Interruption Feedback - Vague": {
        "name": "PPT 模糊表达打断反馈",
        "template": "这里太笼统了，请补充更具体的细节。",
    },
    "Point Tracking Configuration": {
        "name": "PPT 要点跟踪配置",
        "template": (
            "要点跟踪算法：\n"
            "1. 精确短语匹配（最高置信度）\n"
            "2. 基于 Jaccard 相似度的关键词重合度\n"
            "3. 基于向量的余弦相似度（仅异步模式）\n\n"
            "阈值：POINT_TRACKER_EXACT_THRESHOLD、POINT_TRACKER_KEYWORD_THRESHOLD、POINT_TRACKER_EMBEDDING_THRESHOLD。"
        ),
    },
    "Welcome Message 1": {"name": "销售欢迎话术 1"},
    "Welcome Message 2": {"name": "销售欢迎话术 2"},
    "Welcome Message 3": {"name": "销售欢迎话术 3"},
}


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index["name"] == name for index in inspector.get_indexes("prompt_templates")) or any(
        index["name"] == name for index in inspector.get_indexes("scenario_prompts")
    )


def _normalize_variables(value: Any) -> tuple[list[str], bool]:
    if value is None:
        return [], True
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return [], False
    if isinstance(value, dict):
        return [str(key).strip() for key in value.keys() if str(key).strip()], True
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                candidate = item.strip()
            elif isinstance(item, dict) and str(item.get("name", "")).strip():
                candidate = str(item["name"]).strip()
            else:
                return [], False
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized, True
    return [], False


def _json_update_sql(dialect_name: str) -> str:
    if dialect_name == "postgresql":
        return "CAST(:variables AS JSONB)"
    return ":variables"


def _repair_variables_and_types() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    variable_expr = _json_update_sql(dialect_name)
    rows = bind.execute(
        sa.text(
            "SELECT id, name, prompt_type, variables, is_active, is_default "
            "FROM prompt_templates"
        )
    ).mappings()

    for row in rows:
        variables, can_repair_variables = _normalize_variables(row["variables"])
        prompt_type_valid = str(row["prompt_type"] or "") in ALLOWED_PROMPT_TYPES
        if can_repair_variables and prompt_type_valid:
            bind.execute(
                sa.text(
                    "UPDATE prompt_templates "
                    f"SET variables = {variable_expr}, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = :id"
                ),
                {"id": row["id"], "variables": json.dumps(variables, ensure_ascii=False)},
            )
            continue

        bind.execute(
            sa.text(
                "UPDATE prompt_templates "
                f"SET variables = {variable_expr}, is_active = false, is_default = false, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = :id"
            ),
            {"id": row["id"], "variables": json.dumps(variables, ensure_ascii=False)},
        )


def _localize_system_templates() -> None:
    bind = op.get_bind()
    for old_name, patch in SYSTEM_TEMPLATE_TRANSLATIONS.items():
        params = {"old_name": old_name, "new_name": patch["name"]}
        sql = "UPDATE prompt_templates SET name = :new_name"
        if "template" in patch:
            sql += ", template = :template"
            params["template"] = patch["template"]
        sql += ", updated_at = CURRENT_TIMESTAMP WHERE name = :old_name AND is_system = true"
        bind.execute(sa.text(sql), params)


def _deduplicate_defaults() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, prompt_type, updated_at, created_at "
                "FROM prompt_templates WHERE is_default = true"
            )
        ).mappings()
    )
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_type.setdefault(str(row["prompt_type"]), []).append(dict(row))

    def sort_key(row: dict[str, Any]) -> tuple[Any, Any, str]:
        updated_at = row.get("updated_at") or datetime.min
        created_at = row.get("created_at") or datetime.min
        return updated_at, created_at, str(row.get("id") or "")

    for prompt_type, items in by_type.items():
        if len(items) <= 1:
            continue
        keep = max(items, key=sort_key)
        bind.execute(
            sa.text(
                "UPDATE prompt_templates SET is_default = false, updated_at = CURRENT_TIMESTAMP "
                "WHERE prompt_type = :prompt_type AND id <> :keep_id AND is_default = true"
            ),
            {"prompt_type": prompt_type, "keep_id": keep["id"]},
        )


def _create_active_scenario_binding_index() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    predicate = "is_active = true" if dialect_name == "postgresql" else "is_active = 1"
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_prompts_active_scope "
            "ON scenario_prompts (scenario_type, COALESCE(scenario_id, ''), prompt_type) "
            f"WHERE {predicate}"
        )
    )


def _drop_active_scenario_binding_index() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_scenario_prompts_active_scope"))


def upgrade() -> None:
    _repair_variables_and_types()
    _localize_system_templates()
    _deduplicate_defaults()

    if not _index_exists("uq_prompt_templates_default_per_type"):
        op.create_index(
            "uq_prompt_templates_default_per_type",
            "prompt_templates",
            ["prompt_type"],
            unique=True,
            postgresql_where=sa.text("is_default = true"),
            sqlite_where=sa.text("is_default = 1"),
        )

    if not _index_exists("uq_scenario_prompts_active_scope"):
        _create_active_scenario_binding_index()


def downgrade() -> None:
    _drop_active_scenario_binding_index()
    if _index_exists("uq_prompt_templates_default_per_type"):
        op.drop_index("uq_prompt_templates_default_per_type", table_name="prompt_templates")
