from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    PracticeTemplateCreate,
    PracticeTemplatePublishCandidate,
    PracticeTemplateResponse,
    PracticeTemplateUpdate,
    PublishedTemplateRef,
    PublishGateDecision,
)
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.published_asset_refs import (
    resolve_template_situation_pack_code,
)
from curriculum_practice.services.publishing_gates import PublishingGateService
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


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

    async def import_template(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
    ) -> PracticeTemplate:
        """Create a draft-equivalent template from a validated import bundle."""

        template = PracticeTemplate(
            **payload,
            created_by=actor_id,
            updated_by=actor_id,
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
        reference_reader = CurriculumAssetReferenceReader(
            self._db
        ).read_publish_gate_reference
        situation_pack_config = await BusinessRuleConfigService(
            self._db
        ).resolve_active_config(
            ROLEPLAY_SITUATION_PACKS_KEY,
            fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
            fallback_source="bundled_roleplay_situation_packs",
        )
        if situation_pack_config.config_id is not None:
            active_version = await ConfigBundleLifecycleService(
                self._db
            ).resolve_active_version(ROLEPLAY_SITUATION_PACKS_KEY)
            if (
                active_version is not None
                and active_version.source_config_id == situation_pack_config.config_id
            ):
                situation_pack_config = replace(
                    situation_pack_config,
                    config_version_id=str(active_version.version_id),
                )
        gate_service = PublishingGateService(
            reference_reader=reference_reader,
            situation_packs=await SituationPackRepository.from_database(self._db),
            situation_pack_config=situation_pack_config,
        )
        candidate = _candidate_from_template(template)
        decision = await gate_service.validate(candidate)
        if not decision.can_publish:
            return None, decision

        resolved_at = datetime.now(UTC).isoformat()
        published_asset_refs = await gate_service.build_published_asset_refs(
            candidate,
            resolved_at=resolved_at,
        )
        situation_pack_code = await resolve_template_situation_pack_code(
            candidate,
            reference_reader=reference_reader,
        )

        template.status = "published"
        template.published_by = actor_id
        template.published_at = datetime.now(UTC)
        template.content_hash = _content_hash(template)
        template.situation_pack_code = situation_pack_code
        template.published_asset_refs = published_asset_refs
        await self._db.commit()
        await self._db.refresh(template)
        return template, decision


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
        "situation_pack_code": template.situation_pack_code,
        "published_asset_refs": dict(template.published_asset_refs or {}),
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
        situation_pack_code=template.situation_pack_code,
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
