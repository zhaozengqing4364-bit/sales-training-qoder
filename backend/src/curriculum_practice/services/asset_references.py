from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from inspect import isawaitable
from json import dumps
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
from curriculum_practice.schemas import CurriculumVersionRef, ReferenceReader

VOLATILE_HASH_FIELDS = {
    "actor_id",
    "created_at",
    "compiled_at",
    "compiled_by",
    "published_at",
    "snapshot_hash",
    "trace_id",
    "updated_at",
}

PUBLISHED_SNAPSHOT_LABEL = "published"
LEGACY_UNVERSIONED_SNAPSHOT_LABEL = "legacy_unversioned"


class AssetReferenceBuildError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


ErrorFactory = Callable[[str, str], Exception]


class CurriculumAssetReferenceReader:
    """DB adapter for curriculum asset references used by gates and snapshots."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def read_reference(self, asset_type: str, asset_id: str) -> dict[str, Any] | None:
        if asset_type == "agent":
            item = await self._db.get(Agent, asset_id)
            if item is None:
                return None
            return {
                "id": item.id,
                "status": item.status,
                "version": item.version,
            }
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
            return {
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
            }
        if asset_type == "role_profile":
            item = await self._db.get(RoleProfile, asset_id)
            if item is None:
                return None
            return {
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
            }
        if asset_type == "learning_content":
            item = await self._db.get(LearningContent, asset_id)
            if item is None:
                return None
            return {
                "learning_content_id": item.learning_content_id,
                "status": item.status,
                "version": item.version,
                "content_hash": item.content_hash,
            }
        if asset_type == "examiner_agent":
            item = await self._db.get(ExaminerAgent, asset_id)
            if item is None:
                return None
            return {
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
            }
        if asset_type == "question_item":
            item = await self._db.get(QuestionItem, asset_id)
            if item is None:
                return None
            return {
                "question_id": item.question_id,
                "status": item.status,
                "version": item.version,
                "content_hash": item.content_hash,
                "safety_flagged": item.safety_flagged,
            }
        if asset_type == "practice_template":
            item = await self._db.get(PracticeTemplate, asset_id)
            if item is None:
                return None
            role_profile_voice_id = None
            if item.role_profile_id:
                role_profile = await self._db.get(RoleProfile, item.role_profile_id)
                if role_profile is not None and role_profile.status == "published":
                    role_profile_voice_id = role_profile.voice_id
            return {
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
            }
        return None

    async def read_publish_gate_reference(
        self, asset_type: str, asset_id: str
    ) -> dict[str, Any] | None:
        reference = await self.read_reference(asset_type, asset_id)
        if reference is None or not is_publish_gate_available(asset_type, reference):
            return None
        return reference


class RuntimeSnapshotAssetResolver:
    """Builds frozen CurriculumVersionRef values from a reference reader."""

    def __init__(
        self,
        reference_reader: ReferenceReader,
        *,
        error_factory: ErrorFactory = AssetReferenceBuildError,
    ) -> None:
        self._reference_reader = reference_reader
        self._error_factory = error_factory

    async def read_reference(self, asset_type: str, asset_id: str) -> object | None:
        reference = self._reference_reader(asset_type, asset_id)
        if isawaitable(reference):
            return await reference
        return reference

    async def version_ref(
        self,
        asset_type: str,
        asset_id: str,
        *,
        expected_hash: str | None = None,
        expected_version: int | str | None = None,
        snapshot_label: str | None = None,
    ) -> CurriculumVersionRef:
        reference = _as_dict(await self.read_reference(asset_type, asset_id))
        if not reference:
            self._raise(_missing_reason_code(asset_type), _missing_message(asset_type))

        current_hash = _reference_hash(asset_type, reference)
        if expected_hash is not None and current_hash != expected_hash:
            self._raise(
                "asset_hash_mismatch",
                f"{asset_type} reference hash does not match the frozen ref.",
            )

        reason_code = _unavailable_reason_code(asset_type)
        if not is_snapshot_reference_available(asset_type, reference):
            self._raise(reason_code, _unavailable_message(asset_type))

        return CurriculumVersionRef(
            asset_type=asset_type,
            asset_id=asset_id,
            version=expected_version if expected_version is not None else _version(reference),
            hash=expected_hash or current_hash,
            snapshot_label=snapshot_label or _snapshot_label(asset_type),
        )

    async def stage_asset_ref(self, template_ref_data: dict[str, Any]) -> CurriculumVersionRef:
        return await self.version_ref(
            str(template_ref_data["asset_type"]),
            str(template_ref_data["asset_id"]),
            expected_hash=str(template_ref_data["hash"]),
            expected_version=template_ref_data["version"],
            snapshot_label=str(template_ref_data["snapshot_label"]),
        )

    async def examiner_content_refs(self, asset_id: str) -> list[CurriculumVersionRef]:
        examiner_ref = await self.version_ref("examiner_agent", asset_id)
        examiner_agent = _as_dict(await self.read_reference("examiner_agent", asset_id))
        refs = [examiner_ref]
        for question_id in examiner_agent.get("question_source_ids", []) or []:
            refs.append(await self.version_ref("question_item", str(question_id)))
        return refs

    async def role_profile_ref_from_id(self, asset_id: str) -> CurriculumVersionRef:
        return await self.version_ref("role_profile", asset_id)

    def role_profile_ref_from_data(
        self, role_profile: dict[str, Any]
    ) -> CurriculumVersionRef:
        if not role_profile:
            self._raise("asset_unpublished", "role_profile reference is missing.")
        if not is_snapshot_reference_available("role_profile", role_profile):
            self._raise(
                "asset_unpublished",
                "role_profile reference is unpublished or unavailable.",
            )
        return CurriculumVersionRef(
            asset_type="role_profile",
            asset_id=_asset_id_from_reference("role_profile", role_profile),
            version=_version(role_profile),
            hash=_reference_hash("role_profile", role_profile),
            snapshot_label=_snapshot_label("role_profile"),
        )

    def _raise(self, reason_code: str, message: str) -> None:
        raise self._error_factory(reason_code, message)


def version_ref_from_data(
    asset_type: str,
    reference: dict[str, Any],
    *,
    asset_id: str | None = None,
) -> CurriculumVersionRef:
    if not reference:
        raise AssetReferenceBuildError(
            _missing_reason_code(asset_type),
            _missing_message(asset_type),
        )
    if not is_snapshot_reference_available(asset_type, reference):
        raise AssetReferenceBuildError(
            _unavailable_reason_code(asset_type),
            _unavailable_message(asset_type),
        )
    resolved_asset_id = asset_id or _asset_id_from_reference(asset_type, reference)
    return CurriculumVersionRef(
        asset_type=asset_type,
        asset_id=resolved_asset_id,
        version=_version(reference),
        hash=_reference_hash(asset_type, reference),
        snapshot_label=_snapshot_label(asset_type),
    )


def is_publish_gate_available(asset_type: str, reference: dict[str, Any]) -> bool:
    if asset_type == "agent":
        return reference.get("status") == "published"
    if asset_type == "persona":
        return reference.get("status") == "active"
    if asset_type == "voice_runtime_profile":
        return bool(reference.get("is_active"))
    return is_snapshot_reference_available(asset_type, reference)


def is_snapshot_reference_available(asset_type: str, reference: dict[str, Any]) -> bool:
    if asset_type == "knowledge_base":
        return reference.get("status") == "active"
    if asset_type == "question_item":
        return reference.get("status") == "published" and not bool(
            reference.get("safety_flagged", False)
        )
    if asset_type in {
        "practice_template",
        "case_item",
        "role_profile",
        "learning_content",
        "examiner_agent",
        "scoring_ruleset",
    }:
        return reference.get("status") == "published"
    return bool(reference)


def stable_hash(payload: object) -> str:
    return (
        "sha256:"
        + sha256(
            dumps(
                _without_volatile_fields(payload),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    )


def _without_volatile_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_volatile_fields(value)
            for key, value in payload.items()
            if key not in VOLATILE_HASH_FIELDS
        }
    if isinstance(payload, list):
        return [_without_volatile_fields(item) for item in payload]
    return payload


def _as_dict(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def as_reference_dict(value: object | None) -> dict[str, Any]:
    return _as_dict(value)


def _reference_hash(asset_type: str, reference: dict[str, Any]) -> str:
    if asset_type in {"knowledge_base", "scoring_ruleset"}:
        return stable_hash(reference)
    return str(reference["content_hash"])


def _version(reference: dict[str, Any]) -> int | str:
    return reference.get("version", 1)


def _snapshot_label(asset_type: str) -> str:
    if asset_type == "knowledge_base":
        return LEGACY_UNVERSIONED_SNAPSHOT_LABEL
    return PUBLISHED_SNAPSHOT_LABEL


def _asset_id_from_reference(asset_type: str, reference: dict[str, Any]) -> str:
    key = {
        "practice_template": "template_id",
        "knowledge_base": "id",
        "scoring_ruleset": "ruleset_id",
        "case_item": "case_item_id",
        "role_profile": "role_profile_id",
        "learning_content": "learning_content_id",
        "examiner_agent": "examiner_agent_id",
        "question_item": "question_id",
    }.get(asset_type, "id")
    return str(reference[key])


def _missing_reason_code(asset_type: str) -> str:
    if asset_type == "practice_template":
        return "template_unpublished"
    return _unavailable_reason_code(asset_type)


def _unavailable_reason_code(asset_type: str) -> str:
    if asset_type == "scoring_ruleset":
        return "rubric_missing"
    if asset_type == "examiner_agent":
        return "examiner_agent_unpublished"
    if asset_type == "question_item":
        return "question_item_unpublished"
    if asset_type == "practice_template":
        return "template_unpublished"
    return "asset_unpublished"


def _missing_message(asset_type: str) -> str:
    return f"{asset_type} reference is missing."


def _unavailable_message(asset_type: str) -> str:
    return f"{asset_type} reference is unpublished or unavailable."
