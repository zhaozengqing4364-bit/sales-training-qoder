from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, Persona
from common.knowledge.contributors import register_knowledge_reference_checker

AGENT_KNOWLEDGE_REFERENCE_CHECKER = "agent.knowledge_reference_checker"


def _orm_field(row: object, name: str) -> object:
    return getattr(row, name)


def _orm_str(row: object, name: str) -> str:
    return str(_orm_field(row, name))


def _orm_str_list(row: object, name: str) -> list[str]:
    value = _orm_field(row, name)
    return list(value) if isinstance(value, list) else []


async def check_agent_knowledge_references(
    db: AsyncSession,
    kb_id: str,
) -> str | None:
    agent_result = await db.execute(select(Agent))
    agents = agent_result.scalars().all()
    referencing_agents = [
        agent
        for agent in agents
        if kb_id in _orm_str_list(agent, "default_knowledge_base_ids")
    ]
    if referencing_agents:
        names = ", ".join(_orm_str(agent, "name") for agent in referencing_agents[:3])
        return f"Referenced by Agents: {names}"

    persona_result = await db.execute(select(Persona))
    personas = persona_result.scalars().all()
    referencing_personas = [
        persona
        for persona in personas
        if kb_id in _orm_str_list(persona, "knowledge_base_ids")
    ]
    if referencing_personas:
        names = ", ".join(
            _orm_str(persona, "name") for persona in referencing_personas[:3]
        )
        return f"Referenced by Personas: {names}"

    return None


def register_agent_knowledge_contributor() -> None:
    register_knowledge_reference_checker(
        AGENT_KNOWLEDGE_REFERENCE_CHECKER,
        check_agent_knowledge_references,
    )
