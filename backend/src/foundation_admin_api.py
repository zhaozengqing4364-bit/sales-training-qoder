"""Application-root admin API for newcomer and learning governance."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi import (
    Path as ApiPath,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import CoachHumanInterventionInput
from ai_coach.errors import AICoachError
from ai_coach.governance import CoachGovernanceService, CoachReviewActor
from ai_coach.models import CoachCommandAudit, CoachProfileRevision
from audio_assessment.errors import AudioAssessmentError
from audio_assessment.governance import AudioGovernanceService
from audio_assessment.models import (
    AudioActivityResourceRevision,
    AudioActivityRun,
    AudioCommandAudit,
)
from common.api.response import error_response, success_response
from common.auth.roles import SALES_TRAINER_LEARNER_ROLES
from common.auth.service import get_current_user
from common.db.models import User
from common.db.session import get_db
from common.monitoring.logger import get_trace_id
from common.storage import get_document_storage_service
from common.teams import TeamDataScope, TeamScopePolicy
from foundation_admin_permissions import (
    FoundationAdminActors,
    foundation_admin_actors,
)
from foundation_admin_workspace import FoundationAdminWorkspaceQueryService
from foundation_audio_governance_composition import (
    FoundationAudioAttemptInvalidationAdapter,
)
from foundation_competency_composition import FoundationCompetencyMappingAdapter
from foundation_learner_api import (
    get_foundation_organization_id,
    get_foundation_task_registry,
)
from foundation_question_generation import (
    FoundationQuestionGenerationPolicyService,
    FoundationQuestionGenerationSelection,
)
from foundation_readiness_composition import FoundationReadinessProjection
from foundation_release_composition import FoundationReleaseDependencyAdapter
from learning.admin_queries import (
    LearningAdminQueryService,
    LearningResourceType,
)
from learning.application import (
    LearningGovernanceService,
    QuestionCandidateBulkItem,
)
from learning.contracts import (
    LearningUnitRevisionDraft,
    QuestionCandidateContent,
    QuizRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestionGenerationBatch,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from learning.multimedia import (
    SourceContentKind,
    SourceUploadError,
    finalize_staged_source,
    preview_root,
    stage_source_upload,
)
from learning.source_ingestion import (
    SOURCE_DOCUMENT_PARSER_VERSION,
    SUPPORTED_SOURCE_FILE_TYPES,
    SourceFileType,
    source_document_artifact_uri,
    source_document_file_path,
)
from newcomer_foundation_composition import (
    FoundationLessonAdministrationService,
    FoundationPublishedResourceAdapter,
)
from newcomer_training.admin_queries import FoundationLearnerAdminQueryService
from newcomer_training.application import PathEnrollmentService
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import NewcomerActivityAttempt
from newcomer_training.release import ReleasePlanService
from task_runtime.registry import TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime

router = APIRouter(
    prefix="/admin/newcomer-training",
    tags=["admin-newcomer-training"],
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


class CreatePathRequest(StrictRequest):
    stable_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)


class CreateCohortRequest(StrictRequest):
    stable_key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    path_revision_id: str = Field(min_length=1, max_length=160)


class CreateEnrollmentRequest(StrictRequest):
    learner_id: str = Field(min_length=1, max_length=160)


class CohortStatusRequest(StrictRequest):
    target_status: Literal["active", "paused", "cancelled", "closed"]
    reason: str = Field(min_length=1, max_length=2_000)


class EnrollmentImportPreviewRequest(StrictRequest):
    learner_ids: list[str] = Field(default_factory=list, max_length=1_000)
    emails: list[EmailStr] = Field(default_factory=list, max_length=1_000)
    reason: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def require_one_identity_source(self) -> EnrollmentImportPreviewRequest:
        if bool(self.learner_ids) == bool(self.emails):
            raise ValueError("provide exactly one of learner_ids or emails")
        normalized_emails = [str(email).strip().lower() for email in self.emails]
        if len(normalized_emails) != len(set(normalized_emails)):
            raise ValueError("emails cannot contain duplicates")
        return self


class EnrollmentImportConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class MigrationPreviewRequest(StrictRequest):
    target_revision_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)


class MigrationConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=2_000)


class BatchMigrationPreviewRequest(StrictRequest):
    enrollment_ids: list[str] = Field(min_length=1, max_length=1_000)
    target_revision_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)


class BatchMigrationConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1, max_length=2_000)


class CreateSourceResourceRequest(StrictRequest):
    resource_type: Literal["source_document"]
    stable_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    working_revision: SourceDocumentRevisionDraft


class CreateLearningUnitResourceRequest(StrictRequest):
    resource_type: Literal["learning_unit"]
    stable_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    working_revision: LearningUnitRevisionDraft


class CreateQuestionResourceRequest(StrictRequest):
    resource_type: Literal["question"]
    stable_key: str = Field(min_length=1, max_length=160)
    working_revision: QuestionCandidateContent
    review_reason: str = Field(min_length=1, max_length=2_000)


class CreateQuizResourceRequest(StrictRequest):
    resource_type: Literal["quiz"]
    stable_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    working_revision: QuizRevisionDraft


CreateResourceRequest = Annotated[
    CreateSourceResourceRequest
    | CreateLearningUnitResourceRequest
    | CreateQuestionResourceRequest
    | CreateQuizResourceRequest,
    Field(discriminator="resource_type"),
]


class SaveSourceResourceRequest(StrictRequest):
    resource_type: Literal["source_document"]
    working_revision: SourceDocumentRevisionDraft


class SaveLearningUnitResourceRequest(StrictRequest):
    resource_type: Literal["learning_unit"]
    working_revision: LearningUnitRevisionDraft


class SaveQuestionResourceRequest(StrictRequest):
    resource_type: Literal["question"]
    working_revision: QuestionCandidateContent
    review_reason: str = Field(min_length=1, max_length=2_000)


class SaveQuizResourceRequest(StrictRequest):
    resource_type: Literal["quiz"]
    working_revision: QuizRevisionDraft


SaveResourceRequest = Annotated[
    SaveSourceResourceRequest
    | SaveLearningUnitResourceRequest
    | SaveQuestionResourceRequest
    | SaveQuizResourceRequest,
    Field(discriminator="resource_type"),
]


class CandidateCommandRequest(StrictRequest):
    review_reason: str | None = Field(default=None, max_length=2_000)
    content: QuestionCandidateContent | None = None

    @model_validator(mode="after")
    def reject_empty_reason(self) -> CandidateCommandRequest:
        if self.review_reason is not None and not self.review_reason.strip():
            raise ValueError("review_reason cannot be blank")
        return self


class BulkCandidateCommandRequest(StrictRequest):
    command: Literal["begin-review", "approve", "reject", "supersede"]
    items: tuple[QuestionCandidateBulkItem, ...] = Field(
        min_length=1,
        max_length=100,
    )
    review_reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_reason_and_uniqueness(self) -> BulkCandidateCommandRequest:
        candidate_ids = [item.candidate_id for item in self.items]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id must be unique")
        if self.command == "begin-review":
            if self.review_reason is not None:
                raise ValueError("begin-review does not accept review_reason")
        elif self.review_reason is None or not self.review_reason.strip():
            raise ValueError("review_reason is required")
        return self


class CandidateBulkPreviewRequest(StrictRequest):
    command: Literal["approve", "reject", "supersede"]
    candidate_ids: list[str] = Field(min_length=1, max_length=500)
    review_reason: str = Field(min_length=1, max_length=2_000)


class CandidateBulkConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class InvalidateLessonRequest(StrictRequest):
    expected_detail_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2_000)


class ArchiveResourceRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class PublishRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class ReleasePlanPreviewRequest(StrictRequest):
    path_revision_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)


class ReleasePlanPublishRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReleaseRollbackPreviewRequest(StrictRequest):
    target_release_plan_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)


class ReleaseRollbackConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


BindingResourceType = Literal[
    "learning_unit",
    "quiz",
    "audio_material",
    "scoring_scheme",
    "scenario",
    "coach_profile",
]


class AudioRegradePreviewRequest(StrictRequest):
    mode: Literal["regrade", "retranscribe"] = "regrade"
    target_scoring_scheme_revision_id: str | None = Field(
        default=None,
        max_length=160,
    )
    reason: str = Field(min_length=1, max_length=2_000)


class AudioTranscriptCorrectionPreviewRequest(StrictRequest):
    transcript: str = Field(min_length=1, max_length=1_000_000)
    reason: str = Field(min_length=1, max_length=2_000)


class AudioInvalidationPreviewRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class AudioPreviewConfirmRequest(StrictRequest):
    preview_token: str = Field(min_length=1, max_length=200)
    impact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AudioRepairRequest(StrictRequest):
    reason: str = Field(min_length=1, max_length=2_000)


class CoachInterventionRequest(CoachHumanInterventionInput):
    pass


async def get_foundation_admin_actors(
    current_user: User = Depends(get_current_user),
    organization_id: str = Depends(get_foundation_organization_id),
) -> FoundationAdminActors:
    return foundation_admin_actors(
        user=current_user,
        organization_id=organization_id,
        trace_id=get_trace_id(),
    )


async def get_foundation_admin_scope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamDataScope:
    return await TeamScopePolicy(db).resolve(current_user)


def _version(if_match: str) -> int:
    matched = _ETAG_PATTERN.fullmatch(if_match.strip())
    if matched is None:
        raise NewcomerTrainingError(
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


def _error(
    exc: (
        NewcomerTrainingError
        | LearningGovernanceError
        | AudioAssessmentError
        | AICoachError
    ),
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            exc.code,
            message=exc.message,
            details=exc.details,
        ),
    )


async def _rollback_known(
    db: AsyncSession,
    exc: NewcomerTrainingError | LearningGovernanceError | AudioAssessmentError,
) -> JSONResponse:
    await db.rollback()
    return _error(exc)


def _release_service(db: AsyncSession) -> ReleasePlanService:
    mappings = FoundationCompetencyMappingAdapter(db)
    return ReleasePlanService(
        db,
        dependencies=FoundationReleaseDependencyAdapter(db),
        competency_mappings=mappings,
        path_service=PathEnrollmentService(
            db,
            published_resources=FoundationPublishedResourceAdapter(db),
            competency_mappings=mappings,
        ),
    )


@router.get("/capabilities", response_model=None)
async def get_admin_capabilities(
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
) -> JSONResponse:
    capabilities = sorted(actors.capabilities)
    return _success(
        {
            "capabilities": capabilities,
            "access": {capability: True for capability in capabilities},
            "permission_help": "如需更多权限，请联系组织管理员或培训负责人。",
        }
    )


@router.get("/binding-resources", response_model=None)
async def list_activity_binding_resources(
    resource_type: BindingResourceType,
    status: str | None = Query(default=None, max_length=24),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return safe, exact revision options for the in-flow path binder."""

    try:
        _require_ui_capability(actors, "edit_paths")
        items = await _binding_resource_options(
            db,
            organization_id=actors.newcomer.organization_id,
            resource_type=resource_type,
            status=status,
            search=search,
            limit=limit,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success({"items": items, "limit": limit})


@router.get("/learner-options", response_model=None)
async def list_foundation_learner_options(
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Resolve learner identities without exposing database identifiers in labels."""

    try:
        _require_ui_capability(actors, "manage_cohorts")
        statement = (
            select(User)
            .where(User.is_active.is_(True))
            .where(User.role.in_(sorted(SALES_TRAINER_LEARNER_ROLES)))
            .order_by(User.name.asc(), User.user_id.asc())
            .limit(limit)
        )
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(User.name.ilike(pattern), User.email.ilike(pattern))
            )
        rows = list((await db.execute(statement)).scalars())
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(
        {
            "items": [
                {
                    "learner_id": row.user_id,
                    "name": row.name,
                    "email": row.email,
                    "already_enrolled": False,
                }
                for row in rows
            ],
            "limit": limit,
        }
    )


@router.get("/learners", response_model=None)
async def list_foundation_learners(
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    scope: TeamDataScope = Depends(get_foundation_admin_scope),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationLearnerAdminQueryService(
            db,
            actors=actors,
            scope=scope,
        ).list_learners(search=search, limit=limit, offset=offset)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/learners/{learner_id}", response_model=None)
async def get_foundation_learner(
    learner_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    scope: TeamDataScope = Depends(get_foundation_admin_scope),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationLearnerAdminQueryService(
            db,
            actors=actors,
            scope=scope,
        ).learner_detail(learner_id=learner_id)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/workspace", response_model=None)
async def get_admin_workspace(
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).overview()
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/paths", response_model=None)
async def list_paths(
    query: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).list_paths(query=query, status=status, limit=limit)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/paths/{path_id}/workspace", response_model=None)
async def get_path_workspace(
    path_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).path_workspace(path_id=path_id)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/cohorts", response_model=None)
async def list_cohorts(
    query: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).list_cohorts(query=query, status=status, limit=limit)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/cohorts/{cohort_id}/workspace", response_model=None)
async def get_cohort_workspace(
    cohort_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).cohort_workspace(cohort_id=cohort_id)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/assessment-tasks", response_model=None)
async def list_assessment_tasks(
    state: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).assessment_tasks(state=state, limit=limit)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.get("/audits", response_model=None)
async def list_foundation_audits(
    object_id: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).audits(object_id=object_id, limit=limit)
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.post("/paths", response_model=None)
async def create_path(
    payload: CreatePathRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(
            db,
            published_resources=FoundationPublishedResourceAdapter(db),
            competency_mappings=FoundationCompetencyMappingAdapter(db),
        ).create_path(
            actor=actors.newcomer,
            stable_key=payload.stable_key,
            title=payload.title,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except (NewcomerTrainingError, LearningGovernanceError) as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.get("/paths/{path_id}", response_model=None)
async def get_path(
    path_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).get_path(
            actor=actors.newcomer,
            path_id=path_id,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result, version=result.version)


@router.put("/paths/{path_id}/working-revision", response_model=None)
async def save_path_working_revision(
    path_id: str,
    payload: PathRevisionDraft,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(
            db,
            published_resources=FoundationPublishedResourceAdapter(db),
            competency_mappings=FoundationCompetencyMappingAdapter(db),
        ).save_working_revision(
            actor=actors.newcomer,
            path_id=path_id,
            draft=payload,
            expected_path_version=_version(if_match),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except (NewcomerTrainingError, LearningGovernanceError) as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post("/paths/{path_id}/commands/validate", response_model=None)
async def validate_path_working_revision(
    path_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(
            db,
            published_resources=FoundationPublishedResourceAdapter(db),
            competency_mappings=FoundationCompetencyMappingAdapter(db),
        ).validate_working_revision(
            actor=actors.newcomer,
            path_id=path_id,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.post(
    "/path-revisions/{revision_id}/commands/publish",
    response_model=None,
)
async def publish_path_revision(
    revision_id: str,
    payload: PublishRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    del revision_id, payload, if_match, idempotency_key, actors, db
    return _error(
        NewcomerTrainingError(
            "[NEWCOMER_RELEASE_PLAN_REQUIRED]",
            "路径必须通过发布计划完成校验、影响预览和发布。",
            409,
        )
    )


@router.post("/release-plans/preview", response_model=None)
async def preview_release_plan(
    payload: ReleasePlanPreviewRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await _release_service(db).preview(
            actor=actors.newcomer,
            path_revision_id=payload.path_revision_id,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.get("/release-plans", response_model=None)
async def list_release_plans(
    path_id: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await _release_service(db).list_plans(
            actor=actors.newcomer,
            path_id=path_id,
            limit=limit,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success({"items": result, "limit": limit})


@router.post(
    "/release-plans/{release_plan_id}/commands/publish", response_model=None
)
async def publish_release_plan(
    release_plan_id: str,
    payload: ReleasePlanPublishRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await _release_service(db).publish(
            actor=actors.newcomer,
            release_plan_id=release_plan_id,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            expected_version=_version(if_match),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        if exc.details is not None and exc.details.get("failure_persisted") is True:
            await db.commit()
            return _error(exc)
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post(
    "/release-plans/{release_plan_id}/rollback-preview", response_model=None
)
async def preview_release_rollback(
    release_plan_id: str,
    payload: ReleaseRollbackPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await _release_service(db).preview_rollback(
            actor=actors.newcomer,
            active_release_plan_id=release_plan_id,
            target_release_plan_id=payload.target_release_plan_id,
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/release-plans/{release_plan_id}/commands/rollback", response_model=None
)
async def confirm_release_rollback(
    release_plan_id: str,
    payload: ReleaseRollbackConfirmRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await _release_service(db).confirm_rollback(
            actor=actors.newcomer,
            active_release_plan_id=release_plan_id,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            expected_version=_version(if_match),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post("/cohorts", response_model=None)
async def create_cohort(
    payload: CreateCohortRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).create_cohort(
            actor=actors.newcomer,
            stable_key=payload.stable_key,
            name=payload.name,
            path_revision_id=payload.path_revision_id,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post("/cohorts/{cohort_id}/enrollments", response_model=None)
async def create_enrollment(
    cohort_id: str,
    payload: CreateEnrollmentRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).enroll(
            actor=actors.newcomer,
            cohort_id=cohort_id,
            learner_id=payload.learner_id,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post("/cohorts/{cohort_id}/commands/change-status", response_model=None)
async def change_cohort_status(
    cohort_id: str,
    payload: CohortStatusRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).update_cohort_status(
            actor=actors.newcomer,
            cohort_id=cohort_id,
            target_status=payload.target_status,
            expected_version=_version(if_match),
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post(
    "/cohorts/{cohort_id}/enrollment-imports/preview", response_model=None
)
async def preview_enrollment_import(
    cohort_id: str,
    payload: EnrollmentImportPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        learner_ids = list(payload.learner_ids)
        missing_email_by_placeholder: dict[str, str] = {}
        if payload.emails:
            normalized_emails = [
                str(email).strip().lower() for email in payload.emails
            ]
            rows = list(
                (
                    await db.execute(
                        select(User)
                        .where(func.lower(User.email).in_(normalized_emails))
                        .where(User.role.in_(sorted(SALES_TRAINER_LEARNER_ROLES)))
                    )
                ).scalars()
            )
            by_email = {
                str(row.email).strip().lower(): row
                for row in rows
                if row.email
            }
            for email in normalized_emails:
                learner = by_email.get(email)
                if learner is not None:
                    learner_ids.append(str(learner.user_id))
                    continue
                placeholder = (
                    "unresolved-email-"
                    + hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]
                )
                learner_ids.append(placeholder)
                missing_email_by_placeholder[placeholder] = email
        result = await PathEnrollmentService(db).preview_enrollment_import(
            actor=actors.newcomer,
            cohort_id=cohort_id,
            learner_ids=learner_ids,
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    if missing_email_by_placeholder:
        result = result.model_copy(
            update={
                "items": tuple(
                    item.model_copy(
                        update={
                            "learner_id": "",
                            "learner_name": missing_email_by_placeholder[
                                item.learner_id
                            ],
                            "reason": "learner_email_not_found_or_inactive",
                        }
                    )
                    if item.learner_id in missing_email_by_placeholder
                    else item
                    for item in result.items
                )
            }
        )
    return _success(result)


@router.post("/enrollment-imports/commands/confirm", response_model=None)
async def confirm_enrollment_import(
    payload: EnrollmentImportConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).confirm_enrollment_import(
            actor=actors.newcomer,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/enrollments/{enrollment_id}/revision-migrations/preview",
    response_model=None,
)
async def preview_enrollment_revision_migration(
    enrollment_id: str,
    payload: MigrationPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).preview_revision_migration(
            actor=actors.newcomer,
            enrollment_ids=[enrollment_id],
            target_revision_id=payload.target_revision_id,
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post("/enrollment-revision-migrations/preview", response_model=None)
async def preview_batch_enrollment_revision_migration(
    payload: BatchMigrationPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).preview_revision_migration(
            actor=actors.newcomer,
            enrollment_ids=payload.enrollment_ids,
            target_revision_id=payload.target_revision_id,
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/enrollment-revision-migrations/commands/confirm", response_model=None
)
async def confirm_batch_enrollment_revision_migration(
    payload: BatchMigrationConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).confirm_revision_migration(
            actor=actors.newcomer,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/enrollments/{enrollment_id}/commands/migrate-revision",
    response_model=None,
)
async def confirm_enrollment_revision_migration(
    enrollment_id: str,
    payload: MigrationConfirmRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await PathEnrollmentService(db).confirm_revision_migration(
            actor=actors.newcomer,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
            expected_enrollment_id=enrollment_id,
            expected_enrollment_version=_version(if_match),
            reason=payload.reason,
        )
        await db.commit()
    except NewcomerTrainingError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    migrated = next(
        (item for item in result.items if item.enrollment_id == enrollment_id),
        None,
    )
    return _success(
        result,
        version=migrated.after_version if migrated is not None else None,
    )


@router.get("/resources", response_model=None)
async def list_resources(
    resource_type: LearningResourceType,
    status: str | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["-updated_at", "updated_at", "title"] = "-updated_at",
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningAdminQueryService(db).list_resources(
            actor=actors.learning,
            resource_type=resource_type,
            status=status,
            search=search,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except LearningGovernanceError as exc:
        return _error(exc)
    return _success(result)


@router.post("/resources/{resource_type}", response_model=None)
async def create_resource(
    resource_type: LearningResourceType,
    payload: CreateResourceRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if resource_type != payload.resource_type:
        return _error(
            LearningGovernanceError(
                "[LEARNING_RESOURCE_TYPE_MISMATCH]",
                "资源类型与请求内容不一致。",
                422,
            )
        )
    service = LearningGovernanceService(db)
    try:
        result, version = await _create_resource(
            service=service,
            actors=actors,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=version)


@router.post("/resources/source_document/uploads", response_model=None)
async def upload_source_document(
    stable_key: Annotated[str, Form(min_length=1, max_length=160)],
    title: Annotated[str, Form(min_length=1, max_length=240)],
    revision_label: Annotated[str, Form(min_length=1, max_length=120)],
    file: Annotated[UploadFile, File()],
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
    content_kind: Annotated[
        Literal[
            "document",
            "slide_deck",
            "demo_video",
            "example_audio",
            "attachment",
        ],
        Form(),
    ] = "document",
) -> JSONResponse:
    """Stream, register and enqueue without holding a long database transaction."""

    if not stable_key.strip() or not title.strip() or not revision_label.strip():
        raise HTTPException(
            status_code=422,
            detail="材料名称、业务编码和修订说明不能为空。",
        )
    storage = get_document_storage_service()
    try:
        staged = await stage_source_upload(
            file,
            content_kind=cast(SourceContentKind, content_kind),
            storage=storage,
        )
    except SourceUploadError as exc:
        return _error(
            LearningGovernanceError(
                f"[{exc.code.upper()}]",
                exc.message,
                exc.status_code,
            )
        )

    source_revision = None
    source_resource = None
    try:
        service = LearningGovernanceService(db)
        source_resource = await service.create_source_document(
            actor=actors.learning,
            stable_key=stable_key.strip(),
            title=title.strip(),
            idempotency_key=f"{idempotency_key}:resource",
        )
        artifact_uri = source_document_artifact_uri(
            document_id=source_resource.document_id,
            file_hash=staged.file_hash,
            file_type=staged.file_type,
        )
        source_revision = await service.save_source_revision(
            actor=actors.learning,
            document_id=source_resource.document_id,
            draft=SourceDocumentRevisionDraft(
                revision_label=revision_label.strip(),
                source_type="file",
                content_kind=content_kind,
                source_uri=artifact_uri,
                file_hash=staged.file_hash,
                parser_version=SOURCE_DOCUMENT_PARSER_VERSION,
                parse_status="pending",
                original_filename=staged.original_filename,
                trusted_mime_type=staged.trusted_mime_type,
                file_extension=staged.file_type,
                file_size_bytes=staged.file_size_bytes,
                processing_state="pending",
                processing_stage="registered",
            ),
            expected_document_version=source_resource.version,
            idempotency_key=f"{idempotency_key}:revision",
        )
        await db.commit()
    except LearningGovernanceError as exc:
        await db.rollback()
        staged.discard()
        return _error(exc)
    except Exception:
        await db.rollback()
        staged.discard()
        raise

    assert source_revision is not None and source_resource is not None
    target_path = source_document_file_path(
        storage=storage,
        organization_id=actors.learning.organization_id,
        document_id=source_resource.document_id,
        file_hash=staged.file_hash,
        file_type=staged.file_type,
    )
    try:
        finalize_staged_source(staged, target_path)
    except SourceUploadError as exc:
        await _mark_source_registration_failed(
            db=db,
            actors=actors,
            revision_id=source_revision.revision_id,
            code=exc.code,
            message=exc.message,
        )
        return _error(
            LearningGovernanceError(
                f"[{exc.code.upper()}]",
                exc.message,
                exc.status_code,
            )
        )
    except Exception:
        staged.discard()
        await _mark_source_registration_failed(
            db=db,
            actors=actors,
            revision_id=source_revision.revision_id,
            code="source_artifact_store_failed",
            message="材料文件暂时无法保存，登记信息和原文件名已保留，可重新上传。",
        )
        raise

    try:
        service = LearningGovernanceService(
            db,
            task_runtime=SQLAlchemyTaskRuntime(db, registry=registry),
        )
        task = await service.enqueue_source_document_parse(
            actor=actors.learning,
            revision_id=source_revision.revision_id,
            file_hash=staged.file_hash,
            file_type=staged.file_type,
            idempotency_key=idempotency_key,
        )
        source_resource = await service.get_source_document(
            actor=actors.learning,
            document_id=source_resource.document_id,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        await db.rollback()
        await _mark_source_registration_failed(
            db=db,
            actors=actors,
            revision_id=source_revision.revision_id,
            code="source_task_enqueue_failed",
            message="材料已安全保存，但处理任务暂未提交，可从材料详情重试。",
        )
        return _error(exc)
    except Exception:
        await db.rollback()
        await _mark_source_registration_failed(
            db=db,
            actors=actors,
            revision_id=source_revision.revision_id,
            code="source_task_enqueue_failed",
            message="材料已安全保存，但处理任务暂未提交，可从材料详情重试。",
        )
        raise
    return _success(
        {
            "resource": source_resource,
            "working_revision": source_revision,
            "task": task,
        },
        version=source_resource.version,
    )


@router.post(
    "/source-revisions/{revision_id}/commands/retry-processing",
    response_model=None,
)
async def retry_source_processing(
    revision_id: str,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    revision = await db.get(LearningSourceDocumentRevision, revision_id)
    if (
        revision is None
        or revision.organization_id != actors.learning.organization_id
        or revision.file_extension not in SUPPORTED_SOURCE_FILE_TYPES
    ):
        return _error(
            LearningGovernanceError(
                "[LEARNING_RESOURCE_NOT_FOUND]",
                "材料修订不存在或不可重试。",
                404,
            )
        )
    try:
        task = await LearningGovernanceService(
            db,
            task_runtime=SQLAlchemyTaskRuntime(db, registry=registry),
        ).enqueue_source_document_parse(
            actor=actors.learning,
            revision_id=revision.revision_id,
            file_hash=revision.file_hash,
            file_type=cast(SourceFileType, revision.file_extension),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success({"task": task, "processing_state": "pending"})


@router.get("/source-revisions/{revision_id}/original", response_model=None)
async def download_source_original(
    revision_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> Response:
    return await _serve_admin_source_asset(
        db=db,
        actors=actors,
        revision_id=revision_id,
        command="download_source_original",
    )


@router.get(
    "/source-revisions/{revision_id}/preview/pages/{page}",
    response_model=None,
)
async def view_source_preview_page(
    revision_id: str,
    page: Annotated[int, ApiPath(ge=1, le=10_000)],
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> Response:
    return await _serve_admin_source_asset(
        db=db,
        actors=actors,
        revision_id=revision_id,
        command="view_source_preview",
        page=page,
    )


@router.get("/source-revisions/{revision_id}/playback", response_model=None)
async def play_source_media(
    revision_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> Response:
    return await _serve_admin_source_asset(
        db=db,
        actors=actors,
        revision_id=revision_id,
        command="play_source_media",
    )


@router.put(
    "/resources/{resource_type}/{resource_id}/working-revision",
    response_model=None,
)
async def save_resource_working_revision(
    resource_type: LearningResourceType,
    resource_id: str,
    payload: SaveResourceRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if resource_type != payload.resource_type:
        return _error(
            LearningGovernanceError(
                "[LEARNING_RESOURCE_TYPE_MISMATCH]",
                "资源类型与请求内容不一致。",
                422,
            )
        )
    service = LearningGovernanceService(db)
    try:
        result, resource_version = await _save_resource_revision(
            service=service,
            actors=actors,
            resource_id=resource_id,
            payload=payload,
            expected_version=_version(if_match),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=resource_version)


@router.get(
    "/resources/{resource_type}/{resource_id}",
    response_model=None,
)
async def get_resource_detail(
    resource_type: LearningResourceType,
    resource_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningAdminQueryService(db).get_resource_detail(
            actor=actors.learning,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except LearningGovernanceError as exc:
        return _error(exc)
    return _success(result, version=result.resource.version)


@router.get(
    "/resources/{resource_type}/{resource_id}/references",
    response_model=None,
)
async def get_resource_references(
    resource_type: LearningResourceType,
    resource_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationAdminWorkspaceQueryService(
            db, actors=actors
        ).resource_references(
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(result)


@router.post(
    "/resources/{resource_type}/{resource_id}/commands/validate",
    response_model=None,
)
async def validate_resource_working_revision(
    resource_type: LearningResourceType,
    resource_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(db).validate_resource_working_revision(
            actor=actors.learning,
            resource_type=resource_type,
            resource_id=resource_id,
        )
    except LearningGovernanceError as exc:
        return _error(exc)
    return _success(result)


@router.post(
    "/resources/{resource_type}/{resource_id}/commands/archive",
    response_model=None,
)
async def archive_resource(
    resource_type: LearningResourceType,
    resource_id: str,
    payload: ArchiveResourceRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(db).archive_resource(
            actor=actors.learning,
            resource_type=resource_type,
            resource_id=resource_id,
            expected_version=_version(if_match),
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.get("/source-revisions/{revision_id}/anchors", response_model=None)
async def list_source_anchors(
    revision_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        _require_ui_capability(actors, "edit_content")
        rows = list(
            (
                await db.execute(
                    select(LearningSourceAnchor)
                    .where(
                        LearningSourceAnchor.organization_id
                        == actors.learning.organization_id
                    )
                    .where(LearningSourceAnchor.source_revision_id == revision_id)
                    .order_by(
                        LearningSourceAnchor.created_at.asc(),
                        LearningSourceAnchor.anchor_id.asc(),
                    )
                    .limit(200)
                )
            ).scalars()
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(
        {
            "items": [
                {
                    "anchor_id": row.anchor_id,
                    "anchor_key": row.anchor_key,
                    "label": row.label,
                    "locator_type": row.locator_type,
                    "locator": row.locator_json,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        }
    )


@router.post("/source-revisions/{revision_id}/anchors", response_model=None)
async def create_source_anchor(
    revision_id: str,
    payload: SourceAnchorDraft,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(db).create_source_anchor(
            actor=actors.learning,
            source_revision_id=revision_id,
            draft=payload,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.get("/question-generation-options", response_model=None)
async def get_question_generation_options(
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await FoundationQuestionGenerationPolicyService(db).list_options(
            actor=actors.learning
        )
    except LearningGovernanceError as exc:
        return _error(exc)
    return _success(result)


@router.get("/question-generation-batches", response_model=None)
async def list_question_generation_batches(
    limit: int = Query(default=30, ge=1, le=100),
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        _require_ui_capability(actors, "review_questions")
        rows = list(
            (
                await db.execute(
                    select(LearningQuestionGenerationBatch)
                    .where(
                        LearningQuestionGenerationBatch.organization_id
                        == actors.learning.organization_id
                    )
                    .order_by(
                        LearningQuestionGenerationBatch.created_at.desc(),
                        LearningQuestionGenerationBatch.batch_id.asc(),
                    )
                    .limit(limit)
                )
            ).scalars()
        )
    except NewcomerTrainingError as exc:
        return _error(exc)
    return _success(
        {
            "items": [
                {
                    "batch_id": row.batch_id,
                    "status": row.status,
                    "requested_count": row.requested_count,
                    "candidate_count": row.candidate_count,
                    "source_revision_id": row.source_revision_id,
                    "learning_unit_revision_id": row.learning_unit_revision_id,
                    "task_id": row.task_id,
                    "created_at": row.created_at,
                    "completed_at": row.completed_at,
                    "result_location": "/admin/newcomer-training/questions",
                    "recovery_available": row.status in {"failed", "cancelled"},
                }
                for row in rows
            ],
            "limit": limit,
        }
    )


@router.post("/question-generation-batches", response_model=None)
async def start_question_generation(
    payload: FoundationQuestionGenerationSelection,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        request = await FoundationQuestionGenerationPolicyService(db).build_request(
            actor=actors.learning,
            selection=payload,
        )
        result = await LearningGovernanceService(
            db,
            task_runtime=SQLAlchemyTaskRuntime(db, registry=registry),
        ).start_question_generation(
            actor=actors.learning,
            request=request,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.get("/question-candidates", response_model=None)
async def list_question_candidates(
    status: str | None = None,
    batch_id: str | None = None,
    source_revision_id: str | None = None,
    question_type: str | None = None,
    risk_level: Literal["normal", "high"] | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["-created_at", "risk_level", "status"] = "-created_at",
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningAdminQueryService(db).list_question_candidates(
            actor=actors.learning,
            status=status,
            batch_id=batch_id,
            source_revision_id=source_revision_id,
            question_type=question_type,
            risk_level=risk_level,
            search=search,
            page=page,
            page_size=page_size,
            sort=sort,
        )
    except LearningGovernanceError as exc:
        return _error(exc)
    return _success(result)


@router.post(
    "/question-candidates/bulk-review/preview",
    response_model=None,
)
async def preview_bulk_question_candidate_review(
    payload: CandidateBulkPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(
            db
        ).preview_bulk_question_candidate_review(
            actor=actors.learning,
            command=payload.command,
            candidate_ids=tuple(payload.candidate_ids),
            review_reason=payload.review_reason,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/question-candidates/bulk-review/commands/confirm",
    response_model=None,
)
async def confirm_bulk_question_candidate_review(
    payload: CandidateBulkConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(
            db
        ).confirm_bulk_question_candidate_review(
            actor=actors.learning,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/question-candidates/commands/bulk-review",
    response_model=None,
)
async def bulk_review_question_candidates(
    payload: BulkCandidateCommandRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await LearningGovernanceService(db).bulk_review_question_candidates(
            actor=actors.learning,
            command=payload.command,
            items=payload.items,
            review_reason=payload.review_reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/question-candidates/{candidate_id}/commands/{command}",
    response_model=None,
)
async def execute_candidate_command(
    candidate_id: str,
    command: Literal["begin-review", "approve", "reject", "supersede", "edit"],
    payload: CandidateCommandRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    service = LearningGovernanceService(db)
    expected_version = _version(if_match)
    try:
        if command == "begin-review":
            if payload.review_reason is not None or payload.content is not None:
                raise LearningGovernanceError(
                    "[QUESTION_CANDIDATE_COMMAND_INVALID]",
                    "开始审核命令不接受额外内容。",
                    422,
                )
            result: Any = await service.begin_question_candidate_review(
                actor=actors.learning,
                candidate_id=candidate_id,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
            )
        elif command == "edit":
            if payload.content is None or payload.review_reason is None:
                raise LearningGovernanceError(
                    "[QUESTION_CANDIDATE_COMMAND_INVALID]",
                    "修改候选题需要内容和修改依据。",
                    422,
                )
            result = await service.edit_question_candidate(
                actor=actors.learning,
                candidate_id=candidate_id,
                content=payload.content,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                review_reason=payload.review_reason,
            )
        elif command == "approve":
            if payload.review_reason is None or payload.content is not None:
                raise LearningGovernanceError(
                    "[QUESTION_CANDIDATE_COMMAND_INVALID]",
                    "批准候选题需要审核依据且不能携带修改内容。",
                    422,
                )
            result = await service.approve_question_candidate(
                actor=actors.learning,
                candidate_id=candidate_id,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                review_reason=payload.review_reason,
            )
        else:
            if payload.review_reason is None or payload.content is not None:
                raise LearningGovernanceError(
                    "[QUESTION_CANDIDATE_COMMAND_INVALID]",
                    "该审核命令需要审核依据且不能携带修改内容。",
                    422,
                )
            close = (
                service.reject_question_candidate
                if command == "reject"
                else service.supersede_question_candidate
            )
            result = await close(
                actor=actors.learning,
                candidate_id=candidate_id,
                expected_version=expected_version,
                idempotency_key=idempotency_key,
                review_reason=payload.review_reason,
            )
        await db.commit()
    except LearningGovernanceError as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.post(
    "/lesson-attempts/{attempt_id}/commands/invalidate",
    response_model=None,
)
async def invalidate_lesson_attempt(
    attempt_id: str,
    payload: InvalidateLessonRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        attempt, lesson = await FoundationLessonAdministrationService(db).invalidate(
            newcomer_actor=actors.newcomer,
            learning_actor=actors.learning,
            attempt_id=attempt_id,
            expected_attempt_version=_version(if_match),
            expected_detail_version=payload.expected_detail_version,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except (NewcomerTrainingError, LearningGovernanceError) as exc:
        return await _rollback_known(db, exc)
    except Exception:
        await db.rollback()
        raise
    return _success(
        {"attempt": attempt, "lesson": lesson},
        version=attempt.version,
    )


async def _mark_source_registration_failed(
    *,
    db: AsyncSession,
    actors: FoundationAdminActors,
    revision_id: str,
    code: str,
    message: str,
) -> None:
    try:
        await LearningGovernanceService(db).mark_source_revision_processing_failed(
            actor=actors.learning,
            revision_id=revision_id,
            failure_code=code,
            failure_message=message,
        )
        await db.commit()
    except Exception:
        await db.rollback()


async def _serve_admin_source_asset(
    *,
    db: AsyncSession,
    actors: FoundationAdminActors,
    revision_id: str,
    command: Literal[
        "download_source_original",
        "view_source_preview",
        "play_source_media",
    ],
    page: int | None = None,
) -> Response:
    service = LearningGovernanceService(db)
    try:
        revision = await service.authorize_source_revision_asset(
            actor=actors.learning,
            revision_id=revision_id,
            command=command,
        )
    except LearningGovernanceError as exc:
        await db.rollback()
        return _error(exc)
    if revision.file_extension not in SUPPORTED_SOURCE_FILE_TYPES:
        await db.rollback()
        return _error(
            LearningGovernanceError(
                "[SOURCE_ASSET_NOT_AVAILABLE]", "材料原文件暂不可用。", 404
            )
        )
    file_type = cast(SourceFileType, revision.file_extension)
    storage = get_document_storage_service()
    original = source_document_file_path(
        storage=storage,
        organization_id=actors.learning.organization_id,
        document_id=revision.document_id,
        file_hash=revision.file_hash,
        file_type=file_type,
    )
    path = original
    media_type = revision.trusted_mime_type or "application/octet-stream"
    filename = revision.original_filename or f"training-material.{file_type}"
    if command == "view_source_preview":
        pages = revision.preview_manifest_json.get("pages", [])
        if page is None or not any(
            isinstance(item, dict)
            and item.get("page") == page
            and item.get("status") == "ready"
            for item in (pages if isinstance(pages, list) else [])
        ):
            path = original.with_name("missing-preview")
        else:
            path = preview_root(original) / f"page-{page}.png"
        media_type = "image/png"
        filename = f"slide-{page or 0}.png"
    elif command == "play_source_media":
        if revision.content_kind not in {"demo_video", "example_audio"}:
            path = original.with_name("missing-playback")
        else:
            path = preview_root(original) / f"playback.{file_type}"
        filename = f"training-media.{file_type}"
    available = path.is_file()
    await service.audit_source_revision_asset_access(
        actor=actors.learning,
        revision=revision,
        command=command,
        result="succeeded" if available else "failed",
    )
    await db.commit()
    if not available:
        return _error(
            LearningGovernanceError(
                "[SOURCE_ASSET_NOT_AVAILABLE]",
                "材料文件或预览暂不可用，可返回详情重新处理。",
                404,
            )
        )
    return FileResponse(path, media_type=media_type, filename=filename)


async def _create_resource(
    *,
    service: LearningGovernanceService,
    actors: FoundationAdminActors,
    payload: CreateResourceRequest,
    idempotency_key: str,
) -> tuple[dict[str, object], int]:
    if isinstance(payload, CreateSourceResourceRequest):
        source_resource = await service.create_source_document(
            actor=actors.learning,
            stable_key=payload.stable_key,
            title=payload.title,
            idempotency_key=f"{idempotency_key}:resource",
        )
        source_revision = await service.save_source_revision(
            actor=actors.learning,
            document_id=source_resource.document_id,
            draft=payload.working_revision,
            expected_document_version=1,
            idempotency_key=f"{idempotency_key}:revision",
        )
        source_resource = await service.get_source_document(
            actor=actors.learning,
            document_id=source_resource.document_id,
        )
        return {
            "resource": source_resource,
            "working_revision": source_revision,
        }, source_resource.version
    if isinstance(payload, CreateLearningUnitResourceRequest):
        unit_resource = await service.create_learning_unit(
            actor=actors.learning,
            stable_key=payload.stable_key,
            title=payload.title,
            idempotency_key=f"{idempotency_key}:resource",
        )
        unit_revision = await service.save_learning_unit_revision(
            actor=actors.learning,
            unit_id=unit_resource.unit_id,
            draft=payload.working_revision,
            expected_unit_version=1,
            idempotency_key=f"{idempotency_key}:revision",
        )
        unit_resource = await service.get_learning_unit(
            actor=actors.learning,
            unit_id=unit_resource.unit_id,
        )
        return {
            "resource": unit_resource,
            "working_revision": unit_revision,
        }, unit_resource.version
    if isinstance(payload, CreateQuestionResourceRequest):
        question_revision = await service.save_manual_question_revision(
            actor=actors.learning,
            stable_key=payload.stable_key,
            content=payload.working_revision,
            expected_question_version=None,
            idempotency_key=idempotency_key,
            review_reason=payload.review_reason,
        )
        return {
            "resource": {
                "resource_id": question_revision.question_id,
                "stable_key": payload.stable_key,
                "version": 1,
            },
            "working_revision": question_revision,
        }, 1
    quiz_resource = await service.create_quiz(
        actor=actors.learning,
        stable_key=payload.stable_key,
        title=payload.title,
        idempotency_key=f"{idempotency_key}:resource",
    )
    quiz_revision = await service.save_quiz_revision(
        actor=actors.learning,
        quiz_id=quiz_resource.quiz_id,
        draft=payload.working_revision,
        expected_quiz_version=1,
        idempotency_key=f"{idempotency_key}:revision",
    )
    quiz_resource = await service.get_quiz(
        actor=actors.learning,
        quiz_id=quiz_resource.quiz_id,
    )
    return {
        "resource": quiz_resource,
        "working_revision": quiz_revision,
    }, quiz_resource.version


async def _save_resource_revision(
    *,
    service: LearningGovernanceService,
    actors: FoundationAdminActors,
    resource_id: str,
    payload: SaveResourceRequest,
    expected_version: int,
    idempotency_key: str,
) -> tuple[Any, int]:
    if isinstance(payload, SaveSourceResourceRequest):
        source_result = await service.save_source_revision(
            actor=actors.learning,
            document_id=resource_id,
            draft=payload.working_revision,
            expected_document_version=expected_version,
            idempotency_key=idempotency_key,
        )
        return source_result, expected_version + 1
    if isinstance(payload, SaveLearningUnitResourceRequest):
        unit_result = await service.save_learning_unit_revision(
            actor=actors.learning,
            unit_id=resource_id,
            draft=payload.working_revision,
            expected_unit_version=expected_version,
            idempotency_key=idempotency_key,
        )
        return unit_result, expected_version + 1
    if isinstance(payload, SaveQuestionResourceRequest):
        question = await service.get_question(
            actor=actors.learning,
            question_id=resource_id,
        )
        question_result = await service.save_manual_question_revision(
            actor=actors.learning,
            stable_key=question.stable_key,
            content=payload.working_revision,
            expected_question_version=expected_version,
            idempotency_key=idempotency_key,
            review_reason=payload.review_reason,
        )
        return question_result, expected_version + 1
    quiz_result = await service.save_quiz_revision(
        actor=actors.learning,
        quiz_id=resource_id,
        draft=payload.working_revision,
        expected_quiz_version=expected_version,
        idempotency_key=idempotency_key,
    )
    return quiz_result, expected_version + 1


@router.get("/coach-sessions/help-queue", response_model=None)
async def list_coach_human_help_queue(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await CoachGovernanceService(db).list_help_queue(
            actor=_coach_actor(actors),
            limit=limit,
        )
    except AICoachError as exc:
        return await _coach_failure(
            db,
            actors=actors,
            object_id="help-queue",
            command="view_coach_help_queue",
            exc=exc,
        )
    return _success(result)


@router.get("/coach-sessions/{session_id}/help-detail", response_model=None)
async def get_coach_human_help_detail(
    session_id: str,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await CoachGovernanceService(db).get_help_detail(
            actor=_coach_actor(actors),
            session_id=session_id,
        )
    except AICoachError as exc:
        return await _coach_failure(
            db,
            actors=actors,
            object_id=session_id,
            command="view_coach_help_detail",
            exc=exc,
        )
    return _success(result, version=result.version)


@router.post(
    "/coach-sessions/{session_id}/commands/intervene",
    response_model=None,
)
async def intervene_coach_session(
    session_id: str,
    payload: CoachInterventionRequest,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    try:
        result = await CoachGovernanceService(db).intervene(
            actor=_coach_actor(actors),
            session_id=session_id,
            payload=CoachHumanInterventionInput.model_validate(payload),
            expected_version=_version(if_match),
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except AICoachError as exc:
        return await _coach_failure(
            db,
            actors=actors,
            object_id=session_id,
            command="intervene_coach_session",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result, version=result.version)


@router.get("/audio-assessments/queue", response_model=None)
async def list_audio_assessment_queue(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).list_queue(
            actor=actors.newcomer,
            limit=limit,
        )
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id="queue",
            command="view_audio_queue",
            exc=exc,
        )
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/commands/repair",
    response_model=None,
)
async def repair_audio_pipeline(
    submission_id: str,
    payload: AudioRepairRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).repair_pipeline(
            actor=actors.newcomer,
            submission_id=submission_id,
            reason=payload.reason,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="repair_audio_pipeline",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/regrade/preview",
    response_model=None,
)
async def preview_audio_regrade(
    submission_id: str,
    payload: AudioRegradePreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).preview_regrade(
            actor=actors.newcomer,
            submission_id=submission_id,
            mode=payload.mode,
            target_scoring_scheme_revision_id=(
                payload.target_scoring_scheme_revision_id
            ),
            reason=payload.reason,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="preview_audio_regrade",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/regrade/confirm",
    response_model=None,
)
async def confirm_audio_regrade(
    submission_id: str,
    payload: AudioPreviewConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).confirm_regrade(
            actor=actors.newcomer,
            submission_id=submission_id,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="regrade_audio_submission",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/transcript-correction/preview",
    response_model=None,
)
async def preview_audio_transcript_correction(
    submission_id: str,
    payload: AudioTranscriptCorrectionPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(
            db,
            registry,
        ).preview_transcript_correction(
            actor=actors.newcomer,
            submission_id=submission_id,
            transcript=payload.transcript,
            reason=payload.reason,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="preview_audio_transcript_correction",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/transcript-correction/confirm",
    response_model=None,
)
async def confirm_audio_transcript_correction(
    submission_id: str,
    payload: AudioPreviewConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(
            db,
            registry,
        ).confirm_transcript_correction(
            actor=actors.newcomer,
            submission_id=submission_id,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="correct_audio_transcript",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/invalidation/preview",
    response_model=None,
)
async def preview_audio_invalidation(
    submission_id: str,
    payload: AudioInvalidationPreviewRequest,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).preview_invalidation(
            actor=actors.newcomer,
            submission_id=submission_id,
            reason=payload.reason,
        )
        await db.commit()
    except AudioAssessmentError as exc:
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="preview_audio_invalidation",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


@router.post(
    "/audio-submissions/{submission_id}/invalidation/confirm",
    response_model=None,
)
async def confirm_audio_invalidation(
    submission_id: str,
    payload: AudioPreviewConfirmRequest,
    idempotency_key: IdempotencyKey,
    actors: FoundationAdminActors = Depends(get_foundation_admin_actors),
    db: AsyncSession = Depends(get_db),
    registry: TaskRegistry = Depends(get_foundation_task_registry),
) -> JSONResponse:
    try:
        result = await _audio_governance(db, registry).confirm_invalidation(
            actor=actors.newcomer,
            submission_id=submission_id,
            preview_token=payload.preview_token,
            impact_hash=payload.impact_hash,
            idempotency_key=idempotency_key,
        )
        run = await db.get(AudioActivityRun, result.run_id)
        if run is not None:
            attempt = await db.get(NewcomerActivityAttempt, run.attempt_id)
            if attempt is not None and attempt.outcome_id is not None:
                await FoundationReadinessProjection(db).project_outcome(
                    outcome_id=attempt.outcome_id,
                    actor_id=actors.newcomer.actor_id,
                    trace_id=actors.newcomer.trace_id,
                )
        await db.commit()
    except (AudioAssessmentError, NewcomerTrainingError) as exc:
        if isinstance(exc, NewcomerTrainingError):
            await db.rollback()
            return _error(exc)
        return await _audio_failure(
            db,
            actors=actors,
            object_id=submission_id,
            command="invalidate_audio_run",
            exc=exc,
        )
    except Exception:
        await db.rollback()
        raise
    return _success(result)


def _audio_governance(
    db: AsyncSession,
    registry: TaskRegistry,
) -> AudioGovernanceService:
    return AudioGovernanceService(
        db,
        task_runtime=SQLAlchemyTaskRuntime(db, registry=registry),
        attempt_invalidator=FoundationAudioAttemptInvalidationAdapter(db),
    )


def _coach_actor(actors: FoundationAdminActors) -> CoachReviewActor:
    return CoachReviewActor(
        organization_id=actors.newcomer.organization_id,
        actor_id=actors.newcomer.actor_id,
        capabilities=actors.newcomer.capabilities,
        trace_id=actors.newcomer.trace_id,
    )


async def _coach_failure(
    db: AsyncSession,
    *,
    actors: FoundationAdminActors,
    object_id: str,
    command: str,
    exc: AICoachError,
) -> JSONResponse:
    await db.rollback()
    if exc.status_code in {403, 404}:
        row = CoachCommandAudit(
            audit_id=str(uuid.uuid4()),
            organization_id=actors.newcomer.organization_id,
            actor_id=actors.newcomer.actor_id,
            capability="newcomer.coach.review",
            object_type="coach_session",
            object_id=object_id,
            command=command,
            before_version=None,
            after_version=None,
            idempotency_key_hash=None,
            reason=None,
            trace_id=actors.newcomer.trace_id,
            result="denied",
            details_json={},
            occurred_at=datetime.now(UTC),
        )
        db.add(row)
        await db.commit()
    return _error(exc)


async def _audio_failure(
    db: AsyncSession,
    *,
    actors: FoundationAdminActors,
    object_id: str,
    command: str,
    exc: AudioAssessmentError,
) -> JSONResponse:
    await db.rollback()
    if exc.status_code in {403, 404}:
        row = AudioCommandAudit(
            audit_id=str(uuid.uuid4()),
            organization_id=actors.newcomer.organization_id,
            actor_id=actors.newcomer.actor_id,
            capability="newcomer.audio.review",
            object_type="audio_submission",
            object_id=object_id,
            command=command,
            before_version=None,
            after_version=None,
            idempotency_key_hash=None,
            expected_version=None,
            actual_version=None,
            reason=None,
            preview_token_hash=None,
            impact_hash=None,
            trace_id=actors.newcomer.trace_id,
            result="denied",
            details_json={},
            occurred_at=datetime.now(UTC),
        )
        db.add(row)
        await db.commit()
    return _error(exc)


def _require_ui_capability(
    actors: FoundationAdminActors, capability: str
) -> None:
    if capability not in actors.capabilities:
        raise NewcomerTrainingError(
            "[NEWCOMER_PERMISSION_DENIED]",
            "没有执行此操作的权限，请联系组织管理员。",
            403,
        )


async def _binding_resource_options(
    db: AsyncSession,
    *,
    organization_id: str,
    resource_type: BindingResourceType,
    status: str | None,
    search: str | None,
    limit: int,
) -> list[dict[str, object]]:
    pattern = f"%{search.strip()}%" if search and search.strip() else None
    items: list[dict[str, object]] = []
    if resource_type == "learning_unit":
        unit_statement = (
            select(LearningUnitRevision, LearningUnit)
            .join(LearningUnit, LearningUnit.unit_id == LearningUnitRevision.unit_id)
            .where(LearningUnitRevision.organization_id == organization_id)
            .where(
                or_(
                    LearningUnit.working_revision_id
                    == LearningUnitRevision.revision_id,
                    LearningUnit.published_revision_id
                    == LearningUnitRevision.revision_id,
                )
            )
            .order_by(
                LearningUnitRevision.created_at.desc(),
                LearningUnitRevision.revision_id.asc(),
            )
            .limit(limit)
        )
        if status:
            unit_statement = unit_statement.where(
                LearningUnitRevision.status == status
            )
        if pattern:
            unit_statement = unit_statement.where(
                or_(
                    LearningUnit.title.ilike(pattern),
                    LearningUnit.stable_key.ilike(pattern),
                )
            )
        unit_rows = (await db.execute(unit_statement)).all()
        items = [
            _binding_option(
                resource_type=resource_type,
                revision_id=revision.revision_id,
                stable_key=resource.stable_key,
                title=resource.title,
                status=revision.status,
                revision_no=revision.revision_no,
                created_at=revision.created_at,
                quick_create_supported=True,
            )
            for revision, resource in unit_rows
        ]
    elif resource_type == "quiz":
        quiz_statement = (
            select(LearningQuizRevision, LearningQuiz)
            .join(LearningQuiz, LearningQuiz.quiz_id == LearningQuizRevision.quiz_id)
            .where(LearningQuizRevision.organization_id == organization_id)
            .where(
                or_(
                    LearningQuiz.working_revision_id
                    == LearningQuizRevision.revision_id,
                    LearningQuiz.published_revision_id
                    == LearningQuizRevision.revision_id,
                )
            )
            .order_by(
                LearningQuizRevision.created_at.desc(),
                LearningQuizRevision.revision_id.asc(),
            )
            .limit(limit)
        )
        if status:
            quiz_statement = quiz_statement.where(
                LearningQuizRevision.status == status
            )
        if pattern:
            quiz_statement = quiz_statement.where(
                or_(
                    LearningQuiz.title.ilike(pattern),
                    LearningQuiz.stable_key.ilike(pattern),
                )
            )
        quiz_rows = (await db.execute(quiz_statement)).all()
        items = [
            _binding_option(
                resource_type=resource_type,
                revision_id=revision.revision_id,
                stable_key=resource.stable_key,
                title=resource.title,
                status=revision.status,
                revision_no=revision.revision_no,
                created_at=revision.created_at,
                quick_create_supported=True,
            )
            for revision, resource in quiz_rows
        ]
    elif resource_type in {"audio_material", "scoring_scheme", "scenario"}:
        audio_statement = (
            select(AudioActivityResourceRevision)
            .where(AudioActivityResourceRevision.organization_id == organization_id)
            .where(AudioActivityResourceRevision.resource_type == resource_type)
            .order_by(
                AudioActivityResourceRevision.created_at.desc(),
                AudioActivityResourceRevision.revision_id.asc(),
            )
            .limit(limit)
        )
        if status:
            audio_statement = audio_statement.where(
                AudioActivityResourceRevision.status == status
            )
        if pattern:
            audio_statement = audio_statement.where(
                or_(
                    AudioActivityResourceRevision.title.ilike(pattern),
                    AudioActivityResourceRevision.stable_key.ilike(pattern),
                )
            )
        audio_rows = list((await db.execute(audio_statement)).scalars())
        items = [
            _binding_option(
                resource_type=resource_type,
                revision_id=row.revision_id,
                stable_key=row.stable_key,
                title=row.title,
                status=row.status,
                revision_no=row.revision_no,
                created_at=row.created_at,
                quick_create_supported=(resource_type in {"audio_material", "scenario"}),
            )
            for row in audio_rows
        ]
    else:
        coach_statement = (
            select(CoachProfileRevision)
            .where(CoachProfileRevision.organization_id == organization_id)
            .order_by(
                CoachProfileRevision.created_at.desc(),
                CoachProfileRevision.revision_id.asc(),
            )
            .limit(limit)
        )
        if status:
            coach_statement = coach_statement.where(
                CoachProfileRevision.status == status
            )
        if pattern:
            coach_statement = coach_statement.where(
                CoachProfileRevision.stable_key.ilike(pattern)
            )
        coach_rows = list((await db.execute(coach_statement)).scalars())
        items = [
            _binding_option(
                resource_type=resource_type,
                revision_id=row.revision_id,
                stable_key=row.stable_key,
                title=str(row.snapshot_json.get("title") or "教练配置"),
                status=row.status,
                revision_no=row.revision_no,
                created_at=row.created_at,
                quick_create_supported=False,
            )
            for row in coach_rows
            if not pattern
            or pattern.strip("%").casefold()
            in str(row.snapshot_json.get("title") or "").casefold()
            or pattern.strip("%").casefold() in row.stable_key.casefold()
        ][:limit]
    return items


def _binding_option(
    *,
    resource_type: BindingResourceType,
    revision_id: str,
    stable_key: str,
    title: str,
    status: str,
    revision_no: int,
    created_at: datetime,
    quick_create_supported: bool,
) -> dict[str, object]:
    return {
        "resource_type": resource_type,
        "revision_id": revision_id,
        "stable_key": stable_key,
        "title": title,
        "status": status,
        "revision_no": revision_no,
        "created_at": created_at,
        "bindable": status in {"working", "published"}
        if resource_type in {"learning_unit", "quiz"}
        else status == "published",
        "needs_approval": status != "published",
        "quick_create_supported": quick_create_supported,
    }


__all__ = ["get_foundation_admin_actors", "router"]
