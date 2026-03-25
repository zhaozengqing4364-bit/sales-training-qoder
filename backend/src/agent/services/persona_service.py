"""
Persona Service - Business logic for Persona management

Implements CRUD operations for Personas with duplication support.

References:
- Requirements: R3 (Persona Management)
- Design: Section 5 (Persona Service)
- API Contract: docs/api-contract/personas.md
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

from ..models import AgentPersona, Persona, PersonaStatus
from ..schemas import (
    CreatePersonaRequest,
    PersonaListItem,
    UpdatePersonaRequest,
)
from .persona_policy import (
    PERSONA_POLICY_VERSION,
    normalize_persona_policy,
    sync_legacy_persona_fields,
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
            persona_policy = normalize_persona_policy(
                data.persona_policy,
                fallback_system_prompt=data.system_prompt,
                fallback_kb_ids=data.knowledge_base_ids or [],
            )
            persona.persona_policy = persona_policy
            sync_legacy_persona_fields(persona, persona_policy)

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

        persona_ids = [persona.id for persona in personas]
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

        items: list[PersonaListItem] = []
        for persona in personas:
            persona_id = str(persona.id)
            items.append(
                PersonaListItem(
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
            )

        return items, total

    async def get_by_id(self, persona_id: str) -> Result[Persona]:
        """Get Persona by ID - R3.3"""
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            return Result.fail("[PERSONA_NOT_FOUND]")

        persona.persona_policy = self._build_normalized_policy(persona)
        sync_legacy_persona_fields(persona, persona.persona_policy)
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
        legacy_system_prompt = str(persona.system_prompt or "")
        legacy_kb_ids = (
            list(persona.knowledge_base_ids)
            if isinstance(persona.knowledge_base_ids, list)
            else []
        )
        incoming_persona_policy = update_data.pop("persona_policy", None)

        for field, value in update_data.items():
            if value is not None:
                if field == "behavior_config" and hasattr(value, "model_dump"):
                    value = value.model_dump()
                setattr(persona, field, value)

        next_system_prompt = (
            str(update_data.get("system_prompt") or legacy_system_prompt)
            if "system_prompt" in update_data
            else legacy_system_prompt
        )
        next_kb_ids = (
            update_data.get("knowledge_base_ids")
            if "knowledge_base_ids" in update_data
            else legacy_kb_ids
        )
        next_kb_ids = next_kb_ids if isinstance(next_kb_ids, list) else legacy_kb_ids
        touched_legacy_policy_fields = (
            "system_prompt" in update_data
            or "knowledge_base_ids" in update_data
        )
        if incoming_persona_policy is not None or touched_legacy_policy_fields:
            existing_policy = (
                dict(persona.persona_policy)
                if isinstance(persona.persona_policy, dict)
                else {}
            )
            raw_persona_policy = (
                incoming_persona_policy
                if incoming_persona_policy is not None
                else existing_policy
            )
            if incoming_persona_policy is None:
                # Let explicit legacy field updates take precedence over stale policy fields.
                if "system_prompt" in update_data:
                    raw_persona_policy.pop("system_prompt", None)
                if "knowledge_base_ids" in update_data:
                    raw_persona_policy.pop("knowledge_base_ids", None)

            persona_policy = normalize_persona_policy(
                raw_persona_policy,
                fallback_system_prompt=next_system_prompt,
                fallback_kb_ids=next_kb_ids,
            )
            persona.persona_policy = persona_policy
            sync_legacy_persona_fields(persona, persona_policy)

        persona.updated_at = datetime.now(UTC)

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
            persona_policy = normalize_persona_policy(
                original.persona_policy
                if isinstance(original.persona_policy, dict)
                else {},
                fallback_system_prompt=original.system_prompt,
                fallback_kb_ids=(
                    original.knowledge_base_ids
                    if isinstance(original.knowledge_base_ids, list)
                    else []
                ),
            )
            new_persona.persona_policy = persona_policy
            sync_legacy_persona_fields(new_persona, persona_policy)

            self.db.add(new_persona)
            await self.db.flush()
            await self.db.refresh(new_persona)

            logger.info(f"Duplicated Persona: {original.id} -> {new_persona.id}")
            return Result.ok(new_persona)

        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to duplicate Persona: {e}")
            return Result.fail(f"[PERSONA_DUPLICATE_FAILED] {str(e)}")

    async def audit_policy_health(self, sample_limit: int = 50) -> dict[str, Any]:
        """Audit persona_policy consistency and report actionable issues."""
        stmt = select(Persona).order_by(Persona.updated_at.desc())
        result = await self.db.execute(stmt)
        personas = result.scalars().all()

        issue_type_counts: dict[str, int] = {}
        issues: list[dict[str, Any]] = []
        healthy_count = 0

        for persona in personas:
            raw_policy = persona.persona_policy if isinstance(persona.persona_policy, dict) else {}
            normalized_policy = self._build_normalized_policy(persona)
            persona_issues: list[str] = []

            if not isinstance(persona.persona_policy, dict) or not persona.persona_policy:
                persona_issues.append("missing_policy")

            raw_version = raw_policy.get("version") if isinstance(raw_policy, dict) else None
            if raw_version != PERSONA_POLICY_VERSION:
                persona_issues.append("version_mismatch")

            normalized_prompt = str(normalized_policy.get("system_prompt") or "").strip()
            legacy_prompt = str(persona.system_prompt or "").strip()
            if not normalized_prompt:
                persona_issues.append("empty_system_prompt")
            if legacy_prompt != normalized_prompt:
                persona_issues.append("legacy_prompt_drift")

            normalized_kb_ids = self._normalize_kb_ids(
                normalized_policy.get("knowledge_base_ids")
            )
            legacy_kb_ids = self._normalize_kb_ids(persona.knowledge_base_ids)
            if normalized_kb_ids != legacy_kb_ids:
                persona_issues.append("legacy_kb_drift")

            normalized_tool_policy = normalized_policy.get("tool_policy")
            require_kb_grounding = (
                isinstance(normalized_tool_policy, dict)
                and bool(normalized_tool_policy.get("require_kb_grounding"))
            )
            if require_kb_grounding and not normalized_kb_ids:
                persona_issues.append("kb_lock_unbound")

            normalized_customer_pressure = normalized_policy.get("customer_pressure")
            pressure_source = (
                normalized_customer_pressure.get("source")
                if isinstance(normalized_customer_pressure, dict)
                else None
            )
            if pressure_source == "legacy_sales_focus_extensions":
                persona_issues.append("pressure_model_legacy_only")

            if not persona_issues:
                healthy_count += 1
                continue

            for issue_type in persona_issues:
                issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1

            if len(issues) < sample_limit:
                issues.append(
                    {
                        "persona_id": persona.id,
                        "persona_name": persona.name,
                        "issue_types": persona_issues,
                        "policy_version": raw_version,
                        "require_kb_grounding": require_kb_grounding,
                        "pressure_source": pressure_source,
                    }
                )

        total = len(personas)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "total": total,
                "healthy": healthy_count,
                "with_issues": max(0, total - healthy_count),
            },
            "issue_type_counts": issue_type_counts,
            "sample_issues": issues,
        }

    @staticmethod
    def _normalize_kb_ids(raw_ids: Any) -> list[str]:
        if not isinstance(raw_ids, list):
            return []
        deduped: list[str] = []
        seen: set[str] = set()
        for item in raw_ids:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    @staticmethod
    def _build_normalized_policy(persona: Persona) -> dict[str, Any]:
        return normalize_persona_policy(
            persona.persona_policy if isinstance(persona.persona_policy, dict) else {},
            fallback_system_prompt=str(persona.system_prompt or ""),
            fallback_kb_ids=(
                list(persona.knowledge_base_ids)
                if isinstance(persona.knowledge_base_ids, list)
                else []
            ),
        )
