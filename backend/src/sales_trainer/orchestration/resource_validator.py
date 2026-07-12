"""Batched publish-readiness validation for activity resource bindings."""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerExamPaper,
    SalesTrainerMaterial,
    SalesTrainerUnitQuestion,
)
from sales_trainer.orchestration.contracts import (
    AiCoachActivityConfig,
    AudioAssessmentConfig,
    LessonConfig,
    QuizConfig,
    RealtimeRoleplayConfig,
    TrainingPathPayload,
)
from sales_trainer.orchestration.graph import PathIssue
from sales_trainer.services.curriculum_practice_adapter import (
    published_learning_content_ids,
    published_practice_template_ids,
)
from sales_trainer.services.voice_runtime_adapter import active_voice_runtime_ids


class PathResourceValidator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def validate(self, payload: TrainingPathPayload) -> tuple[PathIssue, ...]:
        activities = [
            (activity, f"phases[{pi}].modules[{mi}].activities[{ai}]")
            for pi, phase in enumerate(payload.phases)
            for mi, module in enumerate(phase.modules)
            for ai, activity in enumerate(module.activities)
        ]
        ids: dict[str, set[str]] = defaultdict(set)
        for activity, _ in activities:
            config = activity.config
            if activity.type == "lesson":
                config = cast(LessonConfig, config)
                ids["lesson"].add(config.learning_content_id)
            elif activity.type == "quiz":
                config = cast(QuizConfig, config)
                ids["quiz"].add(config.exam_paper_id)
            elif activity.type == "audio_assessment":
                config = cast(AudioAssessmentConfig, config)
                ids["rubric"].add(config.scoring_rubric_id)
                if config.material_id:
                    ids["material"].add(config.material_id)
            elif activity.type == "realtime_roleplay":
                config = cast(RealtimeRoleplayConfig, config)
                ids["template"].add(config.practice_template_id)
                ids["runtime"].add(config.runtime_profile_id)
            elif activity.type == "ai_coach":
                config = cast(AiCoachActivityConfig, config)
                ids["coach"].add(config.coach_profile_id)

        valid_lessons = await published_learning_content_ids(self._db, ids["lesson"])
        valid_quizzes = await self._published_quizzes(ids["quiz"])
        valid_materials = await self._published_materials(ids["material"])
        valid_templates = await published_practice_template_ids(self._db, ids["template"])
        valid_runtimes = await active_voice_runtime_ids(self._db, ids["runtime"])
        valid_rubrics = await self._active_assets("audio_scoring_rubric", ids["rubric"])
        valid_coaches = await self._active_assets("ai_coach_profile", ids["coach"])

        issues: list[PathIssue] = []
        for activity, path in activities:
            config = activity.config
            missing: list[tuple[bool, str, str, str]] = []
            if activity.type == "lesson":
                config = cast(LessonConfig, config)
                missing.append(
                    (
                        config.learning_content_id not in valid_lessons,
                        "learning_content_not_published",
                        "学习内容尚未发布或没有章节。",
                        "learning_content_id",
                    )
                )
            elif activity.type == "quiz":
                config = cast(QuizConfig, config)
                missing.append(
                    (
                        config.exam_paper_id not in valid_quizzes,
                        "exam_paper_not_published",
                        "小测没有已发布考卷。",
                        "exam_paper_id",
                    )
                )
            elif activity.type == "audio_assessment":
                config = cast(AudioAssessmentConfig, config)
                missing.append(
                    (
                        config.scoring_rubric_id not in valid_rubrics,
                        "scoring_rubric_not_published",
                        "录音评分标准尚未发布。",
                        "scoring_rubric_id",
                    )
                )
                if config.material_id:
                    missing.append(
                        (
                            config.material_id not in valid_materials,
                            "material_not_published",
                            "讲解材料没有当前已发布版本。",
                            "material_id",
                        )
                    )
            elif activity.type == "realtime_roleplay":
                config = cast(RealtimeRoleplayConfig, config)
                missing.extend(
                    (
                        (
                            config.practice_template_id not in valid_templates,
                            "practice_template_not_published",
                            "实时对练模板尚未发布。",
                            "practice_template_id",
                        ),
                        (
                            config.runtime_profile_id not in valid_runtimes,
                            "runtime_profile_not_ready",
                            "实时语音运行配置尚未启用。",
                            "runtime_profile_id",
                        ),
                    )
                )
            elif activity.type == "ai_coach":
                config = cast(AiCoachActivityConfig, config)
                missing.append(
                    (
                        config.coach_profile_id not in valid_coaches,
                        "coach_profile_not_ready",
                        "AI 教练配置尚未发布。",
                        "coach_profile_id",
                    )
                )
            for is_missing, code, message, field in missing:
                if is_missing:
                    issues.append(
                        PathIssue(
                            code=code,
                            message=f"{activity.title}：{message}",
                            object_id=activity.activity_id,
                            field_path=f"{path}.config.{field}",
                        )
                    )
        return tuple(sorted(issues, key=lambda item: (item.field_path, item.code)))

    async def _published_quizzes(self, values: set[str]) -> set[str]:
        if not values:
            return set()
        rows = await self._db.scalars(
            select(SalesTrainerExamPaper.paper_id)
            .join(
                SalesTrainerUnitQuestion,
                SalesTrainerUnitQuestion.unit_id == SalesTrainerExamPaper.unit_id,
            )
            .where(
                SalesTrainerExamPaper.paper_id.in_(values),
                SalesTrainerExamPaper.status == "published",
            )
            .group_by(SalesTrainerExamPaper.paper_id)
            .having(func.count(SalesTrainerUnitQuestion.id) > 0)
        )
        return {str(value) for value in rows}

    async def _published_materials(self, values: set[str]) -> set[str]:
        if not values:
            return set()
        rows = await self._db.scalars(
            select(SalesTrainerMaterial.material_id).where(
                SalesTrainerMaterial.material_id.in_(values),
                SalesTrainerMaterial.status == "published",
                SalesTrainerMaterial.current_version_id.is_not(None),
            )
        )
        return {str(value) for value in rows}

    async def _active_assets(self, resource_type: str, values: set[str]) -> set[str]:
        if not values:
            return set()
        rows = await self._db.scalars(
            select(SalesTrainerAssetRevision.logical_id)
            .join(
                SalesTrainerAssetActiveRevision,
                SalesTrainerAssetActiveRevision.active_revision_id
                == SalesTrainerAssetRevision.revision_id,
            )
            .where(
                SalesTrainerAssetRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.logical_id.in_(values),
                SalesTrainerAssetRevision.status == "published",
            )
        )
        return {str(value) for value in rows}


__all__ = ["PathResourceValidator"]
