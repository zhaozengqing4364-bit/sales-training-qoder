"""Per-asset export builders for config-asset-export-v1."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.natural_keys import derive_natural_key, topology_ref
from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import ScoringRuleset, TrainingTask
from common.knowledge.models import KnowledgeBase
from curriculum_practice.models import (
    CaseItem,
    ExaminerAgent,
    LearningChapter,
    LearningContent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
    RoleProfile,
)
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


def _export_status_persona(status: str) -> str:
    if status == "active":
        return "published"
    if status == "inactive":
        return "archived"
    return status


def _export_status_kb(status: str) -> str:
    if status == "active":
        return "published"
    return status


def _situation_pack_payload(dto: SituationPackDTO) -> dict[str, Any]:
    return {
        "code": dto.code,
        "label": dto.label,
        "description": dto.label,
        "version": dto.version,
        "relationship_context": dict(dto.relationship_context),
        "visible_information_scope": dict(dto.visible_information_scope),
        "forbidden_claim_patterns": list(dto.forbidden_claim_patterns),
        "forbidden_topic_codes": list(dto.forbidden_topic_codes),
        "forbidden_stage_codes": list(dto.forbidden_stage_codes),
        "conflict_response_strategy": dto.conflict_response_strategy,
        "behavior_rules_for_prompt_only": list(dto.behavior_rules_for_prompt_only),
        "disclosure_policy": dict(dto.disclosure_policy),
        "runtime_violation_policy": dict(dto.runtime_violation_policy),
        "compatible_practice_modes": list(dto.compatible_practice_modes),
        "compatible_scenario_types": list(dto.compatible_scenario_types),
    }


def _ruleset_entry_from_dto(dto: SituationPackDTO) -> dict[str, Any]:
    return dto.as_legacy_dict()


def _natural_ref(asset_type: str, natural_key: str, namespace: str) -> dict[str, str]:
    return {
        "asset_type": asset_type,
        "namespace": namespace,
        "natural_key": natural_key,
    }


async def _natural_ref_for_id(
    db: AsyncSession,
    *,
    asset_type: str,
    asset_id: str | None,
    namespace: str,
) -> dict[str, str] | None:
    if not asset_id:
        return None
    natural_key: str | None = None
    if asset_type == "agent":
        row = await db.get(Agent, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "persona":
        row = await db.get(Persona, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "voice_runtime_profile":
        row = await db.get(VoiceRuntimeProfile, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "scoring_ruleset":
        row = await db.get(ScoringRuleset, asset_id)
        natural_key = (
            derive_natural_key(asset_type, version=row.version) if row else None
        )
    elif asset_type == "knowledge_base":
        row = await db.get(KnowledgeBase, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "case_item":
        row = await db.get(CaseItem, asset_id)
        natural_key = (
            derive_natural_key(asset_type, name=row.customer_role) if row else None
        )
    elif asset_type == "role_profile":
        row = await db.get(RoleProfile, asset_id)
        natural_key = (
            derive_natural_key(asset_type, name=row.role_name) if row else None
        )
    elif asset_type == "learning_content":
        row = await db.get(LearningContent, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.title) if row else None
    elif asset_type == "examiner_agent":
        row = await db.get(ExaminerAgent, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "practice_template":
        row = await db.get(PracticeTemplate, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "question_category":
        row = await db.get(QuestionCategory, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.name) if row else None
    elif asset_type == "question_item":
        row = await db.get(QuestionItem, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.title) if row else None
    elif asset_type == "training_task":
        row = await db.get(TrainingTask, asset_id)
        natural_key = derive_natural_key(asset_type, name=row.title) if row else None
    if natural_key is None:
        return None
    return _natural_ref(asset_type, natural_key, namespace)


async def _append_dependency_ref(
    db: AsyncSession,
    *,
    depends_on: list[dict[str, str]],
    asset_refs: dict[str, object],
    field: str,
    asset_type: str,
    asset_id: str | None,
    namespace: str,
) -> None:
    ref = await _natural_ref_for_id(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        namespace=namespace,
    )
    if ref is None:
        return
    asset_refs[field] = ref
    depends_on.append(ref)


async def export_knowledge_base(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(KnowledgeBase))
    for row in result.scalars().all():
        if derive_natural_key("knowledge_base", name=row.name) != natural_key:
            continue
        payload = {
            "name": row.name,
            "description": row.description,
            "category": row.category,
            "collection_name": row.vector_collection,
            "status": row.status,
        }
        return {
            "asset_type": "knowledge_base",
            "namespace": namespace,
            "natural_key": natural_key,
            "name": row.name,
            "version": 1,
            "content_hash": stable_hash(payload),
            "status": _export_status_kb(str(row.status)),
            "governance": "native_lifecycle",
            "payload": payload,
            "depends_on": [],
        }
    return None


async def export_persona(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(Persona))
    for row in result.scalars().all():
        if derive_natural_key("persona", name=row.name) != natural_key:
            continue
        payload = {
            "name": row.name,
            "description": row.description,
            "icon": row.icon,
            "category": row.category,
            "difficulty": row.difficulty,
            "system_prompt": row.system_prompt,
            "traits": dict(row.traits or {}),
            "persona_policy": dict(row.persona_policy or {}),
            "behavior_config": dict(row.behavior_config or {}),
            "knowledge_base_ids": list(row.knowledge_base_ids or []),
            "status": row.status,
        }
        return {
            "asset_type": "persona",
            "namespace": namespace,
            "natural_key": natural_key,
            "name": row.name,
            "version": 1,
            "content_hash": stable_hash(payload),
            "status": _export_status_persona(str(row.status)),
            "governance": "native_lifecycle",
            "payload": payload,
            "depends_on": [],
        }
    return None


async def export_situation_pack(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    repository = await SituationPackRepository.from_database(db)
    dto = repository.get_any(natural_key)
    if dto is None:
        return None
    payload = _situation_pack_payload(dto)
    return {
        "asset_type": "situation_pack",
        "namespace": namespace,
        "natural_key": natural_key,
        "name": dto.label or dto.code,
        "version": dto.version,
        "content_hash": situation_pack_content_hash(dto),
        "status": dto.status if dto.status in {"draft", "published", "archived"} else "published",
        "governance": "config_bundle",
        "source_bundle_key": ROLEPLAY_SITUATION_PACKS_KEY,
        "payload": payload,
        "depends_on": [],
    }


async def export_practice_template(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(PracticeTemplate))
    for row in result.scalars().all():
        if derive_natural_key("practice_template", name=row.name) != natural_key:
            continue
        depends_on: list[dict[str, str]] = []
        asset_refs: dict[str, object] = {}
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="agent",
            asset_type="agent",
            asset_id=row.agent_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="persona",
            asset_type="persona",
            asset_id=row.persona_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="runtime_profile",
            asset_type="voice_runtime_profile",
            asset_id=row.runtime_profile_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="scoring_ruleset",
            asset_type="scoring_ruleset",
            asset_id=row.scoring_ruleset_id,
            namespace=namespace,
        )
        kb_refs: list[dict[str, str]] = []
        for kb_id in row.knowledge_base_refs or []:
            ref = await _natural_ref_for_id(
                db,
                asset_type="knowledge_base",
                asset_id=str(kb_id),
                namespace=namespace,
            )
            if ref is not None:
                kb_refs.append(ref)
                depends_on.append(ref)
        if kb_refs:
            asset_refs["knowledge_bases"] = kb_refs
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="case_item",
            asset_type="case_item",
            asset_id=row.case_item_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="role_profile",
            asset_type="role_profile",
            asset_id=row.role_profile_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="learning_content",
            asset_type="learning_content",
            asset_id=row.learning_content_id,
            namespace=namespace,
        )
        await _append_dependency_ref(
            db,
            depends_on=depends_on,
            asset_refs=asset_refs,
            field="examiner_agent",
            asset_type="examiner_agent",
            asset_id=row.examiner_agent_id,
            namespace=namespace,
        )
        if row.situation_pack_code:
            situation_ref = _natural_ref(
                "situation_pack",
                str(row.situation_pack_code),
                namespace,
            )
            asset_refs["situation_pack"] = situation_ref
            depends_on.append(situation_ref)
        payload = {
            "name": row.name,
            "description": row.description,
            "scenario_type": row.scenario_type,
            "mode": row.mode,
            "situation_pack_code": row.situation_pack_code,
            "target_learner_level": row.target_learner_level,
            "timeout_config": dict(row.timeout_config or {}),
            "curriculum_plan": dict(row.curriculum_plan or {}),
            "asset_refs": asset_refs,
            "status": row.status,
        }
        return {
            "asset_type": "practice_template",
            "namespace": namespace,
            "natural_key": natural_key,
            "name": row.name,
            "version": int(row.version or 1),
            "content_hash": str(row.content_hash or stable_hash(payload)),
            "status": str(row.status),
            "governance": "native_lifecycle",
            "payload": payload,
            "depends_on": depends_on,
        }
    return None


async def export_agent(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(Agent))
    for row in result.scalars().all():
        if derive_natural_key("agent", name=row.name) != natural_key:
            continue
        payload = {
            "name": row.name,
            "description": row.description,
            "icon": row.icon,
            "category": row.category,
            "welcome_message": row.welcome_message,
            "capabilities_config": dict(row.capabilities_config or {}),
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="agent",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.name),
            version=int(row.version or 1),
            status=str(row.status),
            payload=payload,
        )
    return None


async def export_voice_runtime_profile(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(VoiceRuntimeProfile))
    for row in result.scalars().all():
        if derive_natural_key("voice_runtime_profile", name=row.name) != natural_key:
            continue
        payload = {
            "name": row.name,
            "description": row.description,
            "is_default": bool(row.is_default),
            "is_active": bool(row.is_active),
            "voice_mode": row.voice_mode,
            "model_name": row.model_name,
            "voice_name": row.voice_name,
            "temperature": row.temperature,
            "input_audio_format": row.input_audio_format,
            "output_audio_format": row.output_audio_format,
            "output_sample_rate": row.output_sample_rate,
            "turn_detection": row.turn_detection,
            "system_instruction_template": row.system_instruction_template,
            "tool_policy": dict(row.tool_policy or {}),
        }
        return _native_asset_entry(
            asset_type="voice_runtime_profile",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.name),
            version=1,
            status="published" if row.is_active else "draft",
            payload=payload,
        )
    return None


async def export_scoring_ruleset(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(ScoringRuleset))
    for row in result.scalars().all():
        if derive_natural_key("scoring_ruleset", version=row.version) != natural_key:
            continue
        payload = {
            "scenario_type": row.scenario_type,
            "version": row.version,
            "display_name": row.display_name,
            "description": row.description,
            "definition": dict(row.definition_json or {}),
            "status": row.status,
            "is_active": bool(row.is_active),
        }
        return _native_asset_entry(
            asset_type="scoring_ruleset",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.display_name),
            version=str(row.version),
            status=str(row.status),
            payload=payload,
        )
    return None


async def export_case_item(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    return await _export_simple_model(
        db,
        model=CaseItem,
        asset_type="case_item",
        namespace=namespace,
        natural_key=natural_key,
        name_getter=lambda row: str(row.customer_role),
        version_getter=lambda row: int(row.version or 1),
        status_getter=lambda row: str(row.status),
        payload_getter=lambda row: {
            "industry": row.industry,
            "company_profile": row.company_profile,
            "customer_role": row.customer_role,
            "pain_points": list(row.pain_points or []),
            "objections": list(row.objections or []),
            "hidden_information": row.hidden_information,
            "success_criteria": list(row.success_criteria or []),
            "allowed_disclosure_policy": dict(row.allowed_disclosure_policy or {}),
            "content_hash": row.content_hash,
            "status": row.status,
        },
    )


async def export_role_profile(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(RoleProfile))
    for row in result.scalars().all():
        if derive_natural_key("role_profile", name=str(row.role_name)) != natural_key:
            continue
        depends_on: list[dict[str, str]] = []
        asset_refs: dict[str, object] = {}
        if row.persona_ref:
            ref = await _natural_ref_for_id(
                db,
                asset_type="persona",
                asset_id=str(row.persona_ref),
                namespace=namespace,
            )
            if ref is not None:
                asset_refs["persona"] = ref
                depends_on.append(ref)
        payload = {
            "role_type": row.role_type,
            "role_name": row.role_name,
            "communication_style": row.communication_style,
            "pressure_level": row.pressure_level,
            "knowledge_boundary": list(row.knowledge_boundary or []),
            "behavior_rules": list(row.behavior_rules or []),
            "voice_style_hint": row.voice_style_hint,
            "content_hash": row.content_hash,
            "asset_refs": asset_refs,
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="role_profile",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.role_name),
            version=int(row.version or 1),
            status=str(row.status),
            payload=payload,
            depends_on=depends_on,
        )
    return None


async def export_learning_content(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(LearningContent))
    for row in result.scalars().all():
        if derive_natural_key("learning_content", name=str(row.title)) != natural_key:
            continue
        chapters_result = await db.execute(
            select(LearningChapter)
            .where(LearningChapter.learning_content_id == row.learning_content_id)
            .order_by(LearningChapter.order_index.asc())
        )
        chapters = [
            {
                "title": chapter.title,
                "content": chapter.content,
                "order_index": chapter.order_index,
            }
            for chapter in chapters_result.scalars().all()
        ]
        payload = {
            "title": row.title,
            "summary": row.summary,
            "owner": row.owner,
            "source": row.source,
            "safety_flagged": bool(row.safety_flagged),
            "chapters": chapters,
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="learning_content",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.title),
            version=int(row.version or 1),
            status=str(row.status),
            payload=payload,
        )
    return None


async def export_question_category(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    return await _export_simple_model(
        db,
        model=QuestionCategory,
        asset_type="question_category",
        namespace=namespace,
        natural_key=natural_key,
        name_getter=lambda row: str(row.name),
        version_getter=lambda _row: 1,
        status_getter=lambda _row: "published",
        payload_getter=lambda row: {
            "name": row.name,
            "description": row.description,
            "order_index": row.order_index,
        },
    )


async def export_question_item(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(QuestionItem))
    for row in result.scalars().all():
        if derive_natural_key("question_item", name=str(row.title)) != natural_key:
            continue
        depends_on: list[dict[str, str]] = []
        asset_refs: dict[str, object] = {}
        category_ref = await _natural_ref_for_id(
            db,
            asset_type="question_category",
            asset_id=str(row.category_id),
            namespace=namespace,
        )
        if category_ref is not None:
            asset_refs["category"] = category_ref
            depends_on.append(category_ref)
        payload = {
            "title": row.title,
            "stem": row.stem,
            "reference_answer": row.reference_answer,
            "scoring_criteria": dict(row.scoring_criteria or {}),
            "scoring_dimensions": list(row.scoring_dimensions or []),
            "tags": list(row.tags or []),
            "difficulty": row.difficulty,
            "safety_flagged": bool(row.safety_flagged),
            "department": row.department,
            "asset_refs": asset_refs,
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="question_item",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.title),
            version=int(row.version or 1),
            status=str(row.status),
            payload=payload,
            depends_on=depends_on,
        )
    return None


async def export_examiner_agent(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(ExaminerAgent))
    for row in result.scalars().all():
        if derive_natural_key("examiner_agent", name=str(row.name)) != natural_key:
            continue
        depends_on: list[dict[str, str]] = []
        asset_refs: dict[str, object] = {}
        question_refs: list[dict[str, str]] = []
        for question_id in row.question_source_ids or []:
            ref = await _natural_ref_for_id(
                db,
                asset_type="question_item",
                asset_id=str(question_id),
                namespace=namespace,
            )
            if ref is not None:
                question_refs.append(ref)
                depends_on.append(ref)
        if question_refs:
            asset_refs["question_sources"] = question_refs
        scoring_ref = await _natural_ref_for_id(
            db,
            asset_type="scoring_ruleset",
            asset_id=str(row.scoring_policy_id),
            namespace=namespace,
        )
        if scoring_ref is not None:
            asset_refs["scoring_policy"] = scoring_ref
            depends_on.append(scoring_ref)
        payload = {
            "name": row.name,
            "description": row.description,
            "learner_level_strategy": dict(row.learner_level_strategy or {}),
            "timeout_config": dict(row.timeout_config or {}),
            "safety_config": dict(row.safety_config or {}),
            "prompt_config": dict(row.prompt_config or {}),
            "simulation_config": dict(row.simulation_config or {}),
            "asset_refs": asset_refs,
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="examiner_agent",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.name),
            version=int(row.version or 1),
            status=str(row.status),
            payload=payload,
            depends_on=depends_on,
        )
    return None


async def export_training_task(
    db: AsyncSession,
    *,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    result = await db.execute(select(TrainingTask))
    for row in result.scalars().all():
        if derive_natural_key("training_task", name=str(row.title)) != natural_key:
            continue
        depends_on: list[dict[str, str]] = []
        asset_refs: dict[str, object] = {}
        if row.practice_template_id:
            ref = await _natural_ref_for_id(
                db,
                asset_type="practice_template",
                asset_id=str(row.practice_template_id),
                namespace=namespace,
            )
            if ref is not None:
                asset_refs["practice_template"] = ref
                depends_on.append(ref)
        payload = {
            "title": row.title,
            "assignee_id": row.assignee_id,
            "scenario_type": row.scenario_type,
            "goal": row.goal,
            "focus_intent": row.focus_intent,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "completion_criteria": dict(row.completion_criteria or {}),
            "curriculum_plan_id": row.curriculum_plan_id,
            "source": row.source,
            "asset_refs": asset_refs,
            "status": row.status,
        }
        return _native_asset_entry(
            asset_type="training_task",
            namespace=namespace,
            natural_key=natural_key,
            name=str(row.title),
            version=1,
            status=str(row.status),
            payload=payload,
            depends_on=depends_on,
        )
    return None


async def _export_simple_model(
    db: AsyncSession,
    *,
    model: Any,
    asset_type: str,
    namespace: str,
    natural_key: str,
    name_getter: Any,
    version_getter: Any,
    status_getter: Any,
    payload_getter: Any,
) -> dict[str, Any] | None:
    result = await db.execute(select(model))
    for row in result.scalars().all():
        name = name_getter(row)
        if derive_natural_key(asset_type, name=name) != natural_key:
            continue
        payload = payload_getter(row)
        return _native_asset_entry(
            asset_type=asset_type,
            namespace=namespace,
            natural_key=natural_key,
            name=name,
            version=version_getter(row),
            status=status_getter(row),
            payload=payload,
        )
    return None


def _native_asset_entry(
    *,
    asset_type: str,
    namespace: str,
    natural_key: str,
    name: str,
    version: str | int,
    status: str,
    payload: dict[str, Any],
    depends_on: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "asset_type": asset_type,
        "namespace": namespace,
        "natural_key": natural_key,
        "name": name,
        "version": version,
        "content_hash": stable_hash(payload),
        "status": "published" if status == "active" else status,
        "governance": "native_lifecycle",
        "payload": payload,
        "depends_on": list(depends_on or []),
    }


EXPORTERS = {
    "agent": export_agent,
    "knowledge_base": export_knowledge_base,
    "persona": export_persona,
    "situation_pack": export_situation_pack,
    "case_item": export_case_item,
    "role_profile": export_role_profile,
    "learning_content": export_learning_content,
    "question_category": export_question_category,
    "question_item": export_question_item,
    "scoring_ruleset": export_scoring_ruleset,
    "voice_runtime_profile": export_voice_runtime_profile,
    "examiner_agent": export_examiner_agent,
    "practice_template": export_practice_template,
    "training_task": export_training_task,
}


def sort_topology(assets: list[dict[str, Any]]) -> list[str]:
    refs = {
        topology_ref(str(item["asset_type"]), str(item["natural_key"])): item
        for item in assets
    }
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ref: str) -> None:
        if ref in visited:
            return
        if ref in visiting:
            raise ValueError(f"[TOPOLOGY_CYCLE] {ref}")
        visiting.add(ref)
        item = refs.get(ref)
        if item is not None:
            for dep in item.get("depends_on") or []:
                dep_ref = topology_ref(
                    str(dep["asset_type"]),
                    str(dep["natural_key"]),
                )
                if dep_ref in refs:
                    visit(dep_ref)
        visiting.remove(ref)
        visited.add(ref)
        ordered.append(ref)

    for ref in refs:
        visit(ref)
    return ordered


async def export_asset(
    db: AsyncSession,
    *,
    asset_type: str,
    namespace: str,
    natural_key: str,
) -> dict[str, Any] | None:
    exporter = EXPORTERS.get(asset_type)
    if exporter is None:
        raise ValueError(f"[UNSUPPORTED_ASSET_TYPE] {asset_type}")
    return await exporter(db, namespace=namespace, natural_key=natural_key)


async def load_ruleset_snapshot(db: AsyncSession) -> dict[str, Any]:
    resolution = await BusinessRuleConfigService(db).resolve_active_config(
        ROLEPLAY_SITUATION_PACKS_KEY,
        fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        fallback_source="bundled_roleplay_situation_packs",
    )
    return dict(resolution.value or {})
