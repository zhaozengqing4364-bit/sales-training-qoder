"""Read-only Journey projection over the frozen enrollment revision and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)


class JourneyEnrollmentView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enrollment_id: str
    status: str
    revision_id: str
    version: int


class JourneyPathView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path_id: str
    title: str
    revision_label: str


class JourneyProgressView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    completed_required: int = 0
    total_required: int = 0
    percentage: int = Field(default=0, ge=0, le=100)


class JourneyPrimaryAction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command_type: str
    activity_id: str
    label: str
    href: str


class JourneyActivityView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    activity_id: str
    type: str
    title: str
    objective: str
    status: Literal[
        "available",
        "locked",
        "in_progress",
        "awaiting_review",
        "completed",
        "needs_remediation",
        "retryable",
        "invalidated",
    ]
    status_label: str
    estimated_minutes: int
    required: bool
    blocked_reason: str | None = None
    latest_attempt_id: str | None = None
    latest_outcome_id: str | None = None


class JourneyStageView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_id: str
    sequence: int
    title: str
    objective: str
    status: Literal["locked", "current", "completed"]
    activities: tuple[JourneyActivityView, ...]


class JourneyOutcomeView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome_id: str
    activity_id: str
    activity_title: str
    lifecycle_result: str
    assessment_result: str | None
    score: float | None
    max_score: float | None
    passed: bool | None
    produced_at: datetime
    next_action: dict[str, Any] | None


class JourneyProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["journey_projection_v1"] = "journey_projection_v1"
    generated_at: datetime
    data_freshness: Literal["fresh", "stale"] = "fresh"
    capabilities: tuple[str, ...]
    status: Literal[
        "not_enrolled", "active", "blocked", "awaiting_review", "completed"
    ]
    status_label: str
    status_reason: str | None
    enrollment: JourneyEnrollmentView | None
    path: JourneyPathView | None
    progress: JourneyProgressView
    stages: tuple[JourneyStageView, ...]
    current_activity: JourneyActivityView | None
    background_tasks: tuple[dict[str, Any], ...] = ()
    recent_outcomes: tuple[JourneyOutcomeView, ...] = ()
    primary_action: JourneyPrimaryAction | None
    projection_version: int


@dataclass(frozen=True, slots=True)
class JourneyProjectionState:
    stage_views: tuple[JourneyStageView, ...]
    completed_required: int
    total_required: int
    current_activity: JourneyActivityView | None
    primary_action: JourneyPrimaryAction | None
    status: Literal["active", "blocked", "awaiting_review", "completed"]
    status_label: str
    status_reason: str | None


class JourneyQueryService:
    """A GET-only projector. It never enrolls, migrates, or commits."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_my_journey(
        self,
        *,
        actor: CommandActor,
        expected_enrollment_version: int | None = None,
    ) -> JourneyProjection:
        if "newcomer.journey.read" not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有查看新人训练的权限。", 403
            )
        enrollment = await self._session.scalar(
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == actor.organization_id)
            .where(NewcomerEnrollment.learner_id == actor.actor_id)
            .where(NewcomerEnrollment.status == "active")
            .limit(1)
        )
        now = datetime.now(UTC)
        if enrollment is None:
            return JourneyProjection(
                generated_at=now,
                capabilities=("view_journey",),
                status="not_enrolled",
                status_label="尚未分配",
                status_reason="尚未分配新人训练，请联系培训负责人。",
                enrollment=None,
                path=None,
                progress=JourneyProgressView(),
                stages=(),
                current_activity=None,
                primary_action=None,
                projection_version=0,
            )
        if (
            expected_enrollment_version is not None
            and expected_enrollment_version != enrollment.version
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                "训练进度已更新，请刷新后继续。",
                412,
                details={
                    "expected_version": expected_enrollment_version,
                    "actual_version": enrollment.version,
                },
            )
        revision = await self._session.get(
            NewcomerPathRevision, enrollment.path_revision_id
        )
        if (
            revision is None
            or revision.organization_id != actor.organization_id
            or revision.status not in {"published", "archived"}
        ):
            return self._configuration_blocked(now=now, enrollment=enrollment)
        path = await self._session.get(NewcomerPath, revision.path_id)
        if path is None or path.organization_id != actor.organization_id:
            return self._configuration_blocked(now=now, enrollment=enrollment)
        try:
            draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        except ValueError:
            return self._configuration_blocked(now=now, enrollment=enrollment)

        attempts = (
            await self._session.execute(
                select(NewcomerActivityAttempt)
                .where(
                    NewcomerActivityAttempt.enrollment_id
                    == enrollment.enrollment_id
                )
                .where(
                    NewcomerActivityAttempt.path_revision_id
                    == enrollment.path_revision_id
                )
                .order_by(
                    NewcomerActivityAttempt.activity_id,
                    desc(NewcomerActivityAttempt.attempt_no),
                )
            )
        ).scalars()
        latest_attempt: dict[str, NewcomerActivityAttempt] = {}
        attempt_by_id: dict[str, NewcomerActivityAttempt] = {}
        for loaded_attempt in attempts:
            attempt_by_id[loaded_attempt.attempt_id] = loaded_attempt
            latest_attempt.setdefault(loaded_attempt.activity_id, loaded_attempt)
        outcomes = (
            await self._session.execute(
                select(NewcomerActivityOutcome)
                .where(
                    NewcomerActivityOutcome.attempt_id.in_(tuple(attempt_by_id))
                    if attempt_by_id
                    else NewcomerActivityOutcome.attempt_id == ""
                )
                .order_by(
                    desc(NewcomerActivityOutcome.produced_at),
                    desc(NewcomerActivityOutcome.outcome_id),
                )
            )
        ).scalars().all()
        outcome_by_attempt: dict[str, NewcomerActivityOutcome] = {}
        for row in outcomes:
            outcome_by_attempt.setdefault(row.attempt_id, row)
        title_by_activity = {
            activity.activity_id: activity.title
            for stage in draft.stages
            for activity in stage.activities
        }

        state = self.project_state(
            draft=draft,
            latest_attempt=latest_attempt,
            outcome_by_attempt=outcome_by_attempt,
        )
        recent_outcomes = tuple(
            JourneyOutcomeView(
                outcome_id=outcome.outcome_id,
                activity_id=attempt_by_id[outcome.attempt_id].activity_id,
                activity_title=title_by_activity.get(
                    attempt_by_id[outcome.attempt_id].activity_id, "训练活动"
                ),
                lifecycle_result=outcome.lifecycle_result,
                assessment_result=outcome.assessment_result,
                score=float(outcome.score) if outcome.score is not None else None,
                max_score=(
                    float(outcome.max_score)
                    if outcome.max_score is not None
                    else None
                ),
                passed=outcome.passed,
                produced_at=outcome.produced_at,
                next_action=outcome.next_action_json,
            )
            for outcome in outcomes[:10]
        )
        percentage = (
            int(state.completed_required * 100 / state.total_required)
            if state.total_required
            else 0
        )
        projection_version = enrollment.version + sum(
            loaded_attempt.version for loaded_attempt in latest_attempt.values()
        )
        return JourneyProjection(
            generated_at=now,
            capabilities=("view_journey", "execute_current_activity"),
            status=state.status,
            status_label=state.status_label,
            status_reason=state.status_reason,
            enrollment=JourneyEnrollmentView(
                enrollment_id=enrollment.enrollment_id,
                status=enrollment.status,
                revision_id=enrollment.path_revision_id,
                version=enrollment.version,
            ),
            path=JourneyPathView(
                path_id=path.path_id,
                title=draft.title,
                revision_label=draft.revision_label,
            ),
            progress=JourneyProgressView(
                completed_required=state.completed_required,
                total_required=state.total_required,
                percentage=percentage,
            ),
            stages=state.stage_views,
            current_activity=state.current_activity,
            recent_outcomes=recent_outcomes,
            primary_action=state.primary_action,
            projection_version=projection_version,
        )

    @classmethod
    def project_state(
        cls,
        *,
        draft: PathRevisionDraft,
        latest_attempt: dict[str, NewcomerActivityAttempt],
        outcome_by_attempt: dict[str, NewcomerActivityOutcome],
    ) -> JourneyProjectionState:
        """Project shared learner/admin state from one immutable revision snapshot."""

        title_by_activity = {
            activity.activity_id: activity.title
            for stage in draft.stages
            for activity in stage.activities
        }
        completed = {
            activity_id
            for activity_id, attempt in latest_attempt.items()
            if cls._is_completed(
                attempt,
                outcome_by_attempt.get(attempt.attempt_id),
            )
        }
        stage_views: list[JourneyStageView] = []
        activity_views: list[JourneyActivityView] = []
        total_required = 0
        completed_required = 0
        prior_stage_complete = True
        for stage in sorted(draft.stages, key=lambda item: item.sequence):
            stage_activities: list[JourneyActivityView] = []
            for activity in stage.activities:
                if activity.required:
                    total_required += 1
                    if activity.activity_id in completed:
                        completed_required += 1
                attempt = latest_attempt.get(activity.activity_id)
                outcome = (
                    outcome_by_attempt.get(attempt.attempt_id)
                    if attempt is not None
                    else None
                )
                missing_prerequisites = [
                    prerequisite_id
                    for prerequisite_id in activity.prerequisite_activity_ids
                    if prerequisite_id not in completed
                ]
                view = cls._activity_view(
                    activity=activity,
                    attempt=attempt,
                    outcome=outcome,
                    blocked_titles=[
                        title_by_activity.get(item, item)
                        for item in missing_prerequisites
                    ],
                    stage_unavailable=not prior_stage_complete,
                )
                stage_activities.append(view)
                activity_views.append(view)
            stage_required = (
                list(stage.activities)
                if str(stage.completion_rule) == "all_activities"
                else [activity for activity in stage.activities if activity.required]
            )
            stage_complete = all(
                activity.activity_id in completed for activity in stage_required
            )
            if stage_complete:
                stage_status: Literal["locked", "current", "completed"] = (
                    "completed"
                )
            elif prior_stage_complete:
                stage_status = "current"
            else:
                stage_status = "locked"
            stage_views.append(
                JourneyStageView(
                    stage_id=stage.stage_id,
                    sequence=stage.sequence,
                    title=stage.title,
                    objective=stage.objective,
                    status=stage_status,
                    activities=tuple(stage_activities),
                )
            )
            prior_stage_complete = prior_stage_complete and stage_complete

        current_activity = next(
            (
                item
                for item in activity_views
                if item.status
                in {
                    "in_progress",
                    "awaiting_review",
                    "needs_remediation",
                    "retryable",
                    "invalidated",
                    "available",
                }
            ),
            None,
        )
        primary_action = cls._primary_action(current_activity)
        if completed_required == total_required and total_required > 0:
            status: Literal[
                "active", "blocked", "awaiting_review", "completed"
            ] = "completed"
            status_label = "训练已完成"
            status_reason = None
            current_activity = None
            primary_action = None
        elif current_activity is None:
            status = "blocked"
            status_label = "暂时无法继续"
            status_reason = "当前训练存在阻塞，请联系培训负责人。"
        elif current_activity.status == "awaiting_review":
            status = "awaiting_review"
            status_label = "结果处理中"
            status_reason = "结果正在后台处理，完成后会在这里更新。"
        else:
            status = "active"
            status_label = "训练进行中"
            status_reason = None
        return JourneyProjectionState(
            stage_views=tuple(stage_views),
            completed_required=completed_required,
            total_required=total_required,
            current_activity=current_activity,
            primary_action=primary_action,
            status=status,
            status_label=status_label,
            status_reason=status_reason,
        )

    @staticmethod
    def _activity_view(
        *,
        activity: Any,
        attempt: NewcomerActivityAttempt | None,
        outcome: NewcomerActivityOutcome | None,
        blocked_titles: list[str],
        stage_unavailable: bool,
    ) -> JourneyActivityView:
        status: str
        label: str
        blocked_reason: str | None = None
        if blocked_titles or stage_unavailable:
            status = "locked"
            label = "尚未解锁"
            blocked_reason = (
                f"请先完成：{'、'.join(blocked_titles)}"
                if blocked_titles
                else "请先完成上一阶段。"
            )
        elif attempt is None:
            status = "available"
            label = "可以开始"
        elif attempt.status == "invalidated":
            status = "invalidated"
            label = "需要重新学习"
        elif attempt.status in {"submitted", "processing"}:
            status = "awaiting_review"
            label = "结果处理中"
        elif attempt.status in {"started", "in_progress"}:
            status = "in_progress"
            label = "继续完成"
        elif attempt.status in {"failed", "cancelled"}:
            status = "retryable"
            label = "可以重试"
        elif outcome is not None and outcome.passed is False:
            status = "needs_remediation"
            label = "需要补练"
        elif JourneyQueryService._is_completed(attempt, outcome):
            status = "completed"
            label = "已完成"
        else:
            status = "retryable"
            label = "可以重试"
        return JourneyActivityView(
            activity_id=activity.activity_id,
            type=str(activity.type),
            title=activity.title,
            objective=activity.objective,
            status=status,  # type: ignore[arg-type]
            status_label=label,
            estimated_minutes=activity.estimated_minutes,
            required=activity.required,
            blocked_reason=blocked_reason,
            latest_attempt_id=attempt.attempt_id if attempt is not None else None,
            latest_outcome_id=outcome.outcome_id if outcome is not None else None,
        )

    @staticmethod
    def _is_completed(
        attempt: NewcomerActivityAttempt,
        outcome: NewcomerActivityOutcome | None,
    ) -> bool:
        if attempt.status != "completed" or outcome is None:
            return False
        return outcome.passed is not False and outcome.lifecycle_result == "completed"

    @staticmethod
    def _primary_action(
        activity: JourneyActivityView | None,
    ) -> JourneyPrimaryAction | None:
        if activity is None:
            return None
        command_by_status = {
            "available": ("start_activity", f"开始{activity.title}"),
            "in_progress": ("continue_activity", f"继续{activity.title}"),
            "awaiting_review": ("view_task_status", "查看处理进度"),
            "needs_remediation": ("start_new_attempt", "完成补学后重试"),
            "retryable": ("start_new_attempt", "重新尝试"),
            "invalidated": ("start_relearning", "重新学习"),
        }
        command = command_by_status.get(activity.status)
        if command is None:
            return None
        return JourneyPrimaryAction(
            command_type=command[0],
            activity_id=activity.activity_id,
            label=command[1],
            href=f"/newcomer-training/activities/{activity.activity_id}",
        )

    @staticmethod
    def _configuration_blocked(
        *, now: datetime, enrollment: NewcomerEnrollment
    ) -> JourneyProjection:
        return JourneyProjection(
            generated_at=now,
            capabilities=("view_journey",),
            status="blocked",
            status_label="训练配置待处理",
            status_reason="训练配置暂不可用，培训负责人可以在当前工作台补充关联。",
            enrollment=JourneyEnrollmentView(
                enrollment_id=enrollment.enrollment_id,
                status=enrollment.status,
                revision_id=enrollment.path_revision_id,
                version=enrollment.version,
            ),
            path=None,
            progress=JourneyProgressView(),
            stages=(),
            current_activity=None,
            primary_action=None,
            projection_version=enrollment.version,
        )


__all__ = ["JourneyProjection", "JourneyProjectionState", "JourneyQueryService"]
