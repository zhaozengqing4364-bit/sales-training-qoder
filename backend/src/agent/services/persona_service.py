"""
Persona Service - Business logic for Persona management

Implements CRUD operations for Personas with duplication support.

References:
- Requirements: R3 (Persona Management)
- Design: Section 5 (Persona Service)
- API Contract: docs/api-contract/personas.md
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from common.monitoring.logger import get_logger

from sqlalchemy.exc import SQLAlchemyError

from ..models import AgentPersona, Persona, PersonaStatus
from ..schemas import (
    CreatePersonaRequest,
    PersonaListItem,
    UpdatePersonaRequest,
)

logger = get_logger(__name__)


class PersonaService:
    """Persona management service - handles CRUD and duplication."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: CreatePersonaRequest,
        user_id: str | None = None
    ) -> Result[Persona]:
        """Create a new Persona - R3.1"""
        try:
            behavior_config = data.behavior_config
            if hasattr(behavior_config, "model_dump"):
                behavior_config = behavior_config.model_dump()

            tts_config = data.tts_config
            if hasattr(tts_config, "model_dump"):
                tts_config = tts_config.model_dump()

            persona = Persona(
                name=data.name,
                description=data.description,
                icon=data.icon,
                category=data.category,
                difficulty=data.difficulty,
                system_prompt=data.system_prompt,
                traits=data.traits or {},
                knowledge_base_ids=data.knowledge_base_ids or [],
                behavior_config=behavior_config or {},
                scoring_weights=data.scoring_weights,
                tts_config=tts_config,
                is_public=data.is_public,
                status=PersonaStatus.ACTIVE.value,
                created_by=user_id,
            )

            self.db.add(persona)
            await self.db.flush()
            await self.db.refresh(persona)

            logger.info(f"Created Persona: {persona.id} - {persona.name}")
            return Result.ok(persona)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to create Persona: {e}")
            return Result.fail(f"[PERSONA_CREATE_FAILED] {str(e)}")

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        difficulty: str | None = None,
        status: str | None = None
    ) -> tuple[list[PersonaListItem], int]:
        """Get paginated Persona list with optional filters - R3.2"""
        stmt = select(Persona)

        if category:
            stmt = stmt.where(Persona.category == category)
        if difficulty:
            stmt = stmt.where(Persona.difficulty == difficulty)
        if status:
            stmt = stmt.where(Persona.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(Persona.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        personas = result.scalars().all()

        items = []
        for persona in personas:
            agent_count_stmt = select(func.count()).where(
                AgentPersona.persona_id == persona.id
            )
            agent_count = (await self.db.execute(agent_count_stmt)).scalar() or 0

            items.append(PersonaListItem(
                id=persona.id,
                name=persona.name,
                description=persona.description,
                icon=persona.icon,
                category=persona.category,
                difficulty=persona.difficulty,
                status=persona.status,
                is_public=persona.is_public,
                usage_count=0,
                agent_count=agent_count
            ))

        return items, total

    async def get_by_id(self, persona_id: str) -> Result[Persona]:
        """Get Persona by ID - R3.3"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")

        return Result.ok(persona)

    async def update(
        self,
        persona_id: str,
        data: UpdatePersonaRequest
    ) -> Result[Persona]:
        """Update Persona with partial data - R3.4"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if value is not None:
                if field == "behavior_config" and hasattr(value, "model_dump"):
                    value = value.model_dump()
                setattr(persona, field, value)

        persona.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(persona)

        logger.info(f"Updated Persona: {persona.id}")
        return Result.ok(persona)

    async def delete(self, persona_id: str) -> Result[bool]:
        """Delete Persona if not linked to any Agent - R3.5"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")

        agent_count_stmt = select(func.count()).where(
            AgentPersona.persona_id == persona_id
        )
        agent_count = (await self.db.execute(agent_count_stmt)).scalar() or 0

        if agent_count > 0:
            return Result.fail("[PERSONA_IN_USE]")

        await self.db.delete(persona)
        await self.db.flush()

        logger.info(f"Deleted Persona: {persona_id}")
        return Result.ok(True)

    async def duplicate(
        self,
        persona_id: str,
        user_id: str | None = None
    ) -> Result[Persona]:
        """Duplicate an existing Persona - R3.6"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(stmt)
        original = result.scalar_one_or_none()

        if not original:
            return Result.fail("[PERSONA_NOT_FOUND]")

        try:
            new_persona = Persona(
                name=f"{original.name} (副本)",
                description=original.description,
                icon=original.icon,
                category=original.category,
                difficulty=original.difficulty,
                system_prompt=original.system_prompt,
                traits=original.traits or {},
                knowledge_base_ids=original.knowledge_base_ids or [],
                behavior_config=original.behavior_config or {},
                scoring_weights=original.scoring_weights,
                tts_config=original.tts_config,
                is_public=original.is_public,
                status=PersonaStatus.ACTIVE.value,
                created_by=user_id,
            )

            self.db.add(new_persona)
            await self.db.flush()
            await self.db.refresh(new_persona)

            logger.info(f"Duplicated Persona: {original.id} -> {new_persona.id}")
            return Result.ok(new_persona)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to duplicate Persona: {e}")
            return Result.fail(f"[PERSONA_DUPLICATE_FAILED] {str(e)}")
