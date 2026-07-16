"""Supervisor review and retraining task APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import Team, TeamLeaderAssignment, TeamMembership, User
from common.db.session import get_db
from common.teams.policy import TeamScopePolicy
from supervisor.schemas import (
    RetrainingTaskCompleteRequest,
    RetrainingTaskCreate,
    SupervisorReviewCreate,
    SupervisorReviewDecisionUpdate,
    SupervisorScoreCalibrationUpsert,
)
from supervisor.service import SupervisorReviewService, SupervisorServiceError

router = APIRouter()


@router.get("/supervisor/team/scope")
async def get_team_scope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return active explicit teams and members visible to the current reader."""
    policy = TeamScopePolicy(db)
    if not policy.has_unrestricted_scope(current_user) and not policy.is_team_leader(
        current_user
    ):
        return _error(403, "[TEAM_READER_REQUIRED]", "需要平台管理员或销售组长权限。")
    team_ids = await policy.authorized_team_ids(current_user)
    if team_ids is not None and not team_ids:
        return success_response({"teams": [], "members": []})
    now = datetime.now(UTC)
    team_query = select(Team).where(Team.is_active.is_(True))
    if team_ids is not None:
        team_query = team_query.where(Team.team_id.in_(team_ids))
    teams = list((await db.scalars(team_query.order_by(Team.name, Team.code))).all())
    visible_team_ids = [str(team.team_id) for team in teams]
    memberships = []
    if visible_team_ids:
        memberships = list(
            (
                await db.execute(
                    select(TeamMembership, User)
                    .join(User, User.user_id == TeamMembership.user_id)
                    .where(
                        TeamMembership.team_id.in_(visible_team_ids),
                        TeamMembership.effective_from <= now,
                        or_(
                            TeamMembership.effective_to.is_(None),
                            TeamMembership.effective_to > now,
                        ),
                        User.is_active.is_(True),
                    )
                    .order_by(User.name, User.user_id)
                )
            ).all()
        )
    leaders = []
    if visible_team_ids:
        leaders = list(
            (
                await db.execute(
                    select(TeamLeaderAssignment, User)
                    .join(User, User.user_id == TeamLeaderAssignment.leader_user_id)
                    .where(
                        TeamLeaderAssignment.team_id.in_(visible_team_ids),
                        TeamLeaderAssignment.effective_from <= now,
                        or_(
                            TeamLeaderAssignment.effective_to.is_(None),
                            TeamLeaderAssignment.effective_to > now,
                        ),
                    )
                )
            ).all()
        )
    leaders_by_team: dict[str, list[dict[str, Any]]] = {}
    for assignment, leader in leaders:
        leaders_by_team.setdefault(str(assignment.team_id), []).append(
            {
                "user_id": str(leader.user_id),
                "name": leader.name,
                "role": assignment.assignment_role,
            }
        )
    return success_response(
        {
            "teams": [
                {
                    "team_id": str(team.team_id),
                    "code": team.code,
                    "name": team.name,
                    "leaders": leaders_by_team.get(str(team.team_id), []),
                }
                for team in teams
            ],
            "members": [
                {
                    "team_id": str(membership.team_id),
                    "learner_id": str(user.user_id),
                    "learner_name": user.name,
                    "email": user.email,
                }
                for membership, user in memberships
            ],
        }
    )


def _error(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message),
    )


def _service_error(exc: SupervisorServiceError) -> JSONResponse:
    return _error(exc.status_code, exc.error_code, exc.message)


@router.get("/supervisor/team/reports")
async def list_team_reports(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List completed team reports for supervisor review."""
    try:
        reports = await SupervisorReviewService(db).list_team_reports(
            current_user=current_user,
            limit=limit,
        )
        return success_response([item.model_dump(mode="json") for item in reports])
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_TEAM_REPORTS_FAILED]",
            message="主管报告列表暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/certification-review-queue")
async def list_certification_review_queue(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List high-stakes certification/onboarding sessions awaiting review."""
    try:
        items = await SupervisorReviewService(db).list_certification_review_queue(
            current_user=current_user,
            limit=limit,
        )
        return success_response([item.model_dump(mode="json") for item in items])
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[CERTIFICATION_REVIEW_QUEUE_FAILED]",
            message="认证复核队列暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/team/insights")
async def get_team_insights(
    scenario_type: str | None = Query(default=None),
    learner_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    team_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return supervisor team training management read model."""
    try:
        insights = await SupervisorReviewService(db).get_team_insights(
            current_user=current_user,
            scenario_type=scenario_type,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
            team_id=team_id,
            search=search,
        )
        return success_response(insights.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_TEAM_INSIGHTS_FAILED]",
            message="主管团队训练洞察暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/team/workbench")
async def get_team_workbench(
    team_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Read-only team result without readiness, calibration, ranking or retraining."""
    try:
        result = await SupervisorReviewService(db).get_team_workbench(
            current_user=current_user,
            team_id=team_id,
            search=search,
            date_from=date_from,
            date_to=date_to,
        )
        return success_response(result)
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_TEAM_WORKBENCH_FAILED]",
            message="团队训练工作台暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/team/workbench/{learner_id}")
