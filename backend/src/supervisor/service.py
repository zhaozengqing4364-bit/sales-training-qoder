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
    ConversationMessage,
    Page,
    PracticeSession,
    RetrainingTask,
    Scenario,
    SupervisorReview,
    SupervisorScoreCalibration,
    User,
)
from common.db.schemas import ScenarioType, SessionCreate
from common.services.practice_report_service import PracticeReportService
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
    SupervisorScoreCalibrationResponse,
    SupervisorScoreCalibrationUpsert,
    SupervisorTeamReport,
    TrainingReportDimensionScore,
    TrainingReportEvidenceItem,
    TrainingReportIssue,
    TrainingReportNextAction,
    TrainingReportRiskFlag,
    TrainingReportTrainee,
    TrainingReportViewModel,
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


def _short_text(value: Any, *, max_length: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}..."


class SupervisorReviewService:
    """Coordinates supervisor review decisions and retraining task lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_training_report_view(
        self,
        *,
        session_id: str,
        current_user: User,
    ) -> TrainingReportViewModel:
        session = await self._get_session(session_id)
        if session is None:
            raise SupervisorServiceError(
                "[SESSION_NOT_FOUND]",
                status_code=404,
                message="训练记录不存在。",
            )
        self._assert_session_access(session, current_user)

        scenario_type = await self._get_session_scenario_type(session)
        trainee = await self._get_user(_as_str(session.user_id))
        review = await self._get_review_for_session(session_id)
        review_response = (
            await self._serialize_review(review) if review is not None else None
        )
        tasks = review_response.retraining_tasks if review_response is not None else []
        before_after = review_response.before_after if review_response is not None else None
        report = await self._build_session_report_or_none(
            session_id=session_id,
            session=session,
            scenario_type=scenario_type,
        )
        stored_report = await self._get_report(session_id)
        messages = await self._get_messages_for_session(session_id)
        pages_by_number = await self._get_pages_by_number(session)

        dimension_scores, key_issues, evidence_items = self._build_report_evidence(
            session=session,
            scenario_type=scenario_type,
            report=report,
            stored_report=stored_report,
            messages=messages,
            pages_by_number=pages_by_number,
        )
        missing_evidence_ids = [
            item.evidence_id
            for item in evidence_items
            if item.evidence_type == "evidence_missing"
        ]
        risk_flags: list[TrainingReportRiskFlag] = []
        if missing_evidence_ids:
            risk_flags.append(
                TrainingReportRiskFlag(
                    code="evidence_missing",
                    message="部分扣分项或维度分暂缺可引用原话、页码或知识来源。",
                    evidence_item_ids=missing_evidence_ids,
                )
            )
        if getattr(report, "evaluable", None) is False:
            risk_flags.append(
                TrainingReportRiskFlag(
                    code="not_evaluable",
                    message="当前训练证据不足，报告不会进入正式均分。",
                )
            )

        return TrainingReportViewModel(
            session_id=session_id,
            scenario_type=scenario_type,
            trainee=TrainingReportTrainee(
                user_id=_as_str(getattr(trainee, "user_id", session.user_id)),
                name=cast(str | None, getattr(trainee, "name", None)),
                email=cast(str | None, getattr(trainee, "email", None)),
            ),
            overall_score=self._report_overall_score(report, stored_report, session),
            readiness_suggestion=(
                _as_str(review_response.readiness_status)
                if review_response is not None
                else "pending_supervisor_review"
            ),
            dimension_scores=dimension_scores,
            key_strengths=self._report_key_strengths(report, stored_report),
            key_issues=key_issues,
            evidence_items=evidence_items,
            recommendations=self._report_recommendations(report, stored_report),
            risk_flags=risk_flags,
            next_actions=self._build_next_actions(
                report=report,
                stored_report=stored_report,
                tasks=tasks,
            ),
            supervisor_review=review_response,
            retraining_tasks=tasks,
            before_after=before_after,
        )

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

    async def upsert_score_calibration(
        self,
        *,
        review_id: str,
        payload: SupervisorScoreCalibrationUpsert,
        supervisor: User,
    ) -> SupervisorScoreCalibrationResponse:
        self._require_admin(supervisor)
        review = await self._get_review(review_id)
        if review is None:
            raise SupervisorServiceError(
                "[SUPERVISOR_REVIEW_NOT_FOUND]",
                status_code=404,
                message="主管评审不存在。",
            )
        if payload.session_id != _as_str(review.session_id):
            raise SupervisorServiceError(
                "[CALIBRATION_SESSION_MISMATCH]",
                status_code=422,
                message="校准会话必须与主管评审会话一致。",
            )

        dimension = payload.dimension.strip()
        result = await self.db.execute(
            select(SupervisorScoreCalibration).where(
                SupervisorScoreCalibration.review_id == review_id,
                SupervisorScoreCalibration.dimension == dimension,
            )
        )
        calibration = result.scalar_one_or_none()
        if calibration is None:
            calibration = SupervisorScoreCalibration(
                calibration_id=str(uuid.uuid4()),
                review_id=review_id,
                session_id=payload.session_id,
                dimension=dimension,
            )
        setattr(calibration, "ai_score", payload.ai_score)
        setattr(calibration, "supervisor_score", payload.supervisor_score)
        setattr(calibration, "calibration_label", payload.calibration_label)
        setattr(calibration, "comment", payload.comment)
        setattr(calibration, "calibrated_by_user_id", _as_str(supervisor.user_id))
        setattr(calibration, "updated_at", _now())
        self.db.add(calibration)
        await self._commit_with_unique_handling()
        await self.db.refresh(calibration)
        return self._serialize_calibration(calibration)

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

    def _assert_session_access(self, session: PracticeSession, user: User) -> None:
        if _is_admin(user):
            return
        if _as_str(session.user_id) != _as_str(user.user_id):
            raise SupervisorServiceError(
                "[ACCESS_DENIED]",
                status_code=403,
                message="你没有权限访问该训练报告。",
            )

    async def _get_user(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def _get_messages_for_session(
        self,
        session_id: str,
    ) -> list[ConversationMessage]:
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.turn_number)
        )
        return list(result.scalars().all())

    async def _get_pages_by_number(
        self,
        session: PracticeSession,
    ) -> dict[int, Page]:
        presentation_id = _as_str(getattr(session, "presentation_id", ""))
        if not presentation_id:
            return {}
        result = await self.db.execute(
            select(Page).where(Page.presentation_id == presentation_id)
        )
        pages: dict[int, Page] = {}
        for page in result.scalars().all():
            page_number = getattr(page, "page_number", None)
            if isinstance(page_number, int):
                pages[page_number] = page
        return pages

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

    async def _get_calibrations_for_review(
        self, review_id: str
    ) -> list[SupervisorScoreCalibration]:
        result = await self.db.execute(
            select(SupervisorScoreCalibration)
            .where(SupervisorScoreCalibration.review_id == review_id)
            .order_by(SupervisorScoreCalibration.created_at.desc())
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
        calibrations = await self._get_calibrations_for_review(_as_str(review.review_id))
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
            calibrations=[
                self._serialize_calibration(calibration)
                for calibration in calibrations
            ],
        )

    def _serialize_calibration(
        self,
        calibration: SupervisorScoreCalibration,
    ) -> SupervisorScoreCalibrationResponse:
        return SupervisorScoreCalibrationResponse(
            review_id=_as_str(calibration.review_id),
            session_id=_as_str(calibration.session_id),
            dimension=_as_str(calibration.dimension),
            ai_score=_as_float(calibration.ai_score),
            supervisor_score=_as_float(calibration.supervisor_score),
            calibration_label=cast(Any, calibration.calibration_label),
            comment=cast(str | None, calibration.comment),
            created_at=cast(datetime | None, calibration.created_at),
            updated_at=cast(datetime | None, calibration.updated_at),
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

    async def _build_session_report_or_none(
        self,
        *,
        session_id: str,
        session: PracticeSession,
        scenario_type: str,
    ) -> Any | None:
        try:
            return await PracticeReportService(self.db).build_session_report(
                session_id=session_id,
                session=session,
                scenario_type=scenario_type,
            )
        except PracticeServiceError:
            return None

    def _build_report_evidence(
        self,
        *,
        session: PracticeSession,
        scenario_type: str,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
        messages: list[ConversationMessage],
        pages_by_number: dict[int, Page],
    ) -> tuple[
        list[TrainingReportDimensionScore],
        list[TrainingReportIssue],
        list[TrainingReportEvidenceItem],
    ]:
        evidence_items: list[TrainingReportEvidenceItem] = []

        def add_evidence(
            *,
            dimension: str | None,
            issue: str | None,
            reason: str | None,
            page_number: int | None = None,
            turn_number: int | None = None,
            quote: str | None = None,
            knowledge_source_id: str | None = None,
            confidence: float | None = None,
        ) -> str:
            source_page = pages_by_number.get(page_number) if page_number else None
            source_message = self._select_message(
                messages,
                turn_number=turn_number,
                page_number=page_number,
            )
            resolved_quote = quote or (
                _short_text(getattr(source_message, "content", None))
                if source_message is not None
                else None
            )
            evidence_type = "evidence_missing"
            if knowledge_source_id:
                evidence_type = "knowledge_source"
            elif source_page is not None:
                evidence_type = "ppt_page"
            elif source_message is not None:
                evidence_type = "transcript_quote"

            evidence_id = f"evidence-{len(evidence_items) + 1}"
            evidence_items.append(
                TrainingReportEvidenceItem(
                    evidence_id=evidence_id,
                    dimension=dimension,
                    issue=issue,
                    evidence_type=evidence_type,
                    turn_number=cast(int | None, getattr(source_message, "turn_number", None)),
                    speaker=cast(str | None, getattr(source_message, "role", None)),
                    quote=resolved_quote,
                    source_message_id=(
                        _as_str(getattr(source_message, "id", None))
                        if source_message is not None
                        else None
                    ),
                    source_page_id=(
                        _as_str(getattr(source_page, "page_id", None))
                        if source_page is not None
                        else None
                    ),
                    knowledge_source_id=knowledge_source_id,
                    reason=reason,
                    severity=None,
                    confidence=confidence,
                )
            )
            return evidence_id

        dimension_scores = self._report_dimension_scores(
            session=session,
            report=report,
            stored_report=stored_report,
        )
        for index, dimension in enumerate(dimension_scores):
            page_number = index + 1 if scenario_type == "presentation" else None
            evidence_id = add_evidence(
                dimension=dimension.name,
                issue=None,
                reason=f"{dimension.name} 维度分的可追溯证据。",
                page_number=page_number,
            )
            dimension.evidence_item_ids.append(evidence_id)

        raw_issues = self._report_raw_issues(
            scenario_type=scenario_type,
            report=report,
            stored_report=stored_report,
        )
        key_issues: list[TrainingReportIssue] = []
        for raw_issue in raw_issues:
            issue_text = str(raw_issue.get("issue") or "").strip()
            if not issue_text:
                continue
            evidence_id = add_evidence(
                dimension=cast(str | None, raw_issue.get("dimension")),
                issue=issue_text,
                reason=cast(str | None, raw_issue.get("reason")),
                page_number=cast(int | None, raw_issue.get("page_number")),
                turn_number=cast(int | None, raw_issue.get("turn_number")),
                quote=_short_text(raw_issue.get("quote")),
                knowledge_source_id=cast(str | None, raw_issue.get("knowledge_source_id")),
                confidence=cast(float | None, raw_issue.get("confidence")),
            )
            key_issues.append(
                TrainingReportIssue(
                    issue=issue_text,
                    dimension=cast(str | None, raw_issue.get("dimension")),
                    reason=cast(str | None, raw_issue.get("reason")),
                    severity=cast(str | None, raw_issue.get("severity")),
                    evidence_item_ids=[evidence_id],
                )
            )

        knowledge_evidence = self._knowledge_evidence_from_report(report)
        if knowledge_evidence is not None:
            add_evidence(
                dimension=knowledge_evidence.get("dimension"),
                issue=knowledge_evidence.get("issue"),
                reason=knowledge_evidence.get("reason"),
                quote=knowledge_evidence.get("quote"),
                knowledge_source_id=knowledge_evidence.get("knowledge_source_id"),
                confidence=cast(float | None, knowledge_evidence.get("confidence")),
            )

        return dimension_scores, key_issues, evidence_items

    def _report_dimension_scores(
        self,
        *,
        session: PracticeSession,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
    ) -> list[TrainingReportDimensionScore]:
        presentation_review = self._as_dict(getattr(report, "presentation_review", None))
        presentation_dimensions = presentation_review.get("dimension_scores")
        if isinstance(presentation_dimensions, list) and presentation_dimensions:
            return [
                TrainingReportDimensionScore(
                    name=str(item.get("name") or item.get("dimension") or ""),
                    score=_as_float(item.get("score")),
                    description=cast(str | None, item.get("description")),
                )
                for item in presentation_dimensions
                if isinstance(item, dict) and (item.get("name") or item.get("dimension"))
            ]

        stored_dimensions = getattr(stored_report, "dimension_scores", None)
        if isinstance(stored_dimensions, list) and stored_dimensions:
            parsed = []
            for item in stored_dimensions:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("dimension") or "").strip()
                if not name:
                    continue
                parsed.append(
                    TrainingReportDimensionScore(
                        name=name,
                        score=_as_float(item.get("score")),
                        description=cast(str | None, item.get("description")),
                    )
                )
            if parsed:
                return parsed

        return [
            TrainingReportDimensionScore(
                name="逻辑结构",
                score=_as_float(getattr(report, "logic_score", None))
                or _as_float(getattr(session, "logic_score", None)),
                description="训练表达结构与推进逻辑。",
            ),
            TrainingReportDimensionScore(
                name="准确表达",
                score=_as_float(getattr(report, "accuracy_score", None))
                or _as_float(getattr(session, "accuracy_score", None)),
                description="内容准确性、事实支撑和表达一致性。",
            ),
            TrainingReportDimensionScore(
                name="完整覆盖",
                score=_as_float(getattr(report, "completeness_score", None))
                or _as_float(getattr(session, "completeness_score", None)),
                description="训练目标、关键步骤和必要信息覆盖度。",
            ),
        ]

    def _report_raw_issues(
        self,
        *,
        scenario_type: str,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        presentation_review = self._as_dict(getattr(report, "presentation_review", None))
        if scenario_type == "presentation" and presentation_review:
            for item in self._as_string_list(presentation_review.get("improvements")):
                issues.append(
                    {
                        "issue": item,
                        "dimension": "PPT 表达",
                        "reason": "来自 PPT 复盘改进项。",
                    }
                )
            page_summaries = presentation_review.get("page_summaries")
            if isinstance(page_summaries, list):
                for page_summary in page_summaries:
                    if not isinstance(page_summary, dict):
                        continue
                    page_number = self._as_int(page_summary.get("page_number"))
                    for point in self._as_string_list(
                        page_summary.get("missing_required_points")
                    ):
                        issues.append(
                            {
                                "issue": f"第 {page_number or '--'} 页遗漏要点：{point}",
                                "dimension": "要点覆盖",
                                "page_number": page_number,
                                "reason": "必讲要点未被页级复盘判定为已覆盖。",
                            }
                        )
                    issue_clusters = page_summary.get("issue_clusters")
                    if not isinstance(issue_clusters, list):
                        continue
                    for cluster in issue_clusters:
                        if not isinstance(cluster, dict):
                            continue
                        turn_numbers = cluster.get("turn_numbers")
                        evidence = self._as_string_list(cluster.get("evidence"))
                        issues.append(
                            {
                                "issue": str(
                                    cluster.get("summary")
                                    or cluster.get("issue_type")
                                    or "页级表达问题"
                                ),
                                "dimension": str(
                                    cluster.get("issue_type") or "PPT 表达"
                                ),
                                "page_number": page_number,
                                "turn_number": (
                                    turn_numbers[0]
                                    if isinstance(turn_numbers, list)
                                    and turn_numbers
                                    and isinstance(turn_numbers[0], int)
                                    else None
                                ),
                                "quote": evidence[0] if evidence else None,
                                "reason": "来自 PPT 页级问题簇。",
                            }
                        )
            return issues

        main_issue = self._as_dict(getattr(report, "main_issue", None))
        issue_text = _short_text(main_issue.get("issue_text"))
        if issue_text:
            issues.append(
                {
                    "issue": issue_text,
                    "dimension": cast(str | None, main_issue.get("issue_type")),
                    "reason": cast(str | None, main_issue.get("recovery_rule")),
                }
            )
        stored_improvements = getattr(stored_report, "key_improvements", None)
        for item in self._as_string_list(stored_improvements):
            issues.append(
                {
                    "issue": item,
                    "dimension": "综合报告",
                    "reason": "来自综合报告改进项。",
                }
            )
        return issues

    def _knowledge_evidence_from_report(
        self,
        report: Any | None,
    ) -> dict[str, Any] | None:
        snapshot = self._as_dict(getattr(report, "effectiveness_snapshot", None))
        retrieval_facts = self._as_dict(snapshot.get("retrieval_facts"))
        latest_attempt = self._as_dict(retrieval_facts.get("latest_attempt"))
        result_summaries = latest_attempt.get("result_summaries")
        if not isinstance(result_summaries, list) or not result_summaries:
            return None
        first = result_summaries[0]
        if not isinstance(first, dict):
            return None
        source_id = _short_text(
            first.get("knowledge_base_id") or first.get("document_id")
        )
        if not source_id:
            return None
        return {
            "dimension": "知识库证据",
            "issue": "知识库 grounding",
            "quote": _short_text(first.get("snippet")),
            "knowledge_source_id": source_id,
            "reason": "来自训练时最近一次知识库检索命中。",
            "confidence": _as_float(first.get("score")),
        }

    def _report_key_strengths(
        self,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
    ) -> list[str]:
        presentation_review = self._as_dict(getattr(report, "presentation_review", None))
        strengths = self._as_string_list(presentation_review.get("strengths"))
        if strengths:
            return strengths
        return self._as_string_list(getattr(stored_report, "key_strengths", None))

    def _report_recommendations(
        self,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
    ) -> list[str]:
        presentation_review = self._as_dict(getattr(report, "presentation_review", None))
        recommendations = self._as_string_list(presentation_review.get("recommendations"))
        if recommendations:
            return recommendations
        recommendations = self._as_string_list(getattr(report, "suggestions", None))
        recommendations.extend(
            item
            for item in self._as_string_list(getattr(stored_report, "recommendations", None))
            if item not in recommendations
        )
        return recommendations

    def _build_next_actions(
        self,
        *,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
        tasks: list[RetrainingTaskResponse],
    ) -> list[TrainingReportNextAction]:
        actions = [
            TrainingReportNextAction(
                action_type="recommendation",
                label=item,
            )
            for item in self._report_recommendations(report, stored_report)
        ]
        actions.extend(
            TrainingReportNextAction(
                action_type="retraining_task",
                label=task.title,
                target=task.task_id,
            )
            for task in tasks
        )
        return actions

    def _report_overall_score(
        self,
        report: Any | None,
        stored_report: ComprehensiveReport | None,
        session: PracticeSession,
    ) -> float | None:
        return (
            _as_float(getattr(report, "overall_score", None))
            or _as_float(getattr(stored_report, "overall_score", None))
            or _as_float(
                (
                    float(getattr(session, "logic_score", 0) or 0)
                    + float(getattr(session, "accuracy_score", 0) or 0)
                    + float(getattr(session, "completeness_score", 0) or 0)
                )
                / 3
            )
        )

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json")
            if isinstance(dumped, dict):
                return dumped
        return {}

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for text in (_short_text(item) for item in value) if text]

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _select_message(
        messages: list[ConversationMessage],
        *,
        turn_number: int | None = None,
        page_number: int | None = None,
    ) -> ConversationMessage | None:
        if turn_number is not None:
            for message in messages:
                if getattr(message, "turn_number", None) == turn_number:
                    return message
        if page_number is not None:
            page_messages = [
                message
                for message in messages
                if SupervisorReviewService._message_page_number(message) == page_number
            ]
            for preferred_role in ("user", "assistant"):
                for message in page_messages:
                    if getattr(message, "role", None) == preferred_role:
                        return message
            if page_messages:
                return page_messages[0]
        for preferred_role in ("user", "assistant"):
            for message in messages:
                if getattr(message, "role", None) == preferred_role:
                    return message
        return messages[0] if messages else None

    @staticmethod
    def _message_page_number(message: ConversationMessage) -> int | None:
        metadata = getattr(message, "transcript_metadata", None)
        if not isinstance(metadata, dict):
            return None
        return SupervisorReviewService._as_int(metadata.get("page_number"))

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
