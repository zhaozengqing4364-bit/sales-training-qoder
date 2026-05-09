"""Supervisor review and retraining task APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from supervisor.schemas import (
    RetrainingTaskCompleteRequest,
    RetrainingTaskCreate,
    SupervisorReviewCreate,
    SupervisorReviewDecisionUpdate,
    SupervisorScoreCalibrationUpsert,
)
from supervisor.service import SupervisorReviewService, SupervisorServiceError

router = APIRouter()


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
        return success_response(view.model_dump(mode="json"))
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
