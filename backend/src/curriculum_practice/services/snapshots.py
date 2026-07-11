from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from inspect import isawaitable
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.schemas import (
    CurriculumRuntimeRef,
    CurriculumRuntimeSnapshot,
    CurriculumTrainingTaskRef,
    CurriculumVersionRef,
    PublishedAssetRef,
    PublishedAssetRefSchema,
    PublishedTemplateRef,
    ReferenceReader,
    TemplateStageSnapshot,
)
from curriculum_practice.services.asset_references import (
    RuntimeSnapshotAssetResolver,
    as_reference_dict,
    stable_hash,
)
from curriculum_practice.services.asset_resolution import (
    build_asset_resolution_payload,
    classify_template_asset_resolution,
    template_legacy_warnings,
)
from curriculum_practice.services.frozen_asset_refs import (
    LEGACY_SOURCE_CONFIG_RESOLUTION_MODE,
    FrozenAssetRefError,
    FrozenSituationPackResolver,
    parse_published_asset_refs,
)
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.roleplay_contracts import (
    build_roleplay_contract_compiler,
)
from roleplay.compiler import RoleplayContractCompileError


class RuntimeSnapshotBuildError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class RuntimeSnapshotService:
    def __init__(
        self,
        reference_reader: ReferenceReader,
        *,
        situation_packs: SituationPackRepository | None = None,
        frozen_situation_pack_resolver: FrozenSituationPackResolver | None = None,
    ) -> None:
        self._reference_reader = reference_reader
        self._situation_packs = situation_packs
        self._frozen_situation_pack_resolver = frozen_situation_pack_resolver
        self._last_frozen_situation_pack_resolution_mode: str | None = None
        self._asset_refs = RuntimeSnapshotAssetResolver(
            reference_reader,
            error_factory=RuntimeSnapshotBuildError,
        )

    @classmethod
    def from_database(
        cls,
        db: AsyncSession,
        *,
        reference_reader: ReferenceReader,
        situation_packs: SituationPackRepository | None = None,
    ) -> RuntimeSnapshotService:
        return cls(
            reference_reader,
            situation_packs=situation_packs,
            frozen_situation_pack_resolver=FrozenSituationPackResolver.from_database(db),
        )

    async def build_for_session(
        self,
        template_ref: PublishedTemplateRef,
        training_task_ref: dict[str, object],
        actor_id: str,
        *,
        trace_id: str | None = None,
        created_at: str | None = None,
        learner_level: str = "conservative",
    ) -> CurriculumRuntimeSnapshot:
        template = await self._read_reference("practice_template", template_ref.asset_id)
        template_data = _as_dict(template)
        if template_data.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "template_unpublished",
                "PracticeTemplate must be published before building a runtime snapshot.",
            )
        if str(template_data.get("content_hash")) != template_ref.hash:
            raise RuntimeSnapshotBuildError(
                "asset_hash_mismatch",
                "PracticeTemplate published ref hash does not match current template hash.",
            )
        training_task = CurriculumTrainingTaskRef(
            id=str(training_task_ref["id"]),
            scenario_type=str(training_task_ref["scenario_type"]),
        )
        published_asset_refs_raw = template_data.get("published_asset_refs")
        published_asset_refs = parse_published_asset_refs(published_asset_refs_raw)
        examiner_question_refs = _parse_examiner_question_refs(published_asset_refs_raw)
        frozen_situation_pack = await self._resolve_frozen_situation_pack(
            published_asset_refs
        )
        runtime_profile_id = str(template_data["runtime_profile_id"])
        runtime_profile = _as_dict(
            await self._read_reference("voice_runtime_profile", runtime_profile_id)
        )
        if not runtime_profile or not bool(runtime_profile.get("is_active")):
            raise RuntimeSnapshotBuildError(
                "voice_policy_unavailable",
                "Voice runtime policy is missing or unavailable.",
            )
        if runtime_profile.get("voice_mode") != "stepfun_realtime":
            raise RuntimeSnapshotBuildError(
                "voice_policy_unavailable",
                "Voice runtime policy must use stepfun_realtime mode.",
        )
        content_assets = [
            await self._knowledge_base_ref(str(asset_id))
            for asset_id in template_data.get("knowledge_base_refs", [])
        ]
        if template_data.get("case_item_id"):
            content_assets.append(
                await self._frozen_or_live_ref(
                    "case_item",
                    str(template_data["case_item_id"]),
                    published_asset_refs.get("case_item_ref"),
                )
            )
        if template_data.get("learning_content_id"):
            content_assets.append(
                await self._frozen_or_live_ref(
                    "learning_content",
                    str(template_data["learning_content_id"]),
                    published_asset_refs.get("learning_content_ref"),
                )
            )
        if template_data.get("examiner_agent_id"):
            content_assets.extend(
                await self._examiner_content_refs(
                    str(template_data["examiner_agent_id"]),
                    published_asset_refs.get("examiner_agent_ref"),
                    examiner_question_refs,
                )
            )
        role_profile_data = None
        if template_data.get("role_profile_id"):
            role_profile_data = _as_dict(
                await self._read_reference(
                    "role_profile", str(template_data["role_profile_id"])
                )
            )
            content_assets.append(
                await self._frozen_or_live_ref(
                    "role_profile",
                    str(template_data["role_profile_id"]),
                    published_asset_refs.get("role_profile_ref"),
                    role_profile_data=role_profile_data,
                )
            )
        try:
            compiler = build_roleplay_contract_compiler(
                self._reference_reader,
                situation_packs=self._situation_packs,
            )
            if published_asset_refs:
                roleplay_contract = await compiler.compile_from_frozen_refs(
                    template_data,
                    published_asset_refs,
                    actor_id,
                    frozen_situation_pack=frozen_situation_pack,
                )
            else:
                # Legacy templates without publish-time frozen refs still compile from live assets.
                roleplay_contract = await compiler.compile_from_template_data(
                    template_data,
                    actor_id,
                )
        except RoleplayContractCompileError as exc:
            raise RuntimeSnapshotBuildError(
                exc.reason_code,
                "PracticeTemplate Roleplay Contract is invalid and cannot be frozen.",
            ) from exc
        runtime = CurriculumRuntimeRef(
            agent_id=str(template_data["agent_id"]),
            persona_id=str(template_data["persona_id"]),
            runtime_profile_id=runtime_profile_id,
            voice_policy_snapshot_hash=stable_hash(runtime_profile),
            instruction_contract_hash=_instruction_contract_hash(
                runtime_profile_id=runtime_profile_id,
                runtime_profile=runtime_profile,
                content_assets=content_assets,
            ),
        )
        resolution_mode = classify_template_asset_resolution(
            template_data.get("published_asset_refs")
        )
        legacy_warnings = template_legacy_warnings(
            template_data.get("published_asset_refs")
        )
        asset_resolution_payload = build_asset_resolution_payload(
            mode=resolution_mode,
            entry="practice_template",
            practice_template_id=str(template_ref.asset_id),
            published_asset_refs=template_data.get("published_asset_refs"),
            legacy_warnings=legacy_warnings,
        )
        if (
            self._last_frozen_situation_pack_resolution_mode
            == LEGACY_SOURCE_CONFIG_RESOLUTION_MODE
        ):
            asset_resolution_payload = {
                **asset_resolution_payload,
                "frozen_situation_pack_resolution_mode": (
                    LEGACY_SOURCE_CONFIG_RESOLUTION_MODE
                ),
            }
        snapshot = CurriculumRuntimeSnapshot(
            snapshot_hash="sha256:pending",
            created_at=created_at or datetime.now(UTC).isoformat(),
            trace_id=trace_id,
            training_task=training_task,
            practice_template=CurriculumVersionRef(
                asset_type="practice_template",
                asset_id=template_ref.asset_id,
                version=template_ref.version,
                hash=template_ref.hash,
                snapshot_label=template_ref.snapshot_label,
            ),
            content_assets=content_assets,
            rubric=await self._frozen_or_live_ref(
                "scoring_ruleset",
                str(template_data["scoring_ruleset_id"]),
                published_asset_refs.get("scoring_ruleset_ref"),
            ),
            runtime=runtime,
            roleplay_contract=roleplay_contract,
            role_profile_voice_id=_voice_id_from_role_profile(role_profile_data),
            learner_level=learner_level,
            asset_resolution=asset_resolution_payload,
            legacy_warnings=legacy_warnings,
            stage_snapshots=await self._stage_snapshots(template_data),
        )
        payload = snapshot.model_dump()
        payload["actor_id"] = actor_id
        return snapshot.model_copy(update={"snapshot_hash": stable_hash(payload)})

    async def _read_reference(self, asset_type: str, asset_id: str) -> object | None:
        reference = self._reference_reader(asset_type, asset_id)
        if isawaitable(reference):
            return await cast(Awaitable[object | None], reference)
        return reference

    async def _stage_snapshots(
        self, template_data: dict[str, Any]
    ) -> dict[str, TemplateStageSnapshot]:
        curriculum_plan = template_data.get("curriculum_plan")
        if not isinstance(curriculum_plan, dict):
            return {}
        stages = curriculum_plan.get("stages")
        if not isinstance(stages, list):
            return {}

        snapshots: dict[str, TemplateStageSnapshot] = {}
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            stage_key = str(stage["template_stage_key"])
            stage_type = str(stage.get("stage_type", "practice"))
            template_ref_data = _as_dict(stage.get("template_ref"))
            stage_runtime_fields = _stage_runtime_fields(stage, template_ref_data)
            if stage_type in ("study", "exam"):
                asset_ref = await self._asset_refs.stage_asset_ref(template_ref_data)
                snapshots[stage_key] = TemplateStageSnapshot(
                    template_ref=asset_ref,
                    runtime_payload={
                        **stage_runtime_fields,
                        "stage_type": stage_type,
                        "asset_type": str(template_ref_data["asset_type"]),
                        "asset_id": str(template_ref_data["asset_id"]),
                        "version": template_ref_data["version"],
                        "content_hash": str(template_ref_data["hash"]),
                    },
                    content_assets=[asset_ref],
                )
                continue
            child_template_id = str(template_ref_data["asset_id"])
            child_template = _as_dict(
                await self._read_reference("practice_template", child_template_id)
            )
            child_published_asset_refs_raw = child_template.get("published_asset_refs")
            child_published_asset_refs = parse_published_asset_refs(
                child_published_asset_refs_raw
            )
            child_examiner_question_refs = _parse_examiner_question_refs(
                child_published_asset_refs_raw
            )
            if child_template.get("status") != "published":
                raise RuntimeSnapshotBuildError(
                    "template_unpublished",
                    "CurriculumPlan child template must be published.",
                )
            if str(child_template.get("content_hash")) != str(template_ref_data["hash"]):
                raise RuntimeSnapshotBuildError(
                    "asset_hash_mismatch",
                    "CurriculumPlan child template hash does not match stage ref.",
                )
            child_runtime = await self._runtime_ref(child_template)
            child_content_assets = [
                await self._knowledge_base_ref(str(asset_id))
                for asset_id in child_template.get("knowledge_base_refs", [])
            ]
            if child_template.get("case_item_id"):
                child_content_assets.append(
                    await self._frozen_or_live_ref(
                        "case_item",
                        str(child_template["case_item_id"]),
                        child_published_asset_refs.get("case_item_ref"),
                    )
                )
            if child_template.get("examiner_agent_id"):
                child_content_assets.extend(
                    await self._examiner_content_refs(
                        str(child_template["examiner_agent_id"]),
                        child_published_asset_refs.get("examiner_agent_ref"),
                        child_examiner_question_refs,
                    )
                )
            child_role_profile_data = None
            if child_template.get("role_profile_id"):
                child_role_profile_data = _as_dict(
                    await self._read_reference(
                        "role_profile", str(child_template["role_profile_id"])
                    )
                )
                child_content_assets.append(
                    await self._frozen_or_live_ref(
                        "role_profile",
                        str(child_template["role_profile_id"]),
                        child_published_asset_refs.get("role_profile_ref"),
                        role_profile_data=child_role_profile_data,
                    )
                )
            snapshots[stage_key] = TemplateStageSnapshot(
                template_ref=CurriculumVersionRef(
                    asset_type="practice_template",
                    asset_id=child_template_id,
                    version=template_ref_data["version"],
                    hash=str(template_ref_data["hash"]),
                    snapshot_label=template_ref_data["snapshot_label"],
                ),
                runtime_payload={
                    **stage_runtime_fields,
                    **_minimal_template_runtime_payload(
                        child_template, role_profile_data=child_role_profile_data
                    ),
                },
                content_assets=child_content_assets,
                rubric=await self._frozen_or_live_ref(
                    "scoring_ruleset",
                    str(child_template["scoring_ruleset_id"]),
                    child_published_asset_refs.get("scoring_ruleset_ref"),
                ),
                runtime=child_runtime,
            )
        return snapshots

    async def _curriculum_stage_asset_ref(
        self, template_ref_data: dict[str, Any]
    ) -> CurriculumVersionRef:
        return await self._asset_refs.stage_asset_ref(template_ref_data)

    async def _learning_content_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("learning_content", asset_id)

    async def _runtime_ref(self, template_data: dict[str, Any]) -> CurriculumRuntimeRef:
        runtime_profile_id = str(template_data["runtime_profile_id"])
        runtime_profile = _as_dict(
            await self._read_reference("voice_runtime_profile", runtime_profile_id)
        )
        if not runtime_profile or not bool(runtime_profile.get("is_active")):
            raise RuntimeSnapshotBuildError(
                "voice_policy_unavailable",
                "Voice runtime policy is missing or unavailable.",
            )
        if runtime_profile.get("voice_mode") != "stepfun_realtime":
            raise RuntimeSnapshotBuildError(
                "voice_policy_unavailable",
                "Voice runtime policy must use stepfun_realtime mode.",
            )
        return CurriculumRuntimeRef(
            agent_id=str(template_data["agent_id"]),
            persona_id=str(template_data["persona_id"]),
            runtime_profile_id=runtime_profile_id,
            voice_policy_snapshot_hash=stable_hash(runtime_profile),
            instruction_contract_hash=_instruction_contract_hash(
                runtime_profile_id=runtime_profile_id,
                runtime_profile=runtime_profile,
                content_assets=[],
            ),
        )

    async def _knowledge_base_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("knowledge_base", asset_id)

    async def _rubric_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("scoring_ruleset", asset_id)

    async def _case_item_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("case_item", asset_id)

    async def _role_profile_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("role_profile", asset_id)

    async def _examiner_agent_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("examiner_agent", asset_id)

    async def _examiner_content_refs(
        self,
        asset_id: str,
        frozen_ref: PublishedAssetRef | None = None,
        frozen_question_refs: dict[str, PublishedAssetRef] | None = None,
    ) -> list[CurriculumVersionRef]:
        examiner_ref = await self._frozen_or_live_ref(
            "examiner_agent",
            asset_id,
            frozen_ref,
        )
        examiner_agent = _as_dict(await self._read_reference("examiner_agent", asset_id))
        refs = [examiner_ref]
        for question_id in examiner_agent.get("question_source_ids", []) or []:
            question_id_text = str(question_id)
            frozen_question_ref = (frozen_question_refs or {}).get(question_id_text)
            refs.append(
                await self._frozen_or_live_ref(
                    "question_item",
                    question_id_text,
                    frozen_question_ref,
                )
            )
        return refs

    async def _question_item_ref(self, asset_id: str) -> CurriculumVersionRef:
        return await self._asset_refs.version_ref("question_item", asset_id)

    async def _resolve_frozen_situation_pack(
        self,
        published_asset_refs: dict[str, PublishedAssetRef],
    ) -> SituationPackDTO | None:
        self._last_frozen_situation_pack_resolution_mode = None
        situation_pack_ref = published_asset_refs.get("situation_pack_ref")
        if (
            situation_pack_ref is None
            or not situation_pack_ref.can_reconstruct_from_snapshot()
            or self._frozen_situation_pack_resolver is None
        ):
            return None
        try:
            pack = await self._frozen_situation_pack_resolver.resolve(
                situation_pack_ref
            )
            self._last_frozen_situation_pack_resolution_mode = (
                self._frozen_situation_pack_resolver.last_resolution_mode
            )
            return pack
        except FrozenAssetRefError as exc:
            raise RuntimeSnapshotBuildError(exc.reason_code, str(exc)) from exc

    async def _frozen_or_live_ref(
        self,
        asset_type: str,
        asset_id: str,
        frozen_ref: PublishedAssetRef | None,
        *,
        role_profile_data: dict[str, Any] | None = None,
    ) -> CurriculumVersionRef:
        if frozen_ref is not None and str(frozen_ref.asset_id or "") == asset_id:
            return await self._asset_refs.version_ref(
                asset_type,
                asset_id,
                expected_hash=frozen_ref.content_hash,
                expected_version=frozen_ref.version,
                snapshot_label=frozen_ref.snapshot_label,
            )
        if asset_type == "role_profile" and role_profile_data:
            return self._asset_refs.role_profile_ref_from_data(role_profile_data)
        if asset_type == "case_item":
            return await self._case_item_ref(asset_id)
        if asset_type == "learning_content":
            return await self._learning_content_ref(asset_id)
        if asset_type == "scoring_ruleset":
            return await self._rubric_ref(asset_id)
        if asset_type == "examiner_agent":
            return await self._examiner_agent_ref(asset_id)
        return await self._asset_refs.version_ref(asset_type, asset_id)


