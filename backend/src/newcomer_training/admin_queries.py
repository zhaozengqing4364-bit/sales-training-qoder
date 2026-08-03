"""Organization- and team-scoped learner progress read models for administrators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.teams import TeamDataScope
from foundation_admin_permissions import FoundationAdminActors
from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.journey import JourneyProjectionState, JourneyQueryService
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerActivityOutcome,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)


class FoundationLearnerAdminQueryService:
    """Expose the v2 Journey authority without reviving legacy journey tables."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        actors: FoundationAdminActors,
        scope: TeamDataScope,
    ) -> None:
        self._session = session
        self._actors = actors
        self._scope = scope
        self._organization_id = actors.newcomer.organization_id

    async def list_learners(
        self,
        *,
        search: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._require_read_access()
        filters = [
            NewcomerEnrollment.organization_id == self._organization_id,
            NewcomerEnrollment.status == "active",
            User.is_active.is_(True),
        ]
        if not self._scope.unrestricted:
            if not self._scope.learner_ids:
                return self._empty_page(search=search, limit=limit, offset=offset)
            filters.append(User.user_id.in_(self._scope.learner_ids))
        normalized_search = search.strip() if search else ""
        if normalized_search:
            pattern = f"%{normalized_search}%"
            filters.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))

        total = int(
            await self._session.scalar(
                select(func.count())
                .select_from(NewcomerEnrollment)
                .join(User, User.user_id == NewcomerEnrollment.learner_id)
                .where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.execute(
                    select(
                        NewcomerEnrollment,
                        User,
                        NewcomerCohort,
                        NewcomerPathRevision,
                        NewcomerPath,
                    )
                    .join(User, User.user_id == NewcomerEnrollment.learner_id)
                    .join(
                        NewcomerCohort,
                        NewcomerCohort.cohort_id == NewcomerEnrollment.cohort_id,
                    )
                    .join(
                        NewcomerPathRevision,
                        NewcomerPathRevision.revision_id
                        == NewcomerEnrollment.path_revision_id,
                    )
                    .join(
                        NewcomerPath,
                        NewcomerPath.path_id == NewcomerPathRevision.path_id,
                    )
                    .where(*filters)
                    .order_by(
                        User.name.asc(),
                        NewcomerEnrollment.assigned_at.desc(),
                        NewcomerEnrollment.enrollment_id.asc(),
                    )
                    .limit(limit)
                    .offset(offset)
                )
            ).tuples().all()
        )
        states = await self._load_states(rows)
        return {
            "items": [
                self._list_item(
                    enrollment=enrollment,
                    learner=learner,
                    cohort=cohort,
                    revision=revision,
                    path=path,
                    state=states.get(enrollment.enrollment_id),
                )
                for enrollment, learner, cohort, revision, path in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "applied_filters": {"search": normalized_search or None},
            "generated_at": datetime.now(UTC),
        }

    async def learner_detail(self, *, learner_id: str) -> dict[str, Any]:
        self._require_read_access()
        if not self._scope.allows_learner(learner_id):
            raise self._not_found()
        row = (
            await self._session.execute(
                select(NewcomerEnrollment, User, NewcomerCohort)
                .join(User, User.user_id == NewcomerEnrollment.learner_id)
                .join(
                    NewcomerCohort,
                    NewcomerCohort.cohort_id == NewcomerEnrollment.cohort_id,
                )
                .where(
                    NewcomerEnrollment.organization_id == self._organization_id,
                    NewcomerEnrollment.learner_id == learner_id,
                    NewcomerEnrollment.status == "active",
                    User.is_active.is_(True),
                )
                .limit(1)
            )
        ).one_or_none()
        if row is None:
            raise self._not_found()
        enrollment, learner, cohort = row
        projection = await JourneyQueryService(self._session).get_my_journey(
            actor=CommandActor(
                organization_id=self._organization_id,
                actor_id=learner_id,
                capabilities=frozenset({"newcomer.journey.read"}),
            ),
            expected_enrollment_version=enrollment.version,
        )
        return {
            "learner": {
                "learner_id": learner.user_id,
                "name": learner.name,
            },
            "cohort": {
                "cohort_id": cohort.cohort_id,
                "name": cohort.name,
            },
            "journey": projection.model_dump(),
        }

    async def _load_states(
        self,
        rows: list[
            tuple[
                NewcomerEnrollment,
                User,
                NewcomerCohort,
                NewcomerPathRevision,
                NewcomerPath,
            ]
        ],
    ) -> dict[str, JourneyProjectionState | None]:
        if not rows:
            return {}
        revision_by_enrollment = {
            enrollment.enrollment_id: enrollment.path_revision_id
            for enrollment, _learner, _cohort, _revision, _path in rows
        }
        attempts = list(
            (
                await self._session.execute(
                    select(NewcomerActivityAttempt)
                    .where(
                        NewcomerActivityAttempt.enrollment_id.in_(
                            tuple(revision_by_enrollment)
                        )
                    )
                    .order_by(
                        NewcomerActivityAttempt.enrollment_id,
                        NewcomerActivityAttempt.activity_id,
                        NewcomerActivityAttempt.attempt_no.desc(),
                    )
                )
            ).scalars()
        )
        latest_by_enrollment: dict[
            str, dict[str, NewcomerActivityAttempt]
        ] = {enrollment_id: {} for enrollment_id in revision_by_enrollment}
        for attempt in attempts:
            if (
                attempt.path_revision_id
                != revision_by_enrollment.get(attempt.enrollment_id)
            ):
                continue
            latest_by_enrollment[attempt.enrollment_id].setdefault(
                attempt.activity_id, attempt
            )
        latest_attempt_ids = tuple(
            attempt.attempt_id
            for attempts_by_activity in latest_by_enrollment.values()
            for attempt in attempts_by_activity.values()
        )
        outcomes = (
            list(
                (
                    await self._session.execute(
                        select(NewcomerActivityOutcome)
                        .where(
                            NewcomerActivityOutcome.attempt_id.in_(
                                latest_attempt_ids
                            )
                        )
                        .order_by(
                            NewcomerActivityOutcome.produced_at.desc(),
                            NewcomerActivityOutcome.outcome_id.desc(),
                        )
                    )
                ).scalars()
            )
            if latest_attempt_ids
            else []
        )
        outcome_by_attempt: dict[str, NewcomerActivityOutcome] = {}
        for outcome in outcomes:
            outcome_by_attempt.setdefault(outcome.attempt_id, outcome)

        states: dict[str, JourneyProjectionState | None] = {}
        draft_by_revision: dict[str, PathRevisionDraft | None] = {}
        for enrollment, _learner, _cohort, revision, _path in rows:
            if revision.revision_id not in draft_by_revision:
                try:
                    draft_by_revision[revision.revision_id] = (
                        PathRevisionDraft.model_validate(revision.snapshot_json)
                    )
                except ValueError:
                    draft_by_revision[revision.revision_id] = None
            draft = draft_by_revision[revision.revision_id]
            if draft is None:
                states[enrollment.enrollment_id] = None
                continue
            states[enrollment.enrollment_id] = JourneyQueryService.project_state(
                draft=draft,
                latest_attempt=latest_by_enrollment[enrollment.enrollment_id],
                outcome_by_attempt=outcome_by_attempt,
            )
        return states

    @staticmethod
    def _list_item(
        *,
        enrollment: NewcomerEnrollment,
        learner: User,
        cohort: NewcomerCohort,
        revision: NewcomerPathRevision,
        path: NewcomerPath,
        state: JourneyProjectionState | None,
    ) -> dict[str, Any]:
        if state is None:
            status = "blocked"
            status_label = "训练配置待处理"
            progress = {
                "completed_required": 0,
                "total_required": 0,
                "percentage": 0,
            }
            current_activity = None
            primary_action = None
        else:
            status = state.status
            status_label = state.status_label
            progress = {
                "completed_required": state.completed_required,
                "total_required": state.total_required,
                "percentage": (
                    int(state.completed_required * 100 / state.total_required)
                    if state.total_required
                    else 0
                ),
            }
            current_activity = (
                state.current_activity.model_dump()
                if state.current_activity is not None
                else None
            )
            primary_action = (
                state.primary_action.model_dump()
                if state.primary_action is not None
                else None
            )
        return {
            "learner": {
                "learner_id": learner.user_id,
                "name": learner.name,
            },
            "cohort": {
                "cohort_id": cohort.cohort_id,
                "name": cohort.name,
            },
            "enrollment": {
                "enrollment_id": enrollment.enrollment_id,
                "status": enrollment.status,
                "revision_id": enrollment.path_revision_id,
                "version": enrollment.version,
            },
            "path": {
                "path_id": path.path_id,
                "title": path.title,
                "revision_label": revision.revision_label,
            },
            "status": status,
            "status_label": status_label,
            "progress": progress,
            "current_activity": current_activity,
            "primary_action": primary_action,
            "updated_at": enrollment.updated_at,
        }

    def _require_read_access(self) -> None:
        if not self._actors.capabilities.intersection(
            {"manage_cohorts", "review_readiness"}
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]",
                "当前账号没有查看学员训练进度的权限。",
                403,
            )

    @staticmethod
    def _not_found() -> NewcomerTrainingError:
        return NewcomerTrainingError(
            "[NEWCOMER_LEARNER_NOT_FOUND]",
            "学员不存在或不在当前管理范围内。",
            404,
        )

    @staticmethod
    def _empty_page(
        *, search: str | None, limit: int, offset: int
    ) -> dict[str, Any]:
        return {
            "items": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "applied_filters": {"search": search.strip() if search else None},
            "generated_at": datetime.now(UTC),
        }


__all__ = ["FoundationLearnerAdminQueryService"]
