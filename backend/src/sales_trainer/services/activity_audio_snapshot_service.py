"""Freeze governed audio activity bindings before submission."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AudioAssessmentConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
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
        rubric = await self._rubric_revision(
            logical_id=config.scoring_rubric_id,
            confirmed_revision_id=confirmed_scoring_rubric_revision_id,
        )
        if rubric is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_RUBRIC_NOT_PUBLISHED]", "录音评分标准尚未发布。", 409
            )
        material_snapshot = await self._material_snapshot(
            material_id=config.material_id,
            confirmed_version_id=confirmed_material_version_id,
        )
        rubric_payload = dict(rubric.payload_json)
        return ActivityAudioSnapshots(
            material_snapshot=material_snapshot,
            score_scheme_snapshot={
                **rubric_payload,
                "rubric_id": config.scoring_rubric_id,
                "rubric_revision_id": str(rubric.revision_id),
                "pass_threshold": config.pass_score,
            },
            task_brief_snapshot={
                "activity_id": context.activity.activity_id,
                "enrollment_id": context.enrollment_id,
                "path_revision_id": context.path_revision_id,
                "phase_id": context.phase_id,
                "module_id": context.module_id,
                "activity": context.activity.model_dump(mode="json"),
            },
        )

    async def _rubric_revision(
        self,
        *,
        logical_id: str,
        confirmed_revision_id: str | None,
    ) -> SalesTrainerAssetRevision | None:
        if confirmed_revision_id is None:
            revision = await self._revisions.active_revision(
                resource_type="audio_scoring_rubric",
                logical_id=logical_id,
            )
            return (
                revision
                if revision is not None and str(revision.status) == "published"
                else None
            )
        revision = await self._revisions.revision_by_id(confirmed_revision_id)
        if (
            revision is None
            or str(revision.resource_type) != "audio_scoring_rubric"
            or str(revision.logical_id) != logical_id
            or str(revision.status) != "published"
        ):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_AUDIO_RUBRIC_VERSION_INVALID]",
                "本次录音使用的评分标准版本无效或尚未发布，请刷新页面后重试。",
                409,
            )
        return revision

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
