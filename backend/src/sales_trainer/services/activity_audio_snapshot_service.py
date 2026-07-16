"""Freeze governed audio activity bindings before submission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AudioAssessmentConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.material_service import normalize_learner_rubric
from sales_trainer.services.prompt_revision_payloads import (
    PROMPT_RESOURCE_TYPE,
    prompt_lifecycle_snapshot,
)


@dataclass(frozen=True, slots=True)
class ActivityAudioSnapshots:
    material_snapshot: dict[str, object] | None
    score_scheme_snapshot: dict[str, object]
    task_brief_snapshot: dict[str, object]


class ActivityAudioSnapshotService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def freeze(
        self,
        *,
        context: ActivityExecutionContext,
        confirmed_material_version_id: str | None,
        confirmed_scoring_rubric_revision_id: str | None = None,
    ) -> ActivityAudioSnapshots:
        if context.activity.type != "audio_assessment":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_CONTEXT_MISMATCH]", "当前活动不是录音讲解。", 409
            )
        config = cast(AudioAssessmentConfig, context.activity.config)
        score_scheme = await self._score_scheme_snapshot(
            prompt_id=config.scoring_rubric_id,
            pass_threshold=config.pass_score,
            confirmed_revision_id=confirmed_scoring_rubric_revision_id,
        )
        material_snapshot = await self._material_snapshot(
            material_id=config.material_id,
            confirmed_version_id=confirmed_material_version_id,
        )
        return ActivityAudioSnapshots(
            material_snapshot=material_snapshot,
            score_scheme_snapshot=score_scheme,
            task_brief_snapshot={
                "activity_id": context.activity.activity_id,
                "enrollment_id": context.enrollment_id,
                "path_revision_id": context.path_revision_id,
                "phase_id": context.phase_id,
                "module_id": context.module_id,
                "activity": context.activity.model_dump(mode="json"),
            },
        )

    async def _score_scheme_snapshot(
        self,
        *,
        prompt_id: str,
        pass_threshold: float,
        confirmed_revision_id: str | None,
    ) -> dict[str, object]:
        revision = await self._prompt_revision(
            prompt_id=prompt_id,
            confirmed_revision_id=confirmed_revision_id,
        )
        if revision is not None:
            return self._scheme_from_revision_payload(
                revision=revision,
                prompt_id=prompt_id,
                pass_threshold=pass_threshold,
            )

        prompt = await self._db.get(SalesTrainerAudioScorePrompt, prompt_id)
        if prompt is None or str(prompt.status) != "published":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]",
                "录音评分标准尚未发布，请重新选择或新建评分标准。",
                409,
            )
        snapshot = prompt_lifecycle_snapshot(prompt)
        rubric = cast(dict[str, Any], normalize_learner_rubric(prompt.learner_rubric))
        if "pass_threshold" not in rubric:
            rubric = {**rubric, "pass_threshold": pass_threshold}
        active = await self._revisions.active_revision(
            resource_type=PROMPT_RESOURCE_TYPE,
            logical_id=prompt_id,
        )
        return {
            "prompt_id": str(prompt.prompt_id),
            "name": str(prompt.name),
            "purpose": str(prompt.purpose),
            "version": int(prompt.version),
            "status": str(prompt.status),
            "learner_rubric": rubric,
            "pass_threshold": pass_threshold,
            "prompt_snapshot": snapshot,
            "rubric_revision_id": (
                str(active.revision_id) if active is not None else None
            ),
        }

    async def _prompt_revision(
        self,
        *,
        prompt_id: str,
        confirmed_revision_id: str | None,
    ) -> SalesTrainerAssetRevision | None:
        if confirmed_revision_id is None:
            return None
        revision = await self._revisions.revision_by_id(confirmed_revision_id)
        if (
            revision is None
            or str(revision.resource_type) != PROMPT_RESOURCE_TYPE
            or str(revision.logical_id) != prompt_id
            or str(revision.status) != "published"
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_RUBRIC_VERSION_INVALID]",
                "本次录音使用的评分标准版本无效或尚未发布，请刷新页面后重试。",
                409,
            )
        return revision

    def _scheme_from_revision_payload(
        self,
        *,
        revision: SalesTrainerAssetRevision,
        prompt_id: str,
        pass_threshold: float,
    ) -> dict[str, object]:
        payload = cast(dict[str, Any], dict(revision.payload_json or {}))
        prompt_snapshot = {
            "prompt_id": str(payload.get("prompt_id") or prompt_id),
            "name": str(payload.get("name") or "录音评分标准"),
            "purpose": str(payload.get("purpose") or "general_audio_scoring"),
            "system_prompt": str(payload.get("system_prompt") or ""),
            "scoring_template": str(payload.get("scoring_template") or ""),
            "output_schema": payload.get("output_schema") or {},
            "learner_rubric": normalize_learner_rubric(payload.get("learner_rubric")),
            "version": int(payload.get("version") or revision.revision_no or 1),
            "status": "published",
        }
        if (
            not prompt_snapshot["system_prompt"]
            or not prompt_snapshot["scoring_template"]
            or "{transcript}" not in str(prompt_snapshot["scoring_template"])
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_RUBRIC_VERSION_INVALID]",
                "本次录音使用的评分标准版本无效或尚未发布，请刷新页面后重试。",
                409,
            )
        rubric = cast(
            dict[str, Any],
            normalize_learner_rubric(prompt_snapshot["learner_rubric"]),
        )
        if "pass_threshold" not in rubric:
            rubric = {**rubric, "pass_threshold": pass_threshold}
        return {
            "prompt_id": prompt_snapshot["prompt_id"],
            "name": prompt_snapshot["name"],
            "purpose": prompt_snapshot["purpose"],
            "version": prompt_snapshot["version"],
            "status": "published",
            "learner_rubric": rubric,
            "pass_threshold": pass_threshold,
            "prompt_snapshot": prompt_snapshot,
            "rubric_revision_id": str(revision.revision_id),
        }

    async def _material_snapshot(
        self, *, material_id: str | None, confirmed_version_id: str | None
    ) -> dict[str, object] | None:
        if material_id is None:
            if confirmed_version_id is not None:
                raise NewcomerOrchestrationError(
                    "[NEWCOMER_AUDIO_MATERIAL_MISMATCH]",
                    "当前活动没有配置讲解材料。",
                    409,
                )
            return None
        if confirmed_version_id is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_MATERIAL_CONFIRMATION_REQUIRED]",
                "请确认本次讲解使用的材料版本。",
                422,
            )
        material = await self._db.get(SalesTrainerMaterial, material_id)
        version = await self._db.get(SalesTrainerMaterialVersion, confirmed_version_id)
        if (
            material is None
            or version is None
            or str(version.material_id) != material_id
            or str(version.status) != "published"
            or str(material.status) != "published"
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_MATERIAL_VERSION_INVALID]",
                "讲解材料版本无效或尚未发布。",
                409,
            )
        return {
            "material_id": material_id,
            "material_version_id": confirmed_version_id,
            "name": str(material.name),
            "title": str(version.title),
            "file_hash": str(version.file_hash) if version.file_hash else None,
        }


__all__ = ["ActivityAudioSnapshotService", "ActivityAudioSnapshots"]
