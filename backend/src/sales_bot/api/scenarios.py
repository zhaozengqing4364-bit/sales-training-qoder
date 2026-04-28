"""Sales scenario APIs for listing scenarios and available personas."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona
from agent.services.industry_pack_contract import (
    build_persona_runtime_binding_summary,
    build_sales_scenario_runtime_contract,
)
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import Scenario, User
from common.db.session import get_db

router = APIRouter()


def _extract_persona_characteristics(traits: Any) -> list[str]:
    """Normalize persona traits into frontend-friendly characteristic strings."""
    if isinstance(traits, dict):
        items = [
            f"{key}: {value}"
            for key, value in traits.items()
            if isinstance(key, str) and str(key).strip() and value is not None
        ]
        if items:
            return items

    if isinstance(traits, list):
        return [
            str(item).strip()
            for item in traits
            if isinstance(item, str) and item.strip()
        ]

    return []


@router.get("/scenarios")
async def list_scenarios(
    scenario_type: str = Query(
        None, description="Filter by scenario type: 'presentation' or 'sales'"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List available practice scenarios

    Returns:
        List of scenarios with their configurations
    """
    try:
        query = select(Scenario).where(Scenario.is_active.is_(True))

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

    except (SQLAlchemyError, RuntimeError, ValueError, OSError) as e:
        return build_server_error(
            "[SCENARIOS_LIST_FAILED]",
            message="Failed to list scenarios",
            exc=e,
            scenario_type=scenario_type,
        )


@router.get("/scenarios/sales/runtime-contract")
async def get_sales_runtime_contract(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Expose how sales scenarios compose persona/customer-pressure/knowledge runtime truth."""
    del current_user, db
    return build_sales_scenario_runtime_contract()


@router.get("/scenarios/sales/personas")
async def list_sales_personas(
    agent_id: str | None = Query(None, description="Optional agent ID filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List available sales personas for practice

    Returns:
        List of persona configurations with descriptions
    """
    try:
        stmt = (
            select(Persona, AgentPersona.display_order)
            .join(AgentPersona, AgentPersona.persona_id == Persona.id)
            .join(Agent, Agent.id == AgentPersona.agent_id)
            .where(
                Agent.category == "sales",
                Agent.status == "published",
                Persona.status == "active",
                Persona.is_public.is_(True),
            )
            .order_by(AgentPersona.display_order.asc(), Persona.created_at.asc())
        )

        if agent_id:
            stmt = stmt.where(Agent.id == agent_id)

        result = await db.execute(stmt)
        rows = result.all()

        unique_personas: dict[str, dict[str, Any]] = {}
        for persona, _display_order in rows:
            if persona.id in unique_personas:
                continue

            unique_personas[persona.id] = {
                "id": persona.id,
                "name": persona.name,
                "description": persona.description or "",
                "characteristics": _extract_persona_characteristics(persona.traits),
                "difficulty": persona.difficulty,
                "runtime_binding": build_persona_runtime_binding_summary(persona),
            }

        return list(unique_personas.values())

    except (SQLAlchemyError, RuntimeError, ValueError, OSError) as e:
        return build_server_error(
            "[SALES_PERSONAS_LIST_FAILED]",
            message="Failed to list sales personas",
            exc=e,
            agent_id=agent_id,
        )


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
            "created_at": scenario.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except (RuntimeError, ValueError, OSError) as e:
        return build_server_error(
            "[SCENARIO_LOAD_FAILED]",
            message="Failed to load scenario",
            exc=e,
            scenario_id=scenario_id,
        )
