"""
Agent Service - Business logic for Agent management

Implements CRUD operations for Agents with lifecycle management.

References:
- Requirements: R1, R2 (Agent Management)
- Design: Section 4 (Agent Service)
- API Contract: docs/api-contract/agents.md
"""

from __future__ import annotations

import builtins
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

from ..models import Agent, AgentPersona, AgentStatus, Persona
from ..schemas import (
    AgentListItem,
    AgentUserResponse,
    CreateAgentRequest,
    PersonaUserListItem,
    UpdateAgentRequest,
)

logger = get_logger(__name__)

SUPPORTED_AGENT_CATEGORIES = {"sales", "presentation"}
DEPRECATED_AGENT_WRITE_FIELDS = ("system_prompt", "default_knowledge_base_ids")


class AgentService:
    """
    Agent management service

    Handles all Agent CRUD operations, lifecycle management,
    and Persona associations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, data: CreateAgentRequest, user_id: str | None = None
    ) -> Result[Agent]:
        """
        Create a new Agent with draft status

        Requirements: R1.1
        """
        try:
            if data.category not in SUPPORTED_AGENT_CATEGORIES:
                return Result.fail("[AGENT_CATEGORY_RESTRICTED]")
            if data.system_prompt is not None:
                return Result.fail("[FIELD_DEPRECATED_PERSONA_CENTERED] system_prompt")
            if data.default_knowledge_base_ids:
                return Result.fail(
                    "[FIELD_DEPRECATED_PERSONA_CENTERED] default_knowledge_base_ids"
                )

            agent = Agent(
                name=data.name,
                description=data.description,
                icon=data.icon,
                category=data.category,
                system_prompt=None,
                welcome_message=data.welcome_message,
                capabilities_config=data.capabilities_config or {},
                default_knowledge_base_ids=[],
                status=AgentStatus.DRAFT.value,
                created_by=user_id,
            )

            self.db.add(agent)
            await self.db.flush()
            await self.db.refresh(agent)

            logger.info(f"Created Agent: {agent.id} - {agent.name}")
            return Result.ok(agent)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to create Agent: {e}")
            return Result.fail(f"[AGENT_CREATE_FAILED] {str(e)}")

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        status: str | None = None,
        admin: bool = False,
    ) -> tuple[list[AgentListItem], int]:
        """
        Get paginated Agent list with optional filters

        Requirements: R1.2, R2.1
        - admin=False: Only return published Agents (user endpoint)
        - admin=True: Return all Agents with status filter (admin endpoint)
        """
        # Base query
        stmt = select(Agent)

        # Apply filters
        if not admin:
            # User endpoint: only published
            stmt = stmt.where(Agent.status == AgentStatus.PUBLISHED.value)
        elif status:
            stmt = stmt.where(Agent.status == status)

        if category:
            stmt = stmt.where(Agent.category == category)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Apply pagination and ordering
        stmt = stmt.order_by(Agent.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        agents = result.scalars().all()

        # Batch load persona counts to avoid N+1 queries
        agent_ids = [str(agent.id) for agent in agents]
        persona_count_map: dict[str, int] = {}
        if agent_ids:
            persona_counts_stmt = (
                select(
                    AgentPersona.agent_id,
                    func.count().label("persona_count"),
                )
                .where(AgentPersona.agent_id.in_(agent_ids))
                .group_by(AgentPersona.agent_id)
            )
            persona_counts_result = await self.db.execute(persona_counts_stmt)
            persona_count_map = {
                str(row.agent_id): int(row.persona_count or 0)
                for row in persona_counts_result
            }

        # Build list items with persona count
        items = []
        for agent in agents:
            persona_count = persona_count_map.get(str(agent.id), 0)

            items.append(
                AgentListItem(
                    id=agent.id,
                    name=agent.name,
                    description=agent.description,
                    icon=agent.icon,
                    category=agent.category,
                    status=agent.status,
                    persona_count=persona_count,
                    knowledge_base_count=len(agent.default_knowledge_base_ids or []),
                )
            )

        return items, total

    async def get_by_id(self, agent_id: str, admin: bool = False) -> Result:
        """
        Get Agent by ID

        Requirements: R1.3, R2.2
        - admin=True: Return full Agent with system_prompt
        - admin=False: Return user-facing response without system_prompt
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        # User endpoint: check if published
        if not admin and agent.status != AgentStatus.PUBLISHED.value:
            return Result.fail("[AGENT_NOT_FOUND]")

        if admin:
            return Result.ok(agent)

        # Build user response (without system_prompt)
        capabilities_config = cast(
            dict[str, Any] | None,
            getattr(agent, "capabilities_config", None),
        )
        capabilities = self._extract_capability_names(capabilities_config)
        user_response = AgentUserResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            icon=agent.icon,
            category=agent.category,
            welcome_message=agent.welcome_message,
            capabilities=capabilities,
        )
        return Result.ok(user_response)

    async def update(self, agent_id: str, data: UpdateAgentRequest) -> Result[Agent]:
        """
        Update Agent with partial data

        Requirements: R1.4
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        # Apply updates (only non-None fields)
        update_data = data.model_dump(exclude_unset=True)

        if (
            "category" in update_data
            and update_data["category"] is not None
            and update_data["category"] not in SUPPORTED_AGENT_CATEGORIES
        ):
            return Result.fail("[AGENT_CATEGORY_RESTRICTED]")
        for deprecated_field in DEPRECATED_AGENT_WRITE_FIELDS:
            if deprecated_field in update_data:
                return Result.fail(
                    f"[FIELD_DEPRECATED_PERSONA_CENTERED] {deprecated_field}"
                )

        for field, value in update_data.items():
            if value is not None:
                setattr(agent, field, value)

        setattr(agent, "updated_at", datetime.now(UTC))

        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Updated Agent: {agent.id}")
        return Result.ok(agent)

    async def delete(self, agent_id: str) -> Result[bool]:
        """
        Delete Agent if no associated sessions exist

        Requirements: R1.7
        """
        from common.db.models import PracticeSession

        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        # Check for associated sessions
        session_count_stmt = select(func.count()).where(
            PracticeSession.agent_id == agent_id
        )
        session_count = (await self.db.execute(session_count_stmt)).scalar() or 0

        if session_count > 0:
            return Result.fail("[AGENT_CANNOT_DELETE]")

        await self.db.delete(agent)
        await self.db.flush()

        logger.info(f"Deleted Agent: {agent_id}")
        return Result.ok(True)

    async def publish(self, agent_id: str) -> Result[Agent]:
        """
        Publish Agent (draft -> published)

        Requirements: R1.5
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        if agent.status == AgentStatus.PUBLISHED.value:
            return Result.fail("[AGENT_ALREADY_PUBLISHED]")

        setattr(agent, "status", AgentStatus.PUBLISHED.value)
        setattr(agent, "published_at", datetime.now(UTC))
        setattr(agent, "updated_at", datetime.now(UTC))

        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Published Agent: {agent.id}")
        return Result.ok(agent)

    async def archive(self, agent_id: str) -> Result[Agent]:
        """
        Archive Agent (any status -> archived)

        Requirements: R1.6
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        setattr(agent, "status", AgentStatus.ARCHIVED.value)
        setattr(agent, "updated_at", datetime.now(UTC))

        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Archived Agent: {agent.id}")
        return Result.ok(agent)

    async def unpublish(self, agent_id: str) -> Result[Agent]:
        """
        Unpublish Agent (any status -> draft)

        Allows reverting published or archived agents back to draft status.
        """
        stmt = select(Agent).where(Agent.id == agent_id)
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        if agent.status == AgentStatus.DRAFT.value:
            return Result.fail("[AGENT_ALREADY_DRAFT]")

        setattr(agent, "status", AgentStatus.DRAFT.value)
        setattr(agent, "published_at", None)
        setattr(agent, "updated_at", datetime.now(UTC))

        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Unpublished Agent: {agent.id}")
        return Result.ok(agent)

    async def get_personas(self, agent_id: str) -> Result:
        """
        Get Personas associated with an Agent

        Requirements: R2.3
        Returns personas sorted by display_order
        """
        # First check if agent exists and is published
        agent_stmt = select(Agent).where(Agent.id == agent_id)
        agent_result = await self.db.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()

        if not agent:
            return Result.fail("[AGENT_NOT_FOUND]")

        # Get associated personas with details
        stmt = (
            select(AgentPersona, Persona)
            .join(Persona, AgentPersona.persona_id == Persona.id)
            .where(AgentPersona.agent_id == agent_id)
            .where(Persona.status == "active")
            .order_by(AgentPersona.display_order)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        personas = []
        for agent_persona, persona in rows:
            personas.append(
                PersonaUserListItem(
                    id=persona.id,
                    name=persona.name,
                    description=persona.description,
                    icon=persona.icon,
                    difficulty=persona.difficulty,
                    is_default=agent_persona.is_default,
                )
            )

        return Result.ok(personas)

    def _extract_capability_names(
        self, capabilities_config: dict[str, Any] | None
    ) -> builtins.list[str]:
        """Extract enabled capability display names from config"""
        if not capabilities_config:
            return []

        # Map capability IDs to display names
        capability_names = {
            "asr": "语音识别",
            "tts": "语音合成",
            "llm": "智能对话",
            "fuzzy_detection": "模糊词检测",
            "scoring": "实时评分",
            "sales_stage": "销售阶段识别",
            "knowledge_retrieval": "知识库检索",
        }

        enabled: builtins.list[str] = []
        for cap_id, config in capabilities_config.items():
            if isinstance(config, dict) and config.get("enabled"):
                name = capability_names.get(cap_id, cap_id)
                enabled.append(name)

        return enabled
