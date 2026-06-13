from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona
from agent.models import Persona as AgentPersonaModel
from common.services.practice_session_ports import (
    PracticeSessionPortError,
    register_agent_persona_pair_validator,
)


async def validate_agent_persona_pair(
    db: AsyncSession,
    agent_id_str: str | None,
    persona_id_str: str | None,
) -> dict[str, Any] | None:
    if not (agent_id_str and persona_id_str):
        return None

    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id_str))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise PracticeSessionPortError("[AGENT_NOT_FOUND]", status_code=404)
    if agent.status == "archived":
        raise PracticeSessionPortError("[AGENT_ARCHIVED]", status_code=400)
    if agent.status != "published":
        raise PracticeSessionPortError("[AGENT_NOT_PUBLISHED]", status_code=400)

    persona_result = await db.execute(
        select(AgentPersonaModel).where(AgentPersonaModel.id == persona_id_str)
    )
    persona_obj = persona_result.scalar_one_or_none()
    if not persona_obj:
        raise PracticeSessionPortError("[PERSONA_NOT_FOUND]", status_code=404)
    if persona_obj.status != "active":
        raise PracticeSessionPortError("[PERSONA_INACTIVE]", status_code=400)

    link_result = await db.execute(
        select(AgentPersona).where(
            AgentPersona.agent_id == agent_id_str,
            AgentPersona.persona_id == persona_id_str,
        )
    )
    link = link_result.scalar_one_or_none()
    if not link:
        raise PracticeSessionPortError(
            "[PERSONA_NOT_LINKED_TO_AGENT]",
            status_code=400,
        )
    return link.override_config or None


def register_agent_practice_session_contributor() -> None:
    register_agent_persona_pair_validator(validate_agent_persona_pair)