async def get_team_workbench_member(
    learner_id: str,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Read-only member drilldown with source tasks and deterministic evidence."""
    try:
        detail = await SupervisorReviewService(db).get_team_insights_detail(
            current_user=current_user,
            learner_id=learner_id,
            date_from=date_from,
            date_to=date_to,
        )
        return success_response(
            {
                "learner_id": detail.learner_id,
                "learner_name": detail.learner_name,
                "learner_email": detail.learner_email,
                "extra_task_progress": detail.completion.model_dump(mode="json"),
                "training_tasks": [
                    task.model_dump(mode="json") for task in detail.training_tasks
                ],
                "risk_labels": [item.dimension for item in detail.top_weaknesses],
                "common_issues": [
                    item.model_dump(mode="json") for item in detail.common_issues
                ],
            }
        )
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_TEAM_MEMBER_WORKBENCH_FAILED]",
            message="成员训练详情暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/team/insights/{learner_id}/details")
async def get_team_insights_detail(
    learner_id: str,
    scenario_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Return one learner's supervisor training management detail."""
    try:
        detail = await SupervisorReviewService(db).get_team_insights_detail(
            current_user=current_user,
            learner_id=learner_id,
            scenario_type=scenario_type,
            date_from=date_from,
            date_to=date_to,
        )
        return success_response(detail.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_TEAM_INSIGHTS_DETAIL_FAILED]",
            message="主管学员训练详情暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/reviews")
async def list_supervisor_reviews(
    session_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List supervisor reviews; employees only see reviews for their own sessions."""
    try:
        reviews = await SupervisorReviewService(db).list_reviews(
            current_user=current_user,
            session_id=session_id,
        )
        return success_response([item.model_dump(mode="json") for item in reviews])
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_REVIEWS_FAILED]",
            message="主管评审暂时无法读取。",
            exc=exc,
        )


@router.get("/supervisor/report-view/{session_id}")
async def get_training_report_view(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Read the unified report view used for evidence-based supervisor review."""
    try:
        view = await SupervisorReviewService(db).get_training_report_view(
            session_id=session_id,
            current_user=current_user,
        )
        payload = view.model_dump(mode="json")
        if str(getattr(current_user, "role", "user")).lower() != "admin":
            payload.pop("thinking_evidence", None)
        return success_response(payload)
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[TRAINING_REPORT_VIEW_FAILED]",
            message="证据化报告暂时无法读取。",
            exc=exc,
        )


@router.post("/supervisor/reviews", status_code=201)
async def create_supervisor_review(
    payload: SupervisorReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create or update the supervisor review for one session report."""
    try:
        review = await SupervisorReviewService(db).create_review(
            payload=payload,
            supervisor=current_user,
        )
        return success_response(review.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_REVIEW_CREATE_FAILED]",
            message="主管评审暂时无法保存。",
            exc=exc,
        )


@router.patch("/supervisor/reviews/{review_id}/decision")
async def update_supervisor_review_decision(
    review_id: str,
    payload: SupervisorReviewDecisionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update supervisor decision and create a retraining task when required."""
    try:
        review = await SupervisorReviewService(db).update_decision(
            review_id=review_id,
            payload=payload,
            supervisor=current_user,
        )
        return success_response(review.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_REVIEW_UPDATE_FAILED]",
            message="主管评审决策暂时无法保存。",
            exc=exc,
        )


@router.post("/supervisor/reviews/{review_id}/score-calibrations")
async def upsert_supervisor_score_calibration(
    review_id: str,
    payload: SupervisorScoreCalibrationUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Save a supervisor score calibration without changing the original AI score."""
    try:
        calibration = await SupervisorReviewService(db).upsert_score_calibration(
            review_id=review_id,
            payload=payload,
            supervisor=current_user,
        )
        return success_response(calibration.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[SUPERVISOR_SCORE_CALIBRATION_FAILED]",
            message="主管评分校准暂时无法保存。",
            exc=exc,
        )


@router.get("/retraining/tasks")
async def list_retraining_tasks(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List retraining tasks for the current employee, or all tasks for admins."""
    try:
        tasks = await SupervisorReviewService(db).list_tasks(
            current_user=current_user,
            status=status,
        )
        return success_response([item.model_dump(mode="json") for item in tasks])
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[RETRAINING_TASKS_FAILED]",
            message="复训任务暂时无法读取。",
            exc=exc,
        )


@router.post("/retraining/tasks", status_code=201)
async def create_retraining_task(
    payload: RetrainingTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a retraining task from a supervisor review."""
    try:
        task = await SupervisorReviewService(db).create_task(
            payload=payload,
            current_user=current_user,
        )
        return success_response(task.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[RETRAINING_TASK_CREATE_FAILED]",
            message="复训任务暂时无法创建。",
            exc=exc,
        )


@router.post("/retraining/tasks/{task_id}/start-session")
async def start_retraining_session(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new practice session seeded from the source session runtime."""
    try:
        result = await SupervisorReviewService(db).start_task_session(
            task_id=task_id,
            current_user=current_user,
        )
        return success_response(result.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[RETRAINING_TASK_START_FAILED]",
            message="复训会话暂时无法创建。",
            exc=exc,
        )


@router.post("/retraining/tasks/{task_id}/complete-with-session")
async def complete_retraining_task_with_session(
    task_id: str,
    payload: RetrainingTaskCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Mark a retraining task completed and attach the completed session."""
    try:
        task = await SupervisorReviewService(db).complete_task_with_session(
            task_id=task_id,
            payload=payload,
            current_user=current_user,
        )
        return success_response(task.model_dump(mode="json"))
    except SupervisorServiceError as exc:
        return _service_error(exc)
    except SQLAlchemyError as exc:
        return build_server_error(
            "[RETRAINING_TASK_COMPLETE_FAILED]",
            message="复训任务暂时无法完成。",
            exc=exc,
        )
