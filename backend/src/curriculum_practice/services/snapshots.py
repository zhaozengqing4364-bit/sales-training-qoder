from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from inspect import isawaitable
from json import dumps
from typing import Any

from curriculum_practice.schemas import (
    CurriculumRuntimeRef,
    CurriculumRuntimeSnapshot,
    CurriculumTrainingTaskRef,
    CurriculumVersionRef,
    PublishedTemplateRef,
    ReferenceReader,
    TemplateStageSnapshot,
)

VOLATILE_HASH_FIELDS = {
    "actor_id",
    "created_at",
    "published_at",
    "snapshot_hash",
    "trace_id",
    "updated_at",
}


class RuntimeSnapshotBuildError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class RuntimeSnapshotService:
    def __init__(self, reference_reader: ReferenceReader) -> None:
        self._reference_reader = reference_reader

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
        runtime = CurriculumRuntimeRef(
            agent_id=str(template_data["agent_id"]),
            persona_id=str(template_data["persona_id"]),
            runtime_profile_id=runtime_profile_id,
            voice_policy_snapshot_hash=_stable_hash(runtime_profile),
            instruction_contract_hash=_stable_hash(
                {
                    "runtime_profile_id": runtime_profile_id,
                    "system_instruction_template": runtime_profile.get(
                        "system_instruction_template"
                    ),
                }
            ),
        )
        content_assets = [
            await self._knowledge_base_ref(str(asset_id))
            for asset_id in template_data.get("knowledge_base_refs", [])
        ]
        if template_data.get("case_item_id"):
            content_assets.append(await self._case_item_ref(str(template_data["case_item_id"])))
        if template_data.get("learning_content_id"):
            content_assets.append(
                await self._learning_content_ref(str(template_data["learning_content_id"]))
            )
        if template_data.get("examiner_agent_id"):
            content_assets.extend(
                await self._examiner_content_refs(str(template_data["examiner_agent_id"]))
            )
        role_profile_data = None
        if template_data.get("role_profile_id"):
            role_profile_data = _as_dict(
                await self._read_reference(
                    "role_profile", str(template_data["role_profile_id"])
                )
            )
            content_assets.append(_role_profile_ref_from_data(role_profile_data))
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
            rubric=await self._rubric_ref(str(template_data["scoring_ruleset_id"])),
            runtime=runtime,
            role_profile_voice_id=_voice_id_from_role_profile(role_profile_data),
            learner_level=learner_level,
            stage_snapshots=await self._stage_snapshots(template_data),
        )
        payload = snapshot.model_dump()
        payload["actor_id"] = actor_id
        return snapshot.model_copy(update={"snapshot_hash": _stable_hash(payload)})

    async def _read_reference(self, asset_type: str, asset_id: str) -> object | None:
        reference = self._reference_reader(asset_type, asset_id)
        if isawaitable(reference):
            return await reference
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
            if stage_type in ("study", "exam"):
                asset_ref = await self._curriculum_stage_asset_ref(template_ref_data)
                snapshots[stage_key] = TemplateStageSnapshot(
                    template_ref=asset_ref,
                    runtime_payload={
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
                    await self._case_item_ref(str(child_template["case_item_id"]))
                )
            if child_template.get("examiner_agent_id"):
                child_content_assets.extend(
                    await self._examiner_content_refs(
                        str(child_template["examiner_agent_id"])
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
                    _role_profile_ref_from_data(child_role_profile_data)
                )
            snapshots[stage_key] = TemplateStageSnapshot(
                template_ref=CurriculumVersionRef(
                    asset_type="practice_template",
                    asset_id=child_template_id,
                    version=template_ref_data["version"],
                    hash=str(template_ref_data["hash"]),
                    snapshot_label=template_ref_data["snapshot_label"],
                ),
                runtime_payload=_minimal_template_runtime_payload(
                    child_template, role_profile_data=child_role_profile_data
                ),
                content_assets=child_content_assets,
                rubric=await self._rubric_ref(str(child_template["scoring_ruleset_id"])),
                runtime=child_runtime,
            )
        return snapshots

    async def _curriculum_stage_asset_ref(
        self, template_ref_data: dict[str, Any]
    ) -> CurriculumVersionRef:
        asset_type = str(template_ref_data["asset_type"])
        asset_id = str(template_ref_data["asset_id"])
        asset = _as_dict(await self._read_reference(asset_type, asset_id))
        if not asset or asset.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "asset_unpublished",
                "CurriculumPlan stage asset is missing or unpublished.",
            )
        expected_hash = str(template_ref_data["hash"])
        current_hash = str(asset.get("content_hash"))
        if current_hash != expected_hash:
            raise RuntimeSnapshotBuildError(
                "asset_hash_mismatch",
                "CurriculumPlan stage asset hash does not match stage ref.",
            )
        return CurriculumVersionRef(
            asset_type=asset_type,
            asset_id=asset_id,
            version=template_ref_data["version"],
            hash=expected_hash,
            snapshot_label=template_ref_data["snapshot_label"],
        )

    async def _learning_content_ref(self, asset_id: str) -> CurriculumVersionRef:
        content = _as_dict(await self._read_reference("learning_content", asset_id))
        if not content or content.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "asset_unpublished",
                "LearningContent reference is missing or unpublished.",
            )
        return CurriculumVersionRef(
            asset_type="learning_content",
            asset_id=asset_id,
            version=content.get("version", 1),
            hash=str(content["content_hash"]),
            snapshot_label="published",
        )

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
            voice_policy_snapshot_hash=_stable_hash(runtime_profile),
            instruction_contract_hash=_stable_hash(
                {
                    "runtime_profile_id": runtime_profile_id,
                    "system_instruction_template": runtime_profile.get(
                        "system_instruction_template"
                    ),
                }
            ),
        )


    async def _knowledge_base_ref(self, asset_id: str) -> CurriculumVersionRef:
        knowledge_base = _as_dict(await self._read_reference("knowledge_base", asset_id))
        if not knowledge_base or knowledge_base.get("status") != "active":
            raise RuntimeSnapshotBuildError(
                "asset_unpublished",
                "Knowledge base reference is missing or unavailable.",
            )
        return CurriculumVersionRef(
            asset_type="knowledge_base",
            asset_id=asset_id,
            version=1,
            hash=_stable_hash(knowledge_base),
            snapshot_label="legacy_unversioned",
        )

    async def _rubric_ref(self, asset_id: str) -> CurriculumVersionRef:
        ruleset = _as_dict(await self._read_reference("scoring_ruleset", asset_id))
        if not ruleset or ruleset.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "rubric_missing",
                "Scoring rubric reference is missing or unavailable.",
            )
        return CurriculumVersionRef(
            asset_type="scoring_ruleset",
            asset_id=asset_id,
            version=ruleset.get("version", 1),
            hash=_stable_hash(ruleset),
            snapshot_label="published",
        )

    async def _case_item_ref(self, asset_id: str) -> CurriculumVersionRef:
        case_item = _as_dict(await self._read_reference("case_item", asset_id))
        if not case_item or case_item.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "asset_unpublished",
                "CaseItem reference is missing or unpublished.",
            )
        return CurriculumVersionRef(
            asset_type="case_item",
            asset_id=asset_id,
            version=case_item.get("version", 1),
            hash=str(case_item["content_hash"]),
            snapshot_label="published",
        )

    async def _role_profile_ref(self, asset_id: str) -> CurriculumVersionRef:
        role_profile = _as_dict(await self._read_reference("role_profile", asset_id))
        if not role_profile or role_profile.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "asset_unpublished",
                "RoleProfile reference is missing or unpublished.",
            )
        return CurriculumVersionRef(
            asset_type="role_profile",
            asset_id=asset_id,
            version=role_profile.get("version", 1),
            hash=str(role_profile["content_hash"]),
            snapshot_label="published",
        )

    async def _examiner_agent_ref(self, asset_id: str) -> CurriculumVersionRef:
        examiner_agent = _as_dict(await self._read_reference("examiner_agent", asset_id))
        if not examiner_agent or examiner_agent.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "examiner_agent_unpublished",
                "ExaminerAgent reference is missing or unpublished.",
            )
        return CurriculumVersionRef(
            asset_type="examiner_agent",
            asset_id=asset_id,
            version=examiner_agent.get("version", 1),
            hash=str(examiner_agent["content_hash"]),
            snapshot_label="published",
        )

    async def _examiner_content_refs(self, asset_id: str) -> list[CurriculumVersionRef]:
        examiner_agent = _as_dict(await self._read_reference("examiner_agent", asset_id))
        if not examiner_agent or examiner_agent.get("status") != "published":
            raise RuntimeSnapshotBuildError(
                "examiner_agent_unpublished",
                "ExaminerAgent reference is missing or unpublished.",
            )
        refs = [
            CurriculumVersionRef(
                asset_type="examiner_agent",
                asset_id=asset_id,
                version=examiner_agent.get("version", 1),
                hash=str(examiner_agent["content_hash"]),
                snapshot_label="published",
            )
        ]
        for question_id in examiner_agent.get("question_source_ids", []) or []:
            refs.append(await self._question_item_ref(str(question_id)))
        return refs

    async def _question_item_ref(self, asset_id: str) -> CurriculumVersionRef:
        question = _as_dict(await self._read_reference("question_item", asset_id))
        if (
            not question
            or question.get("status") != "published"
            or bool(question.get("safety_flagged", False))
        ):
            raise RuntimeSnapshotBuildError(
                "question_item_unpublished",
                "QuestionItem reference is missing, unpublished, or safety flagged.",
            )
        return CurriculumVersionRef(
            asset_type="question_item",
            asset_id=asset_id,
            version=question.get("version", 1),
            hash=str(question["content_hash"]),
            snapshot_label="published",
        )


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


def _stable_hash(payload: object) -> str:
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
    if not role_profile or role_profile.get("status") != "published":
        raise RuntimeSnapshotBuildError(
            "role_profile_unpublished",
            "RoleProfile reference is missing or unpublished.",
        )
    return CurriculumVersionRef(
        asset_type="role_profile",
        asset_id=str(role_profile["role_profile_id"]),
        version=role_profile.get("version", 1),
        hash=str(role_profile["content_hash"]),
        snapshot_label="published",
    )


def _voice_id_from_role_profile(role_profile: dict[str, Any] | None) -> str | None:
    if not role_profile:
        return None
    voice_id = role_profile.get("voice_id")
    if isinstance(voice_id, str) and voice_id.strip():
        return voice_id.strip()
    return None
