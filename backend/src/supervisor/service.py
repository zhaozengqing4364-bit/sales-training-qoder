"""Application service for supervisor review and retraining tasks."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import inspect, select
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
    TrainingReportSnapshot,
    TrainingTask,
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
    CertificationReviewQueueItem,
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
    TeamInsightsCommonIssue,
    TeamInsightsCompletion,
    TeamInsightsLearnerDetail,
    TeamInsightsLearnerSummary,
    TeamInsightsReadiness,
    TeamInsightsReadinessLearner,
    TeamInsightsResponse,
    TeamInsightsRetrainingCandidate,
    TeamInsightsWeakness,
    TrainingReportDimensionScore,
    TrainingReportEvidenceItem,
    TrainingReportIssue,
    TrainingReportNextAction,
    TrainingReportRiskFlag,
    TrainingReportThinkingEvidence,
    TrainingReportTrainee,
    TrainingReportViewModel,
    TrainingTaskSummary,
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


def _can_access_thinking_evidence(user: User) -> bool:
    return _is_admin(user)


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


def _as_non_negative_int(value: Any, *, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _is_within_date_range(
    value: datetime | None,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
) -> bool:
    if value is None:
        return date_from is None and date_to is None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if date_from is not None and date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=UTC)
    if date_to is not None and date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=UTC)
    if date_from is not None and value < date_from:
        return False
    if date_to is not None and value > date_to:
        return False
    return True


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
        report_snapshot = await self._get_report_snapshot(session_id)
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
            thinking_evidence=self._thinking_evidence_from_session(
                session,
                current_user,
            ),
            recommendations=self._report_recommendations(report, stored_report),
            config_metadata=self._report_config_metadata(report_snapshot),
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

    async def list_certification_review_queue(
        self,
        *,
        current_user: User,
        limit: int = 50,
    ) -> list[CertificationReviewQueueItem]:
        self._require_admin(current_user)
        rows = await self.db.execute(
            select(PracticeSession, User, Scenario.scenario_type)
            .join(User, User.user_id == PracticeSession.user_id)
            .join(Scenario, Scenario.scenario_id == PracticeSession.scenario_id)
            .where(PracticeSession.status == "completed")
            .where(PracticeSession.report_status == "completed")
            .where(PracticeSession.practice_template_id.is_not(None))
            .order_by(PracticeSession.end_time.desc(), PracticeSession.start_time.desc())
            .limit(max(1, min(limit, 100)))
        )
        items: list[CertificationReviewQueueItem] = []
        for session, trainee, scenario_type in rows.all():
            curriculum = await self._certification_curriculum_payload(session)
            if curriculum is None:
                continue
            review = await self._ensure_pending_review_for_session(
                session=session,
                supervisor=current_user,
                audit_metadata={
                    "source": "certification_review_queue",
                    "scenario_type": str(scenario_type or "sales"),
                },
            )
            if str(review.decision) != "pending":
                continue
            view = await self.get_training_report_view(
                session_id=_as_str(session.session_id),
                current_user=current_user,
            )
            items.append(
                CertificationReviewQueueItem(
                    review_id=_as_str(review.review_id),
                    session_id=_as_str(session.session_id),
                    report_id=_as_str(session.session_id),
                    learner={
                        "user_id": _as_str(trainee.user_id),
                        "name": cast(str | None, getattr(trainee, "name", None)),
                        "email": cast(str | None, getattr(trainee, "email", None)),
                    },
                    curriculum=curriculum,
                    score=view.overall_score,
                    evidence={
                        "transcript_anchors": [
                            item.model_dump(mode="json") for item in view.evidence_items
                        ],
                        "stage_snapshots": curriculum["stage_snapshots"],
                        "thinking_evidence": [
                            item.model_dump(mode="json")
                            for item in view.thinking_evidence
                        ],
                    },
                    submitted_at=cast(
                        datetime | None,
                        getattr(session, "end_time", None)
                        or getattr(session, "start_time", None),
                    ),
                    outcome=cast(Any, review.decision),
                )
            )
        return items

    async def get_team_insights(
        self,
        *,
        current_user: User,
        scenario_type: str | None = None,
        learner_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> TeamInsightsResponse:
        self._require_admin(current_user)
        tasks = await self._filtered_training_tasks(
            scenario_type=scenario_type,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
        )
        sessions = await self._filtered_sessions(
            scenario_type=scenario_type,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
        )
        session_ids = {_as_str(session.session_id) for session in sessions}
        reviews = await self._reviews_for_sessions(session_ids)
        retraining_tasks = await self._retraining_tasks_for_reviews(
            {_as_str(review.review_id) for review in reviews}
        )
        reports = await self._reports_for_sessions(session_ids)
        snapshots = await self._snapshots_for_sessions(session_ids)
        users = await self._users_by_id(
            {
                _as_str(task.assignee_id)
                for task in tasks
            }
            | {_as_str(session.user_id) for session in sessions}
        )

        top_weaknesses = self._top_weaknesses(reports, sessions)
        if not top_weaknesses:
            top_weaknesses = self._retraining_weaknesses(retraining_tasks)
        return TeamInsightsResponse(
            completion=self._completion_for_tasks(tasks),
            top_weaknesses=top_weaknesses,
            top3_common_issues=self._common_issues(
                reports,
                sessions,
                reviews=reviews,
                limit=3,
            ),
            readiness=self._readiness(reviews, users),
            retraining_candidates=self._retraining_candidates(
                reviews=reviews,
                tasks=retraining_tasks,
                users=users,
            ),
            learners=await self._learner_summaries(
                users=users,
                tasks=tasks,
                sessions=sessions,
                reviews=reviews,
                reports=reports,
                snapshots=snapshots,
            ),
        )

    async def get_team_insights_detail(
        self,
        *,
        current_user: User,
        learner_id: str,
        scenario_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> TeamInsightsLearnerDetail:
        self._require_admin(current_user)
        user = await self._get_user(learner_id)
        if user is None:
            raise SupervisorServiceError(
                "[LEARNER_NOT_FOUND]",
                status_code=404,
                message="学员不存在。",
            )
        tasks = await self._filtered_training_tasks(
            scenario_type=scenario_type,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
        )
        sessions = await self._filtered_sessions(
            scenario_type=scenario_type,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
        )
        session_ids = {_as_str(session.session_id) for session in sessions}
        reviews = await self._reviews_for_sessions(session_ids)
        reports = await self._reports_for_sessions(session_ids)
        snapshots = await self._snapshots_for_sessions(session_ids)
        retraining_tasks = await self._retraining_tasks_for_reviews(
            {_as_str(review.review_id) for review in reviews}
        )
        summary = await self._learner_summary(
            learner_id=learner_id,
            user=user,
            tasks=tasks,
            sessions=sessions,
            reviews=reviews,
            reports=reports,
            snapshots=snapshots,
        )
        latest_review = self._latest_review(reviews)
        return TeamInsightsLearnerDetail(
            **summary.model_dump(),
            learner_email=cast(str | None, getattr(user, "email", None)),
            training_tasks=[
                TrainingTaskSummary(
                    task_id=_as_str(task.task_id),
                    title=_as_str(task.title),
                    scenario_type=_as_str(task.scenario_type),
                    status=_as_str(task.status),
                    goal=_as_str(task.goal),
                )
                for task in sorted(
                    tasks,
                    key=lambda item: getattr(item, "created_at", None) or datetime.min,
                    reverse=True,
                )
            ],
            latest_review=await self._serialize_review(latest_review)
            if latest_review is not None
            else None,
            common_issues=self._common_issues(
                reports,
                sessions,
                reviews=reviews,
                limit=10,
            ),
            retraining_candidates=self._retraining_candidates(
                reviews=reviews,
                tasks=retraining_tasks,
                users={learner_id: user},
            ),
        )

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

    async def _filtered_training_tasks(
        self,
        *,
        scenario_type: str | None,
        learner_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        stmt = select(
            TrainingTask.task_id,
            TrainingTask.title,
            TrainingTask.assignee_id,
            TrainingTask.scenario_type,
            TrainingTask.goal,
            TrainingTask.status,
            TrainingTask.created_at,
        )
        if scenario_type:
            stmt = stmt.where(TrainingTask.scenario_type == scenario_type)
        if learner_id:
            stmt = stmt.where(TrainingTask.assignee_id == learner_id)
        result = await self.db.execute(stmt)
        return [
            task
            for task in result.all()
            if _is_within_date_range(
                cast(datetime | None, getattr(task, "created_at", None)),
                date_from=date_from,
                date_to=date_to,
            )
        ]

    async def _filtered_sessions(
        self,
        *,
        scenario_type: str | None,
        learner_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[Any]:
        stmt = (
            select(
                PracticeSession.session_id,
                PracticeSession.user_id,
                PracticeSession.start_time,
                PracticeSession.logic_score,
                PracticeSession.accuracy_score,
                PracticeSession.completeness_score,
            )
            .join(Scenario, Scenario.scenario_id == PracticeSession.scenario_id)
            .where(PracticeSession.status.in_(("completed", "scoring")))
        )
        if scenario_type:
            stmt = stmt.where(Scenario.scenario_type == scenario_type)
        if learner_id:
            stmt = stmt.where(PracticeSession.user_id == learner_id)
        result = await self.db.execute(stmt)
        return [
            session
            for session in result.all()
            if _is_within_date_range(
                cast(datetime | None, getattr(session, "start_time", None)),
                date_from=date_from,
                date_to=date_to,
            )
        ]

    async def _reviews_for_sessions(
        self,
        session_ids: set[str],
    ) -> list[SupervisorReview]:
        if not session_ids:
            return []
        result = await self.db.execute(
            select(SupervisorReview)
            .where(SupervisorReview.session_id.in_(list(session_ids)))
            .order_by(SupervisorReview.updated_at.desc())
        )
        return list(result.scalars().all())

    async def _retraining_tasks_for_reviews(
        self,
        review_ids: set[str],
    ) -> list[Any]:
        if not review_ids:
            return []
        columns = [
            RetrainingTask.task_id,
            RetrainingTask.user_id,
            RetrainingTask.source_review_id,
            RetrainingTask.skill_dimension,
        ]
        if await self._column_exists("retraining_tasks", "training_task_id"):
            columns.append(RetrainingTask.training_task_id)
        result = await self.db.execute(
            select(*columns).where(RetrainingTask.source_review_id.in_(list(review_ids)))
        )
        return list(result.all())

    async def _column_exists(self, table_name: str, column_name: str) -> bool:
        def check(sync_session: Any) -> bool:
            bind = sync_session.get_bind()
            return column_name in {
                column["name"] for column in inspect(bind).get_columns(table_name)
            }

        return bool(await self.db.run_sync(check))

    async def _reports_for_sessions(
        self,
        session_ids: set[str],
    ) -> dict[str, ComprehensiveReport]:
        if not session_ids:
            return {}
        result = await self.db.execute(
            select(ComprehensiveReport).where(
                ComprehensiveReport.session_id.in_(list(session_ids))
            )
        )
        return {_as_str(report.session_id): report for report in result.scalars().all()}

    async def _snapshots_for_sessions(
        self,
        session_ids: set[str],
    ) -> dict[str, Any]:
        if not session_ids:
            return {}
        columns = [TrainingReportSnapshot.session_id]
        if await self._column_exists(
            "training_report_snapshots",
            "config_bundle_snapshot",
        ):
            columns.append(TrainingReportSnapshot.config_bundle_snapshot)
        result = await self.db.execute(
            select(*columns).where(
                TrainingReportSnapshot.session_id.in_(list(session_ids))
            )
        )
        return {_as_str(snapshot.session_id): snapshot for snapshot in result.all()}

    async def _users_by_id(self, user_ids: set[str]) -> dict[str, User]:
        clean_ids = {user_id for user_id in user_ids if user_id}
        if not clean_ids:
            return {}
        result = await self.db.execute(select(User).where(User.user_id.in_(list(clean_ids))))
        return {_as_str(user.user_id): user for user in result.scalars().all()}

    def _completion_for_tasks(self, tasks: list[TrainingTask]) -> TeamInsightsCompletion:
        by_status = Counter(_as_str(task.status) for task in tasks)
        total = len(tasks)
        completed = by_status.get("completed", 0)
        return TeamInsightsCompletion(
            total_tasks=total,
            completed_tasks=completed,
            completion_rate=round((completed / total) * 100, 1) if total else 0.0,
            by_status=dict(by_status),
        )

    def _top_weaknesses(
        self,
        reports: dict[str, ComprehensiveReport],
        sessions: list[PracticeSession],
    ) -> list[TeamInsightsWeakness]:
        session_users = {_as_str(session.session_id): _as_str(session.user_id) for session in sessions}
        scores: dict[str, list[float]] = defaultdict(list)
        learners: dict[str, set[str]] = defaultdict(set)
        for session_id, report in reports.items():
            for item in self._report_dimension_score_items(report):
                score = item[1]
                if score is None or score > 70:
                    continue
                dimension = item[0]
                scores[dimension].append(score)
                learners[dimension].add(session_users.get(session_id, ""))
        weaknesses = [
            TeamInsightsWeakness(
                dimension=dimension,
                count=len(values),
                average_score=round(sum(values) / len(values), 1) if values else None,
                learner_ids=sorted(user_id for user_id in learners[dimension] if user_id),
            )
            for dimension, values in scores.items()
        ]
        return sorted(
            weaknesses,
            key=lambda item: (-(item.count), item.average_score or 101, item.dimension),
        )[:5]

    def _common_issues(
        self,
        reports: dict[str, ComprehensiveReport],
        sessions: list[PracticeSession],
        *,
        reviews: list[SupervisorReview] | None = None,
        limit: int,
    ) -> list[TeamInsightsCommonIssue]:
        session_users = {_as_str(session.session_id): _as_str(session.user_id) for session in sessions}
        counts: Counter[tuple[str, str | None]] = Counter()
        learners: dict[tuple[str, str | None], set[str]] = defaultdict(set)
        for session_id, report in reports.items():
            user_id = session_users.get(session_id, "")
            for issue in self._as_string_list(getattr(report, "key_improvements", None)):
                key = (issue, None)
                counts[key] += 1
                learners[key].add(user_id)
        for review in reviews or []:
            issue = _short_text(getattr(review, "comment", None))
            if not issue:
                continue
            key = (issue, None)
            counts[key] += 1
            learners[key].add(_as_str(review.trainee_user_id))
        return [
            TeamInsightsCommonIssue(
                issue=issue,
                dimension=dimension,
                count=count,
                learner_ids=sorted(user_id for user_id in learners[(issue, dimension)] if user_id),
            )
            for (issue, dimension), count in counts.most_common(limit)
        ]

    def _retraining_weaknesses(
        self,
        tasks: list[RetrainingTask],
    ) -> list[TeamInsightsWeakness]:
        counts: Counter[str] = Counter()
        learners: dict[str, set[str]] = defaultdict(set)
        for task in tasks:
            dimension = _as_str(task.skill_dimension)
            if not dimension:
                continue
            counts[dimension] += 1
            learners[dimension].add(_as_str(task.user_id))
        return [
            TeamInsightsWeakness(
                dimension=dimension,
                count=count,
                average_score=None,
                learner_ids=sorted(user_id for user_id in learners[dimension] if user_id),
            )
            for dimension, count in counts.most_common(5)
        ]

    def _readiness(
        self,
        reviews: list[SupervisorReview],
        users: dict[str, User],
    ) -> TeamInsightsReadiness:
        latest = self._latest_reviews_by_learner(reviews)
        by_status = Counter(_as_str(review.readiness_status) for review in latest.values())
        return TeamInsightsReadiness(
            by_status=dict(by_status),
            learners=[
                TeamInsightsReadinessLearner(
                    learner_id=learner_id,
                    learner_name=cast(str | None, getattr(users.get(learner_id), "name", None)),
                    readiness_status=cast(Any, review.readiness_status),
                    latest_review_id=_as_str(review.review_id),
                    session_id=_as_str(review.session_id),
                )
                for learner_id, review in latest.items()
            ],
        )

    def _retraining_candidates(
        self,
        *,
        reviews: list[SupervisorReview],
        tasks: list[RetrainingTask],
        users: dict[str, User],
    ) -> list[TeamInsightsRetrainingCandidate]:
        tasks_by_review: dict[str, list[RetrainingTask]] = defaultdict(list)
        for task in tasks:
            tasks_by_review[_as_str(task.source_review_id)].append(task)
        candidates: list[TeamInsightsRetrainingCandidate] = []
        for review in reviews:
            if not bool(review.required_retraining) and review.decision != "needs_retraining":
                continue
            learner_id = _as_str(review.trainee_user_id)
            linked_tasks = tasks_by_review.get(_as_str(review.review_id)) or [None]
            for task in linked_tasks:
                candidates.append(
                    TeamInsightsRetrainingCandidate(
                        learner_id=learner_id,
                        learner_name=cast(str | None, getattr(users.get(learner_id), "name", None)),
                        session_id=_as_str(review.session_id),
                        review_id=_as_str(review.review_id),
                        retraining_task_id=_as_str(getattr(task, "task_id", None)) or None,
                        training_task_id=_as_str(getattr(task, "training_task_id", None)) or None,
                        skill_dimension=cast(str | None, getattr(task, "skill_dimension", None)),
                        readiness_status=cast(Any, review.readiness_status),
                        reason=cast(str | None, review.comment),
                    )
                )
        return candidates

    async def _learner_summaries(
        self,
        *,
        users: dict[str, User],
        tasks: list[TrainingTask],
        sessions: list[PracticeSession],
        reviews: list[SupervisorReview],
        reports: dict[str, ComprehensiveReport],
        snapshots: dict[str, TrainingReportSnapshot],
    ) -> list[TeamInsightsLearnerSummary]:
        learner_ids = sorted(
            set(users.keys())
            | {_as_str(task.assignee_id) for task in tasks}
            | {_as_str(session.user_id) for session in sessions}
        )
        return [
            await self._learner_summary(
                learner_id=item,
                user=users.get(item),
                tasks=[task for task in tasks if _as_str(task.assignee_id) == item],
                sessions=[session for session in sessions if _as_str(session.user_id) == item],
                reviews=[review for review in reviews if _as_str(review.trainee_user_id) == item],
                reports=reports,
                snapshots=snapshots,
            )
            for item in learner_ids
            if item
        ]

    async def _learner_summary(
        self,
        *,
        learner_id: str,
        user: User | None,
        tasks: list[TrainingTask],
        sessions: list[PracticeSession],
        reviews: list[SupervisorReview],
        reports: dict[str, ComprehensiveReport],
        snapshots: dict[str, TrainingReportSnapshot],
    ) -> TeamInsightsLearnerSummary:
        latest_review = self._latest_review(reviews)
        latest_session = max(
            sessions,
            key=lambda item: getattr(item, "start_time", None) or datetime.min,
        ) if sessions else None
        latest_session_id = _as_str(getattr(latest_session, "session_id", None))
        latest_score = None
        if latest_session_id:
            latest_score = await self._session_overall_score(
                latest_session_id,
                session=latest_session,
            )
        learner_reports = {
            _as_str(session.session_id): reports[_as_str(session.session_id)]
            for session in sessions
            if _as_str(session.session_id) in reports
        }
        return TeamInsightsLearnerSummary(
            learner_id=learner_id,
            learner_name=cast(str | None, getattr(user, "name", None)),
            completion=self._completion_for_tasks(tasks),
            latest_score=latest_score,
            readiness_status=cast(Any, latest_review.readiness_status)
            if latest_review is not None
            else None,
            top_weaknesses=self._top_weaknesses(learner_reports, sessions),
            config_metadata=self._report_config_metadata(
                snapshots.get(latest_session_id)
            ) if latest_session_id else {},
        )

    @staticmethod
    def _latest_review(reviews: list[SupervisorReview]) -> SupervisorReview | None:
        if not reviews:
            return None
        return max(
            reviews,
            key=lambda item: getattr(item, "updated_at", None) or datetime.min,
        )

    def _latest_reviews_by_learner(
        self,
        reviews: list[SupervisorReview],
    ) -> dict[str, SupervisorReview]:
        latest: dict[str, SupervisorReview] = {}
        for review in reviews:
            learner_id = _as_str(review.trainee_user_id)
            current = latest.get(learner_id)
            if current is None or self._latest_review([review, current]) is review:
                latest[learner_id] = review
        return latest

    def _report_dimension_score_items(
        self,
        report: ComprehensiveReport,
    ) -> list[tuple[str, float | None]]:
        raw_dimensions = getattr(report, "dimension_scores", None)
        if isinstance(raw_dimensions, str):
            try:
                raw_dimensions = json.loads(raw_dimensions)
            except json.JSONDecodeError:
                return []
        if not isinstance(raw_dimensions, list):
            return []
        items: list[tuple[str, float | None]] = []
        for item in raw_dimensions:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("dimension") or "").strip()
            if name:
                items.append((name, _as_float(item.get("score"))))
        return items

    async def _ensure_pending_review_for_session(
        self,
        *,
        session: PracticeSession,
        supervisor: User,
        audit_metadata: dict[str, Any],
    ) -> SupervisorReview:
        review = await self._get_review_for_session(_as_str(session.session_id))
        if review is not None:
            return review
        review = SupervisorReview(
            review_id=str(uuid.uuid4()),
            session_id=_as_str(session.session_id),
            trainee_user_id=_as_str(session.user_id),
            supervisor_user_id=_as_str(supervisor.user_id),
            decision="pending",
            readiness_status="not_ready",
            required_retraining=False,
            audit_metadata=audit_metadata,
        )
        self.db.add(review)
        await self._commit_with_unique_handling()
        await self.db.refresh(review)
        return review

    async def _certification_curriculum_payload(
        self,
        session: PracticeSession,
    ) -> dict[str, Any] | None:
        template = await self._practice_template_for_session(session)
        if template is None:
            return None
        stage_snapshots = self._stage_snapshots_from_session(session)
        review_stage_keys = self._review_stage_keys(
            curriculum_plan=cast(dict[str, Any] | None, getattr(template, "curriculum_plan", None)),
            stage_snapshots=stage_snapshots,
        )
        if not review_stage_keys:
            return None
        return {
            "practice_template": {
                "template_id": _as_str(getattr(template, "template_id", None)),
                "name": _as_str(getattr(template, "name", None)),
                "scenario_type": _as_str(getattr(template, "scenario_type", None)),
                "mode": _as_str(getattr(template, "mode", None)),
                "version": getattr(template, "version", None),
            },
            "stage_keys": review_stage_keys,
            "stage_snapshots": {
                key: stage_snapshots.get(key, {}) for key in review_stage_keys
            },
        }

    async def _practice_template_for_session(self, session: PracticeSession) -> Any | None:
        template_id = getattr(session, "practice_template_id", None)
        if not template_id:
            return None
        from curriculum_practice.models import PracticeTemplate

        return await self.db.get(PracticeTemplate, _as_str(template_id))

    @staticmethod
    def _stage_snapshots_from_session(session: PracticeSession) -> dict[str, Any]:
        snapshot = getattr(session, "curriculum_snapshot", None)
        if not isinstance(snapshot, dict):
            return {}
        raw_snapshots = snapshot.get("stage_snapshots")
        return raw_snapshots if isinstance(raw_snapshots, dict) else {}

    @staticmethod
    def _review_stage_keys(
        *,
        curriculum_plan: dict[str, Any] | None,
        stage_snapshots: dict[str, Any],
    ) -> list[str]:
        keywords = ("review", "certification", "onboarding", "复核", "认证", "入职")
        keys: list[str] = []
        stages = curriculum_plan.get("stages") if isinstance(curriculum_plan, dict) else None
        if isinstance(stages, list):
            for stage in stages:
                if not isinstance(stage, dict):
                    continue
                stage_key = _as_str(stage.get("template_stage_key"))
                stage_name = _as_str(stage.get("name"))
                haystack = f"{stage_key} {stage_name}".lower()
                if stage_key and any(keyword in haystack for keyword in keywords):
                    keys.append(stage_key)
        for stage_key in stage_snapshots:
            haystack = _as_str(stage_key).lower()
            if any(keyword in haystack for keyword in keywords) and stage_key not in keys:
                keys.append(stage_key)
        return keys

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
            training_task_id=await self._resolve_training_task_id(
                source_session_id=payload.source_session_id,
                explicit_training_task_id=payload.training_task_id,
            ),
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

    def _thinking_evidence_from_session(
        self,
        session: PracticeSession,
        user: User,
    ) -> list[TrainingReportThinkingEvidence]:
        if not _can_access_thinking_evidence(user):
            return []
        runtime_state = session.runtime_state if isinstance(session.runtime_state, dict) else {}
        thinking_log = runtime_state.get("thinking_log")
        if not isinstance(thinking_log, list):
            return []
        entries: list[TrainingReportThinkingEvidence] = []
        for item in thinking_log:
            if not isinstance(item, dict):
                continue
            thinking_text = _short_text(item.get("thinking_text"), max_length=50_000)
            response_id = _as_str(item.get("response_id"))
            if not thinking_text or not response_id:
                continue
            entries.append(
                TrainingReportThinkingEvidence(
                    turn_index=_as_non_negative_int(item.get("turn_index")),
                    template_stage_key=cast(str | None, item.get("template_stage_key")),
                    response_id=response_id,
                    thinking_text=thinking_text,
                    captured_at=_as_str(item.get("captured_at")),
                )
            )
        return entries

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

    async def _resolve_training_task_id(
        self,
        *,
        source_session_id: str,
        explicit_training_task_id: str | None,
    ) -> str | None:
        if explicit_training_task_id:
            task = await self.db.get(TrainingTask, explicit_training_task_id)
            return _as_str(task.task_id) if task is not None else None

        result = await self.db.execute(
            select(TrainingTask).where(
                TrainingTask.resulting_session_id == source_session_id
            )
        )
        task = result.scalar_one_or_none()
        if task is not None:
            return _as_str(task.task_id)

        session = await self._get_session(source_session_id)
        snapshot = getattr(session, "voice_policy_snapshot", None) if session else None
        if not isinstance(snapshot, dict):
            return None
        context = snapshot.get("training_task_context")
        if not isinstance(context, dict):
            return None
        task_id = context.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return None
        task = await self.db.get(TrainingTask, task_id)
        return _as_str(task.task_id) if task is not None else None

    async def _training_task_summary(
        self,
        training_task_id: str | None,
    ) -> TrainingTaskSummary | None:
        if not training_task_id:
            return None
        task = await self.db.get(TrainingTask, training_task_id)
        if task is None:
            return None
        return TrainingTaskSummary(
            task_id=_as_str(task.task_id),
            title=_as_str(task.title),
            scenario_type=_as_str(task.scenario_type),
            status=_as_str(task.status),
            goal=_as_str(task.goal),
        )

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
        metadata = dict(audit_metadata or {})
        metadata["reviewer_id"] = _as_str(supervisor.user_id)
        metadata.setdefault("reviewed_at", _now().isoformat())
        metadata.setdefault("report_id", _as_str(review.session_id))
        setattr(review, "audit_metadata", metadata)
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
            if getattr(task, "training_task_id", None) is None:
                task.training_task_id = await self._resolve_training_task_id(
                    source_session_id=_as_str(review.session_id),
                    explicit_training_task_id=None,
                ) or await self._ensure_followup_training_task(review, dimension)
                if task.training_task_id is not None:
                    self.db.add(task)
                    await self.db.commit()
                    await self.db.refresh(task)
            return task
        training_task_id = await self._resolve_training_task_id(
            source_session_id=_as_str(review.session_id),
            explicit_training_task_id=None,
        ) or await self._ensure_followup_training_task(review, dimension)
        task = RetrainingTask(
            task_id=str(uuid.uuid4()),
            user_id=_as_str(review.trainee_user_id),
            source_session_id=_as_str(review.session_id),
            source_review_id=_as_str(review.review_id),
            training_task_id=training_task_id,
            skill_dimension=dimension,
            title=f"{DEFAULT_RETRAINING_TITLE_PREFIX}：{dimension}",
            description=cast(str | None, review.comment),
            status="todo",
        )
        self.db.add(task)
        await self._commit_with_unique_handling()
        await self.db.refresh(task)
        return task

    async def _ensure_followup_training_task(
        self,
        review: SupervisorReview,
        skill_dimension: str,
    ) -> str | None:
        session = await self._get_session(_as_str(review.session_id))
        if session is None:
            return None
        result = await self.db.execute(
            select(TrainingTask).where(
                TrainingTask.assignee_id == _as_str(review.trainee_user_id),
                TrainingTask.resulting_session_id == _as_str(review.session_id),
                TrainingTask.source == "supervisor_certification_retrain",
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return _as_str(existing.task_id)
        scenario_type = await self._get_session_scenario_type(session)
        task = TrainingTask(
            task_id=str(uuid.uuid4()),
            title=f"{DEFAULT_RETRAINING_TITLE_PREFIX}：{skill_dimension}",
            assignee_id=_as_str(review.trainee_user_id),
            scenario_type=scenario_type,
            goal=_as_str(review.comment) or f"围绕{skill_dimension}完成认证复训。",
            focus_intent=f"supervisor_retraining:{skill_dimension}",
            completion_criteria={
                "minimum_sessions": 1,
                "source_review_id": _as_str(review.review_id),
            },
            practice_template_id=cast(str | None, session.practice_template_id),
            source="supervisor_certification_retrain",
            status="assigned",
            resulting_session_id=_as_str(review.session_id),
        )
        self.db.add(task)
        await self._commit_with_unique_handling()
        await self.db.refresh(task)
        return _as_str(task.task_id)

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
            training_task_id=cast(str | None, task.training_task_id),
            training_task=await self._training_task_summary(
                cast(str | None, task.training_task_id)
            ),
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
        if isinstance(value, str):
            text = _short_text(value)
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return [text] if text else []
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
        if session is None:
            session = await self._get_session(session_id)
            if session is None:
                return None
            await self.db.refresh(session)
        elif isinstance(session, PracticeSession):
            await self.db.refresh(session)
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
        await self.db.refresh(session)
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

    async def _get_report_snapshot(
        self,
        session_id: str,
    ) -> TrainingReportSnapshot | None:
        result = await self.db.execute(
            select(TrainingReportSnapshot).where(
                TrainingReportSnapshot.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _report_config_metadata(
        snapshot: Any | None,
    ) -> dict[str, Any]:
        if snapshot is None:
            return {"source": "legacy_unversioned"}
        lineage = getattr(snapshot, "config_bundle_snapshot", None)
        return dict(lineage) if isinstance(lineage, dict) else {"source": "legacy_unversioned"}
