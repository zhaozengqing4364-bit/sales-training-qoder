"""Per-asset import handlers for config-asset-export-v1."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import datetime
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.natural_keys import asset_identity, derive_natural_key
from admin.config_assets.types import ConflictStrategy, ImportAssetResult
from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from agent.models import Agent, Persona, VoiceRuntimeProfile
from agent.schemas import CreatePersonaRequest
from agent.services.agent_service import AgentService
from agent.services.persona_service import PersonaService
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import ScoringRuleset, TrainingTask
from common.effectiveness.scoring_rulesets import ScoringRulesetService
from common.knowledge.models import KnowledgeBase
from common.knowledge.schemas import CreateKnowledgeBaseRequest
from common.knowledge.service import KnowledgeService
from common.training_tasks.schemas import TrainingTaskCreate
from common.training_tasks.service import create_training_task
from curriculum_practice.models import (
    CaseItem,
    ExaminerAgent,
    LearningContent,
    PracticeTemplate,
    QuestionCategory,
    QuestionItem,
    RoleProfile,
)
from curriculum_practice.schemas import (
    CaseItemCreate,
    ExaminerAgentCreate,
    LearningChapterCreate,
    LearningContentCreate,
    QuestionCategoryCreate,
    QuestionItemCreate,
    RoleProfileCreate,
)
from curriculum_practice.services.content_assets import (
    ContentAssetService,
    case_item_content_hash,
    role_profile_content_hash,
)
from curriculum_practice.services.examiner_agents import ExaminerAgentService
from curriculum_practice.services.learning_contents import LearningContentService
from curriculum_practice.services.practice_templates import PracticeTemplateService
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.test_bank import TestBankService
from sales_bot.services.voice_runtime_policy import VoiceRuntimePolicyService


class AssetImporter(Protocol):
    def __call__(
        self,
        db: AsyncSession,
        *,
        entry: dict[str, Any],
        conflict_strategy: ConflictStrategy,
        actor_id: str,
        id_mapping: dict[str, str],
        dry_run: bool,
    ) -> Awaitable[ImportAssetResult]: ...


def _str_value(value: object) -> str | None:
    return cast(str | None, value)


def _payload_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def _resolve_export_curriculum_plan(
    raw_plan: object,
    *,
    namespace: str,
    id_mapping: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Bind export-format curriculum_plan natural keys to imported asset IDs."""
    if not isinstance(raw_plan, dict):
        return None, None, None

    plan = deepcopy(raw_plan)
    learning_content_id: str | None = None
    examiner_agent_id: str | None = None
    stage_bindings = (
        ("learning_content_natural_key", "learning_content", "learning_content_id"),
        ("examiner_agent_natural_key", "examiner_agent", "examiner_agent_id"),
        ("persona_natural_key", "persona", "persona_id"),
        ("situation_pack_natural_key", "situation_pack", "situation_pack_code"),
    )
    for stage in plan.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        stage_type = str(stage.get("stage_type") or "")
        template_ref = stage.get("template_ref")
        if isinstance(template_ref, dict):
            ref_asset_type = str(template_ref.get("asset_type") or "")
            ref_natural_key = str(template_ref.get("natural_key") or "").strip()
            ref_namespace = str(template_ref.get("namespace") or namespace)
            if ref_asset_type and ref_natural_key:
                mapped = id_mapping.get(
                    asset_identity(ref_asset_type, ref_natural_key, ref_namespace)
                )
                if mapped:
                    stage["template_ref"] = {
                        "asset_type": ref_asset_type,
                        "asset_id": mapped,
                        "version": template_ref.get("version") or 1,
                        "hash": template_ref.get("hash") or "sha256:imported",
                        "snapshot_label": template_ref.get("snapshot_label")
                        or "published",
                    }
                    if stage_type == "study" and ref_asset_type == "learning_content":
                        learning_content_id = mapped
                    if stage_type == "exam" and ref_asset_type == "examiner_agent":
                        examiner_agent_id = mapped
        for natural_key_field, asset_type, bound_field in stage_bindings:
            natural_key = stage.get(natural_key_field)
            if not natural_key:
                continue
            identity = asset_identity(asset_type, str(natural_key), namespace)
            mapped = id_mapping.get(identity)
            if not mapped:
                continue
            if (
                bound_field in {"persona_id", "situation_pack_code"}
                and "template_ref" not in stage
            ):
                stage[bound_field] = mapped
                continue
            stage.pop(natural_key_field, None)
            if stage_type == "study" and asset_type == "learning_content":
                learning_content_id = mapped
                if "template_ref" not in stage:
                    stage["template_ref"] = {
                        "asset_type": "learning_content",
                        "asset_id": mapped,
                        "version": 1,
                        "hash": "sha256:imported",
                        "snapshot_label": "published",
                    }
            if stage_type == "exam" and asset_type == "examiner_agent":
                examiner_agent_id = mapped
                if "template_ref" not in stage:
                    stage["template_ref"] = {
                        "asset_type": "examiner_agent",
                        "asset_id": mapped,
                        "version": 1,
                        "hash": "sha256:imported",
                        "snapshot_label": "published",
                    }
    return plan, learning_content_id, examiner_agent_id


