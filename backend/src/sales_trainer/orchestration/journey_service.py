"""Canonical learner journey projected from one immutable path revision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    NewcomerTrainingEnrollment,
    SalesTrainerAssetRevision,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
)
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
)
from sales_trainer.orchestration.completion import (
    ProgressAggregate,
    aggregate_module_progress,
    aggregate_path_progress,
    aggregate_phase_progress,
)
from sales_trainer.orchestration.contracts import (
    ActivityConfig,
    ActivityDetailResponse,
    ActivityRunnerDescriptor,
    AiCoachRunnerDescriptor,
    AssignmentConfig,
    AssignmentRunnerDescriptor,
    AudioAssessmentConfig,
    AudioRunnerDescriptor,
    AudioScoringFocus,
    JourneyActivityProgress,
    JourneyModuleProgress,
    JourneyNextAction,
    JourneyPhaseProgress,
    JourneyProgressSummary,
    JourneyResponse,
    LessonConfig,
    LessonRunnerDescriptor,
    ModuleDetailResponse,
    QuizConfig,
    QuizRunnerDescriptor,
    RealtimeRunnerDescriptor,
    TrainingPathPayload,
)
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.registry import (
    ActivityTypeRegistry,
    build_activity_registry,
)
from sales_trainer.orchestration.repository import EnrollmentRepository
from sales_trainer.orchestration.revision_service import (
    PATH_LOGICAL_ID,
    PATH_RESOURCE_TYPE,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)


@dataclass(frozen=True, slots=True)
class ActivityLocation:
    phase_id: str
    module_id: str
    context: ActivityExecutionContext


class NewcomerJourneyService:
    def __init__(
        self, db: AsyncSession, *, registry: ActivityTypeRegistry | None = None
    ) -> None:
        self._db = db
        self._enrollments = EnrollmentRepository(db)
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._registry = registry or build_activity_registry(db)

    async def get_or_create_for_learner(self, *, learner: User) -> JourneyResponse:
        active = await self._required_active_revision()
        enrollment = await self._enrollments.get_or_create(
            learner_id=str(learner.user_id),
            path_id=PATH_LOGICAL_ID,
            path_revision_id=str(active.revision_id),
        )
        revision = await self._db.get(
            SalesTrainerAssetRevision, str(enrollment.path_revision_id)
        )
        if revision is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_PINNED_REVISION_MISSING]",
                "已登记的训练版本不存在。",
                409,
            )
        return await self._project(
            enrollment=enrollment, revision=revision, learner=learner
        )

    async def module_detail(
        self, *, learner: User, module_id: str
    ) -> ModuleDetailResponse:
        journey = await self.get_or_create_for_learner(learner=learner)
        for phase in journey.phases:
            for module in phase.modules:
                if module.module_id == module_id:
                    return ModuleDetailResponse(
                        enrollment_id=journey.enrollment_id,
                        path_revision_id=journey.path_revision_id,
                        phase_id=phase.phase_id,
                        module=module,
                    )
        raise NewcomerOrchestrationError(
            "[NEWCOMER_MODULE_NOT_FOUND]", "训练模块不存在。", 404
        )

    async def activity_detail(
        self, *, learner: User, activity_id: str
    ) -> ActivityDetailResponse:
        journey = await self.get_or_create_for_learner(learner=learner)
        for phase in journey.phases:
            for module in phase.modules:
                for activity in module.activities:
                    if activity.activity_id == activity_id:
                        return ActivityDetailResponse(
                            enrollment_id=journey.enrollment_id,
                            path_revision_id=journey.path_revision_id,
                            phase_id=phase.phase_id,
                            module_id=module.module_id,
                            activity=activity,
                            runner=await _runner_descriptor(
                                self._db,
                                (await self.context_for_activity(
                                    learner=learner, activity_id=activity_id
                                )).activity
                            ),
                        )
        raise NewcomerOrchestrationError(
            "[NEWCOMER_ACTIVITY_NOT_FOUND]", "训练活动不存在。", 404
        )

    async def context_for_activity(
        self, *, learner: User, activity_id: str
    ) -> ActivityExecutionContext:
        _, enrollment, payload = await self._pinned_payload(learner)
        for phase in payload.phases:
            for module in phase.modules:
                for activity in module.activities:
                    if activity.activity_id == activity_id:
                        return ActivityExecutionContext(
                            learner_id=str(learner.user_id),
                            enrollment_id=str(enrollment.enrollment_id),
                            path_revision_id=str(enrollment.path_revision_id),
                            phase_id=phase.phase_id,
                            module_id=module.module_id,
                            activity=activity,
                        )
        raise NewcomerOrchestrationError(
            "[NEWCOMER_ACTIVITY_NOT_FOUND]", "训练活动不存在。", 404
        )

    async def _pinned_payload(
        self, learner: User
    ) -> tuple[
        SalesTrainerAssetRevision, NewcomerTrainingEnrollment, TrainingPathPayload
    ]:
        active = await self._required_active_revision()
        enrollment = await self._enrollments.get_or_create(
            learner_id=str(learner.user_id),
            path_id=PATH_LOGICAL_ID,
            path_revision_id=str(active.revision_id),
        )
        revision = await self._db.get(
            SalesTrainerAssetRevision, str(enrollment.path_revision_id)
        )
        if revision is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_PINNED_REVISION_MISSING]",
                "已登记的训练版本不存在。",
                409,
            )
        return (
            revision,
            enrollment,
            TrainingPathPayload.model_validate(revision.payload_json),
        )

    async def _required_active_revision(self) -> SalesTrainerAssetRevision:
        revision = await self._revisions.active_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )
        if revision is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]", "新人训练路径尚未发布。", 409
            )
        return revision

    async def _project(
        self,
        *,
        enrollment: NewcomerTrainingEnrollment,
        revision: SalesTrainerAssetRevision,
        learner: User,
    ) -> JourneyResponse:
        payload = TrainingPathPayload.model_validate(revision.payload_json)
        phase_rows: list[JourneyPhaseProgress] = []
        phase_aggregates: dict[str, ProgressAggregate] = {}
        primary: JourneyNextAction | None = None
        optional_candidate: tuple[JourneyNextAction, str, str] | None = None
        completed_ids: set[str] = set()
        for phase in sorted(payload.phases, key=lambda item: item.order_index):
            module_rows: list[JourneyModuleProgress] = []
            module_aggregates: dict[str, ProgressAggregate] = {}
            phase_locked = any(
                prerequisite not in completed_ids
                for module in phase.modules
                for prerequisite in module.prerequisites
            )
            for module in sorted(phase.modules, key=lambda item: item.order_index):
                module_locked = phase_locked or any(
                    item not in completed_ids for item in module.prerequisites
                )
                projections: dict[str, ActivityProjection] = {}
                activity_rows: list[JourneyActivityProgress] = []
                for activity in sorted(
                    module.activities, key=lambda item: item.order_index
                ):
                    locked = module_locked or any(
                        item not in completed_ids for item in activity.prerequisites
                    )
                    context = ActivityExecutionContext(
                        learner_id=str(learner.user_id),
                        enrollment_id=str(enrollment.enrollment_id),
                        path_revision_id=str(revision.revision_id),
                        phase_id=phase.phase_id,
                        module_id=module.module_id,
                        activity=activity,
                    )
                    projection = await self._registry.handler_for(
                        activity.type
                    ).project(context)
                    projections[activity.activity_id] = projection
                    if projection.completed:
                        completed_ids.add(activity.activity_id)
                    action_key = (
                        _action_key(activity.type)
                        if not projection.completed and not locked
                        else None
                    )
                    is_primary = (
                        primary is None and activity.required and action_key is not None
                    )
                    if is_primary and action_key is not None:
                        primary = JourneyNextAction(
                            activity_id=activity.activity_id,
                            activity_type=activity.type,
                            action_key=action_key,
                            label=activity.primary_action_label or activity.title,
                        )
                    elif (
                        optional_candidate is None
                        and not activity.required
                        and action_key is not None
                    ):
                        optional_candidate = (
                            JourneyNextAction(
                                activity_id=activity.activity_id,
                                activity_type=activity.type,
                                action_key=action_key,
                                label=activity.primary_action_label or activity.title,
                            ),
                            phase.phase_id,
                            module.module_id,
                        )
                    activity_rows.append(
                        JourneyActivityProgress(
                            activity_id=activity.activity_id,
                            activity_type=activity.type,
                            title=activity.title,
                            description=activity.description,
                            objective=activity.objective,
                            why_it_matters=activity.why_it_matters,
                            steps=activity.steps,
                            success_criteria=activity.success_criteria,
                            primary_action_label=activity.primary_action_label,
                            required=activity.required,
                            estimated_minutes=activity.estimated_minutes,
                            status=projection.status,
                            completed=projection.completed,
                            passed=projection.passed,
                            score=projection.score,
                            max_score=projection.max_score,
                            locked=locked,
                            lock_reason="请先完成前置任务" if locked else None,
                            action_key=action_key,
                            is_primary_next_action=is_primary,
                        )
                    )
                aggregate = aggregate_module_progress(module, projections)
                module_aggregates[module.module_id] = aggregate
                if aggregate.completed:
                    completed_ids.add(module.module_id)
                module_rows.append(
                    JourneyModuleProgress(
                        module_id=module.module_id,
                        title=module.title,
                        description=module.description,
                        outcome=module.outcome,
                        required=module.required,
                        estimated_minutes=module.estimated_minutes,
                        status="completed"
                        if aggregate.completed
                        else "locked"
                        if module_locked
                        else "in_progress",
                        completed=aggregate.completed,
                        completed_count=aggregate.completed_count,
                        total_required=aggregate.total_required,
                        percent=aggregate.percent,
                        locked=module_locked,
                        lock_reason="请先完成前置模块" if module_locked else None,
                        activities=activity_rows,
                    )
                )
            phase_aggregate = aggregate_phase_progress(phase, module_aggregates)
            phase_aggregates[phase.phase_id] = phase_aggregate
            if phase_aggregate.completed:
                completed_ids.add(phase.phase_id)
            phase_rows.append(
                JourneyPhaseProgress(
                    phase_id=phase.phase_id,
                    title=phase.title,
                    description=phase.description,
                    outcome=phase.outcome,
                    required=phase.required,
                    status="completed"
                    if phase_aggregate.completed
                    else "locked"
                    if phase_locked
                    else "in_progress",
                    completed=phase_aggregate.completed,
                    completed_count=phase_aggregate.completed_count,
                    total_required=phase_aggregate.total_required,
                    percent=phase_aggregate.percent,
                    locked=phase_locked,
                    lock_reason="请先完成前置阶段" if phase_locked else None,
                    modules=module_rows,
                )
            )
        overall = aggregate_path_progress(payload, phase_aggregates)
        if primary is None and optional_candidate is not None:
            primary, candidate_phase_id, candidate_module_id = optional_candidate
            phase_rows = [
                phase.model_copy(
                    update={
                        "modules": [
                            module.model_copy(
                                update={
                                    "activities": [
                                        activity.model_copy(
                                            update={
                                                "is_primary_next_action": activity.activity_id
                                                == primary.activity_id
                                            }
                                        )
                                        for activity in module.activities
                                    ]
                                }
                            )
                            if phase.phase_id == candidate_phase_id
                            and module.module_id == candidate_module_id
                            else module
                            for module in phase.modules
                        ]
                    }
                )
                if phase.phase_id == candidate_phase_id
                else phase
                for phase in phase_rows
            ]
        return JourneyResponse(
            enrollment_id=str(enrollment.enrollment_id),
            path_revision_id=str(revision.revision_id),
            path_title=payload.title,
            phases=phase_rows,
            progress=JourneyProgressSummary(
                completed=overall.completed,
                completed_count=overall.completed_count,
                total_required=overall.total_required,
                percent=overall.percent,
            ),
            primary_next_action=primary,
        )


def _action_key(activity_type: str) -> str:
    return {
        "lesson": "continue_lesson",
        "quiz": "start_quiz",
        "audio_assessment": "record_audio",
        "realtime_roleplay": "start_realtime_roleplay",
        "ai_coach": "start_ai_coach",
        "assignment": "submit_assignment",
    }[activity_type]


async def _runner_descriptor(
    db: AsyncSession, activity: ActivityConfig
) -> ActivityRunnerDescriptor:
    if activity.type == "lesson":
        lesson_config = cast(LessonConfig, activity.config)
        return LessonRunnerDescriptor(
            learning_content_id=lesson_config.learning_content_id,
            completion_mode=lesson_config.completion_mode,
        )
    if activity.type == "quiz":
        quiz_config = cast(QuizConfig, activity.config)
        return QuizRunnerDescriptor(
            exam_paper_id=quiz_config.exam_paper_id,
            pass_score=quiz_config.pass_score,
            max_attempts=quiz_config.max_attempts,
        )
    if activity.type == "audio_assessment":
        audio_config = cast(AudioAssessmentConfig, activity.config)
        material_version_id = None
        material_title = None
        material_version_label = None
        material_file_name = None
        material_content_type = None
        if audio_config.material_id:
            material = await db.get(SalesTrainerMaterial, audio_config.material_id)
            if material is not None and material.status == "published":
                material_title = str(material.name)
                version = (
                    await db.get(
                        SalesTrainerMaterialVersion,
                        str(material.current_version_id),
                    )
                    if material.current_version_id is not None
                    else None
                )
                if version is not None and version.status == "published":
                    material_version_id = str(version.version_id)
                    material_version_label = str(version.version_label)
                    material_file_name = str(version.file_name)
                    material_content_type = str(version.content_type)
        rubric = await SalesTrainerAssetRevisionService(db).active_revision(
            resource_type="audio_scoring_rubric",
            logical_id=audio_config.scoring_rubric_id,
        )
        if rubric is not None and rubric.status != "published":
            rubric = None
        rubric_payload = (
            cast(dict[str, object], rubric.payload_json) if rubric is not None else {}
        )
        return AudioRunnerDescriptor(
            material_id=audio_config.material_id,
            material_version_id=material_version_id,
            material_title=material_title,
            material_version_label=material_version_label,
            material_file_name=material_file_name,
            material_content_type=material_content_type,
            scoring_rubric_revision_id=(
                str(rubric.revision_id) if rubric is not None else None
            ),
            scoring_rubric_revision_no=(
                int(rubric.revision_no) if rubric is not None else None
            ),
            scoring_rubric_title=_safe_optional_text(
                rubric_payload.get("title"), max_length=200
            ),
            scoring_focuses=_scoring_focuses(rubric_payload.get("dimensions")),
            example_transcript=audio_config.example_transcript,
            pass_score=audio_config.pass_score,
            max_attempts=audio_config.max_attempts,
        )
    if activity.type == "realtime_roleplay":
        return RealtimeRunnerDescriptor()
    if activity.type == "ai_coach":
        return AiCoachRunnerDescriptor()
    assignment_config = cast(AssignmentConfig, activity.config)
    return AssignmentRunnerDescriptor(
        submission_type=assignment_config.submission_type,
        review_mode=assignment_config.review_mode,
        max_file_size_bytes=assignment_config.max_file_size_bytes,
    )


def _safe_optional_text(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:max_length] or None


def _scoring_focuses(value: object) -> list[AudioScoringFocus]:
    if not isinstance(value, list):
        return []
    focuses: list[AudioScoringFocus] = []
    for raw_dimension in value:
        if isinstance(raw_dimension, str):
            label = _safe_optional_text(raw_dimension, max_length=120)
            description = None
            weight = None
        elif isinstance(raw_dimension, dict):
            label = _safe_optional_text(raw_dimension.get("label"), max_length=120)
            description = _safe_optional_text(
                raw_dimension.get("description"), max_length=500
            )
            raw_weight = raw_dimension.get("weight")
            weight = (
                float(raw_weight)
                if isinstance(raw_weight, (int, float))
                and not isinstance(raw_weight, bool)
                and 0 <= raw_weight <= 100
                else None
            )
        else:
            continue
        if label is not None:
            focuses.append(
                AudioScoringFocus(
                    label=label,
                    description=description,
                    weight=weight,
                )
            )
    return focuses


__all__ = ["NewcomerJourneyService"]
