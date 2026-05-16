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
from curriculum_practice.models import (
    CaseItem,
    ExaminerAgent,
    LearningContent,
    PracticeTemplate,
    QuestionItem,
    RoleProfile,
)
from curriculum_practice.schemas import (
    PracticeTemplateCreate,
    PracticeTemplatePublishCandidate,
    PracticeTemplateResponse,
    PracticeTemplateUpdate,
    PublishedTemplateRef,
    PublishGateDecision,
)
from curriculum_practice.services.publishing_gates import PublishingGateService


class PracticeTemplateNotEditableError(ValueError):
    pass


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
        if template.status != "draft":
            raise PracticeTemplateNotEditableError
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
        if asset_type == "case_item":
            item = await self._db.get(CaseItem, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "role_profile":
            item = await self._db.get(RoleProfile, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "learning_content":
            item = await self._db.get(LearningContent, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "examiner_agent":
            item = await self._db.get(ExaminerAgent, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "question_item":
            item = await self._db.get(QuestionItem, asset_id)
            return item if item is not None and item.status == "published" else None
        if asset_type == "practice_template":
            item = await self._db.get(PracticeTemplate, asset_id)
            if item is None or item.status != "published":
                return None
            role_profile_voice_id = None
            if item.role_profile_id:
                role_profile = await self._db.get(RoleProfile, item.role_profile_id)
                if role_profile is not None and role_profile.status == "published":
                    role_profile_voice_id = role_profile.voice_id
            return {
                "template_id": item.template_id,
                "status": item.status,
                "voice_mode": item.voice_mode,
                "runtime_profile_id": item.runtime_profile_id,
                "scoring_ruleset_id": item.scoring_ruleset_id,
                "role_profile_voice_id": role_profile_voice_id,
            }
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
        "case_item_id": template.case_item_id,
        "role_profile_id": template.role_profile_id,
        "learning_content_id": template.learning_content_id,
        "examiner_agent_id": template.examiner_agent_id,
        "target_learner_level": template.target_learner_level,
        "timeout_config": template.timeout_config,
        "curriculum_plan": template.curriculum_plan,
        "max_stage_duration_seconds": template.max_stage_duration_seconds,
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
        case_item_id=template.case_item_id,
        role_profile_id=template.role_profile_id,
        learning_content_id=template.learning_content_id,
        examiner_agent_id=template.examiner_agent_id,
        target_learner_level=template.target_learner_level,
        timeout_config=template.timeout_config,
        curriculum_plan=template.curriculum_plan,
        max_stage_duration_seconds=template.max_stage_duration_seconds,
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
        "case_item_id": template.case_item_id,
        "role_profile_id": template.role_profile_id,
        "learning_content_id": template.learning_content_id,
        "examiner_agent_id": template.examiner_agent_id,
        "target_learner_level": template.target_learner_level,
        "timeout_config": template.timeout_config,
        "curriculum_plan": template.curriculum_plan,
        "max_stage_duration_seconds": template.max_stage_duration_seconds,
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