def _payload_to_ruleset_entry(payload: dict[str, Any]) -> dict[str, Any]:
    dto = SituationPackDTO.from_ruleset_entry(
        {
            "code": payload.get("code"),
            "label": payload.get("label") or payload.get("name"),
            "version": payload.get("version", "v1"),
            "status": payload.get("status", "draft"),
            "default_relationship_context": payload.get("relationship_context"),
            "default_visible_information_scope": payload.get(
                "visible_information_scope"
            ),
            "default_forbidden_claim_patterns": payload.get("forbidden_claim_patterns"),
            "default_forbidden_topic_codes": payload.get("forbidden_topic_codes"),
            "default_forbidden_stage_codes": payload.get("forbidden_stage_codes"),
            "default_conflict_response_strategy": payload.get(
                "conflict_response_strategy"
            ),
            "default_behavior_rules_for_prompt_only": payload.get(
                "behavior_rules_for_prompt_only"
            ),
            "default_disclosure_policy": payload.get("disclosure_policy"),
            "default_runtime_violation_policy": payload.get("runtime_violation_policy"),
            "compatible_practice_modes": payload.get("compatible_practice_modes"),
            "compatible_scenario_types": payload.get("compatible_scenario_types"),
        }
    )
    return dto.as_legacy_dict()


async def _find_persona_by_natural_key(
    db: AsyncSession, natural_key: str
) -> Persona | None:
    result = await db.execute(select(Persona))
    for row in result.scalars().all():
        if derive_natural_key("persona", name=_str_value(row.name)) == natural_key:
            return row
    return None


async def _find_persona_by_name(db: AsyncSession, name: str) -> Persona | None:
    return cast(
        Persona | None,
        await db.scalar(select(Persona).where(Persona.name == name).limit(1)),
    )


async def _find_kb_by_natural_key(
    db: AsyncSession, natural_key: str
) -> KnowledgeBase | None:
    result = await db.execute(select(KnowledgeBase))
    for row in result.scalars().all():
        if (
            derive_natural_key("knowledge_base", name=_str_value(row.name))
            == natural_key
        ):
            return row
    return None


async def _find_kb_by_name(db: AsyncSession, name: str) -> KnowledgeBase | None:
    return cast(
        KnowledgeBase | None,
        await db.scalar(
            select(KnowledgeBase).where(KnowledgeBase.name == name).limit(1)
        ),
    )


async def _find_template_by_natural_key(
    db: AsyncSession, natural_key: str
) -> PracticeTemplate | None:
    result = await db.execute(select(PracticeTemplate))
    for row in result.scalars().all():
        if (
            derive_natural_key("practice_template", name=_str_value(row.name))
            == natural_key
        ):
            return row
    return None


async def _find_template_by_name(
    db: AsyncSession, name: str
) -> PracticeTemplate | None:
    return cast(
        PracticeTemplate | None,
        await db.scalar(
            select(PracticeTemplate).where(PracticeTemplate.name == name).limit(1)
        ),
    )


async def _find_agent_by_natural_key(
    db: AsyncSession, natural_key: str
) -> Agent | None:
    result = await db.execute(select(Agent))
    for row in result.scalars().all():
        if derive_natural_key("agent", name=_str_value(row.name)) == natural_key:
            return row
    return None


async def _find_runtime_by_natural_key(
    db: AsyncSession, natural_key: str
) -> VoiceRuntimeProfile | None:
    result = await db.execute(select(VoiceRuntimeProfile))
    for row in result.scalars().all():
        if (
            derive_natural_key("voice_runtime_profile", name=_str_value(row.name))
            == natural_key
        ):
            return row
    return None


async def _find_scoring_ruleset_by_natural_key(
    db: AsyncSession, natural_key: str
) -> ScoringRuleset | None:
    result = await db.execute(select(ScoringRuleset))
    for row in result.scalars().all():
        if (
            derive_natural_key(
                "scoring_ruleset",
                version=cast(str | int | None, row.version),
            )
            == natural_key
        ):
            return row
    return None


async def _find_simple_by_natural_key(
    db: AsyncSession,
    *,
    model: Any,
    asset_type: str,
    natural_key: str,
    name_getter: Callable[[Any], str],
) -> Any | None:
    result = await db.execute(select(model))
    for row in result.scalars().all():
        if derive_natural_key(asset_type, name=name_getter(row)) == natural_key:
            return row
    return None


