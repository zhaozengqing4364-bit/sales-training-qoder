"""
Sales Scenarios API - Manage sales practice scenarios
Provides endpoints for listing available sales personas and scenarios
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import get_current_user
from common.db.models import Scenario, User
from common.db.session import get_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/scenarios")
async def list_scenarios(
    scenario_type: str = Query(None, description="Filter by scenario type: 'presentation' or 'sales'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List available practice scenarios

    Returns:
        List of scenarios with their configurations
    """
    try:
        query = select(Scenario).where(Scenario.is_active == True)

        if scenario_type:
            query = query.where(Scenario.scenario_type == scenario_type)

        query = query.order_by(Scenario.name)

        result = await db.execute(query)
        scenarios = result.scalars().all()

        # Format response
        response_data = []
        for scenario in scenarios:
            scenario_data = {
                "scenario_id": scenario.scenario_id,
                "scenario_type": scenario.scenario_type,
                "name": scenario.name,
                "description": scenario.description,
                "is_active": scenario.is_active,
            }

            # Add persona-specific info for sales scenarios
            if scenario.scenario_type == "sales" and scenario.persona_prompt:
                scenario_data["persona_prompt"] = scenario.persona_prompt

            response_data.append(scenario_data)

        return response_data

    except Exception as e:
        logger.error(f"Failed to list scenarios: {str(e)}")
        # Return empty list on error instead of throwing
        return []


@router.get("/scenarios/sales/personas")
async def list_sales_personas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List available sales personas for practice

    Returns:
        List of persona configurations with descriptions
    """
    # Hardcoded personas that match the bot service
    personas = [
        {
            "id": "impatient_ceo",
            "name": "急躁 CEO",
            "description": "时间紧迫，对冗长回答缺乏耐心。要求简洁直接的回答。",
            "characteristics": [
                "不喜欢长篇大论",
                "希望快速得到要点",
                "会打断啰嗦的回答",
                "重视效率"
            ],
            "difficulty": "hard"
        },
        {
            "id": "skeptical_buyer",
            "name": "怀疑型买家",
            "description": "质疑一切，需要证据和证明。对夸张的宣传保持怀疑态度。",
            "characteristics": [
                "会问很多问题",
                "要求看到数据支持",
                "不轻易相信承诺",
                "需要详细解释"
            ],
            "difficulty": "medium"
        },
        {
            "id": "price_focused",
            "name": "价格关注者",
            "description": "只关心价格和折扣，对价值不太敏感。",
            "characteristics": [
                "反复询问价格",
                "要求折扣",
                "与竞品比较价格",
                "对价格敏感"
            ],
            "difficulty": "medium"
        },
        {
            "id": "technical_cto",
            "name": "技术型 CTO",
            "description": "询问深度技术问题，需要专业解答。",
            "characteristics": [
                "关注技术细节",
                "询问架构和实现",
                "需要专业术语",
                "重视技术能力"
            ],
            "difficulty": "hard"
        }
    ]

    # Try to get scenarios from database to check which are active
    try:
        result = await db.execute(
            select(Scenario).where(
                Scenario.scenario_type == "sales",
                Scenario.is_active == True
            )
        )
        active_scenarios = result.scalars().all()

        # Filter personas based on active scenarios
        active_persona_ids = [s.name for s in active_scenarios]

        if active_persona_ids:
            personas = [p for p in personas if p["id"] in active_persona_ids]

    except Exception as e:
        logger.warning(f"Could not filter personas from database: {str(e)}")

    return personas


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific scenario"""
    try:
        result = await db.execute(
            select(Scenario).where(Scenario.scenario_id == scenario_id)
        )
        scenario = result.scalar_one_or_none()

        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        return {
            "scenario_id": scenario.scenario_id,
            "scenario_type": scenario.scenario_type,
            "name": scenario.name,
            "description": scenario.description,
            "persona_prompt": scenario.persona_prompt,
            "is_active": scenario.is_active,
            "created_at": scenario.created_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scenario: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load scenario")
