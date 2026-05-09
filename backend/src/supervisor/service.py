"""Application service for supervisor review and retraining tasks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ComprehensiveReport,
    PracticeSession,
    RetrainingTask,
    Scenario,
    SupervisorReview,
    User,
)
from common.db.schemas import ScenarioType, SessionCreate
from common.services.practice_session_service import (
    PracticeServiceError,
    PracticeSessionCreateService,
)
from supervisor.schemas import (
    BeforeAfterComparison,
    RetrainingTaskCompleteRequest,
    RetrainingTaskCreate,
    RetrainingTaskResponse,
    RetrainingTaskStartResponse,
    ScoreDimensionDelta,
    SupervisorReviewCreate,
    SupervisorReviewDecisionUpdate,
    SupervisorReviewResponse,
    SupervisorTeamReport,
)

DEFAULT_RETRAINING_DIMENSION = "综合表现"
DEFAULT_RETRAINING_TITLE_PREFIX = "复训"


class SupervisorServiceError(Exception):
    """Structured service error converted by the API layer."""

    def __init__(
        self,
        error_code: str,
        *,
        status_code: int = 400,
        message: str | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.message = message or error_code


def _is_admin(user: User) -> bool:
    return str(getattr(user, "role", "user")).lower() == "admin"


def _now() -> datetime:
    return datetime.now(UTC)


def _field(row: Any, name: str, default: Any = None) -> Any:
    return getattr(row, name, default)


def _as_str(value: Any) -> str:
    return str(value or "")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


class SupervisorReviewService:
    """Coordinates supervisor review decisions and retraining task lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_team_reports(
        self,
        *,
        current_user: User,
        limit: int = 50,
    ) -> list[SupervisorTeamReport]:
        self._require_admin(current_user)
        rows = await self.db.execute(
            select(PracticeSession, User, Scenario.scenario_type)
            .join(User, User.user_id == PracticeSession.user_id)
            .join(Scenario, Scenario.scenario_id == PracticeSession.scenario_id)
            .where(PracticeSession.status.in_(("completed", "scoring")))
            .order_by(PracticeSession.start_time.desc())
            .limit(max(1, min(limit, 100)))
        )
        reports: list[SupervisorTeamReport] = []
        for session, trainee, scenario_type in rows.all():
            review = await self._get_review_for_session(_as_str(session.session_id))
            review_response = (
                await self._serialize_review(review) if review is not None else None
            )
            reports.append(
                SupervisorTeamReport(
                    session_id=_as_str(session.session_id),
                    trainee_user_id=_as_str(session.user_id),
                    trainee_name=cast(str | None, getattr(trainee, "name", None)),
                    scenario_type=str(scenario_type or "sales"),
                    status=str(getattr(session, "status", "")),
                    report_status=cast(str | None, getattr(session, "report_status", None)),
                    overall_score=await self._session_overall_score(
                        _as_str(session.session_id),
                        session=session,
                    ),
                    started_at=cast(datetime | None, getattr(session, "start_time", None)),
                    completed_at=cast(datetime | None, getattr(session, "end_time", None)),
                    latest_review=review_response,
                    before_after=review_response.before_after
                    if review_response is not None
                    else None,
                )
            )
        return reports

    async def list_reviews(
        self,
        *,
        current_user: User,
        session_id: str | None = None,
    ) -> list[SupervisorReviewResponse]:
        query = select(SupervisorReview).order_by(SupervisorReview.created_at.desc())
        if session_id:
            query = query.where(SupervisorReview.session_id == session_id)
        if not _is_admin(current_user):
            query = query.where(SupervisorReview.trainee_user_id == current_user.user_id)

        rows = await self.db.execute(query)
        reviews = list(rows.scalars().all())
        return [await self._serialize_review(review) for review in reviews]

    async def create_review(
        self,
        *,
        payload: SupervisorReviewCreate,
        supervisor: User,
    ) -> SupervisorReviewResponse:
        self._require_admin(supervisor)
        session = await self._get_session(payload.session_id)
        if session is None:
            raise SupervisorServiceError(
                "[SESSION_NOT_FOUND]",
                status_code=404,
                message="训练记录不存在。",
            )

        existing = await self._get_review_for_session(payload.session_id)
        review = existing or SupervisorReview(
            review_id=str(uuid.uuid4()),
            session_id=payload.session_id,
            trainee_user_id=_as_str(session.user_id),
            supervisor_user_id=_as_str(supervisor.user_id),
        )
        self._apply_review_payload(
            review,
            decision=payload.decision,
            readiness_status=payload.readiness_status,
            comment=payload.comment,
            required_retraining=payload.required_retraining,
            audit_metadata=payload.audit_metadata,
            supervisor=supervisor,
        )
        self.db.add(review)
        await self._commit_with_unique_handling()
        await self.db.refresh(review)

        if review.decision == "needs_retraining" or bool(review.required_retraining):
            await self._ensure_retraining_task(
                review,
                skill_dimension=payload.skill_dimension,
            )
            await self.db.refresh(review)

        return await self._serialize_review(review)

    async def update_decision(
        self,
        *,
        review_id: str,
        payload: SupervisorReviewDecisionUpdate,
        supervisor: User,
    ) -> SupervisorReviewResponse:
        self._require_admin(supervisor)
        review = await self._get_review(review_id)
        if review is None:
            raise SupervisorServiceError(
                "[SUPERVISOR_REVIEW_NOT_FOUND]",
                status_code=404,
                message="主管评审不存在。",
            )

        self._apply_review_payload(
            review,
            decision=payload.decision,
            readiness_status=payload.readiness_status
            or cast(str, review.readiness_status),
            comment=payload.comment,
            required_retraining=payload.required_retraining,
            audit_metadata=payload.audit_metadata,
            supervisor=supervisor,
        )
        self.db.add(review)
        await self._commit_with_unique_handling()
        await self.db.refresh(review)

        if review.decision == "needs_retraining" or bool(review.required_retraining):
            await self._ensure_retraining_task(
                review,
                skill_dimension=payload.skill_dimension,
            )
            await self.db.refresh(review)

        return await self._serialize_review(review)

    async def list_tasks(
        self,
        *,
        current_user: User,
        status: str | None = None,
    ) -> list[RetrainingTaskResponse]:
        query = select(RetrainingTask).order_by(RetrainingTask.created_at.desc())
        if status:
            query = query.where(RetrainingTask.status == status)
        if not _is_admin(current_user):
            query = query.where(RetrainingTask.user_id == current_user.user_id)
        rows = await self.db.execute(query)
        return [await self._serialize_task(task) for task in rows.scalars().all()]

    async def create_task(
        self,
        *,
        payload: RetrainingTaskCreate,
        current_user: User,
    ) -> RetrainingTaskResponse:
        self._require_admin(current_user)
        review = await self._get_review(payload.source_review_id)
        if review is None:
            raise SupervisorServiceError(
                "[SUPERVISOR_REVIEW_NOT_FOUND]",
                status_code=404,
                message="主管评审不存在。",
            )
        user_id = payload.user_id or _as_str(review.trainee_user_id)
        if user_id != _as_str(review.trainee_user_id):
            raise SupervisorServiceError(
                "[RETRAINING_USER_MISMATCH]",
                status_code=422,
                message="复训任务用户必须与评审员工一致。",
            )
        task = RetrainingTask(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            source_session_id=payload.source_session_id,
            source_review_id=payload.source_review_id,
            skill_dimension=payload.skill_dimension.strip(),
            title=payload.title.strip(),
            description=payload.description,
            status="todo",
        )
        self.db.add(task)
        await self._commit_with_unique_handling()
        await self.db.refresh(task)
        return await self._serialize_task(task)

    async def start_task_session(
        self,
        *,
        task_id: str,
        current_user: User,
    ) -> RetrainingTaskStartResponse:
        task = await self._get_task(task_id)
        if task is None:
            raise SupervisorServiceError(
                "[RETRAINING_TASK_NOT_FOUND]",
                status_code=404,
                message="复训任务不存在。",
            )
        self._assert_task_access(task, current_user)
        source_session = await self._get_session(_as_str(task.source_session_id))
        trainee = await self._get_user(_as_str(task.user_id))
        if source_session is None or trainee is None:
            raise SupervisorServiceError(
                "[RETRAINING_SOURCE_NOT_FOUND]",
                status_code=404,
                message="复训来源不存在。",
            )

        scenario_type = await self._get_session_scenario_type(source_session)
        session_payload = SessionCreate(
            scenario_type=ScenarioType.PRESENTATION
            if scenario_type == "presentation"
            else ScenarioType.SALES,
            scenario_id=_uuid_or_none(source_session.scenario_id),
            presentation_id=_uuid_or_none(source_session.presentation_id),
            agent_id=_uuid_or_none(source_session.agent_id),
            persona_id=_uuid_or_none(source_session.persona_id),
            voice_mode=cast(Any, getattr(source_session, "voice_mode", None)),
            runtime_profile_id=_uuid_or_none(
                getattr(source_session, "voice_runtime_profile_id", None)
            ),
            focus_intent={
                "version": "supervisor_retraining_v1",
                "source_session_id": _as_str(task.source_session_id),
                "main_issue": {
                    "issue_type": "supervisor_retraining",
                    "issue_text": _as_str(task.title),
                    "recovery_rule": _as_str(task.description)
                    or f"围绕{_as_str(task.skill_dimension)}完成一轮复训。",
                },
                "next_goal": {
                    "goal_type": "supervisor_retraining",
                    "goal_text": _as_str(task.title),
                    "rule": f"复训后{_as_str(task.skill_dimension)}应有可见改善。",
                },
            },
        )
        try:
            create_result = await PracticeSessionCreateService(self.db).create_session(
                session_payload,
                current_user=trainee,
            )
        except PracticeServiceError as exc:
            raise SupervisorServiceError(
                exc.error_code,
                status_code=exc.status_code,
                message=exc.message,
            ) from exc
        setattr(task, "status", "in_progress")
        setattr(task, "updated_at", _now())
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return RetrainingTaskStartResponse(
            task=await self._serialize_task(task),
            session_id=_as_str(create_result.session.session_id),
        )

    async def complete_task_with_session(
        self,
        *,
        task_id: str,
        payload: RetrainingTaskCompleteRequest,
        current_user: User,
    ) -> RetrainingTaskResponse:
        task = await self._get_task(task_id)
        if task is None:
            raise SupervisorServiceError(
                "[RETRAINING_TASK_NOT_FOUND]",
                status_code=404,
                message="复训任务不存在。",
            )
        self._assert_task_access(task, current_user)
        completed_session = await self._get_session(payload.completed_session_id)
        if completed_session is None:
            raise SupervisorServiceError(
                "[COMPLETED_SESSION_NOT_FOUND]",
                status_code=404,
                message="复训完成记录不存在。",
            )
        if _as_str(completed_session.user_id) != _as_str(task.user_id):
            raise SupervisorServiceError(
                "[COMPLETED_SESSION_USER_MISMATCH]",
                status_code=422,
                message="复训完成记录必须属于任务员工。",
            )
        setattr(task, "completed_session_id", payload.completed_session_id)
        setattr(task, "status", "completed")
        setattr(task, "updated_at", _now())
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return await self._serialize_task(task)

    def _require_admin(self, user: User) -> None:
        if not _is_admin(user):
            raise SupervisorServiceError(
                "[ADMIN_REQUIRED]",
                status_code=403,
                message="需要管理员权限。",
            )

    def _assert_task_access(self, task: RetrainingTask, user: User) -> None:
        if _is_admin(user):
            return
        if _as_str(task.user_id) != _as_str(user.user_id):
            raise SupervisorServiceError(
                "[ACCESS_DENIED]",
                status_code=403,
                message="你没有权限访问该复训任务。",
            )

    async def _get_user(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def _get_session(self, session_id: str) -> PracticeSession | None:
        result = await self.db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def _get_review(self, review_id: str) -> SupervisorReview | None:
        result = await self.db.execute(
            select(SupervisorReview).where(SupervisorReview.review_id == review_id)
        )
        return result.scalar_one_or_none()

    async def _get_review_for_session(
        self, session_id: str
    ) -> SupervisorReview | None:
        result = await self.db.execute(
            select(SupervisorReview).where(SupervisorReview.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def _get_task(self, task_id: str) -> RetrainingTask | None:
        result = await self.db.execute(
            select(RetrainingTask).where(RetrainingTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def _get_tasks_for_review(self, review_id: str) -> list[RetrainingTask]:
        result = await self.db.execute(
            select(RetrainingTask)
            .where(RetrainingTask.source_review_id == review_id)
            .order_by(RetrainingTask.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_session_scenario_type(self, session: PracticeSession) -> str:
        result = await self.db.execute(
            select(Scenario.scenario_type).where(Scenario.scenario_id == session.scenario_id)
        )
        return str(result.scalar_one_or_none() or "sales")

    def _apply_review_payload(
        self,
        review: SupervisorReview,
        *,
        decision: str,
        readiness_status: str,
        comment: str | None,
        required_retraining: bool | None,
        audit_metadata: dict[str, Any] | None,
        supervisor: User,
    ) -> None:
        required = bool(required_retraining)
        if decision == "needs_retraining":
            required = True
        setattr(review, "decision", decision)
        setattr(review, "readiness_status", readiness_status)
        setattr(review, "comment", comment)
        setattr(review, "required_retraining", required)
        setattr(review, "supervisor_user_id", _as_str(supervisor.user_id))
        setattr(review, "audit_metadata", audit_metadata or {})
        setattr(review, "updated_at", _now())

    async def _ensure_retraining_task(
        self,
        review: SupervisorReview,
        *,
        skill_dimension: str | None,
    ) -> RetrainingTask:
        dimension = (
            skill_dimension.strip()
            if isinstance(skill_dimension, str) and skill_dimension.strip()
            else await self._weakest_dimension(_as_str(review.session_id))
        )
        result = await self.db.execute(
            select(RetrainingTask).where(
                RetrainingTask.source_review_id == review.review_id,
                RetrainingTask.skill_dimension == dimension,
            )
        )
        task = result.scalar_one_or_none()
        if task is not None:
            return task
        task = RetrainingTask(
            task_id=str(uuid.uuid4()),
            user_id=_as_str(review.trainee_user_id),
            source_session_id=_as_str(review.session_id),
            source_review_id=_as_str(review.review_id),
            skill_dimension=dimension,
            title=f"{DEFAULT_RETRAINING_TITLE_PREFIX}：{dimension}",
            description=cast(str | None, review.comment),
            status="todo",
        )
        self.db.add(task)
        await self._commit_with_unique_handling()
        await self.db.refresh(task)
        return task

    async def _commit_with_unique_handling(self) -> None:
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise SupervisorServiceError(
                "[SUPERVISOR_REVIEW_CONFLICT]",
                status_code=409,
                message="评审或复训任务已存在。",
            ) from exc

    async def _serialize_review(
        self, review: SupervisorReview
    ) -> SupervisorReviewResponse:
        tasks = await self._get_tasks_for_review(_as_str(review.review_id))
        serialized_tasks = [await self._serialize_task(task) for task in tasks]
        before_after = next(
            (task.before_after for task in serialized_tasks if task.before_after),
            None,
        )
        return SupervisorReviewResponse(
            review_id=_as_str(review.review_id),
            session_id=_as_str(review.session_id),
            trainee_user_id=_as_str(review.trainee_user_id),
            supervisor_user_id=_as_str(review.supervisor_user_id),
            decision=cast(Any, review.decision),
            readiness_status=cast(Any, review.readiness_status),
            comment=cast(str | None, review.comment),
            required_retraining=bool(review.required_retraining),
            audit_metadata=cast(dict[str, Any] | None, review.audit_metadata),
            created_at=cast(datetime | None, review.created_at),
            updated_at=cast(datetime | None, review.updated_at),
            retraining_tasks=serialized_tasks,
            before_after=before_after,
        )

    async def _serialize_task(self, task: RetrainingTask) -> RetrainingTaskResponse:
        return RetrainingTaskResponse(
            task_id=_as_str(task.task_id),
            user_id=_as_str(task.user_id),
            source_session_id=_as_str(task.source_session_id),
            source_review_id=_as_str(task.source_review_id),
            skill_dimension=_as_str(task.skill_dimension),
            title=_as_str(task.title),
            description=cast(str | None, task.description),
            status=cast(Any, task.status),
            completed_session_id=cast(str | None, task.completed_session_id),
            created_at=cast(datetime | None, task.created_at),
            updated_at=cast(datetime | None, task.updated_at),
            before_after=await self._build_before_after(task),
        )

    async def _build_before_after(
        self, task: RetrainingTask
    ) -> BeforeAfterComparison | None:
        source_session_id = _as_str(task.source_session_id)
        completed_session_id = cast(str | None, task.completed_session_id)
        original_dimensions = await self._session_dimension_scores(source_session_id)
        retraining_dimensions = (
            await self._session_dimension_scores(completed_session_id)
            if completed_session_id
            else {}
        )
        original_score = await self._session_overall_score(source_session_id)
        retraining_score = (
            await self._session_overall_score(completed_session_id)
            if completed_session_id
            else None
        )
        dimension_names = sorted(
            set(original_dimensions.keys()) | set(retraining_dimensions.keys())
        )
        weak_changes = [
            ScoreDimensionDelta(
                name=name,
                original_score=original_dimensions.get(name),
                retraining_score=retraining_dimensions.get(name),
                delta=round(
                    retraining_dimensions[name] - original_dimensions[name],
                    1,
                )
                if name in original_dimensions and name in retraining_dimensions
                else None,
            )
            for name in dimension_names
        ]
        return BeforeAfterComparison(
            source_session_id=source_session_id,
            completed_session_id=completed_session_id,
            original_score=original_score,
            retraining_score=retraining_score,
            score_delta=round(retraining_score - original_score, 1)
            if original_score is not None and retraining_score is not None
            else None,
            weak_dimension_changes=weak_changes,
            retraining_completed=completed_session_id is not None
            and _as_str(task.status) == "completed",
        )

    async def _session_overall_score(
        self,
        session_id: str,
        *,
        session: PracticeSession | None = None,
    ) -> float | None:
        report = await self._get_report(session_id)
        if report is not None:
            return _as_float(report.overall_score)
        session = session or await self._get_session(session_id)
        if session is None:
            return None
        values = [
            _as_float(getattr(session, "logic_score", None)),
            _as_float(getattr(session, "accuracy_score", None)),
            _as_float(getattr(session, "completeness_score", None)),
        ]
        valid = [value for value in values if value is not None]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 1)

    async def _session_dimension_scores(self, session_id: str) -> dict[str, float]:
        report = await self._get_report(session_id)
        if report is not None:
            raw_dimensions = report.dimension_scores
            if isinstance(raw_dimensions, list):
                parsed: dict[str, float] = {}
                for item in raw_dimensions:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name") or item.get("dimension") or "").strip()
                    score = _as_float(item.get("score"))
                    if name and score is not None:
                        parsed[name] = score
                if parsed:
                    return parsed

        session = await self._get_session(session_id)
        if session is None:
            return {}
        values = {
            "逻辑结构": _as_float(getattr(session, "logic_score", None)),
            "准确表达": _as_float(getattr(session, "accuracy_score", None)),
            "完整覆盖": _as_float(getattr(session, "completeness_score", None)),
        }
        return {name: score for name, score in values.items() if score is not None}

    async def _weakest_dimension(self, session_id: str) -> str:
        dimensions = await self._session_dimension_scores(session_id)
        if not dimensions:
            return DEFAULT_RETRAINING_DIMENSION
        return min(dimensions.items(), key=lambda item: item[1])[0]

    async def _get_report(self, session_id: str) -> ComprehensiveReport | None:
        result = await self.db.execute(
            select(ComprehensiveReport).where(ComprehensiveReport.session_id == session_id)
        )
        return result.scalar_one_or_none()
