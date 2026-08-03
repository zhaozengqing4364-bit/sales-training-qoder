"""Application services for path, cohort, enrollment, and revision migration."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerCohort,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerEnrollmentImport,
    NewcomerEnrollmentMigration,
    NewcomerPath,
    NewcomerPathRevision,
)
from newcomer_training.ports import (
    PublishedActivityResourcePort,
    PublishedCompetencyMappingPort,
)
from task_runtime.outbox import DomainEvent, SQLAlchemyOutboxWriter


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CommandActor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    trace_id: str | None = Field(default=None, max_length=160)


class PathSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    path_id: str
    organization_id: str
    stable_key: str
    title: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    active_release_plan_id: str | None = None
    version: int


class PathRevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    revision_id: str
    path_id: str
    organization_id: str
    revision_no: int
    revision_label: str
    status: str
    content_hash: str
    version: int


class PathValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    field: str
    message: str


class PathValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path_id: str
    revision_id: str
    content_hash: str
    valid: bool
    issues: tuple[PathValidationIssue, ...]


class CohortSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    cohort_id: str
    organization_id: str
    stable_key: str
    name: str
    path_revision_id: str
    status: str
    version: int


class EnrollmentSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    enrollment_id: str
    organization_id: str
    learner_id: str
    cohort_id: str
    path_revision_id: str
    status: str
    version: int


class MigrationPreviewItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enrollment_id: str
    status: str
    from_revision_id: str | None = None
    target_revision_id: str
    expected_version: int | None = None
    reason: str | None = None


class MigrationPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    migration_id: str
    preview_token: str
    impact_hash: str
    target_revision_id: str
    eligible_count: int
    failure_count: int
    items: tuple[MigrationPreviewItem, ...]
    expires_at: datetime


class MigrationResultItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enrollment_id: str
    status: str
    from_revision_id: str | None = None
    target_revision_id: str
    before_version: int | None = None
    after_version: int | None = None
    reason: str | None = None


class MigrationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    migration_id: str
    target_revision_id: str
    migrated_count: int
    failure_count: int
    items: tuple[MigrationResultItem, ...]


class EnrollmentImportItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    learner_id: str
    learner_name: str | None = None
    status: Literal["eligible", "succeeded", "failed"]
    enrollment_id: str | None = None
    reason: str | None = None


class EnrollmentImportPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    import_id: str
    cohort_id: str
    preview_token: str
    impact_hash: str
    eligible_count: int
    failure_count: int
    items: tuple[EnrollmentImportItem, ...]
    expires_at: datetime


class EnrollmentImportResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    import_id: str
    cohort_id: str
    succeeded_count: int
    failure_count: int
    items: tuple[EnrollmentImportItem, ...]


class _MissingPublishedResources(PublishedActivityResourcePort):
    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None:
        del organization_id, activity_type, revision_id
        raise NewcomerTrainingError(
            "[NEWCOMER_ACTIVITY_RESOURCE_VALIDATOR_UNAVAILABLE]",
            "训练资源校验暂不可用，路径不能发布。",
            503,
        )


class _SnapshotCompetencyMappings(PublishedCompetencyMappingPort):
    """Compatibility fallback for isolated newcomer-training tests.

    Production composition injects the canonical mapping adapter. This fallback
    retains only the pre-existing non-empty snapshot check and owns no catalog.
    """

    async def require_valid(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
    ) -> None:
        del organization_id, path_revision_id, activity_id, activity_type
        if not competency_keys:
            raise NewcomerTrainingError(
                "[COMPETENCY_MAPPING_REQUIRED]",
                "每个训练活动必须映射至少一项基础能力。",
                422,
            )

    async def record_published(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
        actor_id: str,
    ) -> None:
        del (
            organization_id,
            path_revision_id,
            activity_id,
            activity_type,
            competency_keys,
            actor_id,
        )


class PathEnrollmentService:
    """The sole writer for path, cohort, enrollment, and revision migration."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        published_resources: PublishedActivityResourcePort | None = None,
        competency_mappings: PublishedCompetencyMappingPort | None = None,
    ) -> None:
        self._session = session
        self._published_resources = published_resources or _MissingPublishedResources()
        self._competency_mappings = (
            competency_mappings or _SnapshotCompetencyMappings()
        )
        self._outbox = SQLAlchemyOutboxWriter(session)

    async def create_path(
        self,
        *,
        actor: CommandActor,
        stable_key: str,
        title: str,
        idempotency_key: str,
    ) -> PathSummary:
        self._require(actor, "newcomer.path.manage")
        fingerprint = _canonical_hash(
            {
                "organization_id": actor.organization_id,
                "stable_key": stable_key,
                "title": title,
            }
        )
        existing = await self._session.scalar(
            select(NewcomerPath)
            .where(NewcomerPath.organization_id == actor.organization_id)
            .where(NewcomerPath.stable_key == stable_key)
            .limit(1)
        )
        if existing is not None:
            self._require_same_creation(
                existing.creation_idempotency_key_hash,
                existing.creation_fingerprint,
                idempotency_key,
                fingerprint,
            )
            return PathSummary.model_validate(existing)
        row = NewcomerPath(
            path_id=_id(),
            organization_id=actor.organization_id,
            stable_key=stable_key,
            title=title,
            status="draft",
            version=1,
            creation_idempotency_key_hash=_secret_hash(idempotency_key),
            creation_fingerprint=fingerprint,
            created_by=actor.actor_id,
            created_at=_now(),
            updated_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        return PathSummary.model_validate(row)

    async def get_path(
        self, *, actor: CommandActor, path_id: str
    ) -> PathSummary:
        self._require(actor, "newcomer.path.manage")
        row = await self._session.get(NewcomerPath, path_id)
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_NOT_FOUND]", "训练路径不存在或不可访问。", 404
            )
        return PathSummary.model_validate(row)

    async def save_working_revision(
        self,
        *,
        actor: CommandActor,
        path_id: str,
        draft: PathRevisionDraft,
        expected_path_version: int,
        idempotency_key: str,
    ) -> PathRevisionSummary:
        self._require(actor, "newcomer.path.manage")
        path = await self._load_path_for_update(actor, path_id)
        fingerprint = _canonical_hash(
            {
                "path_id": path_id,
                "expected_path_version": expected_path_version,
                "draft": draft.model_dump(mode="json"),
            }
        )
        replay = await self._session.scalar(
            select(NewcomerPathRevision)
            .where(NewcomerPathRevision.path_id == path_id)
            .where(
                NewcomerPathRevision.save_idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.save_fingerprint != fingerprint:
                self._idempotency_conflict()
            return PathRevisionSummary.model_validate(replay)
        self._require_version(path.version, expected_path_version, "训练路径")

        snapshot = draft.model_dump(mode="json")
        content_hash = _canonical_hash(snapshot)
        working = None
        if path.working_revision_id is not None:
            working = await self._session.get(
                NewcomerPathRevision, path.working_revision_id
            )
            if working is not None and working.status != "working":
                working = None
        now = _now()
        if working is None:
            revision_no = int(
                await self._session.scalar(
                    select(func.max(NewcomerPathRevision.revision_no)).where(
                        NewcomerPathRevision.path_id == path_id
                    )
                )
                or 0
            ) + 1
            working = NewcomerPathRevision(
                revision_id=_id(),
                path_id=path.path_id,
                organization_id=path.organization_id,
                revision_no=revision_no,
                revision_label=draft.revision_label,
                status="working",
                snapshot_json=snapshot,
                content_hash=content_hash,
                version=1,
                save_idempotency_key_hash=_secret_hash(idempotency_key),
                save_fingerprint=fingerprint,
                created_by=actor.actor_id,
                created_at=now,
            )
            self._session.add(working)
            path.working_revision_id = working.revision_id
        else:
            working.revision_label = draft.revision_label
            working.snapshot_json = snapshot
            working.content_hash = content_hash
            working.version += 1
            working.save_idempotency_key_hash = _secret_hash(idempotency_key)
            working.save_fingerprint = fingerprint
        path.title = draft.title
        path.version += 1
        path.updated_at = now
        await self._session.flush([path, working])
        await self._audit(
            actor=actor,
            capability="newcomer.path.manage",
            object_type="path_revision",
            object_id=working.revision_id,
            command="save_working_revision",
            before_version=working.version - 1 if working.version > 1 else None,
            after_version=working.version,
            idempotency_key=idempotency_key,
            expected_version=expected_path_version,
            actual_version=path.version,
            result="succeeded",
        )
        return PathRevisionSummary.model_validate(working)

    async def publish_revision(
        self,
        *,
        actor: CommandActor,
        revision_id: str,
        expected_revision_version: int,
        idempotency_key: str,
        reason: str | None = None,
    ) -> PathRevisionSummary:
        self._require(actor, "newcomer.path.publish")
        if reason is not None and not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_PUBLISH_REASON_REQUIRED]",
                "请填写发布依据。",
                422,
            )
        revision = await self._load_revision_for_update(actor, revision_id)
        fingerprint = _canonical_hash(
            {
                "revision_id": revision_id,
                "expected_revision_version": expected_revision_version,
                "reason": reason.strip() if reason is not None else None,
            }
        )
        if revision.status == "published":
            if (
                revision.publish_idempotency_key_hash == _secret_hash(idempotency_key)
                and revision.publish_fingerprint == fingerprint
            ):
                return PathRevisionSummary.model_validate(revision)
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_IMMUTABLE]",
                "已发布训练路径修订不可再次修改或发布。",
                409,
            )
        self._require_version(
            revision.version, expected_revision_version, "训练路径修订"
        )
        validation = await self._validate_revision_resources(
            actor=actor,
            revision=revision,
        )
        if not validation.valid:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_VALIDATION_FAILED]",
                "训练路径仍有未完成的发布检查。",
                422,
                details={
                    "issues": [
                        item.model_dump(mode="json") for item in validation.issues
                    ]
                },
            )
        path = await self._load_path_for_update(actor, revision.path_id)
        now = _now()
        before_version = revision.version
        revision.status = "published"
        revision.version += 1
        revision.publish_idempotency_key_hash = _secret_hash(idempotency_key)
        revision.publish_fingerprint = fingerprint
        revision.published_by = actor.actor_id
        revision.published_at = now
        path.published_revision_id = revision.revision_id
        if path.working_revision_id == revision.revision_id:
            path.working_revision_id = None
        path.status = "active"
        path.version += 1
        path.updated_at = now
        await self._session.flush([path, revision])
        draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        for stage in draft.stages:
            for activity in stage.activities:
                await self._competency_mappings.record_published(
                    organization_id=actor.organization_id,
                    path_revision_id=revision.revision_id,
                    activity_id=activity.activity_id,
                    activity_type=str(activity.type),
                    competency_keys=activity.competency_keys,
                    actor_id=actor.actor_id,
                )
        await self._audit(
            actor=actor,
            capability="newcomer.path.publish",
            object_type="path_revision",
            object_id=revision.revision_id,
            command="publish_path_revision",
            before_version=before_version,
            after_version=revision.version,
            idempotency_key=idempotency_key,
            expected_version=expected_revision_version,
            actual_version=revision.version,
            result="succeeded",
            reason=reason.strip() if reason is not None else None,
            details={"path_id": path.path_id},
        )
        return PathRevisionSummary.model_validate(revision)

    async def validate_working_revision(
        self,
        *,
        actor: CommandActor,
        path_id: str,
    ) -> PathValidationResult:
        self._require(actor, "newcomer.path.manage")
        path = await self._session.get(NewcomerPath, path_id)
        if path is None or path.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_NOT_FOUND]", "训练路径不存在或不可访问。", 404
            )
        if path.working_revision_id is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_WORKING_REVISION_NOT_FOUND]",
                "当前路径没有可校验的工作修订。",
                404,
            )
        revision = await self._load_revision(actor, path.working_revision_id)
        return await self._validate_revision_resources(
            actor=actor,
            revision=revision,
        )

    async def create_cohort(
        self,
        *,
        actor: CommandActor,
        stable_key: str,
        name: str,
        path_revision_id: str,
        idempotency_key: str,
    ) -> CohortSummary:
        self._require(actor, "newcomer.cohort.manage")
        revision = await self._load_revision(actor, path_revision_id)
        if revision.status != "published":
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_UNPUBLISHED]",
                "班次只能绑定已发布的训练路径修订。",
                422,
            )
        fingerprint = _canonical_hash(
            {
                "organization_id": actor.organization_id,
                "stable_key": stable_key,
                "name": name,
                "path_revision_id": path_revision_id,
            }
        )
        existing = await self._session.scalar(
            select(NewcomerCohort)
            .where(NewcomerCohort.organization_id == actor.organization_id)
            .where(NewcomerCohort.stable_key == stable_key)
            .limit(1)
        )
        if existing is not None:
            self._require_same_creation(
                existing.creation_idempotency_key_hash,
                existing.creation_fingerprint,
                idempotency_key,
                fingerprint,
            )
            return CohortSummary.model_validate(existing)
        row = NewcomerCohort(
            cohort_id=_id(),
            organization_id=actor.organization_id,
            stable_key=stable_key,
            name=name,
            path_revision_id=path_revision_id,
            status="active",
            version=1,
            creation_idempotency_key_hash=_secret_hash(idempotency_key),
            creation_fingerprint=fingerprint,
            created_by=actor.actor_id,
            created_at=_now(),
            updated_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        return CohortSummary.model_validate(row)

    async def enroll(
        self,
        *,
        actor: CommandActor,
        cohort_id: str,
        learner_id: str,
        idempotency_key: str,
    ) -> EnrollmentSummary:
        self._require(actor, "newcomer.enrollment.manage")
        cohort = await self._session.get(NewcomerCohort, cohort_id)
        if cohort is None or cohort.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_NOT_FOUND]", "班次不存在或不可访问。", 404
            )
        if cohort.status != "active":
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_INACTIVE]", "该班次当前不能分配学员。", 409
            )
        revision = await self._load_revision(actor, cohort.path_revision_id)
        if revision.status != "published":
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_UNPUBLISHED]",
                "班次绑定的路径修订尚未发布。",
                422,
            )
        learner = await self._session.get(User, learner_id)
        if learner is None or learner.is_active is False:
            raise NewcomerTrainingError(
                "[NEWCOMER_LEARNER_NOT_FOUND]", "学员不存在或不可分配。", 404
            )
        fingerprint = _canonical_hash(
            {
                "organization_id": actor.organization_id,
                "cohort_id": cohort_id,
                "learner_id": learner_id,
                "path_revision_id": cohort.path_revision_id,
            }
        )
        existing = await self._session.scalar(
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == actor.organization_id)
            .where(NewcomerEnrollment.cohort_id == cohort_id)
            .where(NewcomerEnrollment.learner_id == learner_id)
            .limit(1)
        )
        if existing is not None:
            self._require_same_creation(
                existing.creation_idempotency_key_hash,
                existing.creation_fingerprint,
                idempotency_key,
                fingerprint,
            )
            return EnrollmentSummary.model_validate(existing)
        active = await self._session.scalar(
            select(NewcomerEnrollment)
            .where(NewcomerEnrollment.organization_id == actor.organization_id)
            .where(NewcomerEnrollment.learner_id == learner_id)
            .where(NewcomerEnrollment.status == "active")
            .limit(1)
        )
        if active is not None:
            raise NewcomerTrainingError(
                "[NEWCOMER_LEARNER_ALREADY_ENROLLED]",
                "该学员已有进行中的新人训练。",
                409,
            )
        row = NewcomerEnrollment(
            enrollment_id=_id(),
            organization_id=actor.organization_id,
            learner_id=learner_id,
            cohort_id=cohort_id,
            path_revision_id=cohort.path_revision_id,
            status="active",
            version=1,
            creation_idempotency_key_hash=_secret_hash(idempotency_key),
            creation_fingerprint=fingerprint,
            assigned_by=actor.actor_id,
            assigned_at=_now(),
            updated_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        return EnrollmentSummary.model_validate(row)

    async def update_cohort_status(
        self,
        *,
        actor: CommandActor,
        cohort_id: str,
        target_status: Literal["active", "paused", "cancelled", "closed"],
        expected_version: int,
        reason: str,
        idempotency_key: str,
    ) -> CohortSummary:
        self._require(actor, "newcomer.cohort.manage")
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_REASON_REQUIRED]", "请填写状态调整原因。", 422
            )
        cohort = await self._session.scalar(
            select(NewcomerCohort)
            .where(NewcomerCohort.cohort_id == cohort_id)
            .with_for_update()
            .limit(1)
        )
        if cohort is None or cohort.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_NOT_FOUND]", "班次不存在或不可访问。", 404
            )
        fingerprint = _canonical_hash(
            {
                "cohort_id": cohort_id,
                "target_status": target_status,
                "expected_version": expected_version,
                "reason": reason.strip(),
            }
        )
        replay = await self._session.scalar(
            select(NewcomerCommandAudit)
            .where(NewcomerCommandAudit.organization_id == actor.organization_id)
            .where(NewcomerCommandAudit.object_type == "cohort")
            .where(NewcomerCommandAudit.object_id == cohort_id)
            .where(NewcomerCommandAudit.command == "update_cohort_status")
            .where(
                NewcomerCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.details_json.get("request_fingerprint") != fingerprint:
                self._idempotency_conflict()
            return CohortSummary.model_validate(cohort)
        self._require_version(cohort.version, expected_version, "训练班级")
        transitions = {
            "active": {"paused", "cancelled", "closed"},
            "paused": {"active", "cancelled", "closed"},
            "closed": {"active", "cancelled"},
            "cancelled": set(),
            "archived": set(),
        }
        if target_status == cohort.status:
            return CohortSummary.model_validate(cohort)
        if target_status not in transitions.get(cohort.status, set()):
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_STATE_CONFLICT]",
                "当前班级状态不能执行该调整。",
                409,
                details={"current_status": cohort.status},
            )
        before_version = cohort.version
        cohort.status = target_status
        cohort.version += 1
        cohort.updated_at = _now()
        await self._session.flush([cohort])
        await self._audit(
            actor=actor,
            capability="newcomer.cohort.manage",
            object_type="cohort",
            object_id=cohort.cohort_id,
            command="update_cohort_status",
            before_version=before_version,
            after_version=cohort.version,
            idempotency_key=idempotency_key,
            expected_version=expected_version,
            actual_version=cohort.version,
            result="succeeded",
            reason=reason.strip(),
            details={
                "target_status": target_status,
                "request_fingerprint": fingerprint,
                "active_enrollments_unchanged": True,
            },
        )
        return CohortSummary.model_validate(cohort)

    async def preview_enrollment_import(
        self,
        *,
        actor: CommandActor,
        cohort_id: str,
        learner_ids: list[str],
        reason: str,
    ) -> EnrollmentImportPreview:
        self._require(actor, "newcomer.enrollment.manage")
        if not learner_ids:
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_IMPORT_EMPTY]", "请至少选择一名学员。", 422
            )
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_IMPORT_REASON_REQUIRED]",
                "请填写批量分配原因。",
                422,
            )
        cohort = await self._session.get(NewcomerCohort, cohort_id)
        if (
            cohort is None
            or cohort.organization_id != actor.organization_id
            or cohort.status != "active"
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_COHORT_INACTIVE]", "该班次当前不能分配学员。", 409
            )
        unique_ids = tuple(dict.fromkeys(learner_ids))
        learners = list(
            (
                await self._session.execute(
                    select(User).where(User.user_id.in_(unique_ids))
                )
            ).scalars()
        )
        by_id = {str(row.user_id): row for row in learners}
        active_rows = list(
            (
                await self._session.execute(
                    select(NewcomerEnrollment)
                    .where(
                        NewcomerEnrollment.organization_id
                        == actor.organization_id
                    )
                    .where(NewcomerEnrollment.learner_id.in_(unique_ids))
                    .where(NewcomerEnrollment.status == "active")
                )
            ).scalars()
        )
        active_by_learner = {row.learner_id: row for row in active_rows}
        items: list[EnrollmentImportItem] = []
        for learner_id in unique_ids:
            learner = by_id.get(learner_id)
            active = active_by_learner.get(learner_id)
            if learner is None or learner.is_active is False:
                items.append(
                    EnrollmentImportItem(
                        learner_id=learner_id,
                        status="failed",
                        reason="learner_not_found_or_inactive",
                    )
                )
            elif active is not None:
                items.append(
                    EnrollmentImportItem(
                        learner_id=learner_id,
                        learner_name=learner.name,
                        status="failed",
                        enrollment_id=active.enrollment_id,
                        reason="active_enrollment_exists",
                    )
                )
            else:
                items.append(
                    EnrollmentImportItem(
                        learner_id=learner_id,
                        learner_name=learner.name,
                        status="eligible",
                    )
                )
        preview_payload = {
            "cohort_id": cohort_id,
            "path_revision_id": cohort.path_revision_id,
            "reason": reason.strip(),
            "items": [item.model_dump(mode="json") for item in items],
        }
        impact_hash = _canonical_hash(preview_payload)
        token = _id()
        now = _now()
        row = NewcomerEnrollmentImport(
            import_id=_id(),
            organization_id=actor.organization_id,
            cohort_id=cohort_id,
            requested_by=actor.actor_id,
            status="previewed",
            input_fingerprint=_canonical_hash(
                {"cohort_id": cohort_id, "learner_ids": unique_ids}
            ),
            preview_token_hash=_secret_hash(token),
            impact_hash=impact_hash,
            preview_json=preview_payload,
            expires_at=now + timedelta(minutes=30),
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush([row])
        eligible_count = sum(item.status == "eligible" for item in items)
        return EnrollmentImportPreview(
            import_id=row.import_id,
            cohort_id=cohort_id,
            preview_token=token,
            impact_hash=impact_hash,
            eligible_count=eligible_count,
            failure_count=len(items) - eligible_count,
            items=tuple(items),
            expires_at=row.expires_at,
        )

    async def confirm_enrollment_import(
        self,
        *,
        actor: CommandActor,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
    ) -> EnrollmentImportResult:
        self._require(actor, "newcomer.enrollment.manage")
        batch = await self._session.scalar(
            select(NewcomerEnrollmentImport)
            .where(
                NewcomerEnrollmentImport.preview_token_hash
                == _secret_hash(preview_token)
            )
            .with_for_update()
            .limit(1)
        )
        if batch is None or batch.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_IMPORT_NOT_FOUND]",
                "批量分配预览不存在、已过期或不可访问。",
                404,
            )
        fingerprint = _canonical_hash(
            {"import_id": batch.import_id, "impact_hash": impact_hash}
        )
        if batch.result_json is not None:
            if (
                batch.confirm_idempotency_key_hash
                != _secret_hash(idempotency_key)
                or batch.confirm_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return EnrollmentImportResult.model_validate(batch.result_json)
        if self._is_expired(batch.expires_at):
            batch.status = "expired"
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_IMPORT_EXPIRED]",
                "批量分配预览已过期，请重新预览。",
                409,
            )
        if batch.impact_hash != impact_hash:
            raise NewcomerTrainingError(
                "[NEWCOMER_ENROLLMENT_IMPORT_IMPACT_MISMATCH]",
                "批量分配影响已经变化，请重新预览。",
                409,
            )
        preview_items = tuple(
            EnrollmentImportItem.model_validate(item)
            for item in batch.preview_json.get("items", [])
        )
        results: list[EnrollmentImportItem] = []
        for item in preview_items:
            if item.status != "eligible":
                results.append(item)
                continue
            try:
                async with self._session.begin_nested():
                    enrollment = await self.enroll(
                        actor=actor,
                        cohort_id=batch.cohort_id,
                        learner_id=item.learner_id,
                        idempotency_key=(
                            f"{idempotency_key}:learner:{item.learner_id}"
                        ),
                    )
            except NewcomerTrainingError as exc:
                results.append(
                    EnrollmentImportItem(
                        learner_id=item.learner_id,
                        learner_name=item.learner_name,
                        status="failed",
                        reason=exc.code.strip("[]").lower(),
                    )
                )
            else:
                results.append(
                    EnrollmentImportItem(
                        learner_id=item.learner_id,
                        learner_name=item.learner_name,
                        status="succeeded",
                        enrollment_id=enrollment.enrollment_id,
                    )
                )
        succeeded_count = sum(item.status == "succeeded" for item in results)
        failure_count = len(results) - succeeded_count
        result = EnrollmentImportResult(
            import_id=batch.import_id,
            cohort_id=batch.cohort_id,
            succeeded_count=succeeded_count,
            failure_count=failure_count,
            items=tuple(results),
        )
        batch.status = (
            "succeeded"
            if failure_count == 0
            else "failed" if succeeded_count == 0 else "partial"
        )
        batch.result_json = result.model_dump(mode="json")
        batch.confirm_idempotency_key_hash = _secret_hash(idempotency_key)
        batch.confirm_fingerprint = fingerprint
        batch.confirmed_at = _now()
        await self._session.flush([batch])
        await self._audit(
            actor=actor,
            capability="newcomer.enrollment.manage",
            object_type="enrollment_import",
            object_id=batch.import_id,
            command="confirm_enrollment_import",
            before_version=None,
            after_version=None,
            idempotency_key=idempotency_key,
            expected_version=None,
            actual_version=None,
            result=batch.status,
            reason=str(batch.preview_json.get("reason") or ""),
            preview_token_hash=batch.preview_token_hash,
            impact_hash=batch.impact_hash,
            details={
                "cohort_id": batch.cohort_id,
                "succeeded_count": succeeded_count,
                "failure_count": failure_count,
            },
        )
        return result

    async def preview_revision_migration(
        self,
        *,
        actor: CommandActor,
        enrollment_ids: list[str],
        target_revision_id: str,
        reason: str,
    ) -> MigrationPreview:
        self._require(actor, "newcomer.enrollment.migrate")
        if not enrollment_ids:
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_EMPTY]", "请至少选择一名需要迁移的学员。", 422
            )
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_REASON_REQUIRED]", "请说明迁移原因。", 422
            )
        target = await self._load_revision(actor, target_revision_id)
        if target.status != "published":
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_UNPUBLISHED]",
                "只能迁移到已发布的训练路径修订。",
                422,
            )
        unique_ids = tuple(dict.fromkeys(enrollment_ids))
        rows = (
            await self._session.execute(
                select(NewcomerEnrollment)
                .where(NewcomerEnrollment.organization_id == actor.organization_id)
                .where(NewcomerEnrollment.enrollment_id.in_(unique_ids))
            )
        ).scalars()
        by_id = {row.enrollment_id: row for row in rows}
        items: list[MigrationPreviewItem] = []
        for enrollment_id in unique_ids:
            row = by_id.get(enrollment_id)
            if row is None:
                items.append(
                    MigrationPreviewItem(
                        enrollment_id=enrollment_id,
                        status="failed",
                        target_revision_id=target_revision_id,
                        reason="not_found_or_out_of_scope",
                    )
                )
            elif row.status != "active":
                items.append(
                    MigrationPreviewItem(
                        enrollment_id=enrollment_id,
                        status="failed",
                        from_revision_id=row.path_revision_id,
                        target_revision_id=target_revision_id,
                        expected_version=row.version,
                        reason="enrollment_not_active",
                    )
                )
            elif row.path_revision_id == target_revision_id:
                items.append(
                    MigrationPreviewItem(
                        enrollment_id=enrollment_id,
                        status="failed",
                        from_revision_id=row.path_revision_id,
                        target_revision_id=target_revision_id,
                        expected_version=row.version,
                        reason="already_on_target_revision",
                    )
                )
            else:
                items.append(
                    MigrationPreviewItem(
                        enrollment_id=enrollment_id,
                        status="eligible",
                        from_revision_id=row.path_revision_id,
                        target_revision_id=target_revision_id,
                        expected_version=row.version,
                    )
                )
        impact_payload = {
            "target_revision_id": target_revision_id,
            "items": [item.model_dump(mode="json") for item in items],
        }
        impact_hash = _canonical_hash(impact_payload)
        token = _id()
        now = _now()
        migration = NewcomerEnrollmentMigration(
            migration_id=_id(),
            organization_id=actor.organization_id,
            target_revision_id=target_revision_id,
            requested_by=actor.actor_id,
            reason=reason.strip(),
            status="previewed",
            preview_token_hash=_secret_hash(token),
            impact_hash=impact_hash,
            preview_json=impact_payload,
            expires_at=now + timedelta(minutes=30),
            created_at=now,
        )
        self._session.add(migration)
        await self._session.flush([migration])
        eligible_count = sum(item.status == "eligible" for item in items)
        return MigrationPreview(
            migration_id=migration.migration_id,
            preview_token=token,
            impact_hash=impact_hash,
            target_revision_id=target_revision_id,
            eligible_count=eligible_count,
            failure_count=len(items) - eligible_count,
            items=tuple(items),
            expires_at=migration.expires_at,
        )

    async def confirm_revision_migration(
        self,
        *,
        actor: CommandActor,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
        expected_enrollment_id: str | None = None,
        expected_enrollment_version: int | None = None,
        reason: str | None = None,
    ) -> MigrationResult:
        self._require(actor, "newcomer.enrollment.migrate")
        migration = await self._session.scalar(
            select(NewcomerEnrollmentMigration)
            .where(
                NewcomerEnrollmentMigration.preview_token_hash
                == _secret_hash(preview_token)
            )
            .with_for_update()
            .limit(1)
        )
        if migration is None or migration.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_PREVIEW_NOT_FOUND]",
                "迁移预览不存在、已过期或不可访问。",
                404,
            )
        fingerprint = _canonical_hash(
            {
                "migration_id": migration.migration_id,
                "impact_hash": impact_hash,
            }
        )
        if migration.result_json is not None:
            if (
                migration.confirm_idempotency_key_hash
                != _secret_hash(idempotency_key)
                or migration.confirm_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return MigrationResult.model_validate(migration.result_json)
        if self._is_expired(migration.expires_at):
            migration.status = "expired"
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_PREVIEW_EXPIRED]",
                "迁移预览已过期，请重新预览后确认。",
                409,
            )
        if migration.impact_hash != impact_hash:
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_IMPACT_MISMATCH]",
                "迁移影响已经变化，请重新预览后确认。",
                409,
            )
        preview_items = [
            MigrationPreviewItem.model_validate(item)
            for item in migration.preview_json.get("items", [])
        ]
        if reason is not None and migration.reason != reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_MIGRATION_CONFIRM_MISMATCH]",
                "迁移确认内容与预览不一致，请重新预览。",
                409,
            )
        if expected_enrollment_id is not None:
            if len(preview_items) != 1 or (
                preview_items[0].enrollment_id != expected_enrollment_id
            ):
                raise NewcomerTrainingError(
                    "[NEWCOMER_MIGRATION_CONFIRM_MISMATCH]",
                    "迁移确认对象与预览不一致，请重新预览。",
                    409,
                )
            if (
                expected_enrollment_version is not None
                and preview_items[0].expected_version
                != expected_enrollment_version
            ):
                raise NewcomerTrainingError(
                    "[NEWCOMER_VERSION_CONFLICT]",
                    "训练分配已更新，请刷新后重新预览。",
                    412,
                    details={
                        "expected_version": expected_enrollment_version,
                        "actual_version": preview_items[0].expected_version,
                    },
                )
        result_items: list[MigrationResultItem] = []
        for preview in preview_items:
            if preview.status != "eligible":
                result_items.append(
                    MigrationResultItem(
                        enrollment_id=preview.enrollment_id,
                        status="failed",
                        from_revision_id=preview.from_revision_id,
                        target_revision_id=preview.target_revision_id,
                        before_version=preview.expected_version,
                        reason=preview.reason,
                    )
                )
                continue
            row = await self._session.scalar(
                select(NewcomerEnrollment)
                .where(NewcomerEnrollment.enrollment_id == preview.enrollment_id)
                .where(
                    NewcomerEnrollment.organization_id == actor.organization_id
                )
                .with_for_update()
                .limit(1)
            )
            if (
                row is None
                or row.status != "active"
                or row.version != preview.expected_version
                or row.path_revision_id != preview.from_revision_id
            ):
                result_items.append(
                    MigrationResultItem(
                        enrollment_id=preview.enrollment_id,
                        status="failed",
                        from_revision_id=preview.from_revision_id,
                        target_revision_id=preview.target_revision_id,
                        before_version=preview.expected_version,
                        reason="enrollment_changed_since_preview",
                    )
                )
                continue
            before_version = row.version
            row.path_revision_id = migration.target_revision_id
            row.version += 1
            row.updated_at = _now()
            await self._session.flush([row])
            result_items.append(
                MigrationResultItem(
                    enrollment_id=row.enrollment_id,
                    status="migrated",
                    from_revision_id=preview.from_revision_id,
                    target_revision_id=migration.target_revision_id,
                    before_version=before_version,
                    after_version=row.version,
                )
            )
            await self._outbox.append(
                DomainEvent(
                    event_type="EnrollmentRevisionMigrated",
                    schema_version=1,
                    occurred_at=_now(),
                    organization_id=actor.organization_id,
                    actor_id=actor.actor_id,
                    trace_id=actor.trace_id,
                    correlation_id=migration.migration_id,
                    causation_id=None,
                    idempotency_key=f"{migration.migration_id}:{row.enrollment_id}",
                    aggregate_type="newcomer_enrollment",
                    aggregate_id=row.enrollment_id,
                    aggregate_version=row.version,
                    payload={
                        "from_revision_id": preview.from_revision_id,
                        "to_revision_id": migration.target_revision_id,
                    },
                )
            )
        migrated_count = sum(item.status == "migrated" for item in result_items)
        result = MigrationResult(
            migration_id=migration.migration_id,
            target_revision_id=migration.target_revision_id,
            migrated_count=migrated_count,
            failure_count=len(result_items) - migrated_count,
            items=tuple(result_items),
        )
        migration.result_json = result.model_dump(mode="json")
        migration.status = (
            "succeeded"
            if result.failure_count == 0
            else "partial"
            if migrated_count > 0
            else "failed"
        )
        migration.confirm_idempotency_key_hash = _secret_hash(idempotency_key)
        migration.confirm_fingerprint = fingerprint
        migration.confirmed_at = _now()
        await self._session.flush([migration])
        await self._audit(
            actor=actor,
            capability="newcomer.enrollment.migrate",
            object_type="enrollment_migration",
            object_id=migration.migration_id,
            command="migrate_enrollment_revision",
            before_version=None,
            after_version=None,
            idempotency_key=idempotency_key,
            expected_version=None,
            actual_version=None,
            result=migration.status,
            reason=migration.reason,
            preview_token_hash=migration.preview_token_hash,
            impact_hash=migration.impact_hash,
            details={
                "migrated_count": migrated_count,
                "failure_count": result.failure_count,
            },
        )
        return result

    async def _validate_revision_resources(
        self,
        *,
        actor: CommandActor,
        revision: NewcomerPathRevision,
    ) -> PathValidationResult:
        draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        issues: list[PathValidationIssue] = []
        for stage_index, stage in enumerate(draft.stages):
            for activity_index, activity in enumerate(stage.activities):
                field = f"stages.{stage_index}.activities.{activity_index}"
                if not activity.competency_keys:
                    issues.append(
                        PathValidationIssue(
                            code="competency_mapping_required",
                            field=f"{field}.competency_keys",
                            message="每个训练活动必须映射至少一项基础能力。",
                        )
                    )
                else:
                    try:
                        await self._competency_mappings.require_valid(
                            organization_id=actor.organization_id,
                            path_revision_id=revision.revision_id,
                            activity_id=activity.activity_id,
                            activity_type=str(activity.type),
                            competency_keys=activity.competency_keys,
                        )
                    except NewcomerTrainingError as exc:
                        issues.append(
                            PathValidationIssue(
                                code=exc.code.strip("[]").lower(),
                                field=f"{field}.competency_keys",
                                message=exc.message,
                            )
                        )
                for resource_field, revision_id in self._activity_resource_revisions(
                    activity
                ):
                    if not revision_id.strip():
                        issues.append(
                            PathValidationIssue(
                                code="activity_resource_required",
                                field=f"{field}.config.{resource_field}",
                                message="请选择此活动需要的已治理资源修订。",
                            )
                        )
                        continue
                    try:
                        await self._published_resources.require_published(
                            organization_id=actor.organization_id,
                            activity_type=str(activity.type),
                            revision_id=revision_id,
                        )
                    except NewcomerTrainingError as exc:
                        issues.append(
                            PathValidationIssue(
                                code=exc.code.strip("[]").lower(),
                                field=f"{field}.config.{resource_field}",
                                message=exc.message,
                            )
                        )
        return PathValidationResult(
            path_id=revision.path_id,
            revision_id=revision.revision_id,
            content_hash=revision.content_hash,
            valid=not issues,
            issues=tuple(issues),
        )

    async def _load_path_for_update(
        self, actor: CommandActor, path_id: str
    ) -> NewcomerPath:
        row = await self._session.scalar(
            select(NewcomerPath)
            .where(NewcomerPath.path_id == path_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_NOT_FOUND]", "训练路径不存在或不可访问。", 404
            )
        return row

    async def _load_revision(
        self, actor: CommandActor, revision_id: str
    ) -> NewcomerPathRevision:
        row = await self._session.get(NewcomerPathRevision, revision_id)
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_NOT_FOUND]",
                "训练路径修订不存在或不可访问。",
                404,
            )
        return row

    async def _load_revision_for_update(
        self, actor: CommandActor, revision_id: str
    ) -> NewcomerPathRevision:
        row = await self._session.scalar(
            select(NewcomerPathRevision)
            .where(NewcomerPathRevision.revision_id == revision_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_NOT_FOUND]",
                "训练路径修订不存在或不可访问。",
                404,
            )
        return row

    @staticmethod
    def _activity_resource_revisions(
        activity: Any,
    ) -> tuple[tuple[str, str], ...]:
        config = activity.config
        fields_by_type = {
            "lesson": ("learning_unit_revision_id",),
            "quiz": ("quiz_revision_id",),
            "audio_assessment": (
                "audio_material_revision_id",
                "scoring_scheme_revision_id",
            ),
            "ai_coach": ("coach_profile_revision_id",),
            "assignment": (
                "scenario_revision_id",
                "scoring_scheme_revision_id",
            ),
        }
        return tuple(
            (field, str(getattr(config, field)))
            for field in fields_by_type[str(activity.type)]
        )

    @staticmethod
    def _require(actor: CommandActor, capability: str) -> None:
        if capability not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有执行此操作的权限。", 403
            )

    @staticmethod
    def _require_version(actual: int, expected: int, label: str) -> None:
        if actual != expected:
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                f"{label}已被其他人更新，请刷新后重试。",
                412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _require_same_creation(
        stored_key_hash: str,
        stored_fingerprint: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> None:
        if (
            stored_key_hash != _secret_hash(idempotency_key)
            or stored_fingerprint != fingerprint
        ):
            PathEnrollmentService._idempotency_conflict()

    @staticmethod
    def _idempotency_conflict() -> None:
        raise NewcomerTrainingError(
            "[NEWCOMER_IDEMPOTENCY_CONFLICT]",
            "相同业务对象或幂等键对应了不同请求。",
            409,
        )

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= _now()

    async def _audit(
        self,
        *,
        actor: CommandActor,
        capability: str,
        object_type: str,
        object_id: str,
        command: str,
        before_version: int | None,
        after_version: int | None,
        idempotency_key: str | None,
        expected_version: int | None,
        actual_version: int | None,
        result: str,
        reason: str | None = None,
        preview_token_hash: str | None = None,
        impact_hash: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        row = NewcomerCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=capability,
            object_type=object_type,
            object_id=object_id,
            command=command,
            before_version=before_version,
            after_version=after_version,
            idempotency_key_hash=(
                _secret_hash(idempotency_key) if idempotency_key else None
            ),
            expected_version=expected_version,
            actual_version=actual_version,
            reason=reason,
            preview_token_hash=preview_token_hash,
            impact_hash=impact_hash,
            trace_id=actor.trace_id,
            result=result,
            details_json=details or {},
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])


__all__ = [
    "CohortSummary",
    "CommandActor",
    "EnrollmentImportItem",
    "EnrollmentImportPreview",
    "EnrollmentImportResult",
    "EnrollmentSummary",
    "MigrationPreview",
    "MigrationResult",
    "PathEnrollmentService",
    "PathRevisionSummary",
    "PathSummary",
]
