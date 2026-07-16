"""Batched publish-readiness validation for activity resource bindings."""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
    SalesTrainerAudioScorePrompt,
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


def _binding_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value


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
                if value := _binding_id(config.learning_content_id):
                    ids["lesson"].add(value)
            elif activity.type == "quiz":
                config = cast(QuizConfig, config)
                if value := _binding_id(config.exam_paper_id):
                    ids["quiz"].add(value)
            elif activity.type == "audio_assessment":
                config = cast(AudioAssessmentConfig, config)
                if value := _binding_id(config.scoring_rubric_id):
                    ids["rubric"].add(value)
                if value := _binding_id(config.material_id):
                    ids["material"].add(value)
            elif activity.type == "realtime_roleplay":
                config = cast(RealtimeRoleplayConfig, config)
                if value := _binding_id(config.practice_template_id):
                    ids["template"].add(value)
                if value := _binding_id(config.runtime_profile_id):
                    ids["runtime"].add(value)
            elif activity.type == "ai_coach":
                config = cast(AiCoachActivityConfig, config)
                if value := _binding_id(config.coach_profile_id):
                    ids["coach"].add(value)

        valid_lessons = await published_learning_content_ids(self._db, ids["lesson"])
        valid_quizzes = await self._published_quizzes(ids["quiz"])
        valid_materials = await self._published_materials(ids["material"])
        valid_templates = await published_practice_template_ids(
            self._db, ids["template"]
        )
        valid_runtimes = await active_voice_runtime_ids(self._db, ids["runtime"])
        valid_rubrics = await self._published_score_prompts(ids["rubric"])
        valid_coaches = await self._active_assets("ai_coach_profile", ids["coach"])

        issues: list[PathIssue] = []
        for activity, path in activities:
            config = activity.config

            def add_binding_issue(
                *,
                value: str | None,
                valid_values: set[str],
                required_code: str,
                required_message: str,
                unavailable_code: str,
                unavailable_message: str,
                field: str,
            ) -> None:
                normalized = _binding_id(value)
                if normalized is None:
                    code = required_code
                    message = required_message
                elif normalized not in valid_values:
                    code = unavailable_code
                    message = unavailable_message
                else:
                    return
                issues.append(
                    PathIssue(
                        code=code,
                        message=f"{activity.title}：{message}",
                        object_id=activity.activity_id,
                        field_path=f"{path}.config.{field}",
                    )
                )

            if activity.type == "lesson":
                config = cast(LessonConfig, config)
                add_binding_issue(
                    value=config.learning_content_id,
                    valid_values=valid_lessons,
                    required_code="learning_content_required",
                    required_message="请选择已发布的学习内容。",
                    unavailable_code="learning_content_not_published",
                    unavailable_message="学习内容尚未发布或没有章节。",
                    field="learning_content_id",
                )
            elif activity.type == "quiz":
                config = cast(QuizConfig, config)
                add_binding_issue(
                    value=config.exam_paper_id,
                    valid_values=valid_quizzes,
                    required_code="exam_paper_required",
                    required_message="请选择已发布的试卷。",
                    unavailable_code="exam_paper_not_published",
                    unavailable_message="小测没有已发布考卷。",
                    field="exam_paper_id",
                )
            elif activity.type == "audio_assessment":
                config = cast(AudioAssessmentConfig, config)
                add_binding_issue(
                    value=config.scoring_rubric_id,
                    valid_values=valid_rubrics,
                    required_code="scoring_rubric_required",
                    required_message="请选择已发布的录音评分标准。",
                    unavailable_code="scoring_rubric_not_published",
                    unavailable_message="请重新选择或新建评分标准。",
                    field="scoring_rubric_id",
                )
                if material_id := _binding_id(config.material_id):
                    if material_id not in valid_materials:
                        issues.append(
                            PathIssue(
                                code="material_not_published",
                                message=f"{activity.title}：讲解材料没有当前已发布版本。",
                                object_id=activity.activity_id,
                                field_path=f"{path}.config.material_id",
                            )
                        )
            elif activity.type == "realtime_roleplay":
                config = cast(RealtimeRoleplayConfig, config)
                add_binding_issue(
                    value=config.practice_template_id,
                    valid_values=valid_templates,
                    required_code="practice_template_required",
                    required_message="请选择已发布的实时对练模板。",
                    unavailable_code="practice_template_not_published",
                    unavailable_message="实时对练模板尚未发布。",
                    field="practice_template_id",
                )
                add_binding_issue(
                    value=config.runtime_profile_id,
                    valid_values=valid_runtimes,
                    required_code="runtime_profile_required",
                    required_message="请选择已启用的实时语音运行配置。",
                    unavailable_code="runtime_profile_not_ready",
                    unavailable_message="实时语音运行配置尚未启用。",
                    field="runtime_profile_id",
                )
            elif activity.type == "ai_coach":
                config = cast(AiCoachActivityConfig, config)
                add_binding_issue(
                    value=config.coach_profile_id,
                    valid_values=valid_coaches,
                    required_code="coach_profile_required",
                    required_message="请选择已发布的 AI 教练配置。",
                    unavailable_code="coach_profile_not_ready",
                    unavailable_message="AI 教练配置尚未发布。",
                    field="coach_profile_id",
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

    async def _published_score_prompts(self, values: set[str]) -> set[str]:
        if not values:
            return set()
        rows = await self._db.scalars(
            select(SalesTrainerAudioScorePrompt.prompt_id).where(
                SalesTrainerAudioScorePrompt.prompt_id.in_(values),
                SalesTrainerAudioScorePrompt.status == "published",
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
