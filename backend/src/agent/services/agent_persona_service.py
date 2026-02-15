"""
Agent-Persona Association Service

Manages the relationship between Agents and Personas.

References:
- Requirements: R4 (Agent-Persona Association)
- Design: Section 15 (AgentPersona)
- API Contract: docs/api-contract/personas.md
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

from ..models import Agent, AgentPersona, Persona
from ..schemas import (
    AgentPersonaWithDetails,
    CreateAgentPersonaRequest,
    PersonaListItem,
    UpdateAgentPersonaRequest,
)

logger = get_logger(__name__)


class AgentPersonaService:
    """Manages Agent-Persona associations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_persona(
        self,
        agent_id: str,
        data: CreateAgentPersonaRequest
    ) -> Result[AgentPersona]:
        """Add a Persona to an Agent - R4.1"""
        # Check agent exists
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent_result = await self.db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")
        if agent.status == "archived":
            return Result.fail("[AGENT_ARCHIVED]")

        # Check persona exists
        persona_stmt = select(Persona).where(Persona.id == data.persona_id)
        persona_result = await self.db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")
        if persona.status != "active":
            return Result.fail("[PERSONA_INACTIVE]")

        # Check if already linked
        existing_stmt = select(AgentPersona).where(
            AgentPersona.agent_id == agent_id,
            AgentPersona.persona_id == data.persona_id
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            return Result.fail("[PERSONA_ALREADY_LINKED]")

        # If setting as default, clear other defaults
        if data.is_default:
            await self._clear_default(agent_id)

        try:
            link = AgentPersona(
                agent_id=agent_id,
                persona_id=data.persona_id,
                display_order=data.display_order,
                is_default=data.is_default,
                override_config=data.override_config
            )

            self.db.add(link)
            await self.db.flush()
            await self.db.refresh(link)

            logger.info(f"Linked Persona {data.persona_id} to Agent {agent_id}")
            return Result.ok(link)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to link Persona: {e}")
            return Result.fail(f"[LINK_FAILED] {str(e)}")

    async def list_personas(
        self,
        agent_id: str
    ) -> Result[list[AgentPersonaWithDetails]]:
        """Get all Personas linked to an Agent - R4.2"""
        # Check agent exists
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent_result = await self.db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        # Get linked personas with details
        stmt = (
            select(AgentPersona, Persona)
            .join(Persona, AgentPersona.persona_id == Persona.id)
            .where(AgentPersona.agent_id == agent_id)
            .order_by(AgentPersona.display_order)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        persona_ids = [persona.id for _, persona in rows]
        agent_counts: dict[str, int] = {}
        usage_counts: dict[str, int] = {}

        if persona_ids:
            agent_count_rows = await self.db.execute(
                select(AgentPersona.persona_id, func.count().label("agent_count"))
                .where(AgentPersona.persona_id.in_(persona_ids))
                .group_by(AgentPersona.persona_id)
            )
            agent_counts = {
                str(row.persona_id): int(row.agent_count or 0)
                for row in agent_count_rows.all()
            }

            usage_count_rows = await self.db.execute(
                select(PracticeSession.persona_id, func.count().label("usage_count"))
                .where(PracticeSession.persona_id.in_(persona_ids))
                .group_by(PracticeSession.persona_id)
            )
            usage_counts = {
                str(row.persona_id): int(row.usage_count or 0)
                for row in usage_count_rows.all()
                if row.persona_id is not None
            }

        items: list[AgentPersonaWithDetails] = []
        for link, persona in rows:
            persona_id = str(persona.id)
            persona_item = PersonaListItem(
                id=persona.id,
                name=persona.name,
                description=persona.description,
                icon=persona.icon,
                category=persona.category,
                difficulty=persona.difficulty,
                status=persona.status,
                is_public=persona.is_public,
                usage_count=usage_counts.get(persona_id, 0),
                agent_count=agent_counts.get(persona_id, 0),
            )

            items.append(
                AgentPersonaWithDetails(
                    id=link.id,
                    agent_id=link.agent_id,
                    persona_id=link.persona_id,
                    display_order=link.display_order,
                    is_default=link.is_default,
                    override_config=link.override_config,
                    created_at=link.created_at,
                    persona=persona_item,
                )
            )

        return Result.ok(items)

    async def update_link(
        self,
        agent_id: str,
        persona_id: str,
        data: UpdateAgentPersonaRequest
    ) -> Result[AgentPersona]:
        """Update Agent-Persona association - R4.3"""
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent_result = await self.db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")
        if agent.status == "archived":
            return Result.fail("[AGENT_ARCHIVED]")

        stmt = select(AgentPersona).where(
            AgentPersona.agent_id == agent_id,
            AgentPersona.persona_id == persona_id
        )
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()

        if not link:
            return Result.fail("[LINK_NOT_FOUND]")

        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona_result = await self.db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()
        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")
        if persona.status != "active":
            return Result.fail("[PERSONA_INACTIVE]")

        # If setting as default, clear other defaults
        if data.is_default is True:
            await self._clear_default(agent_id, exclude_persona_id=persona_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(link, field, value)

        await self.db.flush()
        await self.db.refresh(link)

        logger.info(f"Updated link: Agent {agent_id} - Persona {persona_id}")
        return Result.ok(link)

    async def remove_persona(
        self,
        agent_id: str,
        persona_id: str
    ) -> Result[bool]:
        """Remove Persona from Agent - R4.4"""
        stmt = select(AgentPersona).where(
            AgentPersona.agent_id == agent_id,
            AgentPersona.persona_id == persona_id
        )
        result = await self.db.execute(stmt)
        link = result.scalar_one_or_none()

        if not link:
            return Result.fail("[LINK_NOT_FOUND]")

        await self.db.delete(link)
        await self.db.flush()

        logger.info(f"Removed Persona {persona_id} from Agent {agent_id}")
        return Result.ok(True)

    async def _clear_default(
        self,
        agent_id: str,
        exclude_persona_id: str | None = None
    ):
        """Clear is_default flag for all personas of an agent"""
        stmt = select(AgentPersona).where(
            AgentPersona.agent_id == agent_id,
            AgentPersona.is_default.is_(True)
        )
        if exclude_persona_id:
            stmt = stmt.where(AgentPersona.persona_id != exclude_persona_id)

        result = await self.db.execute(stmt)
        links = result.scalars().all()

        for link in links:
            link.is_default = False

        await self.db.flush()
