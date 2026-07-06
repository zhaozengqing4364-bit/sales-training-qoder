from __future__ import annotations

from typing import Any, cast

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

    async def read_reference(
        self, asset_type: str, asset_id: str
    ) -> dict[str, Any] | None:
        if asset_type == "agent":
            agent = await self._db.get(Agent, asset_id)
            if agent is None:
                return None
            return {"id": agent.id, "status": agent.status, "version": agent.version}
        if asset_type == "persona":
            persona = await self._db.get(Persona, asset_id)
            if persona is None:
                return None
            return {
                "id": persona.id,
                "name": persona.name,
                "status": persona.status,
                "category": persona.category,
                "system_prompt": persona.system_prompt,
                "traits": persona.traits or {},
                "persona_policy": persona.persona_policy or {},
                "knowledge_base_ids": list(persona.knowledge_base_ids or []),
            }
        if asset_type == "voice_runtime_profile":
            voice_runtime_profile = await self._db.get(VoiceRuntimeProfile, asset_id)
            if voice_runtime_profile is None:
                return None
            return {
                "id": voice_runtime_profile.id,
                "is_active": voice_runtime_profile.is_active,
                "voice_mode": voice_runtime_profile.voice_mode,
                "model_name": voice_runtime_profile.model_name,
                "voice_name": voice_runtime_profile.voice_name,
                "system_instruction_template": getattr(
                    voice_runtime_profile,
                    "system_instruction_template",
                    None,
                ),
            }
        if asset_type == "scoring_ruleset":
            scoring_ruleset = await self._db.get(ScoringRuleset, asset_id)
            if scoring_ruleset is None:
                return None
            return {
                "ruleset_id": scoring_ruleset.ruleset_id,
                "status": scoring_ruleset.status,
                "version": scoring_ruleset.version,
                "definition_json": scoring_ruleset.definition_json,
            }
        if asset_type == "knowledge_base":
            knowledge_base = await self._db.get(KnowledgeBase, asset_id)
            if knowledge_base is None:
                return None
            return {
                "id": knowledge_base.id,
                "name": knowledge_base.name,
                "status": knowledge_base.status,
                "category": knowledge_base.category,
                "vector_collection": knowledge_base.vector_collection,
            }
        if asset_type == "case_item":
            case_item = await self._db.get(CaseItem, asset_id)
            if case_item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(case_item.case_item_id),
                {
                    "case_item_id": case_item.case_item_id,
                    "status": case_item.status,
                    "version": case_item.version,
                    "content_hash": case_item.content_hash,
                    "industry": case_item.industry,
                    "company_profile": case_item.company_profile,
                    "customer_role": case_item.customer_role,
                    "pain_points": list(case_item.pain_points or []),
                    "objections": list(case_item.objections or []),
                    "hidden_information": case_item.hidden_information,
                    "success_criteria": list(case_item.success_criteria or []),
                    "allowed_disclosure_policy": case_item.allowed_disclosure_policy
                    or {},
                },
            )
        if asset_type == "role_profile":
            role_profile = await self._db.get(RoleProfile, asset_id)
            if role_profile is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(role_profile.role_profile_id),
                {
                    "role_profile_id": role_profile.role_profile_id,
                    "status": role_profile.status,
                    "version": role_profile.version,
                    "content_hash": role_profile.content_hash,
                    "role_type": role_profile.role_type,
                    "role_name": role_profile.role_name,
                    "persona_ref": role_profile.persona_ref,
                    "communication_style": role_profile.communication_style,
                    "pressure_level": role_profile.pressure_level,
                    "knowledge_boundary": list(role_profile.knowledge_boundary or []),
                    "behavior_rules": list(role_profile.behavior_rules or []),
                    "voice_style_hint": role_profile.voice_style_hint,
                    "voice_id": role_profile.voice_id,
                    "voice_sample_url": role_profile.voice_sample_url,
                },
            )
        if asset_type == "learning_content":
            learning_content = await self._db.get(LearningContent, asset_id)
            if learning_content is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(learning_content.learning_content_id),
                {
                    "learning_content_id": learning_content.learning_content_id,
                    "status": learning_content.status,
                    "version": learning_content.version,
                    "content_hash": learning_content.content_hash,
                },
            )
        if asset_type == "examiner_agent":
            examiner_agent = await self._db.get(ExaminerAgent, asset_id)
            if examiner_agent is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(examiner_agent.examiner_agent_id),
                {
                    "examiner_agent_id": examiner_agent.examiner_agent_id,
                    "status": examiner_agent.status,
                    "version": examiner_agent.version,
                    "content_hash": examiner_agent.content_hash,
                    "question_source_ids": list(
                        examiner_agent.question_source_ids or []
                    ),
                    "learner_level_strategy": examiner_agent.learner_level_strategy
                    or {},
                    "scoring_policy_id": examiner_agent.scoring_policy_id,
                    "timeout_config": examiner_agent.timeout_config or {},
                    "safety_config": examiner_agent.safety_config or {},
                    "prompt_config": examiner_agent.prompt_config or {},
                    "simulation_config": examiner_agent.simulation_config or {},
                },
            )
        if asset_type == "question_item":
            question_item = await self._db.get(QuestionItem, asset_id)
            if question_item is None:
                return None
            return await self._with_lineage(
                asset_type,
                str(question_item.question_id),
                {
                    "question_id": question_item.question_id,
                    "status": question_item.status,
                    "version": question_item.version,
                    "content_hash": question_item.content_hash,
                    "safety_flagged": question_item.safety_flagged,
                },
            )
        if asset_type == "practice_template":
            practice_template = await self._db.get(PracticeTemplate, asset_id)
            if practice_template is None:
                return None
            role_profile_voice_id = await self._role_profile_voice_id(practice_template)
            return await self._with_lineage(
                asset_type,
                str(practice_template.template_id),
                {
                    "template_id": practice_template.template_id,
                    "status": practice_template.status,
                    "version": practice_template.version,
                    "content_hash": practice_template.content_hash,
                    "scenario_type": practice_template.scenario_type,
                    "mode": practice_template.mode,
                    "voice_mode": practice_template.voice_mode,
                    "runtime_profile_id": practice_template.runtime_profile_id,
                    "agent_id": practice_template.agent_id,
                    "persona_id": practice_template.persona_id,
                    "knowledge_base_refs": list(
                        practice_template.knowledge_base_refs or []
                    ),
                    "scoring_ruleset_id": practice_template.scoring_ruleset_id,
                    "case_item_id": practice_template.case_item_id,
                    "role_profile_id": practice_template.role_profile_id,
                    "role_profile_voice_id": role_profile_voice_id,
                    "learning_content_id": practice_template.learning_content_id,
                    "examiner_agent_id": practice_template.examiner_agent_id,
                    "target_learner_level": practice_template.target_learner_level,
                    "timeout_config": practice_template.timeout_config,
                    "curriculum_plan": practice_template.curriculum_plan,
                    "max_stage_duration_seconds": (
                        practice_template.max_stage_duration_seconds
                    ),
                    "situation_pack_code": practice_template.situation_pack_code,
                    "published_asset_refs": dict(
                        practice_template.published_asset_refs or {}
                    ),
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
        role_profile_id = cast(str | None, template.role_profile_id)
        if not role_profile_id:
            return None
        role_profile = await self._db.get(RoleProfile, role_profile_id)
        if role_profile is not None and role_profile.status == "published":
            return cast(str | None, role_profile.voice_id)
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