async def _lookup_instance_id_by_natural_key(
    db: AsyncSession,
    *,
    asset_type: str,
    natural_key: str,
) -> str | None:
    if asset_type == "agent":
        agent = await _find_agent_by_natural_key(db, natural_key)
        return str(agent.id) if agent is not None else None
    if asset_type == "persona":
        persona = await _find_persona_by_natural_key(db, natural_key)
        return str(persona.id) if persona is not None else None
    if asset_type == "voice_runtime_profile":
        profile = await _find_runtime_by_natural_key(db, natural_key)
        return str(profile.id) if profile is not None else None
    if asset_type == "scoring_ruleset":
        ruleset = await _find_scoring_ruleset_by_natural_key(db, natural_key)
        return str(ruleset.ruleset_id) if ruleset is not None else None
    if asset_type == "knowledge_base":
        knowledge_base = await _find_kb_by_natural_key(db, natural_key)
        return str(knowledge_base.id) if knowledge_base is not None else None
    if asset_type == "case_item":
        row = await _find_simple_by_natural_key(
            db,
            model=CaseItem,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.customer_role),
        )
        return str(row.case_item_id) if row is not None else None
    if asset_type == "role_profile":
        row = await _find_simple_by_natural_key(
            db,
            model=RoleProfile,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.role_name),
        )
        return str(row.role_profile_id) if row is not None else None
    if asset_type == "learning_content":
        row = await _find_simple_by_natural_key(
            db,
            model=LearningContent,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.title),
        )
        return str(row.learning_content_id) if row is not None else None
    if asset_type == "examiner_agent":
        row = await _find_simple_by_natural_key(
            db,
            model=ExaminerAgent,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.name),
        )
        return str(row.examiner_agent_id) if row is not None else None
    if asset_type == "question_category":
        row = await _find_simple_by_natural_key(
            db,
            model=QuestionCategory,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.name),
        )
        return str(row.category_id) if row is not None else None
    if asset_type == "question_item":
        row = await _find_simple_by_natural_key(
            db,
            model=QuestionItem,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.title),
        )
        return str(row.question_id) if row is not None else None
    if asset_type == "practice_template":
        template = await _find_template_by_natural_key(db, natural_key)
        return str(template.template_id) if template is not None else None
    if asset_type == "training_task":
        row = await _find_simple_by_natural_key(
            db,
            model=TrainingTask,
            asset_type=asset_type,
            natural_key=natural_key,
            name_getter=lambda item: str(item.title),
        )
        return str(row.task_id) if row is not None else None
    if asset_type == "situation_pack":
        return natural_key if await _situation_pack_exists(db, natural_key) else None
    return None


async def _resolve_asset_ref_id(
    db: AsyncSession,
    *,
    asset_type: str,
    ref: object,
    namespace: str,
    id_mapping: dict[str, str],
) -> str | None:
    if isinstance(ref, dict):
        ref_asset_type = str(ref.get("asset_type") or asset_type)
        natural_key = str(ref.get("natural_key") or "").strip()
        ref_namespace = str(ref.get("namespace") or namespace)
    else:
        ref_asset_type = asset_type
        natural_key = str(ref or "").strip()
        ref_namespace = namespace
    if not natural_key:
        return None
    identity = asset_identity(ref_asset_type, natural_key, ref_namespace)
    mapped = id_mapping.get(identity)
    if mapped:
        return mapped
    return await _lookup_instance_id_by_natural_key(
        db,
        asset_type=ref_asset_type,
        natural_key=natural_key,
    )


async def _situation_pack_exists(db: AsyncSession, code: str) -> bool:
    resolution = await BusinessRuleConfigService(db).resolve_active_config(
        ROLEPLAY_SITUATION_PACKS_KEY,
        fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        fallback_source="bundled_roleplay_situation_packs",
    )
    packs = resolution.value.get("packs", []) if resolution.value else []
    return any(
        isinstance(item, dict) and str(item.get("code")) == code for item in packs
    )


async def import_knowledge_base(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("knowledge_base", natural_key, namespace)
    existing = await _find_kb_by_natural_key(db, natural_key)
    if existing is None and payload.get("name"):
        existing = await _find_kb_by_name(db, str(payload["name"]))

    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.id)
            return ImportAssetResult(
                "knowledge_base", namespace, natural_key, "skipped", str(existing.id)
            )
        if conflict_strategy == "fail":
            return ImportAssetResult(
                "knowledge_base",
                namespace,
                natural_key,
                "failed",
                message="natural_key already exists",
            )

    if dry_run:
        id_mapping[identity] = "dry-run-kb-id"
        return ImportAssetResult(
            "knowledge_base", namespace, natural_key, "imported", "dry-run-kb-id"
        )

    service = KnowledgeService(db)
    request = CreateKnowledgeBaseRequest(
        name=str(payload.get("name") or entry["name"]),
        description=payload.get("description"),
        category=str(payload.get("category") or "product"),
    )
    result = await service.create(request)
    if not result.is_success or result.value is None:
        return ImportAssetResult(
            "knowledge_base",
            namespace,
            natural_key,
            "failed",
            message=str(result.fallback),
        )
    kb = result.value
    id_mapping[identity] = str(kb.id)
    return ImportAssetResult(
        "knowledge_base", namespace, natural_key, "imported", str(kb.id)
    )


