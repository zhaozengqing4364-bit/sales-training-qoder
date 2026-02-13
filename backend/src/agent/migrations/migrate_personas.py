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
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.session import AsyncSessionLocal, init_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


# Persona configuration mapping from simple_handler.py
# Maps old persona IDs to new database-friendly configurations
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
            "typical_questions": ["说重点！", "这能给我带来什么？"]
        }
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
            "typical_questions": ["有什么证据？", "能证明吗？"]
        }
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
            "typical_questions": ["太贵了", "能便宜点吗？"]
        }
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
            "typical_questions": ["技术栈是什么？", "怎么实现的？"]
        }
    }
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
        "knowledge_retrieval": {"enabled": True}
    }
}


async def get_system_prompt(persona_id: str) -> str:
    """Get system prompt from simple_handler.py PERSONA_CONFIG"""
    from sales_bot.websocket.simple_handler import PERSONA_CONFIG
    
    config = PERSONA_CONFIG.get(persona_id, {})
    return config.get("system_prompt", "")


async def migrate_personas(db: AsyncSession) -> dict:
    """
    Migrate hardcoded personas to database.
    
    Returns:
        dict: Migration results with created/skipped counts
    """
    from agent.models import Agent, AgentPersona, Persona, AgentStatus, PersonaStatus
    
    results = {
        "agent_created": False,
        "agent_id": None,
        "personas_created": 0,
        "personas_skipped": 0,
        "links_created": 0,
        "errors": []
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
                created_by="system"
            )
            db.add(agent)
            await db.flush()
            await db.refresh(agent)
            results["agent_created"] = True
            logger.info(f"Created default Agent: {agent.name} ({agent.id})")
        else:
            logger.info(f"Agent '{agent.name}' already exists, skipping creation")
        
        results["agent_id"] = agent.id
        
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
                # Get system prompt from simple_handler
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
                    created_by="system"
                )
                db.add(persona)
                await db.flush()
                await db.refresh(persona)
                results["personas_created"] += 1
                logger.info(f"Created Persona: {persona.name} ({persona.id})")
            
            # Step 3: Link persona to agent if not already linked
            link_stmt = select(AgentPersona).where(
                AgentPersona.agent_id == agent.id,
                AgentPersona.persona_id == persona.id
            )
            link_result = await db.execute(link_stmt)
            existing_link = link_result.scalar_one_or_none()
            
            if not existing_link:
                link = AgentPersona(
                    agent_id=agent.id,
                    persona_id=persona.id,
                    display_order=display_order,
                    is_default=is_first  # First persona is default
                )
                db.add(link)
                results["links_created"] += 1
                logger.info(f"Linked Persona '{persona.name}' to Agent '{agent.name}'")
                is_first = False
            else:
                logger.info(f"Link already exists for Persona '{persona.name}'")
            
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


async def main():
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
