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
            content_assets=[
                await self._knowledge_base_ref(str(asset_id))
                for asset_id in template_data.get("knowledge_base_refs", [])
            ],
            rubric=await self._rubric_ref(str(template_data["scoring_ruleset_id"])),
            runtime=runtime,
        )
        payload = snapshot.model_dump()
        payload["actor_id"] = actor_id
        return snapshot.model_copy(update={"snapshot_hash": _stable_hash(payload)})

    async def _read_reference(self, asset_type: str, asset_id: str) -> object | None:
        reference = self._reference_reader(asset_type, asset_id)
        if isawaitable(reference):
            return await reference
        return reference

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