async def import_persona(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("persona", natural_key, namespace)
    existing = await _find_persona_by_natural_key(db, natural_key)
    if existing is None and payload.get("name"):
        existing = await _find_persona_by_name(db, str(payload["name"]))

    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.id)
            return ImportAssetResult(
                "persona", namespace, natural_key, "skipped", str(existing.id)
            )
        if conflict_strategy == "fail":
            return ImportAssetResult(
                "persona",
                namespace,
                natural_key,
                "failed",
                message="natural_key already exists",
            )

    if dry_run:
        id_mapping[identity] = "dry-run-persona-id"
        return ImportAssetResult(
            "persona", namespace, natural_key, "imported", "dry-run-persona-id"
        )

    traits_raw = payload.get("traits") or {}
    traits = {
        str(key): str(value) if not isinstance(value, str) else value
        for key, value in traits_raw.items()
    }

    service = PersonaService(db)
    request = CreatePersonaRequest(
        name=str(payload.get("name") or entry["name"]),
        description=payload.get("description"),
        icon=payload.get("icon"),
        category=str(payload.get("category") or "customer"),
        difficulty=str(payload.get("difficulty") or "medium"),
        system_prompt=str(payload.get("system_prompt") or "placeholder"),
        traits=traits,
        knowledge_base_ids=payload.get("knowledge_base_ids") or [],
        behavior_config=payload.get("behavior_config") or {},
        persona_policy=payload.get("persona_policy"),
    )
    result = await service.create(request, user_id=actor_id)
    if not result.is_success or result.value is None:
        return ImportAssetResult(
            "persona",
            namespace,
            natural_key,
            "failed",
            message=str(result.fallback),
        )
    persona = result.value
    id_mapping[identity] = str(persona.id)
    return ImportAssetResult(
        "persona", namespace, natural_key, "imported", str(persona.id)
    )


