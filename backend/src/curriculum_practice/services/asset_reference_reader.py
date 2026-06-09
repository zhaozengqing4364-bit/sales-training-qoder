from __future__ import annotations

from typing import Any

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
from curriculum_practice.services.asset_reference_lineage import (
    active_revision_lineage,
)


class CurriculumAssetReferenceReader:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def read_reference(self, asset_type: str, asset_id: str) -> dict[str, Any] | None:
        if asset_type == "agent":
            item = await self._db.get(Agent, asset_id)
            if item is None:
                return None
            return {"id": item.id, "status": item.status, "version": item.version}
        if asset_type == "persona":
            item = await self._db.get(Persona, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "category": item.category,
                "system_prompt": item.system_prompt,
                "traits": item.traits or {},
                "persona_policy": item.persona_policy or {},
                "knowledge_base_ids": list(item.knowledge_base_ids or []),
            }
        if asset_type == "voice_runtime_profile":
            item = await self._db.get(VoiceRuntimeProfile, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "is_active": item.is_active,
                "voice_mode": item.voice_mode,
                "model_name": item.model_name,
                "voice_name": item.voice_name,
                "system_instruction_template": getattr(
                    item,
                    "system_instruction_template",
                    None,
                ),
            }
        if asset_type == "scoring_ruleset":
            item = await self._db.get(ScoringRuleset, asset_id)
            if item is None:
                return None
            return {
                "ruleset_id": item.ruleset_id,
                "status": item.status,
                "version": item.version,
                "definition_json": item.definition_json,
            }
        if asset_type == "knowledge_base":
            item = await self._db.get(KnowledgeBase, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "category": item.category,
                "vector_collection": item.vector_collection,
            }
        if asset_type == "case_item":
            item = await self._db.get(CaseItem, asset_id)
            if item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(item.case_item_id),
                {
                    "case_item_id": item.case_item_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                    "industry": item.industry,
                    "company_profile": item.company_profile,
                    "customer_role": item.customer_role,
                    "pain_points": list(item.pain_points or []),
                    "objections": list(item.objections or []),
                    "hidden_information": item.hidden_information,
                    "success_criteria": list(item.success_criteria or []),
                    "allowed_disclosure_policy": item.allowed_disclosure_policy or {},
                },
            )
        if asset_type == "role_profile":
            item = await self._db.get(RoleProfile, asset_id)
            if item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(item.role_profile_id),
                {
                    "role_profile_id": item.role_profile_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                    "role_type": item.role_type,
                    "role_name": item.role_name,
                    "persona_ref": item.persona_ref,
                    "communication_style": item.communication_style,
                    "pressure_level": item.pressure_level,
                    "knowledge_boundary": list(item.knowledge_boundary or []),
                    "behavior_rules": list(item.behavior_rules or []),
                    "voice_style_hint": item.voice_style_hint,
                    "voice_id": item.voice_id,
                    "voice_sample_url": item.voice_sample_url,
                },
            )
        if asset_type == "learning_content":
            item = await self._db.get(LearningContent, asset_id)
            if item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(item.learning_content_id),
                {
                    "learning_content_id": item.learning_content_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                },
            )
        if asset_type == "examiner_agent":
            item = await self._db.get(ExaminerAgent, asset_id)
            if item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(item.examiner_agent_id),
                {
                    "examiner_agent_id": item.examiner_agent_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                    "question_source_ids": list(item.question_source_ids or []),
                    "learner_level_strategy": item.learner_level_strategy or {},
                    "scoring_policy_id": item.scoring_policy_id,
                    "timeout_config": item.timeout_config or {},
                    "safety_config": item.safety_config or {},
                    "prompt_config": item.prompt_config or {},
                    "simulation_config": item.simulation_config or {},
                },
            )
        if asset_type == "question_item":
            item = await self._db.get(QuestionItem, asset_id)
            if item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(item.question_id),
                {
                    "question_id": item.question_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                    "safety_flagged": item.safety_flagged,
                },
            )
        if asset_type == "practice_template":
            item = await self._db.get(PracticeTemplate, asset_id)
            if item is None:
                return None
            role_profile_voice_id = await self._role_profile_voice_id(item)
            return await self._with_lineage(
                asset_type,
                str(item.template_id),
                {
                    "template_id": item.template_id,
                    "status": item.status,
                    "version": item.version,
                    "content_hash": item.content_hash,
                    "scenario_type": item.scenario_type,
                    "mode": item.mode,
                    "voice_mode": item.voice_mode,
                    "runtime_profile_id": item.runtime_profile_id,
                    "agent_id": item.agent_id,
                    "persona_id": item.persona_id,
                    "knowledge_base_refs": list(item.knowledge_base_refs or []),
                    "scoring_ruleset_id": item.scoring_ruleset_id,
                    "case_item_id": item.case_item_id,
                    "role_profile_id": item.role_profile_id,
                    "role_profile_voice_id": role_profile_voice_id,
                    "learning_content_id": item.learning_content_id,
                    "examiner_agent_id": item.examiner_agent_id,
                    "target_learner_level": item.target_learner_level,
                    "timeout_config": item.timeout_config,
                    "curriculum_plan": item.curriculum_plan,
                    "max_stage_duration_seconds": item.max_stage_duration_seconds,
                    "situation_pack_code": item.situation_pack_code,
                    "published_asset_refs": dict(item.published_asset_refs or {}),
                },
            )
        return None

    async def read_publish_gate_reference(
        self, asset_type: str, asset_id: str
    ) -> dict[str, Any] | None:
        from curriculum_practice.services.asset_references import (
            is_publish_gate_available,
        )

        reference = await self.read_reference(asset_type, asset_id)
        if reference is None or not is_publish_gate_available(asset_type, reference):
            return None
        return reference

    async def _role_profile_voice_id(self, template: PracticeTemplate) -> str | None:
        if not template.role_profile_id:
            return None
        role_profile = await self._db.get(RoleProfile, template.role_profile_id)
        if role_profile is not None and role_profile.status == "published":
            return role_profile.voice_id
        return None

    async def _with_lineage(
        self,
        asset_type: str,
        logical_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        lineage = await self._active_revision_lineage(asset_type, logical_id)
        return payload | lineage

    async def _active_revision_lineage(
        self,
        asset_type: str,
        logical_id: str,
    ) -> dict[str, Any]:
        return await active_revision_lineage(
            self._db,
            asset_type=asset_type,
            logical_id=logical_id,
        )
