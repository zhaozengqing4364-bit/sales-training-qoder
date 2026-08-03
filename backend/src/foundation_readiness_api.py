"""HTTP delivery for learner dossiers and authorized readiness review."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.roles import (
    PLATFORM_ADMIN_ROLES,
    TRAINING_MANAGER_ROLES,
    normalize_role,
)
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from common.teams import TeamScopePolicy
from competency_evidence.application import CompetencyEvidenceService
from competency_evidence.errors import CompetencyEvidenceError
from competency_evidence.models import CompetencyEvidenceRecord
from foundation_learner_api import get_foundation_organization_id
from foundation_readiness_composition import FoundationReadinessProjection
from readiness.application import ReadinessService
from readiness.contracts import (
    AISummaryDraft,
    AppealInput,
    AppealResolutionInput,
    CalibrationSessionInput,
    ExceptionDecisionPreviewInput,
    ReadinessActor,
    RetrainingAssignmentInput,
    ReviewDecisionInput,
)
from readiness.errors import ReadinessError
from readiness.models import ReadinessDossier
from sales_trainer.permissions import can_learn_newcomer_training_path

learner_router = APIRouter(
    prefix="/newcomer-training",
    tags=["newcomer-training-readiness"],
)
admin_router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training-readiness"],
)

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200),
]
IfMatch = Annotated[
    str,
    Header(alias="If-Match", min_length=3, max_length=80),
]

_ETAG_PATTERN = re.compile(r'^W/"(?P<version>[1-9][0-9]*)"$')


class StrictRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RebuildDossierRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class InvalidateEvidenceRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class AISummaryRequest(StrictRequest):
    snapshot_id: str = Field(min_length=1, max_length=160)
    draft: AISummaryDraft | None = None
    error_code: str | None = Field(default=None, max_length=120)


async def get_readiness_learner_actor(
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_foundation_organization_id),
) -> ReadinessActor:
    capabilities = (
        frozenset({"readiness.self.read", "readiness.appeal.submit"})
        if can_learn_newcomer_training_path(current_user)
        else frozenset()
    )
    learner_id = str(current_user.user_id)
    return ReadinessActor(
        organization_id=organization_id,
        actor_id=learner_id,
        capabilities=capabilities,
        learner_ids=frozenset({learner_id}),
        is_human=True,
        trace_id=get_trace_id(),
    )


async def get_readiness_admin_actor(
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_foundation_organization_id),
    db: AsyncSession = Depends(get_db),
) -> ReadinessActor:
    role = normalize_role(getattr(current_user, "role", None), default="")
    scope = await TeamScopePolicy(db).resolve(current_user)
    capabilities: set[str] = set()
    if role in TRAINING_MANAGER_ROLES | PLATFORM_ADMIN_ROLES:
        capabilities.update(
            {
                "readiness.queue.read",
                "readiness.dossier.read",
                "readiness.review",
                "readiness.retraining.assign",
                "readiness.appeal.resolve",
                "readiness.calibration",
            }
        )
    if role in PLATFORM_ADMIN_ROLES:
        capabilities.update(
            {
                "readiness.rebuild",
                "readiness.export",
                "readiness.evidence.invalidate",
            }
        )
    return ReadinessActor(
        organization_id=organization_id,
        actor_id=str(current_user.user_id),
        capabilities=frozenset(capabilities),
        unrestricted_scope=scope.unrestricted,
        learner_ids=scope.learner_ids,
        is_human=True,
        trace_id=get_trace_id(),
    )


def _version(value: str) -> int:
    matched = _ETAG_PATTERN.fullmatch(value.strip())
    if matched is None:
        raise ReadinessError(
            "[IF_MATCH_INVALID]",
            "版本头格式无效，请刷新页面后重试。",
            412,
        )
    return int(matched.group("version"))


def _success(value: object, *, version: int | None = None) -> JSONResponse:
    headers = {"ETag": f'W/"{version}"'} if version is not None else None
    return JSONResponse(
        content=jsonable_encoder(success_response(value)),
        headers=headers,
    )


async def _failure(
    db: AsyncSession,
    exc: ReadinessError | CompetencyEvidenceError,
) -> JSONResponse:
    if isinstance(exc, ReadinessError) and exc.audit_persisted:
        await db.commit()
    else:
        await db.rollback()
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


@learner_router.get("/dossier", response_model=None)
async def get_my_readiness_dossier(
    actor: ReadinessActor = Depends(get_readiness_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        dossier = await FoundationReadinessProjection(db).ensure_learner_dossier(
            organization_id=actor.organization_id,
            learner_id=actor.actor_id,
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
        )
        projection = await ReadinessService(db).get_by_enrollment(
            actor=actor,
            enrollment_id=dossier.enrollment_id,
            learner_safe=True,
        )
        await db.commit()
    except (ReadinessError, CompetencyEvidenceError) as exc:
        return await _failure(db, exc)
    return _success(projection, version=int(projection["dossier_version"]))


@learner_router.post("/dossier/appeals", response_model=None)
async def submit_readiness_appeal(
    payload: AppealInput,
    idempotency_key: IdempotencyKey,
    actor: ReadinessActor = Depends(get_readiness_learner_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        dossier = await FoundationReadinessProjection(db).ensure_learner_dossier(
            organization_id=actor.organization_id,
            learner_id=actor.actor_id,
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
        )
        result = await ReadinessService(db).submit_appeal(
            actor=actor,
            enrollment_id=dossier.enrollment_id,
            command=payload,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except (ReadinessError, CompetencyEvidenceError) as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.get("/reviews", response_model=None)
async def list_readiness_reviews(
    state: str | None = Query(default=None, max_length=32),
    cohort_id: str | None = Query(default=None, max_length=120),
    competency_key: str | None = Query(default=None, max_length=80),
    reviewer_id: str | None = Query(default=None, max_length=120),
    waiting_hours_gte: int | None = Query(default=None, ge=0, le=87_600),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ReadinessService(db).list_queue(
            actor=actor,
            state=state,
            cohort_id=cohort_id,
            competency_key=competency_key,
            reviewer_id=reviewer_id,
            waiting_hours_gte=waiting_hours_gte,
            limit=limit,
            offset=offset,
        )
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.get("/reviews/{dossier_id}", response_model=None)
async def get_readiness_review(
    dossier_id: str,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ReadinessService(db).get_by_id(
            actor=actor,
            dossier_id=dossier_id,
        )
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result, version=int(result["dossier_version"]))


@admin_router.post(
    "/reviews/{dossier_id}/commands/preview-exception",
    response_model=None,
)
async def preview_readiness_exception(
    dossier_id: str,
    payload: ExceptionDecisionPreviewInput,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        if payload.expected_dossier_version != _version(if_match):
            raise ReadinessError(
                "[DOSSIER_VERSION_CONFLICT]",
                "请求版本与档案版本头不一致，请刷新后重试。",
                412,
            )
        result = await ReadinessService(db).preview_exception_decision(
            actor=actor,
            dossier_id=dossier_id,
            command=payload,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result, version=payload.expected_dossier_version)


@admin_router.post(
    "/reviews/{dossier_id}/commands/record-decision",
    response_model=None,
)
async def record_readiness_decision(
    dossier_id: str,
    payload: ReviewDecisionInput,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        if payload.expected_dossier_version != _version(if_match):
            raise ReadinessError(
                "[DOSSIER_VERSION_CONFLICT]",
                "请求版本与档案版本头不一致，请刷新后重试。",
                412,
            )
        result = await ReadinessService(db).record_decision(
            actor=actor,
            dossier_id=dossier_id,
            command=payload,
            idempotency_key=idempotency_key,
        )
        dossier = await db.get(ReadinessDossier, dossier_id)
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result, version=(dossier.version if dossier else None))


@admin_router.post(
    "/reviews/{dossier_id}/commands/assign-retraining",
    response_model=None,
)
async def assign_readiness_retraining(
    dossier_id: str,
    payload: RetrainingAssignmentInput,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        if payload.expected_dossier_version != _version(if_match):
            raise ReadinessError(
                "[DOSSIER_VERSION_CONFLICT]",
                "请求版本与档案版本头不一致，请刷新后重试。",
                412,
            )
        if payload.activity_source == "existing_published" and payload.activity_id:
            await FoundationReadinessProjection(
                db
            ).require_published_retraining_activity(
                organization_id=actor.organization_id,
                dossier_id=dossier_id,
                activity_id=payload.activity_id,
                target_competency_keys=payload.target_competency_keys,
            )
        result = await ReadinessService(db).assign_retraining(
            actor=actor,
            dossier_id=dossier_id,
            command=payload,
            idempotency_key=idempotency_key,
        )
        dossier = await db.get(ReadinessDossier, dossier_id)
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result, version=(dossier.version if dossier else None))


@admin_router.post("/reviews/{dossier_id}/rebuild", response_model=None)
async def rebuild_readiness_dossier(
    dossier_id: str,
    payload: RebuildDossierRequest,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    del payload
    service = ReadinessService(db)
    try:
        await service.get_by_id(actor=actor, dossier_id=dossier_id)
        await service.authorize(
            actor=actor,
            capability="readiness.rebuild",
            object_type="readiness_dossier",
            object_id=dossier_id,
            command="rebuild_dossier",
        )
        dossier = await db.get(ReadinessDossier, dossier_id)
        if dossier is None:
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]", "训练档案不存在或不可访问。", 404
            )
        result = await FoundationReadinessProjection(db).rebuild_enrollment(
            organization_id=actor.organization_id,
            enrollment_id=dossier.enrollment_id,
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
            force_refresh=True,
        )
        await db.commit()
    except (ReadinessError, CompetencyEvidenceError) as exc:
        return await _failure(db, exc)
    return _success(result, version=int(result["dossier_version"]))


@admin_router.post("/appeals/{appeal_id}/commands", response_model=None)
async def resolve_readiness_appeal(
    appeal_id: str,
    payload: AppealResolutionInput,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ReadinessService(db).resolve_appeal(
            actor=actor,
            appeal_id=appeal_id,
            command=payload,
        )
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.post("/calibration-sessions", response_model=None)
async def create_readiness_calibration_session(
    payload: CalibrationSessionInput,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ReadinessService(db).create_calibration_session(
            actor=actor,
            command=payload,
        )
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.post("/reviews/{dossier_id}/ai-summaries", response_model=None)
async def record_readiness_ai_summary(
    dossier_id: str,
    payload: AISummaryRequest,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    service = ReadinessService(db)
    try:
        await service.get_by_id(actor=actor, dossier_id=dossier_id)
        await service.authorize(
            actor=actor,
            capability="readiness.review",
            object_type="readiness_dossier",
            object_id=dossier_id,
            command="record_ai_summary",
        )
        result = await service.record_ai_summary(
            actor_id=actor.actor_id,
            dossier_id=dossier_id,
            snapshot_id=payload.snapshot_id,
            draft=payload.draft,
            error_code=payload.error_code,
        )
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.post("/evidence/{evidence_id}/invalidation", response_model=None)
async def invalidate_competency_evidence(
    evidence_id: str,
    payload: InvalidateEvidenceRequest,
    idempotency_key: IdempotencyKey,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    service = ReadinessService(db)
    try:
        await service.authorize(
            actor=actor,
            capability="readiness.evidence.invalidate",
            object_type="competency_evidence",
            object_id=evidence_id,
            command="invalidate_evidence",
        )
        evidence = await db.get(CompetencyEvidenceRecord, evidence_id)
        if (
            evidence is None
            or evidence.organization_id != actor.organization_id
            or not actor.allows_learner(evidence.learner_id)
        ):
            raise ReadinessError(
                "[EVIDENCE_NOT_FOUND]", "训练证据不存在或不可访问。", 404
            )
        result = await CompetencyEvidenceService(db).invalidate(
            organization_id=actor.organization_id,
            evidence_id=evidence_id,
            actor_id=actor.actor_id,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            trace_id=actor.trace_id,
        )
        await FoundationReadinessProjection(db).rebuild_enrollment(
            organization_id=actor.organization_id,
            enrollment_id=evidence.enrollment_id,
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
            force_refresh=False,
        )
        await db.commit()
    except (ReadinessError, CompetencyEvidenceError) as exc:
        return await _failure(db, exc)
    return _success(result)


@admin_router.get("/reviews/{dossier_id}/export", response_model=None)
async def export_readiness_dossier(
    dossier_id: str,
    actor: ReadinessActor = Depends(get_readiness_admin_actor),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await ReadinessService(db).export_dossier(
            actor=actor,
            dossier_id=dossier_id,
        )
        await db.commit()
    except ReadinessError as exc:
        return await _failure(db, exc)
    return _success(result)


__all__ = ["admin_router", "learner_router"]
