"""
Migrate Hardcoded Personas to Database

Migrates PERSONA_CONFIG from simple_handler.py to the database.
Creates a default "销售教练" Agent and links migrated Personas.

This script is idempotent - safe to run multiple times.

Usage:
    python -m agent.migrations.migrate_personas

References:
- Requirements: R13 (Database Migration)
- Design: Section 22 (Hardcoded Persona Migration)
"""

import asyncio
import os
import sys
from typing import Any, TypedDict, cast

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import AsyncSessionLocal, init_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class MigrationResults(TypedDict):
    agent_created: bool
    agent_id: str | None
    personas_created: int
    personas_skipped: int
    links_created: int
    errors: list[str]


# Persona configuration mapping copied from the legacy sales persona seed.
# Keep this migration self-contained so deleting legacy websocket handlers does
# not break historical persona bootstrap flows.
PERSONA_CONFIG_MAPPING = {
    "impatient_ceo": {
        "name": "急躁的CEO",
        "description": "时间非常宝贵，没有耐心听长篇大论，经常打断对方要求说重点",
        "icon": "😤",
        "category": "customer",
        "difficulty": "hard",
        "traits": {"性格": "急躁、直接", "关注点": "效率、结果"},
        "behavior_config": {
            "response_length": "short",
            "challenge_frequency": 0.9,
            "interruption_triggers": ["啰嗦", "长篇大论"],
            "typical_questions": ["说重点！", "这能给我带来什么？"],
        },
        "system_prompt": """你是一个急躁的CEO，正在与销售人员对话。

【角色特点】
- 时间宝贵，没耐心听废话
- 只关心：能解决什么问题？带来多少收益？
- 常用语："说重点！"、"我没时间"、"所以呢？"

【回复规范】
- 每次回复不超过30字
- 语气直接、不客气
- 如果对方啰嗦，直接打断

【禁止】
- 不要长篇分析
- 不要给建议
- 不要解释你是AI""",
    },
    "skeptical_buyer": {
        "name": "怀疑的采购",
        "description": "对任何承诺都持怀疑态度，经常要求提供证据、案例、数据支持",
        "icon": "🤔",
        "category": "customer",
        "difficulty": "hard",
        "traits": {"性格": "怀疑、谨慎", "关注点": "证据、数据"},
        "behavior_config": {
            "response_length": "medium",
            "challenge_frequency": 0.8,
            "interruption_triggers": ["竞品", "证据", "案例"],
            "typical_questions": ["有什么证据？", "能证明吗？"],
        },
        "system_prompt": """你是一个怀疑一切的采购经理，正在与销售人员对话。

【角色特点】
- 对任何承诺都持怀疑态度
- 需要证据、案例、数据才会相信
- 常用语："有数据吗？"、"能证明吗？"、"听起来太好了"

【回复规范】
- 每次回复不超过40字
- 语气质疑但礼貌
- 不断追问细节和证据

【禁止】
- 不要轻易认可对方
- 不要长篇大论
- 不要跳出角色""",
    },
    "price_focused": {
        "name": "价格敏感型",
        "description": "只关心价格，总是想要折扣，不断压价",
        "icon": "💰",
        "category": "customer",
        "difficulty": "medium",
        "traits": {"性格": "精明、计较", "关注点": "价格、折扣"},
        "behavior_config": {
            "response_length": "short",
            "challenge_frequency": 0.7,
            "interruption_triggers": ["价格", "费用", "成本"],
            "typical_questions": ["太贵了", "能便宜点吗？"],
        },
        "system_prompt": """你是一个非常关注价格的采购经理，正在与销售人员对话。

【角色特点】
- 只关心价格，总想要折扣
- 对价值不感兴趣，只看价格
- 常用语："太贵了"、"别家更便宜"、"能打几折？"

【回复规范】
- 每次回复不超过30字
- 语气精明、会砍价
- 不断压价、要优惠

【禁止】
- 不要被价值说服
- 不要长篇分析
- 不要跳出角色""",
    },
    "technical_cto": {
        "name": "技术型CTO",
        "description": "对营销话术不感兴趣，只关心技术细节",
        "icon": "🔧",
        "category": "customer",
        "difficulty": "hard",
        "traits": {"性格": "专业、严谨", "关注点": "技术、架构"},
        "behavior_config": {
            "response_length": "medium",
            "challenge_frequency": 0.8,
            "interruption_triggers": ["技术", "架构", "安全"],
            "typical_questions": ["技术栈是什么？", "怎么实现的？"],
        },
        "system_prompt": """你是一个技术背景很强的CTO，正在与销售人员对话。

【角色特点】
- 只关心技术细节，讨厌营销话术
- 会问架构、安全性、可扩展性
- 常用语："具体怎么实现？"、"用什么技术栈？"、"性能指标是多少？"

【回复规范】
- 每次回复不超过40字
- 语气专业、直接
- 追问技术细节

【禁止】
- 不要接受模糊回答
- 不要长篇大论
- 不要跳出角色""",
    },
}


# Default Sales Coach Agent configuration
DEFAULT_AGENT_CONFIG = {
    "name": "销售教练",
    "description": "AI销售练习教练，帮助销售人员提升沟通技巧和销售能力",
    "icon": "🎯",
    "category": "sales",
    "system_prompt": """你是一个专业的销售教练AI，负责帮助销售人员进行模拟练习。
你会扮演不同类型的客户角色，与销售人员进行对话练习。
在练习过程中，你会根据销售人员的表现给出实时反馈和建议。""",
    "welcome_message": "欢迎来到销售练习！请选择一个客户角色开始练习。",
    "capabilities_config": {
        "fuzzy_detection": {"enabled": True},
        "sales_stage": {"enabled": True},
        "realtime_scoring": {"enabled": True},
        "knowledge_retrieval": {"enabled": True},
    },
}