async def import_situation_pack(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    code = str(payload.get("code") or natural_key)
    identity = asset_identity("situation_pack", natural_key, namespace)
    exists = await _situation_pack_exists(db, code)

    if exists:
        if conflict_strategy == "skip":
            id_mapping[identity] = code
            return ImportAssetResult(
                "situation_pack", namespace, natural_key, "skipped", code
            )
        if conflict_strategy == "fail":
            return ImportAssetResult(
                "situation_pack",
                namespace,
                natural_key,
                "failed",
                message="natural_key already exists",
            )

    if dry_run:
        id_mapping[identity] = code
        return ImportAssetResult(
            "situation_pack", namespace, natural_key, "imported", code
        )

    resolution = await BusinessRuleConfigService(db).resolve_active_config(
        ROLEPLAY_SITUATION_PACKS_KEY,
        fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        fallback_source="bundled_roleplay_situation_packs",
    )
    ruleset = deepcopy(resolution.value or DEFAULT_ROLEPLAY_SITUATION_PACKS)
    packs = [item for item in ruleset.get("packs", []) if isinstance(item, dict)]
    new_entry = _payload_to_ruleset_entry(payload)
    new_entry["code"] = code
    export_status = str(entry.get("status") or "draft")
    if export_status == "published":
        new_entry["status"] = "published"

    replaced = False
    for index, pack in enumerate(packs):
        if str(pack.get("code")) == code:
            merged_status = str(new_entry.get("status") or "draft")
            if conflict_strategy == "replace_draft" and str(pack.get("status")) != "draft":
                merged_status = "draft"
            packs[index] = {**pack, **new_entry, "status": merged_status}
            replaced = True
            break
    if not replaced:
        packs.append(new_entry)
    ruleset["packs"] = packs

    lifecycle = ConfigBundleLifecycleService(db)
    await lifecycle.create_draft(
        bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=ruleset,
        actor_id=actor_id,
        reason=f"config_asset_import:{natural_key}",
    )
    id_mapping[identity] = code
    return ImportAssetResult(
        "situation_pack", namespace, natural_key, "imported", code
    )


async def import_practice_template(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("practice_template", natural_key, namespace)
    existing = await _find_template_by_natural_key(db, natural_key)
    if existing is None and payload.get("name"):
        existing = await _find_template_by_name(db, str(payload["name"]))

    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.template_id)
            return ImportAssetResult(
                "practice_template",
                namespace,
                natural_key,
                "skipped",
                str(existing.template_id),
            )
        if conflict_strategy == "fail":
            return ImportAssetResult(
                "practice_template",
                namespace,
                natural_key,
                "failed",
                message="natural_key already exists",
            )

    asset_refs = _payload_dict(payload.get("asset_refs"))
    missing: list[str] = []

    async def required_ref(field: str, asset_type: str) -> str | None:
        ref = asset_refs.get(field)
        if ref is None:
            missing.append(field)
            return None
        resolved = await _resolve_asset_ref_id(
            db,
            asset_type=asset_type,
            ref=ref,
            namespace=namespace,
            id_mapping=id_mapping,
        )
        if not resolved:
            missing.append(field)
        return resolved

    agent_id = await required_ref("agent", "agent")
    persona_id = await required_ref("persona", "persona")
    runtime_profile_id = await required_ref(
        "runtime_profile",
        "voice_runtime_profile",
    )
    scoring_ruleset_id = await required_ref("scoring_ruleset", "scoring_ruleset")

    kb_ids: list[str] = []
    kb_refs = asset_refs.get("knowledge_bases")
    if not isinstance(kb_refs, list):
        kb_refs = []
        legacy_kb_keys = asset_refs.get("knowledge_base_natural_keys")
        if isinstance(legacy_kb_keys, list):
            kb_refs = [
                {
                    "asset_type": "knowledge_base",
                    "namespace": namespace,
                    "natural_key": key,
                }
                for key in legacy_kb_keys
            ]
    for ref in kb_refs:
        mapped = await _resolve_asset_ref_id(
            db,
            asset_type="knowledge_base",
            ref=ref,
            namespace=namespace,
            id_mapping=id_mapping,
        )
        if mapped:
            kb_ids.append(mapped)

    situation_code = payload.get("situation_pack_code")
    situation_ref = asset_refs.get("situation_pack")
    if situation_ref is None and asset_refs.get("situation_pack_natural_key"):
        situation_ref = {
            "asset_type": "situation_pack",
            "namespace": namespace,
            "natural_key": asset_refs.get("situation_pack_natural_key"),
        }
    if situation_ref is not None:
        situation_code = await _resolve_asset_ref_id(
            db,
            asset_type="situation_pack",
            ref=situation_ref,
            namespace=namespace,
            id_mapping=id_mapping,
        )

    case_item_id = await _resolve_asset_ref_id(
        db,
        asset_type="case_item",
        ref=asset_refs.get("case_item"),
        namespace=namespace,
        id_mapping=id_mapping,
    )
    role_profile_id = await _resolve_asset_ref_id(
        db,
        asset_type="role_profile",
        ref=asset_refs.get("role_profile"),
        namespace=namespace,
        id_mapping=id_mapping,
    )

    if missing or not all([agent_id, persona_id, runtime_profile_id, scoring_ruleset_id]):
        return ImportAssetResult(
            "practice_template",
            namespace,
            natural_key,
            "failed",
            message=f"missing dependency refs: {', '.join(sorted(set(missing)))}",
        )

    if dry_run:
        id_mapping[identity] = "dry-run-template-id"
        return ImportAssetResult(
            "practice_template", namespace, natural_key, "imported", "dry-run-template-id"
        )

    curriculum_plan_raw = payload.get("curriculum_plan")
    curriculum_plan, learning_content_id, examiner_agent_id = (
        _resolve_export_curriculum_plan(
            curriculum_plan_raw,
            namespace=namespace,
            id_mapping=id_mapping,
        )
    )

    template = await PracticeTemplateService(db).import_template(
        {
            "name": str(payload.get("name") or entry["name"]),
            "description": payload.get("description"),
            "scenario_type": str(payload.get("scenario_type") or "sales"),
            "mode": str(payload.get("mode") or "customer_roleplay"),
            "agent_id": str(agent_id),
            "persona_id": str(persona_id),
            "runtime_profile_id": str(runtime_profile_id),
            "voice_mode": str(payload.get("voice_mode") or "stepfun_realtime"),
            "scoring_ruleset_id": str(scoring_ruleset_id),
            "knowledge_base_refs": kb_ids,
            "case_item_id": case_item_id,
            "role_profile_id": role_profile_id,
            "learning_content_id": learning_content_id,
            "examiner_agent_id": examiner_agent_id,
            "target_learner_level": payload.get("target_learner_level"),
            "timeout_config": payload.get("timeout_config"),
            "curriculum_plan": curriculum_plan,
            "situation_pack_code": str(situation_code) if situation_code else None,
        },
        actor_id=actor_id,
    )
    id_mapping[identity] = str(template.template_id)
    return ImportAssetResult(
        "practice_template",
        namespace,
        natural_key,
        "imported",
        str(template.template_id),
    )


async def import_agent(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("agent", natural_key, namespace)
    existing = await _find_agent_by_natural_key(db, natural_key)
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.id)
            return ImportAssetResult("agent", namespace, natural_key, "skipped", str(existing.id))
        if conflict_strategy == "fail":
            return ImportAssetResult("agent", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-agent-id"
        return ImportAssetResult("agent", namespace, natural_key, "imported", "dry-run-agent-id")

    result = await AgentService(db).import_agent(
        payload,
        user_id=actor_id,
        status=str(entry.get("status") or payload.get("status") or "draft"),
    )
    if not result.is_success or result.value is None:
        return ImportAssetResult(
            "agent",
            namespace,
            natural_key,
            "failed",
            message=str(result.fallback),
        )
    agent = result.value
    id_mapping[identity] = str(agent.id)
    return ImportAssetResult("agent", namespace, natural_key, "imported", str(agent.id))


async def import_voice_runtime_profile(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("voice_runtime_profile", natural_key, namespace)
    existing = await _find_runtime_by_natural_key(db, natural_key)
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.id)
            return ImportAssetResult("voice_runtime_profile", namespace, natural_key, "skipped", str(existing.id))
        if conflict_strategy == "fail":
            return ImportAssetResult("voice_runtime_profile", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-runtime-profile-id"
        return ImportAssetResult(
            "voice_runtime_profile",
            namespace,
            natural_key,
            "imported",
            "dry-run-runtime-profile-id",
        )

    created = await VoiceRuntimePolicyService(db).create_profile(payload)
    instance_id = str(created["id"])
    id_mapping[identity] = instance_id
    return ImportAssetResult("voice_runtime_profile", namespace, natural_key, "imported", instance_id)


async def import_scoring_ruleset(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("scoring_ruleset", natural_key, namespace)
    existing = await _find_scoring_ruleset_by_natural_key(db, natural_key)
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = str(existing.ruleset_id)
            return ImportAssetResult("scoring_ruleset", namespace, natural_key, "skipped", str(existing.ruleset_id))
        if conflict_strategy == "fail":
            return ImportAssetResult("scoring_ruleset", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-scoring-ruleset-id"
        return ImportAssetResult(
            "scoring_ruleset",
            namespace,
            natural_key,
            "imported",
            "dry-run-scoring-ruleset-id",
        )

    view = await ScoringRulesetService(db).import_ruleset(
        payload,
        actor_id=actor_id,
        status=str(entry.get("status") or payload.get("status") or "draft"),
        reason=f"config_asset_import:{natural_key}",
    )
    if view.ruleset_id is None:
        return ImportAssetResult("scoring_ruleset", namespace, natural_key, "failed", message="[SCORING_RULESET_IMPORT_ID_MISSING]")
    id_mapping[identity] = str(view.ruleset_id)
    return ImportAssetResult("scoring_ruleset", namespace, natural_key, "imported", str(view.ruleset_id))


async def import_case_item(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("case_item", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="case_item",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult(
                "case_item",
                namespace,
                natural_key,
                "skipped",
                existing,
            )
        if conflict_strategy == "fail":
            return ImportAssetResult(
                "case_item",
                namespace,
                natural_key,
                "failed",
                message="natural_key already exists",
            )
    if dry_run:
        id_mapping[identity] = "dry-run-case-item-id"
        return ImportAssetResult(
            "case_item",
            namespace,
            natural_key,
            "imported",
            "dry-run-case-item-id",
        )

    case_payload = {
        "industry": payload["industry"],
        "company_profile": payload["company_profile"],
        "customer_role": payload["customer_role"],
        "pain_points": payload["pain_points"],
        "objections": payload["objections"],
        "hidden_information": payload["hidden_information"],
        "success_criteria": payload["success_criteria"],
        "allowed_disclosure_policy": payload["allowed_disclosure_policy"],
    }
    service = ContentAssetService(db)
    item = await service.create_case_item(
        CaseItemCreate(
            **case_payload,
            content_hash=case_item_content_hash(case_payload),
        ),
        actor_id=actor_id,
    )
    if str(entry.get("status") or payload.get("status")) == "published":
        item = await service.publish_case_item(item, actor_id=actor_id)
    id_mapping[identity] = str(item.case_item_id)
    return ImportAssetResult(
        "case_item",
        namespace,
        natural_key,
        "imported",
        str(item.case_item_id),
    )


async def import_role_profile(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("role_profile", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="role_profile",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("role_profile", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("role_profile", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-role-profile-id"
        return ImportAssetResult("role_profile", namespace, natural_key, "imported", "dry-run-role-profile-id")

    asset_refs = _payload_dict(payload.get("asset_refs"))
    persona_ref = payload.get("persona_ref")
    if asset_refs.get("persona") is not None:
        persona_ref = await _resolve_asset_ref_id(
            db,
            asset_type="persona",
            ref=asset_refs.get("persona"),
            namespace=namespace,
            id_mapping=id_mapping,
        )
    role_payload = {
        "role_type": payload["role_type"],
        "role_name": payload["role_name"],
        "persona_ref": persona_ref,
        "communication_style": payload["communication_style"],
        "pressure_level": payload["pressure_level"],
        "knowledge_boundary": payload["knowledge_boundary"],
        "behavior_rules": payload["behavior_rules"],
        "voice_style_hint": payload["voice_style_hint"],
    }
    service = ContentAssetService(db)
    item = await service.create_role_profile(
        RoleProfileCreate(
            **role_payload,
            content_hash=role_profile_content_hash(role_payload),
        ),
        actor_id=actor_id,
    )
    if str(entry.get("status") or payload.get("status")) == "published":
        item = await service.publish_role_profile(item, actor_id=actor_id)
    id_mapping[identity] = str(item.role_profile_id)
    return ImportAssetResult("role_profile", namespace, natural_key, "imported", str(item.role_profile_id))


async def import_learning_content(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("learning_content", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="learning_content",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("learning_content", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("learning_content", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-learning-content-id"
        return ImportAssetResult("learning_content", namespace, natural_key, "imported", "dry-run-learning-content-id")

    service = LearningContentService(db)
    created = await service.create_content(
        LearningContentCreate(
            title=str(payload.get("title") or entry["name"]),
            summary=payload.get("summary"),
            owner=payload.get("owner"),
            source=payload.get("source"),
            safety_flagged=bool(payload.get("safety_flagged", False)),
        ),
        actor_id=actor_id,
    )
    if not created.is_success or created.value is None:
        return ImportAssetResult("learning_content", namespace, natural_key, "failed", message=str(created.fallback))
    content = created.value
    for chapter in payload.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_result = await service.add_chapter(
            content,
            LearningChapterCreate(
                title=str(chapter.get("title") or "Chapter"),
                content=str(chapter.get("content") or ""),
                order_index=chapter.get("order_index"),
            ),
            actor_id=actor_id,
        )
        if not chapter_result.is_success:
            return ImportAssetResult("learning_content", namespace, natural_key, "failed", message=str(chapter_result.fallback))
    if str(entry.get("status") or payload.get("status")) == "published":
        publish_result = await service.publish_content(content, actor_id=actor_id)
        if not publish_result.is_success:
            return ImportAssetResult("learning_content", namespace, natural_key, "failed", message=str(publish_result.fallback))
        content = cast(LearningContent, publish_result.value)
    id_mapping[identity] = str(content.learning_content_id)
    return ImportAssetResult("learning_content", namespace, natural_key, "imported", str(content.learning_content_id))


async def import_question_category(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("question_category", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="question_category",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("question_category", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("question_category", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-question-category-id"
        return ImportAssetResult("question_category", namespace, natural_key, "imported", "dry-run-question-category-id")

    service = TestBankService(db)
    parent_id = payload.get("parent_id")
    asset_refs = _payload_dict(payload.get("asset_refs"))
    if asset_refs.get("parent") is not None:
        parent_id = await _resolve_asset_ref_id(
            db,
            asset_type="question_category",
            ref=asset_refs.get("parent"),
            namespace=namespace,
            id_mapping=id_mapping,
        )
    created = await service.create_category(
        QuestionCategoryCreate(
            name=str(payload.get("name") or entry["name"]),
            parent_id=parent_id,
            description=payload.get("description"),
            order_index=int(payload.get("order_index") or 1),
        ),
        actor_id=actor_id,
    )
    if not created.is_success or created.value is None:
        return ImportAssetResult("question_category", namespace, natural_key, "failed", message=str(created.fallback))
    category = created.value
    id_mapping[identity] = str(category.category_id)
    return ImportAssetResult("question_category", namespace, natural_key, "imported", str(category.category_id))


async def import_question_item(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("question_item", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="question_item",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("question_item", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("question_item", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-question-item-id"
        return ImportAssetResult("question_item", namespace, natural_key, "imported", "dry-run-question-item-id")

    asset_refs = _payload_dict(payload.get("asset_refs"))
    category_id = payload.get("category_id")
    if asset_refs.get("category") is not None:
        category_id = await _resolve_asset_ref_id(
            db,
            asset_type="question_category",
            ref=asset_refs.get("category"),
            namespace=namespace,
            id_mapping=id_mapping,
        )
    if not category_id:
        return ImportAssetResult("question_item", namespace, natural_key, "failed", message="missing dependency refs: category")
    service = TestBankService(db)
    created = await service.create_question(
        QuestionItemCreate(
            category_id=str(category_id),
            title=str(payload.get("title") or entry["name"]),
            stem=str(payload.get("stem") or ""),
            reference_answer=payload.get("reference_answer"),
            scoring_criteria=payload.get("scoring_criteria") or {},
            scoring_dimensions=payload.get("scoring_dimensions") or [],
            tags=payload.get("tags") or [],
            difficulty=payload.get("difficulty") or "medium",
            safety_flagged=bool(payload.get("safety_flagged", False)),
            department=payload.get("department"),
        ),
        actor_id=actor_id,
    )
    if not created.is_success or created.value is None:
        return ImportAssetResult("question_item", namespace, natural_key, "failed", message=str(created.fallback))
    question = created.value
    if str(entry.get("status") or payload.get("status")) == "published":
        publish_result = await service.publish_question(question, actor_id=actor_id)
        if not publish_result.is_success:
            return ImportAssetResult("question_item", namespace, natural_key, "failed", message=str(publish_result.fallback))
        question = cast(QuestionItem, publish_result.value)
    id_mapping[identity] = str(question.question_id)
    return ImportAssetResult("question_item", namespace, natural_key, "imported", str(question.question_id))


async def import_examiner_agent(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("examiner_agent", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="examiner_agent",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("examiner_agent", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("examiner_agent", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-examiner-agent-id"
        return ImportAssetResult("examiner_agent", namespace, natural_key, "imported", "dry-run-examiner-agent-id")

    asset_refs = _payload_dict(payload.get("asset_refs"))
    question_ids: list[str] = []
    question_refs = asset_refs.get("question_sources")
    if isinstance(question_refs, list):
        for ref in question_refs:
            resolved = await _resolve_asset_ref_id(
                db,
                asset_type="question_item",
                ref=ref,
                namespace=namespace,
                id_mapping=id_mapping,
            )
            if resolved:
                question_ids.append(resolved)
    else:
        question_ids = [str(item) for item in payload.get("question_source_ids") or []]
    scoring_policy_id = payload.get("scoring_policy_id")
    if asset_refs.get("scoring_policy") is not None:
        scoring_policy_id = await _resolve_asset_ref_id(
            db,
            asset_type="scoring_ruleset",
            ref=asset_refs.get("scoring_policy"),
            namespace=namespace,
            id_mapping=id_mapping,
        )
    if not scoring_policy_id:
        return ImportAssetResult("examiner_agent", namespace, natural_key, "failed", message="missing dependency refs: scoring_policy")
    service = ExaminerAgentService(db)
    created = await service.create_agent(
        ExaminerAgentCreate(
            name=str(payload.get("name") or entry["name"]),
            description=payload.get("description"),
            question_source_ids=question_ids,
            learner_level_strategy=payload.get("learner_level_strategy") or {},
            scoring_policy_id=str(scoring_policy_id),
            timeout_config=payload.get("timeout_config") or {"max_seconds": 900},
            safety_config=payload.get("safety_config") or {},
            prompt_config=payload.get("prompt_config") or {},
            simulation_config=payload.get("simulation_config") or {},
        ),
        actor_id=actor_id,
    )
    if not created.is_success or created.value is None:
        return ImportAssetResult("examiner_agent", namespace, natural_key, "failed", message=str(created.fallback))
    examiner = created.value
    if str(entry.get("status") or payload.get("status")) == "published":
        publish_result = await service.publish_agent(examiner, actor_id=actor_id)
        if not publish_result.is_success:
            return ImportAssetResult("examiner_agent", namespace, natural_key, "failed", message=str(publish_result.fallback))
        examiner = cast(ExaminerAgent, publish_result.value)
    id_mapping[identity] = str(examiner.examiner_agent_id)
    return ImportAssetResult("examiner_agent", namespace, natural_key, "imported", str(examiner.examiner_agent_id))


async def import_training_task(
    db: AsyncSession,
    *,
    entry: dict[str, Any],
    conflict_strategy: ConflictStrategy,
    actor_id: str,
    id_mapping: dict[str, str],
    dry_run: bool,
) -> ImportAssetResult:
    namespace = str(entry["namespace"])
    natural_key = str(entry["natural_key"])
    payload = dict(entry["payload"])
    identity = asset_identity("training_task", natural_key, namespace)
    existing = await _lookup_instance_id_by_natural_key(
        db,
        asset_type="training_task",
        natural_key=natural_key,
    )
    if existing is not None:
        if conflict_strategy == "skip":
            id_mapping[identity] = existing
            return ImportAssetResult("training_task", namespace, natural_key, "skipped", existing)
        if conflict_strategy == "fail":
            return ImportAssetResult("training_task", namespace, natural_key, "failed", message="natural_key already exists")
    if dry_run:
        id_mapping[identity] = "dry-run-training-task-id"
        return ImportAssetResult("training_task", namespace, natural_key, "imported", "dry-run-training-task-id")

    asset_refs = _payload_dict(payload.get("asset_refs"))
    practice_template_id = payload.get("practice_template_id")
    if asset_refs.get("practice_template") is not None:
        practice_template_id = await _resolve_asset_ref_id(
            db,
            asset_type="practice_template",
            ref=asset_refs.get("practice_template"),
            namespace=namespace,
            id_mapping=id_mapping,
        )
    assignee_id = str(payload.get("assignee_id") or actor_id)
    due_date_raw = payload.get("due_date")
    due_date = None
    if isinstance(due_date_raw, str) and due_date_raw.strip():
        due_date = datetime.fromisoformat(due_date_raw.replace("Z", "+00:00"))
    task = await create_training_task(
        db,
        TrainingTaskCreate(
            title=str(payload.get("title") or entry["name"]),
            assignee_id=assignee_id,
            scenario_type=payload.get("scenario_type") or "sales",
            goal=str(payload.get("goal") or "Imported training task"),
            focus_intent=payload.get("focus_intent"),
            due_date=due_date,
            completion_criteria=payload.get("completion_criteria") or {},
            practice_template_id=practice_template_id,
            curriculum_plan_id=payload.get("curriculum_plan_id"),
            source=payload.get("source") or "config_asset_import",
            status=payload.get("status") or "assigned",
        ),
    )
    id_mapping[identity] = str(task.task_id)
    return ImportAssetResult("training_task", namespace, natural_key, "imported", str(task.task_id))


IMPORTERS: dict[str, AssetImporter] = {
    "agent": import_agent,
    "knowledge_base": import_knowledge_base,
    "persona": import_persona,
    "situation_pack": import_situation_pack,
    "case_item": import_case_item,
    "role_profile": import_role_profile,
    "learning_content": import_learning_content,
    "question_category": import_question_category,
    "question_item": import_question_item,
    "scoring_ruleset": import_scoring_ruleset,
    "voice_runtime_profile": import_voice_runtime_profile,
    "examiner_agent": import_examiner_agent,
    "practice_template": import_practice_template,
    "training_task": import_training_task,
}
