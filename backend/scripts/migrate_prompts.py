"""
Migration script for 14 hardcoded prompts to database.

Requirements: B7 - Migrate hardcoded prompts to database

Run: python scripts/migrate_prompts.py
"""

import asyncio
import os
import sys
from uuid import uuid4
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.db.models import PromptTemplate
from prompt_templates.models import PromptType


# 14 system prompts migrated from hardcoded locations
DEFAULT_PROMPTS = [
    {
        "name": "销售对话总结",
        "prompt_type": "summary",
        "category": "sales",
        "template": """请总结以下销售对话：

对话内容：
{{ conversation }}

请从以下几个方面总结：
1. 对话主题和背景
2. 关键决策点
3. 达成的共识
4. 未解决的问题""",
        "variables": ["conversation"],
        "is_default": True,
    },
    {
        "name": "销售系统提示词",
        "prompt_type": "system",
        "category": "sales",
        "template": """你是一位专业的销售培训教练。你的任务是帮助销售人员提升沟通技巧。

当前场景：{{ scenario_name }}
客户画像：{{ customer_persona }}

请扮演客户进行对话，并在对话中提供适当的挑战和反馈。""",
        "variables": ["scenario_name", "customer_persona"],
        "is_default": True,
    },
    {
        "name": "要点提取",
        "prompt_type": "extraction",
        "category": "common",
        "template": """请从以下对话中提取关键要点：

{{ conversation }}

请提取：
1. 客户需求
2. 痛点
3. 预算范围
4. 决策时间
5. 竞争对手提及""",
        "variables": ["conversation"],
        "is_default": True,
    },
    {
        "name": "对话评分",
        "prompt_type": "scoring",
        "category": "sales",
        "template": """请对以下销售对话进行评分（0-100分）：

对话内容：
{{ conversation }}

评分维度：
- communication: 沟通清晰度
- product_knowledge: 产品知识
- problem_solving: 问题解决能力
- customer_focus: 客户导向
- professionalism: 专业度

请以JSON格式返回：{"scores": {"dimension": score}, "feedback": "..."}""",
        "variables": ["conversation"],
        "is_default": True,
    },
    {
        "name": "阶段评判",
        "prompt_type": "stage",
        "category": "sales",
        "template": """请评判销售对话当前阶段：

对话历史：
{{ conversation }}
当前阶段：{{ stage_name }}

请评判：
1. 是否成功完成当前阶段目标
2. 是否可以进入下一阶段
3. 需要改进的地方

返回JSON：{"completed": true/false, "can_advance": true/false, "feedback": "..."}""",
        "variables": ["conversation", "stage_name"],
        "is_default": True,
    },
    {
        "name": "模糊表达检测",
        "prompt_type": "fuzzy_detection",
        "category": "sales",
        "template": """请检测以下销售回答中的模糊表达：

销售回答：
{{ response }}

模糊表达包括：
1. "可能"、"也许"、"大概"等不确定词汇
2. 缺乏具体数据的描述
3. 回避客户问题
4. 过度承诺

返回检测到的模糊表达列表。""",
        "variables": ["response"],
        "is_default": True,
    },
    {
        "name": "打断检测",
        "prompt_type": "interruption",
        "category": "presentation",
        "template": """请分析以下PPT演讲记录，检测不当打断：

演讲记录：
{{ speech_record }}

不当打断包括：
1. 自我纠正过于频繁
2. 不必要的长停顿
3. 重复同一观点超过2次

返回：{"interruptions": [...], "severity": "low/medium/high"}""",
        "variables": ["speech_record"],
        "is_default": True,
    },
    {
        "name": "要点跟踪",
        "prompt_type": "tracking",
        "category": "presentation",
        "template": """请跟踪PPT演讲要点覆盖情况：

预期要点：
{{ expected_points }}

实际演讲内容：
{{ actual_speech }}

返回：
1. 已覆盖要点
2. 遗漏要点
3. 额外添加的要点""",
        "variables": ["expected_points", "actual_speech"],
        "is_default": True,
    },
    {
        "name": "欢迎词",
        "prompt_type": "welcome",
        "category": "common",
        "template": """请为{{ scenario_name }}场景生成欢迎词。

场景描述：{{ scenario_description }}
用户角色：{{ user_role }}

要求：
1. 友好专业
2. 简要说明场景目标
3. 引导用户开始
4. 100字以内""",
        "variables": ["scenario_name", "scenario_description", "user_role"],
        "is_default": True,
    },
    {
        "name": "实时评价",
        "prompt_type": "evaluation",
        "category": "sales",
        "template": """请对当前对话回合进行实时评价：

用户输入：{{ user_message }}
AI回复：{{ ai_response }}
对话上下文：{{ context }}

评价维度：
- 回复相关性 (0-100)
- 信息准确性 (0-100)
- 客户导向程度 (0-100)

返回JSON格式评价。""",
        "variables": ["user_message", "ai_response", "context"],
        "is_default": True,
    },
    {
        "name": "综合报告",
        "prompt_type": "report",
        "category": "common",
        "template": """请生成练习综合报告：

练习类型：{{ practice_type }}
会话时长：{{ duration }}分钟
对话轮数：{{ turn_count }}

阶段评价：
{{ stage_evaluations }}

请生成包含以下内容的专业报告：
1. 总体表现评估
2. 关键优势
3. 优先改进项
4. 个性化建议
5. 练习推荐""",
        "variables": ["practice_type", "duration", "turn_count", "stage_evaluations"],
        "is_default": True,
    },
    {
        "name": "PPT系统提示词",
        "prompt_type": "system",
        "category": "presentation",
        "template": """你是一位专业的演讲教练。请帮助用户提升PPT演讲能力。

当前PPT主题：{{ ppt_title }}
页数：{{ page_count }}

你的任务是：
1. 监听用户演讲
2. 识别演讲要点覆盖情况
3. 检测不当打断和口头禅
4. 提供实时反馈和改进建议""",
        "variables": ["ppt_title", "page_count"],
        "is_default": True,
    },
    {
        "name": "内容提取",
        "prompt_type": "extraction",
        "category": "presentation",
        "template": """请从PPT演讲中提取关键信息：

PPT标题：{{ ppt_title }}
演讲内容：
{{ speech_content }}

请提取：
1. 核心观点
2. 关键数据
3. 逻辑结构
4. 演讲亮点
5. 改进建议""",
        "variables": ["ppt_title", "speech_content"],
        "is_default": True,
    },
    {
        "name": "演讲评分",
        "prompt_type": "scoring",
        "category": "presentation",
        "template": """请对PPT演讲进行综合评分：

演讲内容：
{{ speech_content }}
PPT信息：
{{ ppt_info }}

评分维度（0-100分）：
- 内容完整性
- 逻辑清晰度
- 语言表达
- 时间控制
- 要点覆盖

返回JSON格式评分和详细反馈。""",
        "variables": ["speech_content", "ppt_info"],
        "is_default": True,
    },
]


async def migrate_prompts():
    """Migrate hardcoded prompts to database."""
    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")

    engine = create_async_engine(db_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for prompt_data in DEFAULT_PROMPTS:
            # Check if prompt already exists
            result = await session.execute(
                select(PromptTemplate).where(
                    PromptTemplate.name == prompt_data["name"],
                    PromptTemplate.prompt_type == prompt_data["prompt_type"],
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"Skipping existing prompt: {prompt_data['name']}")
                continue

            # Create new prompt
            template = PromptTemplate(
                id=uuid4(),
                name=prompt_data["name"],
                prompt_type=prompt_data["prompt_type"],
                category=prompt_data["category"],
                template=prompt_data["template"],
                variables=prompt_data["variables"],
                is_active=True,
                is_default=prompt_data.get("is_default", False),
                is_system=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(template)
            print(f"Created prompt: {prompt_data['name']}")

        await session.commit()
        print("Migration completed successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_prompts())
