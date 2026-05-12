from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.db.models import ScoringRuleset
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    PracticeTemplateCreate,
    PracticeTemplatePublishCandidate,
    PracticeTemplateResponse,
    PracticeTemplateUpdate,
    PublishedTemplateRef,
    PublishGateDecision,
)
from curriculum_practice.services.publishing_gates import PublishingGateService


class PracticeTemplateService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_templates(self) -> list[PracticeTemplate]:
        result = await self._db.execute(
            select(PracticeTemplate).order_by(PracticeTemplate.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_template(self, template_id: str) -> PracticeTemplate | None:
        return await self._db.get(PracticeTemplate, template_id)

    async def create_template(
        self, payload: PracticeTemplateCreate, *, actor_id: str | None
    ) -> PracticeTemplate:
        template = PracticeTemplate(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(template)
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def update_template(
        self,
        template: PracticeTemplate,
        payload: PracticeTemplateUpdate,
        *,
        actor_id: str | None,
    ) -> PracticeTemplate:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        template.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def archive_template(
        self, template: PracticeTemplate, *, actor_id: str | None
    ) -> PracticeTemplate:
        template.status = "archived"
        template.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def publish_template(
        self, template: PracticeTemplate, *, actor_id: str | None
    ) -> tuple[PracticeTemplate | None, PublishGateDecision]:
        gate_service = PublishingGateService(reference_reader=self._read_reference)
        decision = await gate_service.validate(_candidate_from_template(template))
        if not decision.can_publish:
            return None, decision

        template.status = "published"
        template.published_by = actor_id
        template.published_at = datetime.now(UTC)
        template.content_hash = _content_hash(template)
        await self._db.commit()
        await self._db.refresh(template)
        return template, decision

    async def _read_reference(self, asset_type: str, asset_id: str) -> object | None:
        if asset_type == "agent":
            item = await self._db.get(Agent, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "persona":
            item = await self._db.get(Persona, asset_id)
            return item if item is not None and item.status == "active" else None
        if asset_type == "voice_runtime_profile":
            item = await self._db.get(VoiceRuntimeProfile, asset_id)
            return item if item is not None and bool(item.is_active) else None
        if asset_type == "scoring_ruleset":
            item = await self._db.get(ScoringRuleset, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "knowledge_base":
            item = await self._db.get(KnowledgeBase, asset_id)
            return item if item is not None and item.status == "active" else None
        return None


def serialize_template(template: PracticeTemplate) -> PracticeTemplateResponse:
    data: dict[str, Any] = {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "scenario_type": template.scenario_type,
        "mode": template.mode,
        "agent_id": template.agent_id,
        "persona_id": template.persona_id,
        "runtime_profile_id": template.runtime_profile_id,
        "voice_mode": template.voice_mode,
        "scoring_ruleset_id": template.scoring_ruleset_id,
        "knowledge_base_refs": list(template.knowledge_base_refs or []),
        "status": template.status,
        "version": template.version,
        "content_hash": template.content_hash,
        "published_at": template.published_at,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }
    return PracticeTemplateResponse.model_validate(data)


def _candidate_from_template(
    template: PracticeTemplate,
) -> PracticeTemplatePublishCandidate:
    return PracticeTemplatePublishCandidate(
        name=str(template.name),
        scenario_type=template.scenario_type,
        mode=template.mode,
        agent_id=str(template.agent_id),
        persona_id=str(template.persona_id),
        runtime_profile_id=str(template.runtime_profile_id),
        voice_mode=template.voice_mode,
        scoring_ruleset_id=str(template.scoring_ruleset_id),
        knowledge_base_refs=list(template.knowledge_base_refs or []),
    )


def _content_hash(template: PracticeTemplate) -> str:
    payload = {
        "name": template.name,
        "description": template.description,
        "scenario_type": template.scenario_type,
        "mode": template.mode,
        "agent_id": template.agent_id,
        "persona_id": template.persona_id,
        "runtime_profile_id": template.runtime_profile_id,
        "voice_mode": template.voice_mode,
        "scoring_ruleset_id": template.scoring_ruleset_id,
        "knowledge_base_refs": list(template.knowledge_base_refs or []),
        "version": template.version,
    }
    return (
        "sha256:"
        + sha256(
            dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    )


def published_ref(template: PracticeTemplate) -> PublishedTemplateRef:
    return PublishedTemplateRef(
        asset_id=str(template.template_id),
        version=int(template.version),
        hash=str(template.content_hash or _content_hash(template)),
    )
