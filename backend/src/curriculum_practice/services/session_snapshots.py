from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, ScoringRuleset
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import CaseItem, PracticeTemplate, RoleProfile
from curriculum_practice.services.practice_templates import published_ref
from curriculum_practice.services.snapshots import (
    RuntimeSnapshotBuildError,
    RuntimeSnapshotService,
)


class CurriculumSessionSnapshotError(ValueError):
    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message


async def apply_curriculum_snapshot_to_session(
    *,
    db: AsyncSession,
    session: PracticeSession,
    practice_template_id: UUID | None,
    scenario_type_value: str,
    actor_id: str,
) -> None:
    if practice_template_id is None:
        return

    template = await db.get(PracticeTemplate, str(practice_template_id))
    if template is None:
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_NOT_FOUND]",
            status_code=404,
        )
    if template.status != "published":
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_NOT_PUBLISHED]",
            status_code=400,
        )
    if template.scenario_type != scenario_type_value:
        raise CurriculumSessionSnapshotError(
            "[PRACTICE_TEMPLATE_SCENARIO_TYPE_MISMATCH]",
            status_code=400,
        )

    snapshot_service = RuntimeSnapshotService(_reference_reader(db))
    try:
        snapshot = await snapshot_service.build_for_session(
            published_ref(template),
            {
                "id": str(session.session_id),
                "scenario_type": scenario_type_value,
            },
            actor_id,
        )
    except RuntimeSnapshotBuildError as exc:
        raise CurriculumSessionSnapshotError(
            f"[RUNTIME_SNAPSHOT_{exc.reason_code.upper()}]",
            status_code=400,
            message=str(exc),
        ) from exc

    session.practice_template_id = str(template.template_id)
    session.curriculum_snapshot = snapshot.model_dump(mode="json")


def _reference_reader(db: AsyncSession):
    async def read_reference(asset_type: str, asset_id: str) -> dict[str, Any] | None:
        if asset_type == "practice_template":
            template = await db.get(PracticeTemplate, asset_id)
            if template is None:
                return None
            return {
                "template_id": template.template_id,
                "status": template.status,
                "version": template.version,
                "content_hash": template.content_hash,
                "scenario_type": template.scenario_type,
                "mode": template.mode,
                "voice_mode": template.voice_mode,
                "runtime_profile_id": template.runtime_profile_id,
                "agent_id": template.agent_id,
                "persona_id": template.persona_id,
                "knowledge_base_refs": list(template.knowledge_base_refs or []),
                "scoring_ruleset_id": template.scoring_ruleset_id,
                "case_item_id": template.case_item_id,
                "role_profile_id": template.role_profile_id,
                "curriculum_plan": template.curriculum_plan,
                "max_stage_duration_seconds": template.max_stage_duration_seconds,
            }
        if asset_type == "voice_runtime_profile":
            from agent.models import VoiceRuntimeProfile

            profile = await db.get(VoiceRuntimeProfile, asset_id)
            if profile is None:
                return None
            return {
                "id": profile.id,
                "is_active": profile.is_active,
                "voice_mode": profile.voice_mode,
                "model_name": profile.model_name,
                "voice_name": profile.voice_name,
                "system_instruction_template": getattr(
                    profile,
                    "system_instruction_template",
                    None,
                ),
            }
        if asset_type == "scoring_ruleset":
            ruleset = await db.get(ScoringRuleset, asset_id)
            if ruleset is None:
                return None
            return {
                "ruleset_id": ruleset.ruleset_id,
                "status": ruleset.status,
                "version": ruleset.version,
                "definition_json": ruleset.definition_json,
            }
        if asset_type == "knowledge_base":
            knowledge_base = await db.get(KnowledgeBase, asset_id)
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
            case_item = await db.get(CaseItem, asset_id)
            if case_item is None:
                return None
            return {
                "case_item_id": case_item.case_item_id,
                "status": case_item.status,
                "version": case_item.version,
                "content_hash": case_item.content_hash,
            }
        if asset_type == "role_profile":
            role_profile = await db.get(RoleProfile, asset_id)
            if role_profile is None:
                return None
            return {
                "role_profile_id": role_profile.role_profile_id,
                "status": role_profile.status,
                "version": role_profile.version,
                "content_hash": role_profile.content_hash,
            }
        return None

    return read_reference
