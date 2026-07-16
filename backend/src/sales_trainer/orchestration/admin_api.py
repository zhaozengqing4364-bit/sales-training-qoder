"""Focused administration API for newcomer-training path orchestration."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.teams import TeamScopePolicy
from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)
from sales_trainer.orchestration.contracts import StrictModel, TrainingPathPayload
from sales_trainer.orchestration.errors import (
    NewcomerOrchestrationError,
    PathValidationError,
)
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.orchestration.journey_summary_service import (
    JourneySummaryReadService,
)
from sales_trainer.orchestration.revision_service import (
    TrainingPathRevisionService,
)
from sales_trainer.permissions import (
    can_manage_newcomer_training_path,
    can_publish_newcomer_training_path,
    can_view_sales_trainer_records,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.readiness_dossier_service import (
    ReadinessDossierError,
    ReadinessDossierService,
)

admin_router = APIRouter(prefix="/admin/newcomer-training/path")
admin_journey_router = APIRouter(prefix="/admin/newcomer-training")


class DraftRequest(StrictModel):
    payload: TrainingPathPayload
    reason: str = Field(min_length=1, max_length=500)
    expected_revision_id: str | None = Field(default=None, min_length=1, max_length=36)


class CandidateRequest(StrictModel):
    payload: TrainingPathPayload


class PublishCandidateRequest(DraftRequest):
    pass


class ReasonRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class RestoreRequest(ReasonRequest):
    expected_revision_id: str | None = Field(default=None, min_length=1, max_length=36)


class ReadinessReviewRequest(StrictModel):
    decision: Literal[
        "approve",
        "require_retraining",
        "mark_manual_follow_up",
        "reject",
        "retrain",
    ]
    reason: str = Field(min_length=1, max_length=500)
    capability_keys: list[str] = Field(default_factory=list, max_length=50)
    source_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class RubricDimensionRequest(StrictModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    weight: float = Field(gt=0, le=100)


class RubricCreateRequest(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    pass_score: float = Field(ge=0, le=100)
    dimensions: list[RubricDimensionRequest] = Field(min_length=1, max_length=20)


def _forbidden() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response(
            "[ROLE_REQUIRED]", message="当前账号没有管理训练路径的权限。"
        ),
    )


def _error(exc: NewcomerOrchestrationError) -> JSONResponse:
    details = None
    if isinstance(exc, PathValidationError):
        details = [
            {
                "code": issue.code,
                "message": issue.message,
                "object_id": issue.object_id,
                "field_path": issue.field_path,
                "severity": issue.severity,
            }
            for issue in exc.issues
        ]
    content = error_response(exc.code, message=exc.message)
    if details is not None:
        content["details"] = details
    return JSONResponse(status_code=exc.status_code, content=content)


def _trace_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request.headers.get("x-trace-id")


@admin_router.get("/", response_model=None)
async def get_path(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        (await TrainingPathRevisionService(db).get_config()).model_dump()
    )


@admin_router.put("/draft", response_model=None)
async def save_draft(
    payload: DraftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        revision = await TrainingPathRevisionService(db).save_draft(
            payload=payload.payload,
            actor=current_user,
            reason=payload.reason,
            trace_id=_trace_id(request),
            expected_revision_id=payload.expected_revision_id,
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(revision))


@admin_router.delete("/draft", response_model=None)
async def delete_draft(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    await TrainingPathRevisionService(db).delete_draft(
        actor=current_user, trace_id=_trace_id(request)
    )
    await db.commit()
    return success_response({"deleted": True})


@admin_router.post("/validate", response_model=None)
async def validate_draft(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await TrainingPathRevisionService(db).validate_draft()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(result.model_dump())


@admin_router.post("/validate-candidate", response_model=None)
async def validate_candidate(
    payload: CandidateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    result = await TrainingPathRevisionService(db).validate_candidate(payload.payload)
    return success_response(result.model_dump())


@admin_router.post("/publish", response_model=None)
async def publish(
    payload: ReasonRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_publish_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await TrainingPathRevisionService(db).publish(
            actor=current_user, reason=payload.reason, trace_id=_trace_id(request)
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(result.revision))


@admin_router.post("/publish-candidate", response_model=None)
async def publish_candidate(
    payload: PublishCandidateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_publish_newcomer_training_path(current_user):
        return _forbidden()
    try:
        result = await TrainingPathRevisionService(db).publish_candidate(
            payload=payload.payload,
            actor=current_user,
            reason=payload.reason,
            expected_revision_id=payload.expected_revision_id,
            trace_id=_trace_id(request),
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        await db.rollback()
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(result.revision))


@admin_router.get("/revisions", response_model=None)
async def revisions(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    rows = await TrainingPathRevisionService(db).list_revisions()
    return success_response(
        [SalesTrainerAssetRevisionService.snapshot(row) for row in rows]
    )


@admin_router.post("/revisions/{revision_id}/restore", response_model=None)
async def restore(
    revision_id: str,
    payload: RestoreRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    try:
        row = await TrainingPathRevisionService(db).restore_as_draft(
            revision_id=revision_id,
            actor=current_user,
            reason=payload.reason,
            trace_id=_trace_id(request),
            expected_revision_id=payload.expected_revision_id,
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(SalesTrainerAssetRevisionService.snapshot(row))


@admin_router.get("/activity-types", response_model=None)
async def activity_types(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        [
            {"type": key, "label": label}
            for key, label in (
                ("lesson", "内容学习"),
                ("quiz", "考试测验"),
                ("audio_assessment", "录音讲解"),
                ("realtime_roleplay", "实时对练"),
                ("ai_coach", "AI 教练"),
                ("assignment", "作业任务"),
            )
        ]
    )


@admin_router.get("/coach-profiles", response_model=None)
async def coach_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        await _active_asset_options(db, resource_type="ai_coach_profile")
    )


async def _active_asset_options(
    db: AsyncSession, *, resource_type: str
) -> list[dict[str, str]]:
    rows = (
        await db.execute(
            select(SalesTrainerAssetRevision)
            .join(
                SalesTrainerAssetActiveRevision,
                SalesTrainerAssetActiveRevision.active_revision_id
                == SalesTrainerAssetRevision.revision_id,
            )
            .where(
                SalesTrainerAssetActiveRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.status == "published",
            )
            .order_by(SalesTrainerAssetRevision.logical_id)
        )
    ).scalars()
    return [
        {
            "id": str(row.logical_id),
            "title": str(row.payload_json.get("title") or row.logical_id),
            "status": "published",
        }
        for row in rows
    ]


@admin_router.get("/scoring-rubrics", response_model=None)
async def scoring_rubrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    return success_response(
        await _active_asset_options(db, resource_type="audio_scoring_rubric")
    )


@admin_router.post("/scoring-rubrics", response_model=None)
async def create_scoring_rubric(
    payload: RubricCreateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_manage_newcomer_training_path(current_user):
        return _forbidden()
    logical_id = str(uuid4())
    revision = await SalesTrainerAssetRevisionService(db).create_published_revision(
        resource_type="audio_scoring_rubric",
        logical_id=logical_id,
        payload=payload.model_dump(mode="json"),
        actor=current_user,
        change_class="scoring_high_risk",
        reason="在训练路径编辑器中创建评分标准",
        trace_id=_trace_id(request),
    )
    await OperationLogService(db).record(
        actor=current_user,
        action="newcomer_training_scoring_rubric_created",
        target_type="audio_scoring_rubric",
        target_id=logical_id,
        request_id=_trace_id(request),
        metadata={"revision_id": str(revision.revision.revision_id)},
    )
    await db.commit()
    return success_response(
        {"id": logical_id, "title": payload.title, "status": "published"}
    )


@admin_journey_router.get("/journeys/{learner_id}", response_model=None)
async def learner_journey(
    learner_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_view_sales_trainer_records(current_user):
        return _forbidden()
    learner = await db.get(User, learner_id)
    scope_policy = TeamScopePolicy(db)
    if learner is None or not await scope_policy.can_view_learner(
        current_user, learner_id
    ):
        return JSONResponse(
            status_code=404,
            content=error_response(
                "[NEWCOMER_LEARNER_NOT_FOUND]", message="学员不存在或不在管理范围内。"
            ),
        )
    try:
        journey = await NewcomerJourneyService(db).get_or_create_for_learner(
            learner=learner
        )
        await db.commit()
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    return success_response(journey.model_dump())


@admin_journey_router.get("/journeys", response_model=None)
async def learner_journeys(
    team_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_view_sales_trainer_records(current_user):
        return _forbidden()
    try:
        result = await JourneySummaryReadService(db).list_summaries(
            current_user=current_user,
            team_id=team_id,
            search=search,
            limit=limit,
            offset=offset,
        )
    except NewcomerOrchestrationError as exc:
        return _error(exc)
    if result.wrote:
        await db.commit()
    return success_response(result.response.model_dump())


@admin_journey_router.get("/readiness/workbench", response_model=None)
async def readiness_workbench(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_view_sales_trainer_records(current_user):
        return _forbidden()
    try:
        payload = await ReadinessDossierService(db).list_workbench(
            viewer=current_user,
            team_scope=await TeamScopePolicy(db).resolve(current_user),
            limit=limit,
            offset=offset,
        )
    except ReadinessDossierError as exc:
        return _readiness_error(exc)
    return success_response(payload)


@admin_journey_router.get("/readiness/dossiers/{learner_id}", response_model=None)
async def readiness_dossier(
    learner_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_view_sales_trainer_records(current_user):
        return _forbidden()
    try:
        payload = await ReadinessDossierService(db).get_dossier(
            learner_id,
            viewer=current_user,
            team_scope=await TeamScopePolicy(db).resolve(current_user),
        )
    except ReadinessDossierError as exc:
        return _readiness_error(exc)
    return success_response(payload)


@admin_journey_router.post(
    "/readiness/dossiers/{learner_id}/review-actions", response_model=None
)
async def create_readiness_review(
    learner_id: str,
    payload: ReadinessReviewRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    if not can_view_sales_trainer_records(current_user):
        return _forbidden()
    try:
        action = await ReadinessDossierService(db).create_review_action(
            learner_id,
            actor=current_user,
            team_scope=await TeamScopePolicy(db).resolve(current_user),
            decision=payload.decision,
            reason=payload.reason,
            capability_keys=payload.capability_keys,
            source_evidence_ids=payload.source_evidence_ids,
            request_id=_trace_id(request),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except ReadinessDossierError as exc:
        return _readiness_error(exc)
    return success_response(action)


def _readiness_error(exc: ReadinessDossierError) -> JSONResponse:
    content = error_response(exc.code, message=exc.message)
    if exc.details is not None:
        content["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)


__all__ = ["admin_journey_router", "admin_router"]