def _as_dict(value: object | None) -> dict[str, Any]:
    return as_reference_dict(value)


def _parse_examiner_question_refs(
    raw: object | None,
) -> dict[str, PublishedAssetRef]:
    if not isinstance(raw, dict):
        return {}
    raw_question_refs = raw.get("examiner_question_refs")
    if not isinstance(raw_question_refs, dict):
        return {}
    parsed: dict[str, PublishedAssetRef] = {}
    for question_id, payload in raw_question_refs.items():
        if not isinstance(payload, dict):
            continue
        parsed[str(question_id)] = PublishedAssetRefSchema.model_validate(
            payload
        ).to_dataclass()
    return parsed


def _minimal_template_runtime_payload(
    template_data: dict[str, Any], *, role_profile_data: dict[str, Any] | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "template_id": str(template_data["template_id"]),
        "version": template_data.get("version", 1),
        "content_hash": str(template_data["content_hash"]),
        "mode": str(template_data["mode"]),
        "scenario_type": str(template_data["scenario_type"]),
        "agent_id": str(template_data["agent_id"]),
        "persona_id": str(template_data["persona_id"]),
        "runtime_profile_id": str(template_data["runtime_profile_id"]),
        "voice_mode": str(template_data["voice_mode"]),
        "scoring_ruleset_id": str(template_data["scoring_ruleset_id"]),
    }
    role_profile_voice_id = _voice_id_from_role_profile(role_profile_data)
    if role_profile_voice_id is not None:
        payload["role_profile_voice_id"] = role_profile_voice_id
    return payload