async def get_system_prompt(persona_id: str) -> str:
    """Get system prompt from the self-contained migration persona config."""
    config = PERSONA_CONFIG_MAPPING.get(persona_id, {})
    return str(config.get("system_prompt", ""))


async def migrate_personas(db: AsyncSession) -> MigrationResults:
    """
    Migrate hardcoded personas to database.

    Returns:
        dict: Migration results with created/skipped counts
    """
    from agent.models import Agent, AgentPersona, AgentStatus, Persona, PersonaStatus

    results: MigrationResults = {
        "agent_created": False,
        "agent_id": None,
        "personas_created": 0,
        "personas_skipped": 0,
        "links_created": 0,
        "errors": [],
    }

    try:
        # Step 1: Create or get default Sales Coach Agent
        agent_stmt = select(Agent).where(Agent.name == DEFAULT_AGENT_CONFIG["name"])
        agent_result = await db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            agent = Agent(
                name=DEFAULT_AGENT_CONFIG["name"],
                description=DEFAULT_AGENT_CONFIG["description"],
                icon=DEFAULT_AGENT_CONFIG["icon"],
                category=DEFAULT_AGENT_CONFIG["category"],
                system_prompt=DEFAULT_AGENT_CONFIG["system_prompt"],
                welcome_message=DEFAULT_AGENT_CONFIG["welcome_message"],
                capabilities_config=DEFAULT_AGENT_CONFIG["capabilities_config"],
                status=AgentStatus.PUBLISHED.value,
                created_by="system",
            )
            db.add(agent)
            await db.flush()
            await db.refresh(agent)
            results["agent_created"] = True
            logger.info(f"Created default Agent: {agent.name} ({agent.id})")
        else:
            logger.info(f"Agent '{agent.name}' already exists, skipping creation")

        agent_id = str(cast(Any, agent.id))
        agent_name = str(cast(Any, agent.name))
        results["agent_id"] = agent_id

        # Step 2: Migrate each persona
        display_order = 0
        is_first = True

        for old_id, config in PERSONA_CONFIG_MAPPING.items():
            # Check if persona already exists by name
            persona_stmt = select(Persona).where(Persona.name == config["name"])
            persona_result = await db.execute(persona_stmt)
            existing_persona = persona_result.scalar_one_or_none()

            if existing_persona:
                logger.info(f"Persona '{config['name']}' already exists, skipping")
                results["personas_skipped"] += 1
                persona = existing_persona
            else:
                # Get system prompt from the self-contained migration mapping.
                system_prompt = await get_system_prompt(old_id)

                if not system_prompt:
                    error_msg = f"No system_prompt found for persona: {old_id}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
                    continue

                # Create new persona
                persona = Persona(
                    name=config["name"],
                    description=config["description"],
                    icon=config["icon"],
                    category=config["category"],
                    difficulty=config["difficulty"],
                    system_prompt=system_prompt,
                    traits=config["traits"],
                    behavior_config=config["behavior_config"],
                    is_public=True,
                    status=PersonaStatus.ACTIVE.value,
                    created_by="system",
                )
                db.add(persona)
                await db.flush()
                await db.refresh(persona)
                results["personas_created"] += 1
                logger.info(f"Created Persona: {persona.name} ({persona.id})")

            # Step 3: Link persona to agent if not already linked
            persona_id = str(cast(Any, persona.id))
            persona_name = str(cast(Any, persona.name))
            link_stmt = select(AgentPersona).where(
                AgentPersona.agent_id == agent_id,
                AgentPersona.persona_id == persona_id,
            )
            link_result = await db.execute(link_stmt)
            existing_link = link_result.scalar_one_or_none()

            if not existing_link:
                link = AgentPersona(
                    agent_id=agent_id,
                    persona_id=persona_id,
                    display_order=display_order,
                    is_default=is_first,  # First persona is default
                )
                db.add(link)
                results["links_created"] += 1
                logger.info(f"Linked Persona '{persona_name}' to Agent '{agent_name}'")
                is_first = False
            else:
                logger.info(f"Link already exists for Persona '{persona_name}'")

            display_order += 1

        # Commit all changes
        await db.commit()
        logger.info("Migration completed successfully")

    except (RuntimeError, ValueError, OSError) as e:
        await db.rollback()
        error_msg = f"Migration failed: {str(e)}"
        logger.error(error_msg)
        results["errors"].append(error_msg)
        raise

    return results


async def main() -> None:
    """Main entry point for migration script"""
    logger.info("=" * 60)
    logger.info("Persona Migration Script")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()

    # Run migration
    async with AsyncSessionLocal() as db:
        logger.info("Running migration...")
        results = await migrate_personas(db)

    # Log results
    logger.info("=" * 60)
    logger.info("Migration Results")
    logger.info("=" * 60)
    logger.info(f"Agent created: {results['agent_created']}")
    logger.info(f"Agent ID: {results['agent_id']}")
    logger.info(f"Personas created: {results['personas_created']}")
    logger.info(f"Personas skipped: {results['personas_skipped']}")
    logger.info(f"Links created: {results['links_created']}")

    if results["errors"]:
        logger.error("Errors:")
        for error in results["errors"]:
            logger.error(f"  - {error}")

    logger.info("Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())
