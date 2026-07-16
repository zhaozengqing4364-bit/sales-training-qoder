"""Batch list projections for admin Journey summaries (no N× full tree)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import Team, TeamMembership, User
from common.teams import TeamScopePolicy
from curriculum_practice.models import (
    LearningChapter,
    LearningContent,
    LearningProgress,
)
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAssetRevision,
)
from sales_trainer.orchestration.activities.base import ActivityProjection
from sales_trainer.orchestration.completion import (
    ProgressAggregate,
    aggregate_module_progress,
    aggregate_path_progress,
    aggregate_phase_progress,
)
from sales_trainer.orchestration.contracts import (
    ActivityConfig,
    AdminJourneyListItem,
    AdminJourneyListResponse,
    JourneyListCurrentPhase,
    JourneyListSummary,
    JourneyNextAction,
    JourneyProgressSummary,
    LessonConfig,
    TrainingPathPayload,
)
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.orchestration.revision_service import (
    PATH_LOGICAL_ID,
    PATH_RESOURCE_TYPE,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)

_ACTION_KEYS = {
    "lesson": "continue_lesson",
    "quiz": "start_quiz",
    "audio_assessment": "record_audio",
    "realtime_roleplay": "start_realtime_roleplay",
    "ai_coach": "start_ai_coach",
    "assignment": "submit_assignment",
}

_RISK_STATUSES = frozenset({"failed", "needs_review", "error"})


@dataclass(frozen=True, slots=True)
class _LessonProgress:
    completed: bool
    status: str


@dataclass(slots=True)
class JourneySummaryListResult:
    response: AdminJourneyListResponse
    wrote: bool


class JourneySummaryReadService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._attempts = AttemptRepository(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def list_summaries(
        self,
        *,
        current_user: User,
        team_id: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> JourneySummaryListResult:
        team_scope = await TeamScopePolicy(self._db).resolve(current_user)
        filters = [NewcomerTrainingEnrollment.path_id == PATH_LOGICAL_ID]
        if team_id is not None:
            if not team_scope.allows_team(team_id):
                return JourneySummaryListResult(
                    AdminJourneyListResponse(items=[], total=0), False
                )
            team_learner_ids = set(
                (
                    await self._db.scalars(
                        select(TeamMembership.user_id).where(
                            TeamMembership.team_id == team_id,
                            TeamMembership.effective_from <= datetime.now(UTC),
                            or_(
                                TeamMembership.effective_to.is_(None),
                                TeamMembership.effective_to > datetime.now(UTC),
                            ),
                        )
                    )
                ).all()
            )
            if not team_learner_ids:
                return JourneySummaryListResult(
                    AdminJourneyListResponse(items=[], total=0), False
                )
            filters.append(User.user_id.in_(team_learner_ids))
        if not team_scope.unrestricted:
            if not team_scope.learner_ids:
                return JourneySummaryListResult(
                    AdminJourneyListResponse(items=[], total=0), False
                )
            filters.append(User.user_id.in_(team_scope.learner_ids))
        if search and search.strip():
            filters.append(User.name.ilike(f"%{search.strip()}%"))

        total = int(
            await self._db.scalar(
                select(func.count())
                .select_from(NewcomerTrainingEnrollment)
                .join(User, User.user_id == NewcomerTrainingEnrollment.learner_id)
                .where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._db.execute(
                    select(NewcomerTrainingEnrollment, User)
                    .join(
                        User,
                        User.user_id == NewcomerTrainingEnrollment.learner_id,
                    )
                    .where(*filters)
                    .order_by(User.name, User.user_id)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )
        if not rows:
            return JourneySummaryListResult(
                AdminJourneyListResponse(items=[], total=total), False
            )

        active = await self._required_active_revision()
        active_id = str(active.revision_id)
        stale_ids = [
            str(enrollment.enrollment_id)
            for enrollment, _learner in rows
            if str(enrollment.path_revision_id) != active_id
        ]
        wrote = False
        if stale_ids:
            await self._db.execute(
                update(NewcomerTrainingEnrollment)
                .where(NewcomerTrainingEnrollment.enrollment_id.in_(stale_ids))
                .values(path_revision_id=active_id)
            )
            await self._db.flush()
            wrote = True
            for enrollment, _learner in rows:
                if str(enrollment.enrollment_id) in set(stale_ids):
                    setattr(enrollment, "path_revision_id", active_id)

        payload = TrainingPathPayload.model_validate(active.payload_json)
        enrollment_ids = [str(enrollment.enrollment_id) for enrollment, _ in rows]
        learner_ids = [str(learner.user_id) for _, learner in rows]
        attempts_by_enrollment = await self._attempts.latest_for_enrollments(
            enrollment_ids=enrollment_ids
        )
        lesson_progress = await self._batch_lesson_progress(
            payload=payload, learner_ids=learner_ids
        )
        team_by_learner = await self._teams_for_learners(learner_ids)

        items: list[AdminJourneyListItem] = []
        for enrollment, learner in rows:
            summary = self._project_summary(
                enrollment=enrollment,
                revision=active,
                payload=payload,
                learner_id=str(learner.user_id),
                attempts=attempts_by_enrollment.get(
                    str(enrollment.enrollment_id), {}
                ),
                lesson_progress=lesson_progress,
            )
            items.append(
                AdminJourneyListItem(
                    learner_id=str(learner.user_id),
                    learner_name=str(learner.name or ""),
                    team=team_by_learner.get(str(learner.user_id)),
                    summary=summary,
                )
            )
        return JourneySummaryListResult(
            AdminJourneyListResponse(items=items, total=total), wrote
        )

    async def _required_active_revision(self) -> SalesTrainerAssetRevision:
        revision = await self._revisions.active_revision(
            resource_type=PATH_RESOURCE_TYPE, logical_id=PATH_LOGICAL_ID
        )
        if revision is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径尚未发布。",
                409,
            )
        return revision

    async def _teams_for_learners(
        self, learner_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        if not learner_ids:
            return {}
        team_rows = await self._db.execute(
            select(
                TeamMembership.user_id,
                Team.team_id,
                Team.code,
                Team.name,
            )
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id.in_(learner_ids),
                TeamMembership.effective_from <= datetime.now(UTC),
                or_(
                    TeamMembership.effective_to.is_(None),
                    TeamMembership.effective_to > datetime.now(UTC),
                ),
                Team.is_active.is_(True),
            )
        )
        return {
            str(user_id): {
                "team_id": str(mapped_team_id),
                "code": str(code),
                "name": str(name),
            }
            for user_id, mapped_team_id, code, name in team_rows.all()
        }

    async def _batch_lesson_progress(
        self, *, payload: TrainingPathPayload, learner_ids: list[str]
    ) -> dict[tuple[str, str], _LessonProgress]:
        content_ids = sorted(
            {
                cast(LessonConfig, activity.config).learning_content_id
                for phase in payload.phases
                for module in phase.modules
                for activity in module.activities
                if activity.type == "lesson"
            }
        )
        if not content_ids or not learner_ids:
            return {}
        published = {
            str(content_id)
            for content_id in (
                await self._db.scalars(
                    select(LearningContent.learning_content_id).where(
                        LearningContent.learning_content_id.in_(content_ids),
                        LearningContent.status == "published",
                    )
                )
            ).all()
        }
        missing = [content_id for content_id in content_ids if content_id not in published]
        if missing:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_LESSON_UNAVAILABLE]",
                "学习内容暂不可用，请联系管理员。",
                409,
            )
        chapter_counts = {
            str(content_id): int(count or 0)
            for content_id, count in (
                await self._db.execute(
                    select(
                        LearningChapter.learning_content_id,
                        func.count(),
                    )
                    .where(LearningChapter.learning_content_id.in_(content_ids))
                    .group_by(LearningChapter.learning_content_id)
                )
            ).all()
        }
        completed_counts = {
            (str(user_id), str(content_id)): int(count or 0)
            for user_id, content_id, count in (
                await self._db.execute(
                    select(
                        LearningProgress.user_id,
                        LearningProgress.learning_content_id,
                        func.count(),
                    )
                    .where(
                        LearningProgress.user_id.in_(learner_ids),
                        LearningProgress.learning_content_id.in_(content_ids),
                    )
                    .group_by(
                        LearningProgress.user_id,
                        LearningProgress.learning_content_id,
                    )
                )
            ).all()
        }
        result: dict[tuple[str, str], _LessonProgress] = {}
        for learner_id in learner_ids:
            for content_id in content_ids:
                total = chapter_counts.get(content_id, 0)
                completed = completed_counts.get((learner_id, content_id), 0)
                is_completed = total > 0 and completed >= total
                if is_completed:
                    status = "completed"
                elif completed:
                    status = "in_progress"
                else:
                    status = "not_started"
                result[(learner_id, content_id)] = _LessonProgress(
                    completed=is_completed, status=status
                )
        return result

    def _project_summary(
        self,
        *,
        enrollment: NewcomerTrainingEnrollment,
        revision: SalesTrainerAssetRevision,
        payload: TrainingPathPayload,
        learner_id: str,
        attempts: dict[str, NewcomerTrainingActivityAttempt],
        lesson_progress: dict[tuple[str, str], _LessonProgress],
    ) -> JourneyListSummary:
        del enrollment  # summary does not expose enrollment_id
        phase_aggregates: dict[str, ProgressAggregate] = {}
        primary: JourneyNextAction | None = None
        optional_candidate: JourneyNextAction | None = None
        completed_ids: set[str] = set()
        risk_labels: list[str] = []
        current_phase: JourneyListCurrentPhase | None = None
        required_phase_gate_open = True

        for phase in sorted(payload.phases, key=lambda item: item.order_index):
            module_aggregates: dict[str, ProgressAggregate] = {}
            phase_locked = phase.required and not required_phase_gate_open
            required_module_gate_open = True
            for module in sorted(phase.modules, key=lambda item: item.order_index):
                sequential_module_locked = (
                    module.required and not required_module_gate_open
                )
                module_locked = (
                    phase_locked
                    or sequential_module_locked
                    or any(item not in completed_ids for item in module.prerequisites)
                )
                projections: dict[str, ActivityProjection] = {}
                required_activity_gate_open = True
                for activity in sorted(
                    module.activities, key=lambda item: item.order_index
                ):
                    sequential_activity_locked = (
                        module.completion_policy.mode == "all_required"
                        and activity.required
                        and not required_activity_gate_open
                    )
                    locked = (
                        module_locked
                        or sequential_activity_locked
                        or any(
                            item not in completed_ids for item in activity.prerequisites
                        )
                    )
                    projection = self._project_activity(
                        activity=activity,
                        attempt=attempts.get(activity.activity_id),
                        learner_id=learner_id,
                        lesson_progress=lesson_progress,
                    )
                    projections[activity.activity_id] = projection
                    if projection.completed:
                        completed_ids.add(activity.activity_id)
                    if (
                        module.completion_policy.mode == "all_required"
                        and activity.required
                        and not projection.completed
                    ):
                        required_activity_gate_open = False
                    if self._is_risk(projection) and len(risk_labels) < 2:
                        risk_labels.append(activity.title)
                    action_key = (
                        _ACTION_KEYS[activity.type]
                        if not projection.completed and not locked
                        else None
                    )
                    if (
                        primary is None
                        and activity.required
                        and action_key is not None
                    ):
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
                        optional_candidate = JourneyNextAction(
                            activity_id=activity.activity_id,
                            activity_type=activity.type,
                            action_key=action_key,
                            label=activity.primary_action_label or activity.title,
                        )
                aggregate = aggregate_module_progress(module, projections)
                module_aggregates[module.module_id] = aggregate
                if aggregate.completed:
                    completed_ids.add(module.module_id)
                if module.required and not aggregate.completed:
                    required_module_gate_open = False
            phase_aggregate = aggregate_phase_progress(phase, module_aggregates)
            phase_aggregates[phase.phase_id] = phase_aggregate
            status = (
                "completed"
                if phase_aggregate.completed
                else "locked"
                if phase_locked
                else "in_progress"
            )
            if (
                current_phase is None
                and not phase_aggregate.completed
                and not phase_locked
            ):
                current_phase = JourneyListCurrentPhase(
                    phase_id=phase.phase_id,
                    title=phase.title,
                    status=status,
                )
            if phase_aggregate.completed:
                completed_ids.add(phase.phase_id)
            if phase.required and not phase_aggregate.completed:
                required_phase_gate_open = False

        overall = aggregate_path_progress(payload, phase_aggregates)
        if primary is None:
            primary = optional_candidate
        if current_phase is None and overall.completed:
            current_phase = None
        return JourneyListSummary(
            path_revision_id=str(revision.revision_id),
            path_title=payload.title,
            current_phase=current_phase,
            progress=JourneyProgressSummary(
                completed=overall.completed,
                completed_count=overall.completed_count,
                total_required=overall.total_required,
                percent=overall.percent,
            ),
            primary_next_action=primary,
            risk_labels=risk_labels[:2],
        )

    def _project_activity(
        self,
        *,
        activity: ActivityConfig,
        attempt: NewcomerTrainingActivityAttempt | None,
        learner_id: str,
        lesson_progress: dict[tuple[str, str], _LessonProgress],
    ) -> ActivityProjection:
        if activity.type == "lesson":
            config = cast(LessonConfig, activity.config)
            progress = lesson_progress.get(
                (learner_id, config.learning_content_id),
                _LessonProgress(completed=False, status="not_started"),
            )
            return ActivityProjection(
                activity.activity_id,
                activity.type,
                progress.status if progress.completed else progress.status,
                progress.completed,
                None,
                None,
                None,
                None if progress.completed else {"action": "continue_lesson"},
                None,
            )
        if activity.type == "quiz":
            if attempt is None:
                return ActivityProjection(
                    activity.activity_id,
                    activity.type,
                    "not_started",
                    False,
                    None,
                    None,
                    None,
                    {"action": "start_quiz"},
                    None,
                )
            return ActivityProjection(
                activity.activity_id,
                activity.type,
                str(attempt.status),
                bool(attempt.passed),
                float(attempt.score) if attempt.score is not None else None,
                float(attempt.max_score) if attempt.max_score is not None else None,
                bool(attempt.passed) if attempt.passed is not None else None,
                None if attempt.passed else {"action": "retry_quiz"},
                None,
            )
        status = str(attempt.status) if attempt else "not_started"
        completed = status == "completed"
        if activity.type == "audio_assessment":
            return ActivityProjection(
                activity.activity_id,
                activity.type,
                status,
                completed,
                float(attempt.score) if attempt and attempt.score is not None else None,
                float(attempt.max_score)
                if attempt and attempt.max_score is not None
                else None,
                bool(attempt.passed) if attempt and attempt.passed is not None else None,
                None if completed else {"action": "record_audio"},
                None,
            )
        if activity.type == "assignment":
            return ActivityProjection(
                activity.activity_id,
                activity.type,
                status,
                completed,
                None,
                None,
                bool(attempt.passed) if attempt and attempt.passed is not None else None,
                None if completed else {"action": "submit_assignment"},
                "等待管理员审核" if status == "needs_review" else None,
            )
        if activity.type == "ai_coach":
            return ActivityProjection(
                activity.activity_id,
                activity.type,
                status,
                completed,
                float(attempt.score) if attempt and attempt.score is not None else None,
                float(attempt.max_score)
                if attempt and attempt.max_score is not None
                else None,
                bool(attempt.passed) if attempt and attempt.passed is not None else None,
                None if completed else {"action": "start_ai_coach"},
                None,
            )
        # realtime_roleplay
        return ActivityProjection(
            activity.activity_id,
            activity.type,
            status,
            completed,
            None,
            None,
            bool(attempt.passed) if attempt and attempt.passed is not None else None,
            None if completed else {"action": "start_realtime_roleplay"},
            None,
        )

    @staticmethod
    def _is_risk(projection: ActivityProjection) -> bool:
        if projection.passed is False:
            return True
        return projection.status in _RISK_STATUSES


__all__ = ["JourneySummaryListResult", "JourneySummaryReadService"]
