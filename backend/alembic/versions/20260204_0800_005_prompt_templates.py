"""Prompt Templates Migration

Creates tables for prompt configuration:
- prompt_templates: Reusable prompt templates (summary, extraction, scoring, etc.)
- scenario_prompts: Scenario-specific prompt template assignments

Imports 14 default system prompts from hardcoded codebase locations.

Revision ID: 005_prompt_templates
Revises: 3752e148c0de
Create Date: 2026-02-04 08:00:00.000000

Requirements: B1 - Create prompt templates database tables
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "3752e148c0de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create prompt_templates and scenario_prompts tables with default data."""

    # 1. Create prompt_templates table
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default="common"),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_prompt_templates_type", "prompt_templates", ["prompt_type"])
    op.create_index("idx_prompt_templates_category", "prompt_templates", ["category"])

    # 2. Create scenario_prompts table
    op.create_table(
        "scenario_prompts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("scenario_id", sa.String(255), nullable=True),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 3. Insert 14 default system prompts
    # From: sales_bot/services/summary_service.py:27
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Sales Conversation Summary',
            'summary',
            'sales',
            'Analyze this sales conversation and provide a summary.\n\n**Persona**: {persona}\n**Total Turns**: {turn_count}\n\n**Conversation Transcript**:\n{transcript}\n\n**Metrics**:\n- Bot Interruptions: {bot_interruptions} (AI interrupted user)\n- Vagueness Detected: {vagueness_count} times\n- Average Challenge Level: {avg_challenge}/5\n\n{format_instructions}\n\nProvide an objective assessment of salesperson''s performance.',
            '["persona", "turn_count", "transcript", "bot_interruptions", "vagueness_count", "avg_challenge", "format_instructions"]',
            true,
            true,
            true
        )
    """)

    # From: common/config.py:186
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Default Sales Persona',
            'system_prompt',
            'sales',
            'You are a challenging customer in a sales conversation. You are skeptical and ask tough questions. Keep responses concise and realistic.',
            '[]',
            true,
            true,
            true
        )
    """)

    # From: presentation_coach/services/point_extraction.py:42
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'PPT Point Extraction',
            'extraction',
            'presentation',
            'Analyze this PPT slide and identify required talking points.\n\n**Slide Title**: {title}\n\n**Slide Content**:\n{content}\n\n**Context**: This is a {page_context} slide.\n\nYour task:\n1. Identify 3-5 key talking points that MUST be covered when presenting this slide\n2. Identify key concepts that should be mentioned\n3. Define success criteria for this slide\n\n{format_instructions}\n\nProvide actionable, specific talking points.',
            '["title", "content", "page_context", "format_instructions"]',
            true,
            true,
            true
        )
    """)

    # From: agent/capabilities/realtime_scoring.py:52
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Realtime Scoring Rules',
            'scoring',
            'sales',
            'Score the user''s performance on 5 dimensions: 专业度, 沟通技巧, 销售流程, 异议处理, 成交能力.\n\nScoring Rules:\n- 专业度: Look for data, evidence, research, statistics, reports. Penalize vague language.\n- 沟通技巧: Use polite language like "您", "请问", "理解", "明白", "感谢". Avoid negative phrases.\n- 销售流程: Look for keywords like "需求", "方案", "价值", "优势", "下一步".\n- 异议处理: Use understanding phrases like "理解您的顾虑", "确实", "同时", "不过".\n- 成交能力: Look for action words like "合作", "开始", "签约", "确认", "行动".',
            '[]',
            true,
            true,
            true
        )
    """)

    # From: agent/capabilities/sales_stage.py:39
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Sales Stage Definition',
            'stage',
            'sales',
            'Identify current sales stage from conversation.\n\nStages:\n1. opening - 开场破冰 (keywords: 你好, 介绍, 了解, 认识)\n2. discovery - 需求挖掘 (keywords: 需求, 问题, 痛点, 挑战, 目标)\n3. presentation - 方案呈现 (keywords: 方案, 产品, 功能, 价值, 优势)\n4. objection - 异议处理 (keywords: 但是, 担心, 价格, 竞品, 考虑)\n5. closing - 促成成交 (keywords: 合作, 签约, 下一步, 决定, 购买)',
            '[]',
            true,
            true,
            true
        )
    """)

    # From: agent/capabilities/fuzzy_detection.py:56
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Fuzzy Detection - Uncertain',
            'fuzzy_detection',
            'sales',
            'Uncertain words: 大概, 可能, 也许, 应该, 估计, 好像.\n\nSuggestion: 请给出具体数据或明确表态.',
            '[]',
            true,
            true,
            true
        )
    """)

    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Fuzzy Detection - Filler',
            'fuzzy_detection',
            'sales',
            'Filler words: 嗯+, 那个, 就是说, 然后, 这个.\n\nSuggestion: 减少填充词，保持表达流畅.',
            '[]',
            true,
            true,
            true
        )
    """)

    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Fuzzy Detection - Vague Number',
            'fuzzy_detection',
            'sales',
            'Vague number words: 差不多, 左右, 大约, 大致, 基本上.\n\nSuggestion: 请给出精确数值或具体范围.',
            '[]',
            true,
            true,
            true
        )
    """)

    # From: presentation_coach/services/interruption_detector.py:25
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Interruption Detection Rules',
            'interruption',
            'presentation',
            'Interruption triggers:\n1. Forbidden words from context\n2. Missing required points\n3. Vague responses like "that''s too vague"\n\nAction: Interrupt user with specific feedback.',
            '[]',
            true,
            true,
            true
        )
    """)

    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Interruption Feedback - Vague',
            'interruption',
            'presentation',
            'That''s too vague. Could you provide more specific details?',
            '[]',
            true,
            true,
            true
        )
    """)

    # From: presentation_coach/services/point_tracker.py:18
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Point Tracking Configuration',
            'tracking',
            'presentation',
            'Point tracking algorithm:\n1. Exact phrase matching (highest confidence)\n2. Keyword overlap with Jaccard similarity\n3. Embedding-based cosine similarity (async mode only)\n\nThresholds: POINT_TRACKER_EXACT_THRESHOLD, POINT_TRACKER_KEYWORD_THRESHOLD, POINT_TRACKER_EMBEDDING_THRESHOLD.',
            '[]',
            true,
            true,
            true
        )
    """)

    # Additional common prompts from config.py
    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Welcome Message 1',
            'welcome',
            'sales',
            '你好，我对你们的产品有些兴趣，但也有一些顾虑。',
            '[]',
            true,
            false,
            true
        )
    """)

    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Welcome Message 2',
            'welcome',
            'sales',
            '我想了解一下你们的解决方案，不过时间有限。',
            '[]',
            true,
            false,
            true
        )
    """)

    op.execute("""
        INSERT INTO prompt_templates (name, prompt_type, category, template, variables, is_active, is_default, is_system)
        VALUES (
            'Welcome Message 3',
            'welcome',
            'sales',
            '听说你们的产品不错，但我需要更多信息。',
            '[]',
            true,
            false,
            true
        )
    """)


def downgrade() -> None:
    """Drop prompt_templates and scenario_prompts tables."""

    # Drop scenario_prompts first (has FK to prompt_templates)
    op.drop_table("scenario_prompts")

    # Drop prompt_templates
    op.drop_index("idx_prompt_templates_category", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_type", table_name="prompt_templates")
    op.drop_table("prompt_templates")