def _role_profile_ref_from_data(role_profile: dict[str, Any]) -> CurriculumVersionRef:
    return RuntimeSnapshotAssetResolver(
        lambda asset_type, asset_id: None,
        error_factory=RuntimeSnapshotBuildError,
    ).role_profile_ref_from_data(role_profile)


def _voice_id_from_role_profile(role_profile: dict[str, Any] | None) -> str | None:
    if not role_profile:
        return None
    voice_id = role_profile.get("voice_id")
    if isinstance(voice_id, str) and voice_id.strip():
        return voice_id.strip()
    return None


def _instruction_contract_hash(
    *,
    runtime_profile_id: str,
    runtime_profile: dict[str, Any],
    content_assets: list[CurriculumVersionRef],
) -> str:
    prompt_asset_refs = [
        asset.model_dump()
        for asset in content_assets
        if asset.asset_type in {"case_item", "role_profile"}
    ]
    return stable_hash(
        {
            "runtime_profile_id": runtime_profile_id,
            "system_instruction_template": runtime_profile.get(
                "system_instruction_template"
            ),
            "prompt_relevant_content_assets": prompt_asset_refs,
        }
    )


def _stage_runtime_fields(
    stage: dict[str, Any],
    template_ref_data: dict[str, Any],
) -> dict[str, object]:
    return {
        "template_stage_key": str(stage["template_stage_key"]),
        "order": int(stage.get("order") or 0),
        "stage_type": str(stage.get("stage_type", "practice")),
        "completion_policy": _as_dict(stage.get("completion_policy")),
        "failure_policy": str(stage.get("failure_policy") or "retry_current"),
        "prerequisites": [
            _as_dict(item) for item in stage.get("prerequisites", []) if isinstance(item, dict)
        ],
        "template_ref": dict(template_ref_data),
    }
