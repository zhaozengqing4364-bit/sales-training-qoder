"""Application services for immutable learning assets and human question review."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Never, TypeVar, cast

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    QuestionCandidateContent,
    QuestionGenerationRequest,
    QuizRevisionDraft,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningCommandAudit,
    LearningQuestion,
    LearningQuestionCandidate,
    LearningQuestionCandidateBulkReview,
    LearningQuestionGenerationBatch,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceAnchor,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)
from learning.question_generation import contains_sensitive_text, question_fingerprint
from learning.source_ingestion import (
    SOURCE_DOCUMENT_PARSE_TASK_TYPE,
    SourceFileType,
    source_revision_content_hash,
)
from task_runtime import TaskCommand, TaskReference, TaskRuntimePort

ScopedRowT = TypeVar("ScopedRowT")


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class SourceDocumentSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    document_id: str
    organization_id: str
    stable_key: str
    title: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    version: int


class SourceRevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    revision_id: str
    document_id: str
    organization_id: str
    revision_no: int
    revision_label: str
    status: str
    content_kind: str
    parse_status: str
    processing_state: str
    processing_stage: str | None
    original_filename: str | None
    trusted_mime_type: str | None
    file_size_bytes: int | None
    page_count: int | None
    duration_ms: int | None
    failure_message: str | None
    content_hash: str
    version: int


class SourceAnchorSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    anchor_id: str
    source_revision_id: str
    anchor_key: str
    label: str
    locator_type: str


class LearningUnitSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    unit_id: str
    organization_id: str
    stable_key: str
    title: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    version: int


class LearningUnitRevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    unit_id: str
    organization_id: str
    revision_no: int
    revision_label: str
    status: str
    content_hash: str
    version: int
    source_anchor_ids: tuple[str, ...]


class QuestionGenerationBatchSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    batch_id: str
    organization_id: str
    source_revision_id: str
    learning_unit_revision_id: str
    status: str
    requested_count: int
    task_id: str | None
    generation_input_hash: str
    version: int


class QuestionCandidateSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    batch_id: str
    organization_id: str
    status: str
    version: int
    content: QuestionCandidateContent
    gate_status: str
    gate_results: dict[str, Any]
    prompt_revision_id: str
    model_routing_revision_id: str
    generation_input_hash: str
    invocation_id: str
    reviewed_by: str | None
    review_reason: str | None
    approved_question_revision_id: str | None


class QuestionCandidateBulkItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    expected_version: int


class QuestionCandidateBulkItemResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    status: Literal["succeeded", "failed"]
    candidate_status: str | None = None
    candidate_version: int | None = None
    question_revision_id: str | None = None
    error_code: str | None = None
    message: str | None = None


class QuestionCandidateBulkResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    command: Literal["begin-review", "approve", "reject", "supersede"]
    status: Literal["succeeded", "partial", "failed"]
    succeeded_count: int
    failure_count: int
    items: tuple[QuestionCandidateBulkItemResult, ...]


class QuestionCandidateBulkPreviewItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    expected_version: int | None = None
    status: Literal["eligible", "failed"]
    reason: str | None = None


class QuestionCandidateBulkPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    review_id: str
    command: Literal["approve", "reject", "supersede"]
    preview_token: str
    impact_hash: str
    eligible_count: int
    failure_count: int
    items: tuple[QuestionCandidateBulkPreviewItem, ...]
    expires_at: datetime


class QuestionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    question_id: str
    organization_id: str
    stable_key: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    version: int


class QuestionRevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    question_id: str
    organization_id: str
    revision_no: int
    status: str
    version: int
    question_type: str
    source_anchor_ids: tuple[str, ...]
    competency_keys: tuple[str, ...]
    deterministic_fingerprint: str
    content_hash: str
    source_candidate_id: str | None
    reviewed_by: str | None


class QuizSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    quiz_id: str
    organization_id: str
    stable_key: str
    title: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    version: int


class QuizRevisionSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: str
    quiz_id: str
    organization_id: str
    revision_no: int
    revision_label: str
    status: str
    question_revision_ids: tuple[str, ...]
    content_hash: str
    version: int


class ResourceValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    field: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ResourceValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: Literal[
        "source_document", "learning_unit", "question", "quiz"
    ]
    resource_id: str
    revision_id: str | None
    valid: bool
    issues: tuple[ResourceValidationIssue, ...]


class ResourceArchiveResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: Literal[
        "source_document", "learning_unit", "question", "quiz"
    ]
    resource_id: str
    status: Literal["archived"] = "archived"
    version: int
    archived_revision_id: str


class ResourcePublishResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: Literal[
        "source_document", "learning_unit", "question", "quiz"
    ]
    resource_id: str
    resource_version: int
    revision_id: str
    revision_status: Literal["published"] = "published"
    revision_version: int


class LearningGovernanceService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        task_runtime: TaskRuntimePort | None = None,
    ) -> None:
        self._session = session
        self._task_runtime = task_runtime

    async def create_source_document(
        self,
        *,
        actor: LearningActor,
        stable_key: str,
        title: str,
        idempotency_key: str,
    ) -> SourceDocumentSummary:
        self._require(actor, "learning.source.manage")
        fingerprint = _canonical_hash(
            {"organization_id": actor.organization_id, "stable_key": stable_key, "title": title}
        )
        existing = await self._session.scalar(
            select(LearningSourceDocument)
            .where(LearningSourceDocument.organization_id == actor.organization_id)
            .where(LearningSourceDocument.stable_key == stable_key)
            .limit(1)
        )
        if existing is not None:
            self._require_creation_replay(existing, idempotency_key, fingerprint)
            return SourceDocumentSummary.model_validate(existing)
        row = LearningSourceDocument(
            document_id=_id(),
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
        return SourceDocumentSummary.model_validate(row)

    async def get_source_document(
        self, *, actor: LearningActor, document_id: str
    ) -> SourceDocumentSummary:
        self._require(actor, "learning.source.manage")
        row = await self._session.get(LearningSourceDocument, document_id)
        row = self._require_scope(row, actor.organization_id, "原始材料")
        return SourceDocumentSummary.model_validate(row)

    async def authorize_source_revision_asset(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        command: Literal[
            "download_source_original",
            "view_source_preview",
            "play_source_media",
        ],
    ) -> LearningSourceDocumentRevision:
        """Object-level gate for server-owned source delivery endpoints."""

        self._require(actor, "learning.source.manage")
        row = await self._session.get(LearningSourceDocumentRevision, revision_id)
        row = self._require_scope(row, actor.organization_id, "原始材料修订")
        if row.source_type != "file":
            raise LearningGovernanceError(
                "[SOURCE_ASSET_NOT_AVAILABLE]",
                "该材料没有可下载的受控文件。",
                404,
            )
        if command != "download_source_original" and row.processing_state not in {
            "ready",
            "partial",
        }:
            raise LearningGovernanceError(
                "[SOURCE_PREVIEW_NOT_READY]",
                "材料预览尚未准备完成，可刷新状态或重新处理。",
                409,
            )
        return row

    async def audit_source_revision_asset_access(
        self,
        *,
        actor: LearningActor,
        revision: LearningSourceDocumentRevision,
        command: Literal[
            "download_source_original",
            "view_source_preview",
            "play_source_media",
        ],
        result: Literal["succeeded", "failed"],
    ) -> None:
        self._require(actor, "learning.source.manage")
        if revision.organization_id != actor.organization_id:
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_NOT_FOUND]", "原始材料修订不存在或不可访问。", 404
            )
        await self._audit(
            actor=actor,
            capability="learning.source.manage",
            object_type="source_document_revision",
            object_id=revision.revision_id,
            command=command,
            before_version=revision.version,
            after_version=revision.version,
            idempotency_key=f"asset:{actor.actor_id}:{command}:{uuid.uuid4()}",
            reason=None,
            result=result,
            details={"document_id": revision.document_id},
        )

    async def mark_source_revision_processing_failed(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        failure_code: str,
        failure_message: str,
    ) -> SourceRevisionSummary:
        """Compensate storage/enqueue failures without deleting the working record."""

        self._require(actor, "learning.source.manage")
        row = await self._load_source_revision_for_update(actor, revision_id)
        if row.status != "working":
            raise LearningGovernanceError(
                "[SOURCE_DOCUMENT_REVISION_NOT_WORKING]",
                "只能更新尚未发布的材料处理状态。",
                409,
            )
        row.parse_status = "failed"
        row.processing_state = "failed"
        row.processing_stage = "registration"
        row.failure_code = failure_code[:120]
        row.failure_message = failure_message[:500]
        row.processed_at = _now()
        row.version += 1
        row.content_hash = source_revision_content_hash(row)
        document = await self._load_document_for_update(actor, row.document_id)
        document.version += 1
        document.updated_at = _now()
        await self._session.flush([row, document])
        return SourceRevisionSummary.model_validate(row)

    async def save_source_revision(
        self,
        *,
        actor: LearningActor,
        document_id: str,
        draft: SourceDocumentRevisionDraft,
        expected_document_version: int,
        idempotency_key: str,
    ) -> SourceRevisionSummary:
        self._require(actor, "learning.source.manage")
        document = await self._load_document_for_update(actor, document_id)
        fingerprint = _canonical_hash(
            {
                "document_id": document_id,
                "draft": draft.model_dump(mode="json"),
            }
        )
        replay = await self._session.scalar(
            select(LearningSourceDocumentRevision)
            .where(LearningSourceDocumentRevision.document_id == document_id)
            .where(
                LearningSourceDocumentRevision.save_idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            self._require_fingerprint(replay.save_fingerprint, fingerprint)
            return SourceRevisionSummary.model_validate(replay)
        self._require_version(document.version, expected_document_version, "原始材料")
        existing_working = None
        if document.working_revision_id:
            existing_working = await self._session.get(
                LearningSourceDocumentRevision, document.working_revision_id
            )
            if existing_working is not None and existing_working.status != "working":
                existing_working = None
        payload = draft.model_dump(mode="json")
        now = _now()
        if existing_working is None:
            revision_no = int(
                await self._session.scalar(
                    select(func.max(LearningSourceDocumentRevision.revision_no)).where(
                        LearningSourceDocumentRevision.document_id == document_id
                    )
                )
                or 0
            ) + 1
            row = LearningSourceDocumentRevision(
                revision_id=_id(),
                document_id=document_id,
                organization_id=actor.organization_id,
                revision_no=revision_no,
                revision_label=draft.revision_label,
                status="working",
                source_type=draft.source_type,
                content_kind=draft.content_kind,
                source_uri=draft.source_uri,
                file_hash=draft.file_hash,
                parser_version=draft.parser_version,
                parse_status=draft.parse_status,
                original_filename=draft.original_filename,
                trusted_mime_type=draft.trusted_mime_type,
                file_extension=draft.file_extension,
                file_size_bytes=draft.file_size_bytes,
                language=draft.language,
                page_count=draft.page_count,
                duration_ms=draft.duration_ms,
                preview_version=draft.preview_version,
                processing_state=draft.processing_state,
                processing_stage=draft.processing_stage,
                failure_code=draft.failure_code,
                failure_message=draft.failure_message,
                manual_content=draft.manual_content,
                preview_manifest_json={},
                content_hash=_canonical_hash(payload),
                version=1,
                save_idempotency_key_hash=_secret_hash(idempotency_key),
                save_fingerprint=fingerprint,
                created_by=actor.actor_id,
                created_at=now,
            )
            self._session.add(row)
            document.working_revision_id = row.revision_id
        else:
            row = existing_working
            row.revision_label = draft.revision_label
            row.source_type = draft.source_type
            row.content_kind = draft.content_kind
            row.source_uri = draft.source_uri
            row.file_hash = draft.file_hash
            row.parser_version = draft.parser_version
            row.parse_status = draft.parse_status
            row.original_filename = draft.original_filename
            row.trusted_mime_type = draft.trusted_mime_type
            row.file_extension = draft.file_extension
            row.file_size_bytes = draft.file_size_bytes
            row.language = draft.language
            row.page_count = draft.page_count
            row.duration_ms = draft.duration_ms
            row.preview_version = draft.preview_version
            row.processing_state = draft.processing_state
            row.processing_stage = draft.processing_stage
            row.failure_code = draft.failure_code
            row.failure_message = draft.failure_message
            row.manual_content = draft.manual_content
            row.preview_manifest_json = {}
            row.processed_at = None
            row.content_hash = _canonical_hash(payload)
            row.version += 1
            row.save_idempotency_key_hash = _secret_hash(idempotency_key)
            row.save_fingerprint = fingerprint
        document.version += 1
        document.updated_at = now
        await self._session.flush([document, row])
        return SourceRevisionSummary.model_validate(row)

    async def publish_source_revision(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        expected_revision_version: int,
        idempotency_key: str,
    ) -> SourceRevisionSummary:
        self._require(actor, "learning.source.manage")
        row = await self._load_source_revision_for_update(actor, revision_id)
        fingerprint = _canonical_hash(
            {"revision_id": revision_id, "expected_revision_version": expected_revision_version}
        )
        if row.status == "published":
            self._require_publish_replay(row, idempotency_key, fingerprint)
            return SourceRevisionSummary.model_validate(row)
        self._require_version(row.version, expected_revision_version, "原始材料修订")
        if row.parse_status != "ready" or row.processing_state != "ready":
            raise LearningGovernanceError(
                "[SOURCE_REVISION_NOT_READY]", "原始材料解析完成后才能发布。", 422
            )
        document = await self._load_document_for_update(actor, row.document_id)
        now = _now()
        before_version = row.version
        row.status = "published"
        row.version += 1
        row.publish_idempotency_key_hash = _secret_hash(idempotency_key)
        row.publish_fingerprint = fingerprint
        row.published_by = actor.actor_id
        row.published_at = now
        document.status = "active"
        document.published_revision_id = row.revision_id
        if document.working_revision_id == row.revision_id:
            document.working_revision_id = None
        document.version += 1
        document.updated_at = now
        await self._session.flush([document, row])
        await self._audit(
            actor=actor,
            capability="learning.source.manage",
            object_type="source_document_revision",
            object_id=row.revision_id,
            command="publish_source_revision",
            before_version=before_version,
            after_version=row.version,
            idempotency_key=idempotency_key,
            reason=None,
            result="succeeded",
            details={
                "document_id": document.document_id,
                "request_fingerprint": fingerprint,
            },
        )
        return SourceRevisionSummary.model_validate(row)

    async def enqueue_source_document_parse(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        file_hash: str,
        file_type: SourceFileType,
        idempotency_key: str,
    ) -> TaskReference:
        self._require(actor, "learning.source.manage")
        if self._task_runtime is None:
            raise LearningGovernanceError(
                "[LEARNING_TASK_RUNTIME_UNAVAILABLE]",
                "材料解析任务暂不可用，请稍后重试。",
                503,
            )
        revision = await self._load_source_revision(actor, revision_id)
        if revision.source_type != "file" or revision.file_hash != file_hash:
            raise LearningGovernanceError(
                "[SOURCE_DOCUMENT_PARSE_INPUT_INVALID]",
                "材料文件与待解析修订不一致。",
                422,
            )
        if revision.status != "working":
            raise LearningGovernanceError(
                "[SOURCE_DOCUMENT_REVISION_NOT_WORKING]",
                "只能为尚未发布的材料修订提交解析任务。",
                422,
            )
        return await self._task_runtime.enqueue(
            TaskCommand(
                task_type=SOURCE_DOCUMENT_PARSE_TASK_TYPE,
                schema_version=1,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                resource_type="source_document_revision",
                resource_id=revision.revision_id,
                idempotency_key=(
                    f"source-parse:{_secret_hash(idempotency_key)}"
                ),
                input_payload={
                    "revision_id": revision.revision_id,
                    "file_hash": file_hash,
                    "file_type": file_type,
                },
                correlation_id=revision.revision_id,
                causation_id=revision.document_id,
                trace_id=actor.trace_id,
                data_classification="internal",
            )
        )

    async def create_source_anchor(
        self,
        *,
        actor: LearningActor,
        source_revision_id: str,
        draft: SourceAnchorDraft,
        idempotency_key: str,
    ) -> SourceAnchorSummary:
        self._require(actor, "learning.source.manage")
        revision = await self._load_source_revision(actor, source_revision_id)
        if revision.parse_status != "ready":
            raise LearningGovernanceError(
                "[SOURCE_REVISION_NOT_READY]",
                "材料解析完成并核对后才能建立来源位置。",
                422,
            )
        if revision.status == "working":
            document = await self._session.get(
                LearningSourceDocument, revision.document_id
            )
            document = self._require_scope(
                document, actor.organization_id, "原始材料"
            )
            if document.working_revision_id != revision.revision_id:
                raise LearningGovernanceError(
                    "[SOURCE_REVISION_NOT_CURRENT]",
                    "该材料修订已不是当前工作版本，请刷新后重试。",
                    409,
                )
        elif revision.status != "published":
            raise LearningGovernanceError(
                "[SOURCE_REVISION_UNAVAILABLE]",
                "只能为当前工作修订或已发布材料建立来源位置。",
                422,
            )
        fingerprint = _canonical_hash(
            {"source_revision_id": source_revision_id, "draft": draft.model_dump(mode="json")}
        )
        existing = await self._session.scalar(
            select(LearningSourceAnchor)
            .where(LearningSourceAnchor.source_revision_id == source_revision_id)
            .where(LearningSourceAnchor.anchor_key == draft.anchor_key)
            .limit(1)
        )
        if existing is not None:
            if (
                existing.idempotency_key_hash != _secret_hash(idempotency_key)
                or existing.fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return SourceAnchorSummary.model_validate(existing)
        locator = draft.locator.model_dump(mode="json")
        row = LearningSourceAnchor(
            anchor_id=_id(),
            organization_id=actor.organization_id,
            source_revision_id=source_revision_id,
            anchor_key=draft.anchor_key,
            label=draft.label,
            locator_type=str(locator["type"]),
            locator_json=locator,
            excerpt_hash=draft.excerpt_hash,
            idempotency_key_hash=_secret_hash(idempotency_key),
            fingerprint=fingerprint,
            created_by=actor.actor_id,
            created_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        return SourceAnchorSummary.model_validate(row)

    async def create_learning_unit(
        self,
        *,
        actor: LearningActor,
        stable_key: str,
        title: str,
        idempotency_key: str,
    ) -> LearningUnitSummary:
        self._require(actor, "learning.content.manage")
        fingerprint = _canonical_hash(
            {"organization_id": actor.organization_id, "stable_key": stable_key, "title": title}
        )
        existing = await self._session.scalar(
            select(LearningUnit)
            .where(LearningUnit.organization_id == actor.organization_id)
            .where(LearningUnit.stable_key == stable_key)
            .limit(1)
        )
        if existing is not None:
            self._require_creation_replay(existing, idempotency_key, fingerprint)
            return LearningUnitSummary.model_validate(existing)
        row = LearningUnit(
            unit_id=_id(),
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
        return LearningUnitSummary.model_validate(row)

    async def get_learning_unit(
        self,
        *,
        actor: LearningActor,
        unit_id: str,
    ) -> LearningUnitSummary:
        self._require(actor, "learning.content.manage")
        row = await self._session.get(LearningUnit, unit_id)
        row = self._require_scope(row, actor.organization_id, "学习单元")
        return LearningUnitSummary.model_validate(row)

    async def save_learning_unit_revision(
        self,
        *,
        actor: LearningActor,
        unit_id: str,
        draft: LearningUnitRevisionDraft,
        expected_unit_version: int,
        idempotency_key: str,
    ) -> LearningUnitRevisionSummary:
        self._require(actor, "learning.content.manage")
        unit = await self._load_unit_for_update(actor, unit_id)
        fingerprint = _canonical_hash(
            {
                "unit_id": unit_id,
                "expected_unit_version": expected_unit_version,
                "draft": draft.model_dump(mode="json"),
            }
        )
        replay = await self._session.scalar(
            select(LearningUnitRevision)
            .where(LearningUnitRevision.unit_id == unit_id)
            .where(
                LearningUnitRevision.save_idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            self._require_fingerprint(replay.save_fingerprint, fingerprint)
            return self._unit_revision_summary(replay)
        self._require_version(unit.version, expected_unit_version, "学习单元")
        anchor_ids = draft.source_anchor_ids()
        if not anchor_ids:
            raise LearningGovernanceError(
                "[LEARNING_SOURCE_ANCHOR_REQUIRED]", "学习内容必须保留来源锚点。", 422
            )
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(LearningSourceAnchor.organization_id == actor.organization_id)
                .where(LearningSourceAnchor.anchor_id.in_(anchor_ids))
            )
        ).scalars().all()
        if {item.anchor_id for item in anchors} != set(anchor_ids):
            raise LearningGovernanceError(
                "[LEARNING_SOURCE_ANCHOR_INVALID]", "学习内容引用了不存在或越权的来源。", 422
            )
        anchors_by_id = {item.anchor_id: item for item in anchors}
        if any(
            anchors_by_id.get(anchor_id) is None
            or anchors_by_id[anchor_id].source_revision_id != source_revision_id
            for source_revision_id, anchor_id in draft.exact_source_references()
        ):
            raise LearningGovernanceError(
                "[LEARNING_EXACT_SOURCE_REFERENCE_INVALID]",
                "内容块的来源修订与定位不一致，请重新选择材料定位。",
                422,
            )
        exact_source_revision_ids = set(draft.source_revision_ids())
        referenced_source_revision_ids = {
            item.source_revision_id for item in anchors
        } | exact_source_revision_ids
        source_revisions = (
            await self._session.execute(
                select(LearningSourceDocumentRevision).where(
                    LearningSourceDocumentRevision.revision_id.in_(
                        referenced_source_revision_ids
                    )
                )
            )
        ).scalars().all()
        source_documents = (
            await self._session.execute(
                select(LearningSourceDocument).where(
                    LearningSourceDocument.document_id.in_(
                        {item.document_id for item in source_revisions}
                    )
                )
            )
        ).scalars().all()
        documents_by_id = {item.document_id: item for item in source_documents}
        invalid_source = any(
            item.organization_id != actor.organization_id
            or item.parse_status != "ready"
            or item.processing_state != "ready"
            or (
                item.status == "working"
                and (
                    (document := documents_by_id.get(item.document_id)) is None
                    or document.organization_id != actor.organization_id
                    or document.working_revision_id != item.revision_id
                )
            )
            or item.status not in {"working", "published"}
            for item in source_revisions
        )
        if len(source_revisions) != len(referenced_source_revision_ids) or invalid_source:
            raise LearningGovernanceError(
                "[LEARNING_SOURCE_REVISION_UNAVAILABLE]",
                "学习内容只能引用同组织内已解析的当前工作材料或已发布材料。",
                422,
            )
        sources_by_id = {item.revision_id: item for item in source_revisions}
        expected_content_kinds = {
            "rich_text": {"document", "script"},
            "source_excerpt": {"document", "script", "slide_deck"},
            "slide_deck": {"slide_deck"},
            "video": {"demo_video", "external_demo"},
            "audio_example": {"example_audio"},
            "attachment": {"attachment"},
        }
        if any(
            (
                expected := expected_content_kinds.get(block.type)
            ) is not None
            and (
                (source := sources_by_id.get(block.source_revision_id)) is None
                or source.content_kind not in expected
            )
            for block in draft.content_blocks
            if hasattr(block, "source_revision_id")
        ):
            raise LearningGovernanceError(
                "[LEARNING_CONTENT_BLOCK_KIND_MISMATCH]",
                "内容块类型与所选材料类型不匹配。",
                422,
            )
        working = None
        if unit.working_revision_id:
            working = await self._session.get(
                LearningUnitRevision, unit.working_revision_id
            )
            if working is not None and working.status != "working":
                working = None
        snapshot = draft.model_dump(mode="json")
        now = _now()
        if working is None:
            revision_no = int(
                await self._session.scalar(
                    select(func.max(LearningUnitRevision.revision_no)).where(
                        LearningUnitRevision.unit_id == unit_id
                    )
                )
                or 0
            ) + 1
            working = LearningUnitRevision(
                revision_id=_id(),
                unit_id=unit_id,
                organization_id=actor.organization_id,
                revision_no=revision_no,
                revision_label=draft.revision_label,
                status="working",
                snapshot_json=snapshot,
                source_anchor_ids_json=list(anchor_ids),
                content_hash=_canonical_hash(snapshot),
                version=1,
                save_idempotency_key_hash=_secret_hash(idempotency_key),
                save_fingerprint=fingerprint,
                created_by=actor.actor_id,
                created_at=now,
            )
            self._session.add(working)
            unit.working_revision_id = working.revision_id
        else:
            working.revision_label = draft.revision_label
            working.snapshot_json = snapshot
            working.source_anchor_ids_json = list(anchor_ids)
            working.content_hash = _canonical_hash(snapshot)
            working.version += 1
            working.save_idempotency_key_hash = _secret_hash(idempotency_key)
            working.save_fingerprint = fingerprint
        unit.title = draft.title
        unit.version += 1
        unit.updated_at = now
        await self._session.flush([unit, working])
        return self._unit_revision_summary(working)

    async def publish_learning_unit_revision(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        expected_revision_version: int,
        idempotency_key: str,
    ) -> LearningUnitRevisionSummary:
        self._require(actor, "learning.content.manage")
        row = await self._load_unit_revision_for_update(actor, revision_id)
        fingerprint = _canonical_hash(
            {"revision_id": revision_id, "expected_revision_version": expected_revision_version}
        )
        if row.status == "published":
            self._require_publish_replay(row, idempotency_key, fingerprint)
            return self._unit_revision_summary(row)
        self._require_version(row.version, expected_revision_version, "学习内容修订")
        unit = await self._load_unit_for_update(actor, row.unit_id)
        now = _now()
        before_version = row.version
        row.status = "published"
        row.version += 1
        row.publish_idempotency_key_hash = _secret_hash(idempotency_key)
        row.publish_fingerprint = fingerprint
        row.published_by = actor.actor_id
        row.published_at = now
        unit.status = "active"
        unit.published_revision_id = row.revision_id
        if unit.working_revision_id == row.revision_id:
            unit.working_revision_id = None
        unit.version += 1
        unit.updated_at = now
        await self._session.flush([unit, row])
        await self._audit(
            actor=actor,
            capability="learning.content.manage",
            object_type="learning_unit_revision",
            object_id=row.revision_id,
            command="publish_learning_unit_revision",
            before_version=before_version,
            after_version=row.version,
            idempotency_key=idempotency_key,
            reason=None,
            result="succeeded",
            details={
                "unit_id": unit.unit_id,
                "request_fingerprint": fingerprint,
            },
        )
        return self._unit_revision_summary(row)

    async def get_learning_unit_revision(
        self, *, actor: LearningActor, revision_id: str
    ) -> LearningUnitRevisionSummary:
        self._require(actor, "learning.content.manage")
        row = await self._session.get(LearningUnitRevision, revision_id)
        row = self._require_scope(row, actor.organization_id, "学习内容修订")
        return self._unit_revision_summary(row)

    async def update_published_learning_unit_revision(
        self, *, actor: LearningActor, revision_id: str, title: str
    ) -> None:
        del title
        self._require(actor, "learning.content.manage")
        row = await self._session.get(LearningUnitRevision, revision_id)
        row = self._require_scope(row, actor.organization_id, "学习内容修订")
        if row.status == "published":
            raise LearningGovernanceError(
                "[LEARNING_REVISION_IMMUTABLE]", "已发布学习内容不可原地修改，请创建新修订。", 409
            )
        raise LearningGovernanceError(
            "[LEARNING_DIRECT_REVISION_UPDATE_FORBIDDEN]", "请通过 working revision 命令保存内容。", 409
        )

    async def start_question_generation(
        self,
        *,
        actor: LearningActor,
        request: QuestionGenerationRequest,
        idempotency_key: str,
    ) -> QuestionGenerationBatchSummary:
        self._require(actor, "learning.question.generate")
        if self._task_runtime is None:
            raise LearningGovernanceError(
                "[LEARNING_TASK_RUNTIME_UNAVAILABLE]", "题目生成任务暂不可用，请稍后重试。", 503
            )
        source = await self._load_source_revision(actor, request.source_revision_id)
        unit = await self._session.get(
            LearningUnitRevision, request.learning_unit_revision_id
        )
        unit = self._require_scope(unit, actor.organization_id, "学习内容修订")
        if source.status != "published" or unit.status != "published":
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_SOURCE_UNPUBLISHED]", "只能从已发布来源和学习内容生成候选题。", 422
            )
        request_payload = request.model_dump(mode="json")
        fingerprint = _canonical_hash(
            {"organization_id": actor.organization_id, "request": request_payload}
        )
        existing = await self._session.scalar(
            select(LearningQuestionGenerationBatch)
            .where(LearningQuestionGenerationBatch.organization_id == actor.organization_id)
            .where(
                LearningQuestionGenerationBatch.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return QuestionGenerationBatchSummary.model_validate(existing)
        batch = LearningQuestionGenerationBatch(
            batch_id=_id(),
            organization_id=actor.organization_id,
            source_revision_id=request.source_revision_id,
            learning_unit_revision_id=request.learning_unit_revision_id,
            status="queued",
            requested_count=request.requested_count,
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            input_schema_version=request.input_schema_version,
            output_schema_version=request.output_schema_version,
            generation_input_hash=_canonical_hash(
                {
                    "source_revision_id": request.source_revision_id,
                    "learning_unit_revision_id": request.learning_unit_revision_id,
                    "requested_count": request.requested_count,
                }
            ),
            idempotency_key_hash=_secret_hash(idempotency_key),
            request_fingerprint=fingerprint,
            requested_by=actor.actor_id,
            version=1,
            created_at=_now(),
        )
        self._session.add(batch)
        await self._session.flush([batch])
        task = await self._task_runtime.enqueue(
            TaskCommand(
                task_type="learning.question_generation.generate",
                schema_version=1,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                resource_type="question_generation_batch",
                resource_id=batch.batch_id,
                idempotency_key=idempotency_key,
                input_payload={"batch_id": batch.batch_id},
                correlation_id=batch.batch_id,
                causation_id=request.learning_unit_revision_id,
                trace_id=actor.trace_id,
                data_classification="internal",
            )
        )
        batch.task_id = task.task_id
        await self._session.flush([batch])
        return QuestionGenerationBatchSummary.model_validate(batch)

    async def get_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
    ) -> QuestionCandidateSummary:
        self._require(actor, "learning.question.review")
        candidate = await self._session.get(LearningQuestionCandidate, candidate_id)
        candidate = self._require_scope(candidate, actor.organization_id, "候选题")
        return self._question_candidate_summary(candidate)

    async def begin_question_candidate_review(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        expected_version: int,
        idempotency_key: str,
    ) -> QuestionCandidateSummary:
        self._require(actor, "learning.question.review")
        candidate = await self._load_candidate_for_update(actor, candidate_id)
        fingerprint = _canonical_hash(
            {
                "candidate_id": candidate_id,
                "command": "begin_review",
                "expected_version": expected_version,
            }
        )
        replay = await self._candidate_command_replay(
            actor=actor,
            candidate_id=candidate_id,
            command="begin_question_candidate_review",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replay is not None:
            return replay
        self._require_version(candidate.version, expected_version, "候选题")
        if candidate.status != "generated":
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_STATE_CONFLICT]",
                "只有待审核候选题可以开始审核。",
                409,
            )
        before = candidate.version
        candidate.status = "in_review"
        candidate.version += 1
        candidate.reviewed_by = actor.actor_id
        candidate.updated_at = _now()
        await self._session.flush([candidate])
        summary = self._question_candidate_summary(candidate)
        await self._audit_candidate_command(
            actor=actor,
            candidate=candidate,
            command="begin_question_candidate_review",
            before_version=before,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            result_snapshot=summary.model_dump(mode="json"),
        )
        return summary

    async def edit_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        content: QuestionCandidateContent,
        expected_version: int,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionCandidateSummary:
        self._require(actor, "learning.question.review")
        if not review_reason.strip():
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]", "请填写修改依据。", 422
            )
        candidate = await self._load_candidate_for_update(actor, candidate_id)
        fingerprint = _canonical_hash(
            {
                "candidate_id": candidate_id,
                "command": "edit",
                "expected_version": expected_version,
                "content": content.model_dump(mode="json"),
                "review_reason": review_reason.strip(),
            }
        )
        replay = await self._candidate_command_replay(
            actor=actor,
            candidate_id=candidate_id,
            command="edit_question_candidate",
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replay is not None:
            return replay
        self._require_version(candidate.version, expected_version, "候选题")
        if candidate.status != "in_review":
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_STATE_CONFLICT]",
                "候选题进入审核后才能修改。",
                409,
            )
        batch = await self._session.get(
            LearningQuestionGenerationBatch, candidate.batch_id
        )
        batch = self._require_scope(batch, actor.organization_id, "题目生成批次")
        deterministic_fingerprint, gates, gate_status = (
            await self._evaluate_candidate_content(
                organization_id=actor.organization_id,
                source_revision_id=batch.source_revision_id,
                candidate_id=candidate.candidate_id,
                content=content,
            )
        )
        before = candidate.version
        candidate.question_type = content.question_type
        candidate.content_json = content.model_dump(mode="json")
        candidate.source_anchor_ids_json = list(content.source_anchor_ids)
        candidate.competency_keys_json = list(content.competency_keys)
        candidate.deterministic_fingerprint = deterministic_fingerprint
        candidate.gate_results_json = gates
        candidate.gate_status = gate_status
        candidate.version += 1
        candidate.reviewed_by = actor.actor_id
        candidate.review_reason = review_reason.strip()
        candidate.updated_at = _now()
        await self._session.flush([candidate])
        summary = self._question_candidate_summary(candidate)
        await self._audit_candidate_command(
            actor=actor,
            candidate=candidate,
            command="edit_question_candidate",
            before_version=before,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            result_snapshot=summary.model_dump(mode="json"),
            reason=review_reason.strip(),
        )
        return summary

    async def reject_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        expected_version: int,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionCandidateSummary:
        return await self._close_question_candidate(
            actor=actor,
            candidate_id=candidate_id,
            target_status="rejected",
            command="reject_question_candidate",
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            review_reason=review_reason,
        )

    async def supersede_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        expected_version: int,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionCandidateSummary:
        return await self._close_question_candidate(
            actor=actor,
            candidate_id=candidate_id,
            target_status="superseded",
            command="supersede_question_candidate",
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            review_reason=review_reason,
        )

    async def approve_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        expected_version: int,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionRevisionSummary:
        self._require(actor, "learning.question.review")
        if not review_reason.strip():
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]", "请填写审核依据。", 422
            )
        candidate = await self._session.scalar(
            select(LearningQuestionCandidate)
            .where(LearningQuestionCandidate.candidate_id == candidate_id)
            .with_for_update()
            .limit(1)
        )
        candidate = self._require_scope(candidate, actor.organization_id, "候选题")
        fingerprint = _canonical_hash(
            {
                "candidate_id": candidate_id,
                "expected_version": expected_version,
                "review_reason": review_reason.strip(),
            }
        )
        if candidate.status == "approved":
            if (
                candidate.review_idempotency_key_hash != _secret_hash(idempotency_key)
                or candidate.review_fingerprint != fingerprint
                or candidate.approved_question_revision_id is None
            ):
                self._idempotency_conflict()
            revision = await self._session.get(
                LearningQuestionRevision, candidate.approved_question_revision_id
            )
            assert revision is not None
            return self._question_revision_summary(revision)
        self._require_version(candidate.version, expected_version, "候选题")
        if candidate.status != "in_review":
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_STATE_CONFLICT]",
                "候选题进入审核后才能批准。",
                409,
            )
        if candidate.gate_status != "passed":
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_GATES_FAILED]", "候选题未通过确定性质量门禁，不能批准。", 422,
                details=candidate.gate_results_json,
            )
        if (
            candidate.question_type == "short_answer"
            and "learning.question.risk_review" not in actor.capabilities
        ):
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]",
                "简答题需要训练管理员复核。",
                403,
            )
        stable_key = f"generated-{candidate.deterministic_fingerprint[:32]}"
        question = LearningQuestion(
            question_id=_id(),
            organization_id=actor.organization_id,
            stable_key=stable_key,
            status="approved",
            version=1,
            created_by=actor.actor_id,
            created_at=_now(),
            updated_at=_now(),
        )
        revision = LearningQuestionRevision(
            revision_id=_id(),
            question_id=question.question_id,
            organization_id=actor.organization_id,
            revision_no=1,
            status="approved",
            question_type=candidate.question_type,
            content_json=candidate.content_json,
            source_anchor_ids_json=candidate.source_anchor_ids_json,
            competency_keys_json=candidate.competency_keys_json,
            deterministic_fingerprint=candidate.deterministic_fingerprint,
            content_hash=_canonical_hash(candidate.content_json),
            source_candidate_id=candidate.candidate_id,
            reviewed_by=actor.actor_id,
            review_reason=review_reason.strip(),
            created_by=actor.actor_id,
            created_at=_now(),
        )
        question.working_revision_id = revision.revision_id
        candidate.status = "approved"
        candidate.version += 1
        candidate.reviewed_by = actor.actor_id
        candidate.review_reason = review_reason.strip()
        candidate.review_idempotency_key_hash = _secret_hash(idempotency_key)
        candidate.review_fingerprint = fingerprint
        candidate.approved_question_revision_id = revision.revision_id
        candidate.updated_at = _now()
        self._session.add_all([question, revision])
        await self._session.flush([question, revision, candidate])
        await self._audit(
            actor=actor,
            capability="learning.question.review",
            object_type="question_candidate",
            object_id=candidate.candidate_id,
            command="approve_question_candidate",
            before_version=expected_version,
            after_version=candidate.version,
            idempotency_key=idempotency_key,
            reason=review_reason.strip(),
            result="succeeded",
            details={"question_revision_id": revision.revision_id},
        )
        return self._question_revision_summary(revision)

    async def preview_bulk_question_candidate_review(
        self,
        *,
        actor: LearningActor,
        command: Literal["approve", "reject", "supersede"],
        candidate_ids: tuple[str, ...],
        review_reason: str,
    ) -> QuestionCandidateBulkPreview:
        self._require(actor, "learning.question.review")
        if not candidate_ids:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_EMPTY]", "请至少选择一道候选题。", 422
            )
        if len(candidate_ids) != len(set(candidate_ids)):
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_DUPLICATE]",
                "批量审核不能重复选择同一道候选题。",
                422,
            )
        if not review_reason.strip():
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]", "请填写批量审核依据。", 422
            )
        rows = list(
            (
                await self._session.execute(
                    select(LearningQuestionCandidate)
                    .where(
                        LearningQuestionCandidate.organization_id
                        == actor.organization_id
                    )
                    .where(
                        LearningQuestionCandidate.candidate_id.in_(candidate_ids)
                    )
                )
            ).scalars()
        )
        by_id = {row.candidate_id: row for row in rows}
        items: list[QuestionCandidateBulkPreviewItem] = []
        for candidate_id in candidate_ids:
            row = by_id.get(candidate_id)
            reason: str | None = None
            if row is None:
                reason = "not_found_or_out_of_scope"
            elif command == "approve" and row.status != "in_review":
                reason = "candidate_not_in_review"
            elif command == "approve" and row.gate_status != "passed":
                reason = "quality_gates_failed"
            elif (
                command == "approve"
                and row.question_type == "short_answer"
                and "learning.question.risk_review" not in actor.capabilities
            ):
                reason = "risk_review_permission_required"
            elif command in {"reject", "supersede"} and row.status not in {
                "generated",
                "in_review",
                "rejected",
            }:
                reason = "candidate_state_conflict"
            elif command == "reject" and row.status == "rejected":
                reason = "already_rejected"
            items.append(
                QuestionCandidateBulkPreviewItem(
                    candidate_id=candidate_id,
                    expected_version=row.version if row is not None else None,
                    status="failed" if reason else "eligible",
                    reason=reason,
                )
            )
        preview_payload = {
            "command": command,
            "review_reason": review_reason.strip(),
            "items": [item.model_dump(mode="json") for item in items],
        }
        impact_hash = _canonical_hash(preview_payload)
        token = _id()
        now = _now()
        batch = LearningQuestionCandidateBulkReview(
            review_id=_id(),
            organization_id=actor.organization_id,
            command=command,
            review_reason=review_reason.strip(),
            status="previewed",
            preview_token_hash=_secret_hash(token),
            impact_hash=impact_hash,
            preview_json=preview_payload,
            expires_at=now + timedelta(minutes=30),
            requested_by=actor.actor_id,
            created_at=now,
        )
        self._session.add(batch)
        await self._session.flush([batch])
        eligible_count = sum(item.status == "eligible" for item in items)
        return QuestionCandidateBulkPreview(
            review_id=batch.review_id,
            command=command,
            preview_token=token,
            impact_hash=impact_hash,
            eligible_count=eligible_count,
            failure_count=len(items) - eligible_count,
            items=tuple(items),
            expires_at=batch.expires_at,
        )

    async def confirm_bulk_question_candidate_review(
        self,
        *,
        actor: LearningActor,
        preview_token: str,
        impact_hash: str,
        idempotency_key: str,
    ) -> QuestionCandidateBulkResult:
        self._require(actor, "learning.question.review")
        batch = await self._session.scalar(
            select(LearningQuestionCandidateBulkReview)
            .where(
                LearningQuestionCandidateBulkReview.preview_token_hash
                == _secret_hash(preview_token)
            )
            .with_for_update()
            .limit(1)
        )
        if batch is None or batch.organization_id != actor.organization_id:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_PREVIEW_NOT_FOUND]",
                "批量审核预览不存在、已过期或不可访问。",
                404,
            )
        fingerprint = _canonical_hash(
            {"review_id": batch.review_id, "impact_hash": impact_hash}
        )
        if batch.result_json is not None:
            if (
                batch.confirm_idempotency_key_hash
                != _secret_hash(idempotency_key)
                or batch.confirm_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return QuestionCandidateBulkResult.model_validate(batch.result_json)
        expires_at = batch.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= _now():
            batch.status = "expired"
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_PREVIEW_EXPIRED]",
                "批量审核预览已过期，请重新预览。",
                409,
            )
        if batch.impact_hash != impact_hash:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_IMPACT_MISMATCH]",
                "候选题状态已经变化，请重新预览。",
                409,
            )
        preview_items = tuple(
            QuestionCandidateBulkPreviewItem.model_validate(item)
            for item in batch.preview_json.get("items", [])
        )
        eligible = tuple(
            QuestionCandidateBulkItem(
                candidate_id=item.candidate_id,
                expected_version=item.expected_version or 1,
            )
            for item in preview_items
            if item.status == "eligible"
        )
        if eligible:
            applied = await self.bulk_review_question_candidates(
                actor=actor,
                command=cast(
                    Literal["begin-review", "approve", "reject", "supersede"],
                    batch.command,
                ),
                items=eligible,
                review_reason=batch.review_reason,
                idempotency_key=f"{idempotency_key}:apply",
            )
            results = list(applied.items)
        else:
            results = []
        results.extend(
            QuestionCandidateBulkItemResult(
                candidate_id=item.candidate_id,
                status="failed",
                error_code="[QUESTION_CANDIDATE_PREVIEW_FAILED]",
                message=item.reason,
            )
            for item in preview_items
            if item.status == "failed"
        )
        succeeded_count = sum(item.status == "succeeded" for item in results)
        failure_count = len(results) - succeeded_count
        status: Literal["succeeded", "partial", "failed"] = (
            "succeeded"
            if failure_count == 0
            else "partial" if succeeded_count else "failed"
        )
        result = QuestionCandidateBulkResult(
            command=cast(
                Literal["begin-review", "approve", "reject", "supersede"],
                batch.command,
            ),
            status=status,
            succeeded_count=succeeded_count,
            failure_count=failure_count,
            items=tuple(results),
        )
        batch.status = status
        batch.result_json = result.model_dump(mode="json")
        batch.confirm_idempotency_key_hash = _secret_hash(idempotency_key)
        batch.confirm_fingerprint = fingerprint
        batch.confirmed_at = _now()
        await self._session.flush([batch])
        await self._audit(
            actor=actor,
            capability="learning.question.review",
            object_type="question_candidate_bulk_preview",
            object_id=batch.review_id,
            command="confirm_bulk_question_candidate_review",
            before_version=None,
            after_version=None,
            idempotency_key=idempotency_key,
            reason=batch.review_reason,
            result=status,
            details={
                "impact_hash": batch.impact_hash,
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def bulk_review_question_candidates(
        self,
        *,
        actor: LearningActor,
        command: Literal["begin-review", "approve", "reject", "supersede"],
        items: tuple[QuestionCandidateBulkItem, ...],
        review_reason: str | None,
        idempotency_key: str,
    ) -> QuestionCandidateBulkResult:
        """Apply one governed review command with per-candidate failure isolation."""

        self._require(actor, "learning.question.review")
        if not items:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_EMPTY]",
                "请至少选择一道候选题。",
                422,
            )
        candidate_ids = [item.candidate_id for item in items]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_BULK_DUPLICATE]",
                "批量审核不能重复选择同一道候选题。",
                422,
            )
        normalized_reason = review_reason.strip() if review_reason is not None else None
        if command != "begin-review" and not normalized_reason:
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]",
                "请填写批量审核依据。",
                422,
            )
        if command == "begin-review" and normalized_reason:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_COMMAND_INVALID]",
                "开始审核不需要填写审核结论。",
                422,
            )
        fingerprint = _canonical_hash(
            {
                "command": command,
                "items": [item.model_dump(mode="json") for item in items],
                "review_reason": normalized_reason,
            }
        )
        replay = await self._session.scalar(
            select(LearningCommandAudit)
            .where(LearningCommandAudit.organization_id == actor.organization_id)
            .where(LearningCommandAudit.object_type == "question_candidate_bulk")
            .where(LearningCommandAudit.command == "bulk_review_question_candidates")
            .where(
                LearningCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.details_json.get("request_fingerprint") != fingerprint:
                self._idempotency_conflict()
            return QuestionCandidateBulkResult.model_validate(
                replay.details_json["result"]
            )

        results: list[QuestionCandidateBulkItemResult] = []
        for item in items:
            item_key = f"{idempotency_key}:{command}:{item.candidate_id}"
            try:
                async with self._session.begin_nested():
                    if command == "begin-review":
                        candidate = await self.begin_question_candidate_review(
                            actor=actor,
                            candidate_id=item.candidate_id,
                            expected_version=item.expected_version,
                            idempotency_key=item_key,
                        )
                        revision_id = None
                    elif command == "approve":
                        revision = await self.approve_question_candidate(
                            actor=actor,
                            candidate_id=item.candidate_id,
                            expected_version=item.expected_version,
                            idempotency_key=item_key,
                            review_reason=normalized_reason or "",
                        )
                        candidate = await self.get_question_candidate(
                            actor=actor,
                            candidate_id=item.candidate_id,
                        )
                        revision_id = revision.revision_id
                    else:
                        close = (
                            self.reject_question_candidate
                            if command == "reject"
                            else self.supersede_question_candidate
                        )
                        candidate = await close(
                            actor=actor,
                            candidate_id=item.candidate_id,
                            expected_version=item.expected_version,
                            idempotency_key=item_key,
                            review_reason=normalized_reason or "",
                        )
                        revision_id = None
                    results.append(
                        QuestionCandidateBulkItemResult(
                            candidate_id=item.candidate_id,
                            status="succeeded",
                            candidate_status=candidate.status,
                            candidate_version=candidate.version,
                            question_revision_id=revision_id,
                        )
                    )
            except LearningGovernanceError as exc:
                results.append(
                    QuestionCandidateBulkItemResult(
                        candidate_id=item.candidate_id,
                        status="failed",
                        error_code=exc.code,
                        message=exc.message,
                    )
                )
        succeeded_count = sum(item.status == "succeeded" for item in results)
        failure_count = len(results) - succeeded_count
        status: Literal["succeeded", "partial", "failed"] = (
            "succeeded"
            if failure_count == 0
            else "partial"
            if succeeded_count > 0
            else "failed"
        )
        result = QuestionCandidateBulkResult(
            command=command,
            status=status,
            succeeded_count=succeeded_count,
            failure_count=failure_count,
            items=tuple(results),
        )
        await self._audit(
            actor=actor,
            capability="learning.question.review",
            object_type="question_candidate_bulk",
            object_id=fingerprint[:32],
            command="bulk_review_question_candidates",
            before_version=None,
            after_version=None,
            idempotency_key=idempotency_key,
            reason=normalized_reason,
            result=status,
            details={
                "request_fingerprint": fingerprint,
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def save_manual_question_revision(
        self,
        *,
        actor: LearningActor,
        stable_key: str,
        content: QuestionCandidateContent,
        expected_question_version: int | None,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionRevisionSummary:
        """Create a human-authored immutable revision without inventing AI lineage."""

        self._require(actor, "learning.question.manage")
        if not review_reason.strip():
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]", "请填写人工审核依据。", 422
            )
        if (
            content.question_type == "short_answer"
            and "learning.question.risk_review" not in actor.capabilities
        ):
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]",
                "简答题需要训练管理员复核。",
                403,
            )
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(LearningSourceAnchor.organization_id == actor.organization_id)
                .where(LearningSourceAnchor.anchor_id.in_(content.source_anchor_ids))
            )
        ).scalars().all()
        if {row.anchor_id for row in anchors} != set(content.source_anchor_ids):
            raise LearningGovernanceError(
                "[QUESTION_SOURCE_ANCHOR_INVALID]",
                "题目必须引用同组织内的有效来源锚点。",
                422,
            )
        request_fingerprint = _canonical_hash(
            {
                "stable_key": stable_key,
                "content": content.model_dump(mode="json"),
                "expected_question_version": expected_question_version,
                "review_reason": review_reason.strip(),
            }
        )
        replay_audit = await self._session.scalar(
            select(LearningCommandAudit)
            .where(LearningCommandAudit.organization_id == actor.organization_id)
            .where(LearningCommandAudit.object_type == "question")
            .where(LearningCommandAudit.object_id == stable_key)
            .where(LearningCommandAudit.command == "save_manual_question_revision")
            .where(
                LearningCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay_audit is not None:
            if (
                replay_audit.details_json.get("request_fingerprint")
                != request_fingerprint
            ):
                self._idempotency_conflict()
            revision_id = str(replay_audit.details_json["question_revision_id"])
            revision = await self._session.get(
                LearningQuestionRevision, revision_id
            )
            revision = self._require_scope(
                revision, actor.organization_id, "题目修订"
            )
            return self._question_revision_summary(revision)
        question = await self._session.scalar(
            select(LearningQuestion)
            .where(LearningQuestion.organization_id == actor.organization_id)
            .where(LearningQuestion.stable_key == stable_key)
            .with_for_update()
            .limit(1)
        )
        now = _now()
        if question is None:
            if expected_question_version is not None:
                raise LearningGovernanceError(
                    "[LEARNING_VERSION_CONFLICT]",
                    "题目尚不存在，请刷新后重试。",
                    412,
                    details={
                        "expected_version": expected_question_version,
                        "actual_version": None,
                    },
                )
            question = LearningQuestion(
                question_id=_id(),
                organization_id=actor.organization_id,
                stable_key=stable_key,
                status="approved",
                version=1,
                created_by=actor.actor_id,
                created_at=now,
                updated_at=now,
            )
            revision_no = 1
            before_version = None
            self._session.add(question)
        else:
            self._require_version(
                question.version,
                expected_question_version
                if expected_question_version is not None
                else -1,
                "题目",
            )
            revision_no = int(
                await self._session.scalar(
                    select(func.max(LearningQuestionRevision.revision_no)).where(
                        LearningQuestionRevision.question_id == question.question_id
                    )
                )
                or 0
            ) + 1
            before_version = question.version
            question.status = "approved"
            question.version += 1
            question.updated_at = now
        revision = LearningQuestionRevision(
            revision_id=_id(),
            question_id=question.question_id,
            organization_id=actor.organization_id,
            revision_no=revision_no,
            status="approved",
            version=1,
            question_type=content.question_type,
            content_json=content.model_dump(mode="json"),
            source_anchor_ids_json=list(content.source_anchor_ids),
            competency_keys_json=list(content.competency_keys),
            deterministic_fingerprint=question_fingerprint(content),
            content_hash=_canonical_hash(content.model_dump(mode="json")),
            source_candidate_id=None,
            reviewed_by=actor.actor_id,
            review_reason=review_reason.strip(),
            created_by=actor.actor_id,
            created_at=now,
        )
        question.working_revision_id = revision.revision_id
        self._session.add(revision)
        await self._session.flush([question, revision])
        await self._audit(
            actor=actor,
            capability="learning.question.manage",
            object_type="question",
            object_id=stable_key,
            command="save_manual_question_revision",
            before_version=before_version,
            after_version=question.version,
            idempotency_key=idempotency_key,
            reason=review_reason.strip(),
            result="succeeded",
            details={
                "request_fingerprint": request_fingerprint,
                "question_id": question.question_id,
                "question_revision_id": revision.revision_id,
            },
        )
        return self._question_revision_summary(revision)

    async def get_question(
        self,
        *,
        actor: LearningActor,
        question_id: str,
    ) -> QuestionSummary:
        if not {
            "learning.question.manage",
            "learning.question.review",
        }.intersection(actor.capabilities):
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]", "没有查看此题目的权限。", 403
            )
        question = await self._session.get(LearningQuestion, question_id)
        question = self._require_scope(question, actor.organization_id, "题目")
        return QuestionSummary.model_validate(question)

    async def publish_question_revision(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        expected_revision_version: int,
        idempotency_key: str,
    ) -> QuestionRevisionSummary:
        self._require(actor, "learning.question.publish")
        row = await self._session.scalar(
            select(LearningQuestionRevision)
            .where(LearningQuestionRevision.revision_id == revision_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "题目修订")
        fingerprint = _canonical_hash(
            {
                "revision_id": revision_id,
                "expected_revision_version": expected_revision_version,
            }
        )
        if row.status == "published":
            audit = await self._session.scalar(
                select(LearningCommandAudit)
                .where(LearningCommandAudit.organization_id == actor.organization_id)
                .where(LearningCommandAudit.object_type == "question_revision")
                .where(LearningCommandAudit.object_id == revision_id)
                .where(LearningCommandAudit.command == "publish_question_revision")
                .where(
                    LearningCommandAudit.idempotency_key_hash
                    == _secret_hash(idempotency_key)
                )
                .limit(1)
            )
            if (
                audit is None
                or audit.details_json.get("request_fingerprint") != fingerprint
            ):
                raise LearningGovernanceError(
                    "[LEARNING_REVISION_IMMUTABLE]",
                    "已发布题目修订不可再次发布。",
                    409,
                )
            return self._question_revision_summary(row)
        self._require_version(row.version, expected_revision_version, "题目修订")
        if row.status != "approved" or row.reviewed_by is None:
            raise LearningGovernanceError(
                "[QUESTION_REVISION_NOT_APPROVED]", "题目经过人工审核后才能发布。", 422
            )
        question = await self._session.scalar(
            select(LearningQuestion)
            .where(LearningQuestion.question_id == row.question_id)
            .with_for_update()
            .limit(1)
        )
        question = self._require_scope(question, actor.organization_id, "题目")
        before = row.version
        row.status = "published"
        row.version += 1
        row.published_by = actor.actor_id
        row.published_at = _now()
        question.status = "published"
        question.published_revision_id = row.revision_id
        if question.working_revision_id == row.revision_id:
            question.working_revision_id = None
        question.version += 1
        question.updated_at = _now()
        await self._session.flush([question, row])
        await self._audit(
            actor=actor,
            capability="learning.question.publish",
            object_type="question_revision",
            object_id=row.revision_id,
            command="publish_question_revision",
            before_version=before,
            after_version=row.version,
            idempotency_key=idempotency_key,
            reason="human_approved",
            result="succeeded",
            details={
                "question_id": question.question_id,
                "request_fingerprint": fingerprint,
            },
        )
        return self._question_revision_summary(row)

    async def create_quiz(
        self,
        *,
        actor: LearningActor,
        stable_key: str,
        title: str,
        idempotency_key: str,
    ) -> QuizSummary:
        self._require(actor, "learning.quiz.manage")
        fingerprint = _canonical_hash(
            {
                "organization_id": actor.organization_id,
                "stable_key": stable_key,
                "title": title,
            }
        )
        existing = await self._session.scalar(
            select(LearningQuiz)
            .where(LearningQuiz.organization_id == actor.organization_id)
            .where(LearningQuiz.stable_key == stable_key)
            .limit(1)
        )
        if existing is not None:
            self._require_creation_replay(existing, idempotency_key, fingerprint)
            return QuizSummary.model_validate(existing)
        row = LearningQuiz(
            quiz_id=_id(),
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
        return QuizSummary.model_validate(row)

    async def get_quiz(
        self,
        *,
        actor: LearningActor,
        quiz_id: str,
    ) -> QuizSummary:
        self._require(actor, "learning.quiz.manage")
        row = await self._session.get(LearningQuiz, quiz_id)
        row = self._require_scope(row, actor.organization_id, "测验")
        return QuizSummary.model_validate(row)

    async def save_quiz_revision(
        self,
        *,
        actor: LearningActor,
        quiz_id: str,
        draft: QuizRevisionDraft,
        expected_quiz_version: int,
        idempotency_key: str,
    ) -> QuizRevisionSummary:
        self._require(actor, "learning.quiz.manage")
        quiz = await self._load_quiz_for_update(actor, quiz_id)
        fingerprint = _canonical_hash(
            {
                "quiz_id": quiz_id,
                "expected_quiz_version": expected_quiz_version,
                "draft": draft.model_dump(mode="json"),
            }
        )
        replay = await self._session.scalar(
            select(LearningQuizRevision)
            .where(LearningQuizRevision.quiz_id == quiz_id)
            .where(
                LearningQuizRevision.save_idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            self._require_fingerprint(replay.save_fingerprint, fingerprint)
            return self._quiz_revision_summary(replay)
        self._require_version(quiz.version, expected_quiz_version, "测验")
        question_revision_ids = tuple(
            item.question_revision_id for item in draft.questions
        )
        question_revisions = (
            await self._session.execute(
                select(LearningQuestionRevision)
                .where(
                    LearningQuestionRevision.organization_id
                    == actor.organization_id
                )
                .where(
                    LearningQuestionRevision.revision_id.in_(
                        question_revision_ids
                    )
                )
            )
        ).scalars().all()
        approved_question_ids = {
            row.question_id
            for row in question_revisions
            if row.status == "approved"
        }
        approved_questions = (
            []
            if not approved_question_ids
            else (
                await self._session.execute(
                    select(LearningQuestion).where(
                        LearningQuestion.question_id.in_(approved_question_ids)
                    )
                )
            ).scalars().all()
        )
        questions_by_id = {row.question_id: row for row in approved_questions}
        invalid_question = any(
            row.status not in {"approved", "published"}
            or (
                row.status == "approved"
                and (
                    row.reviewed_by is None
                    or (question := questions_by_id.get(row.question_id)) is None
                    or question.organization_id != actor.organization_id
                    or question.working_revision_id != row.revision_id
                )
            )
            for row in question_revisions
        )
        if {row.revision_id for row in question_revisions} != set(
            question_revision_ids
        ) or invalid_question:
            raise LearningGovernanceError(
                "[QUIZ_QUESTION_REVISION_UNAVAILABLE]",
                "测验只能引用同组织已批准的当前题目修订或已发布题目修订。",
                422,
            )
        has_short_answer = any(
            row.question_type == "short_answer" for row in question_revisions
        )
        if has_short_answer and draft.short_answer_scoring is None:
            raise LearningGovernanceError(
                "[QUIZ_SHORT_ANSWER_POLICY_REQUIRED]",
                "包含简答题的测验必须冻结评分 Prompt 与模型策略。",
                422,
            )
        working = None
        if quiz.working_revision_id:
            working = await self._session.get(
                LearningQuizRevision, quiz.working_revision_id
            )
            if working is not None and working.status != "working":
                working = None
        snapshot = draft.model_dump(mode="json")
        now = _now()
        if working is None:
            revision_no = int(
                await self._session.scalar(
                    select(func.max(LearningQuizRevision.revision_no)).where(
                        LearningQuizRevision.quiz_id == quiz_id
                    )
                )
                or 0
            ) + 1
            working = LearningQuizRevision(
                revision_id=_id(),
                quiz_id=quiz_id,
                organization_id=actor.organization_id,
                revision_no=revision_no,
                revision_label=draft.revision_label,
                status="working",
                snapshot_json=snapshot,
                question_revision_ids_json=list(question_revision_ids),
                content_hash=_canonical_hash(snapshot),
                version=1,
                save_idempotency_key_hash=_secret_hash(idempotency_key),
                save_fingerprint=fingerprint,
                created_by=actor.actor_id,
                created_at=now,
            )
            self._session.add(working)
            quiz.working_revision_id = working.revision_id
        else:
            working.revision_label = draft.revision_label
            working.snapshot_json = snapshot
            working.question_revision_ids_json = list(question_revision_ids)
            working.content_hash = _canonical_hash(snapshot)
            working.version += 1
            working.save_idempotency_key_hash = _secret_hash(idempotency_key)
            working.save_fingerprint = fingerprint
        quiz.title = draft.title
        quiz.version += 1
        quiz.updated_at = now
        await self._session.flush([quiz, working])
        return self._quiz_revision_summary(working)

    async def publish_quiz_revision(
        self,
        *,
        actor: LearningActor,
        revision_id: str,
        expected_revision_version: int,
        idempotency_key: str,
    ) -> QuizRevisionSummary:
        self._require(actor, "learning.quiz.manage")
        row = await self._session.scalar(
            select(LearningQuizRevision)
            .where(LearningQuizRevision.revision_id == revision_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "测验修订")
        fingerprint = _canonical_hash(
            {
                "revision_id": revision_id,
                "expected_revision_version": expected_revision_version,
            }
        )
        if row.status == "published":
            self._require_publish_replay(row, idempotency_key, fingerprint)
            return self._quiz_revision_summary(row)
        self._require_version(row.version, expected_revision_version, "测验修订")
        quiz = await self._load_quiz_for_update(actor, row.quiz_id)
        now = _now()
        before_version = row.version
        row.status = "published"
        row.version += 1
        row.publish_idempotency_key_hash = _secret_hash(idempotency_key)
        row.publish_fingerprint = fingerprint
        row.published_by = actor.actor_id
        row.published_at = now
        quiz.status = "active"
        quiz.published_revision_id = row.revision_id
        if quiz.working_revision_id == row.revision_id:
            quiz.working_revision_id = None
        quiz.version += 1
        quiz.updated_at = now
        await self._session.flush([quiz, row])
        await self._audit(
            actor=actor,
            capability="learning.quiz.manage",
            object_type="quiz_revision",
            object_id=row.revision_id,
            command="publish_quiz_revision",
            before_version=before_version,
            after_version=row.version,
            idempotency_key=idempotency_key,
            reason=None,
            result="succeeded",
            details={
                "quiz_id": quiz.quiz_id,
                "request_fingerprint": fingerprint,
            },
        )
        return self._quiz_revision_summary(row)

    async def publish_resource_working_revision(
        self,
        *,
        actor: LearningActor,
        resource_type: Literal[
            "source_document", "learning_unit", "question", "quiz"
        ],
        resource_id: str,
        expected_resource_version: int,
        idempotency_key: str,
        reason: str,
    ) -> ResourcePublishResult:
        """Publish the exact working revision behind a resource-level ETag."""

        if not reason.strip():
            raise LearningGovernanceError(
                "[LEARNING_PUBLISH_REASON_REQUIRED]",
                "请填写发布依据。",
                422,
            )
        capability, label, resource, revision = await self._resource_context(
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            for_update=True,
            use_working_revision=True,
        )
        publish_capability = (
            "learning.question.publish"
            if resource_type == "question"
            else capability
        )
        self._require(actor, publish_capability)
        fingerprint = _canonical_hash(
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expected_resource_version": expected_resource_version,
                "reason": reason.strip(),
            }
        )
        replay = await self._session.scalar(
            select(LearningCommandAudit)
            .where(LearningCommandAudit.organization_id == actor.organization_id)
            .where(LearningCommandAudit.object_type == "learning_resource")
            .where(LearningCommandAudit.object_id == resource_id)
            .where(
                LearningCommandAudit.command
                == "publish_resource_working_revision"
            )
            .where(
                LearningCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.details_json.get("request_fingerprint") != fingerprint:
                self._idempotency_conflict()
            return ResourcePublishResult.model_validate(
                replay.details_json["result"]
            )
        self._require_version(resource.version, expected_resource_version, label)
        if revision is None:
            raise LearningGovernanceError(
                "[LEARNING_WORKING_REVISION_NOT_FOUND]",
                f"{label}没有可发布的工作修订。",
                404,
            )
        validation = await self.validate_resource_working_revision(
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if not validation.valid:
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_VALIDATION_FAILED]",
                f"{label}仍有未通过的发布检查。",
                422,
                details={
                    "issues": [
                        item.model_dump(mode="json") for item in validation.issues
                    ]
                },
            )
        revision_key = f"{idempotency_key}:revision"
        published: (
            SourceRevisionSummary
            | LearningUnitRevisionSummary
            | QuestionRevisionSummary
            | QuizRevisionSummary
        )
        if resource_type == "source_document":
            published = await self.publish_source_revision(
                actor=actor,
                revision_id=revision.revision_id,
                expected_revision_version=revision.version,
                idempotency_key=revision_key,
            )
        elif resource_type == "learning_unit":
            published = await self.publish_learning_unit_revision(
                actor=actor,
                revision_id=revision.revision_id,
                expected_revision_version=revision.version,
                idempotency_key=revision_key,
            )
        elif resource_type == "question":
            published = await self.publish_question_revision(
                actor=actor,
                revision_id=revision.revision_id,
                expected_revision_version=revision.version,
                idempotency_key=revision_key,
            )
        else:
            published = await self.publish_quiz_revision(
                actor=actor,
                revision_id=revision.revision_id,
                expected_revision_version=revision.version,
                idempotency_key=revision_key,
            )
        result = ResourcePublishResult(
            resource_type=resource_type,
            resource_id=resource_id,
            resource_version=resource.version,
            revision_id=published.revision_id,
            revision_version=published.version,
        )
        await self._audit(
            actor=actor,
            capability=publish_capability,
            object_type="learning_resource",
            object_id=resource_id,
            command="publish_resource_working_revision",
            before_version=expected_resource_version,
            after_version=resource.version,
            idempotency_key=idempotency_key,
            reason=reason.strip(),
            result="succeeded",
            details={
                "request_fingerprint": fingerprint,
                "result": result.model_dump(mode="json"),
            },
        )
        return result

    async def validate_resource_working_revision(
        self,
        *,
        actor: LearningActor,
        resource_type: Literal[
            "source_document", "learning_unit", "question", "quiz"
        ],
        resource_id: str,
    ) -> ResourceValidationResult:
        """Read-only release validation for one exact working revision."""

        capability, label, resource, revision = await self._resource_context(
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            for_update=False,
            use_working_revision=True,
        )
        self._require(actor, capability)
        if revision is None:
            issue = ResourceValidationIssue(
                code="working_revision_required",
                field="working_revision",
                message=f"{label}没有可校验的工作修订。",
            )
            return ResourceValidationResult(
                resource_type=resource_type,
                resource_id=resource_id,
                revision_id=None,
                valid=False,
                issues=(issue,),
            )

        issues: list[ResourceValidationIssue] = []
        if resource_type == "source_document":
            try:
                SourceDocumentRevisionDraft.model_validate(
                    {
                        "revision_label": revision.revision_label,
                        "source_type": revision.source_type,
                        "content_kind": revision.content_kind,
                        "source_uri": revision.source_uri,
                        "file_hash": revision.file_hash,
                        "parser_version": revision.parser_version,
                        "parse_status": revision.parse_status,
                        "original_filename": revision.original_filename,
                        "trusted_mime_type": revision.trusted_mime_type,
                        "file_extension": revision.file_extension,
                        "file_size_bytes": revision.file_size_bytes,
                        "language": revision.language,
                        "page_count": revision.page_count,
                        "duration_ms": revision.duration_ms,
                        "preview_version": revision.preview_version,
                        "processing_state": revision.processing_state,
                        "processing_stage": revision.processing_stage,
                        "failure_code": revision.failure_code,
                        "failure_message": revision.failure_message,
                        "manual_content": revision.manual_content,
                    }
                )
            except ValueError:
                issues.append(
                    ResourceValidationIssue(
                        code="source_revision_schema_invalid",
                        field="working_revision",
                        message="原始材料修订结构不完整，请重新保存。",
                    )
                )
            if (
                revision.parse_status != "ready"
                or revision.processing_state != "ready"
            ):
                issues.append(
                    ResourceValidationIssue(
                        code="source_parse_not_ready",
                        field="working_revision.parse_status",
                        message="原始材料解析完成后才能进入发布计划。",
                    )
                )
        elif resource_type == "learning_unit":
            try:
                unit_draft = LearningUnitRevisionDraft.model_validate(
                    revision.snapshot_json
                )
            except ValueError:
                unit_draft = None
                issues.append(
                    ResourceValidationIssue(
                        code="learning_unit_schema_invalid",
                        field="working_revision",
                        message="学习内容结构不完整，请重新保存。",
                    )
                )
            if unit_draft is not None:
                await self._validate_anchor_references(
                    actor=actor,
                    anchor_ids=unit_draft.source_anchor_ids(),
                    field="working_revision.source_anchor_ids",
                    issues=issues,
                )
                await self._validate_exact_source_references(
                    actor=actor,
                    references=unit_draft.exact_source_references(),
                    field="working_revision.content_blocks",
                    issues=issues,
                )
        elif resource_type == "question":
            try:
                content = QuestionCandidateContent.model_validate(
                    revision.content_json
                )
            except ValueError:
                content = None
                issues.append(
                    ResourceValidationIssue(
                        code="question_schema_invalid",
                        field="working_revision",
                        message="题目结构或答案合同不完整，请重新保存。",
                    )
                )
            if content is not None:
                await self._validate_anchor_references(
                    actor=actor,
                    anchor_ids=content.source_anchor_ids,
                    field="working_revision.source_anchor_ids",
                    issues=issues,
                )
                if contains_sensitive_text(content):
                    issues.append(
                        ResourceValidationIssue(
                            code="question_sensitive_content",
                            field="working_revision.content",
                            message="题目包含敏感内容，需要修订后再发布。",
                        )
                    )
            if revision.reviewed_by is None:
                issues.append(
                    ResourceValidationIssue(
                        code="question_human_review_required",
                        field="working_revision.reviewed_by",
                        message="题目必须完成人工审核。",
                    )
                )
        else:
            try:
                quiz_draft = QuizRevisionDraft.model_validate(
                    revision.snapshot_json
                )
            except ValueError:
                quiz_draft = None
                issues.append(
                    ResourceValidationIssue(
                        code="quiz_schema_invalid",
                        field="working_revision",
                        message="测验规则或题目绑定结构不完整，请重新保存。",
                    )
                )
            if quiz_draft is not None:
                question_ids = tuple(
                    item.question_revision_id for item in quiz_draft.questions
                )
                questions = (
                    await self._session.execute(
                        select(LearningQuestionRevision)
                        .where(
                            LearningQuestionRevision.organization_id
                            == actor.organization_id
                        )
                        .where(
                            LearningQuestionRevision.revision_id.in_(
                                question_ids
                            )
                        )
                    )
                ).scalars().all()
                if {item.revision_id for item in questions} != set(
                    question_ids
                ) or any(item.status != "published" for item in questions):
                    issues.append(
                        ResourceValidationIssue(
                            code="quiz_question_revision_unpublished",
                            field="working_revision.questions",
                            message="测验只能发布同组织内仍有效的已发布题目修订。",
                        )
                    )
                if any(
                    item.question_type == "short_answer" for item in questions
                ) and quiz_draft.short_answer_scoring is None:
                    issues.append(
                        ResourceValidationIssue(
                            code="quiz_short_answer_policy_required",
                            field="working_revision.short_answer_scoring",
                            message="简答题测验必须冻结评分 Prompt 与模型策略。",
                        )
                    )
        return ResourceValidationResult(
            resource_type=resource_type,
            resource_id=resource_id,
            revision_id=revision.revision_id,
            valid=not any(issue.severity == "error" for issue in issues),
            issues=tuple(issues),
        )

    async def archive_resource(
        self,
        *,
        actor: LearningActor,
        resource_type: Literal[
            "source_document", "learning_unit", "question", "quiz"
        ],
        resource_id: str,
        expected_version: int,
        reason: str,
        idempotency_key: str,
    ) -> ResourceArchiveResult:
        if not reason.strip():
            raise LearningGovernanceError(
                "[LEARNING_ARCHIVE_REASON_REQUIRED]", "请填写归档原因。", 422
            )
        capability, label, resource, revision = await self._resource_context(
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            for_update=True,
            use_working_revision=False,
        )
        self._require(actor, capability)
        fingerprint = _canonical_hash(
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "expected_version": expected_version,
                "reason": reason.strip(),
            }
        )
        replay = await self._session.scalar(
            select(LearningCommandAudit)
            .where(
                LearningCommandAudit.organization_id == actor.organization_id
            )
            .where(LearningCommandAudit.object_type == "learning_resource")
            .where(LearningCommandAudit.object_id == resource_id)
            .where(LearningCommandAudit.command == "archive_resource")
            .where(
                LearningCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.details_json.get("request_fingerprint") != fingerprint:
                self._idempotency_conflict()
            archived_revision_id = str(
                replay.details_json["archived_revision_id"]
            )
            return ResourceArchiveResult(
                resource_type=resource_type,
                resource_id=resource_id,
                version=resource.version,
                archived_revision_id=archived_revision_id,
            )
        self._require_version(resource.version, expected_version, label)
        if resource.status == "archived":
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_STATE_CONFLICT]",
                f"{label}已经归档。",
                409,
            )
        if resource.working_revision_id is not None:
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_WORKING_REVISION_EXISTS]",
                f"{label}仍有未发布工作修订，请先处理后再归档。",
                409,
            )
        if revision is None or revision.status != "published":
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_NOT_PUBLISHED]",
                f"{label}尚无可归档的已发布修订。",
                422,
            )
        before_version = resource.version
        resource.status = "archived"
        resource.version += 1
        resource.updated_at = _now()
        revision.status = "archived"
        revision.version += 1
        await self._session.flush([resource, revision])
        await self._audit(
            actor=actor,
            capability=capability,
            object_type="learning_resource",
            object_id=resource_id,
            command="archive_resource",
            before_version=before_version,
            after_version=resource.version,
            idempotency_key=idempotency_key,
            reason=reason.strip(),
            result="succeeded",
            details={
                "request_fingerprint": fingerprint,
                "resource_type": resource_type,
                "archived_revision_id": revision.revision_id,
            },
        )
        return ResourceArchiveResult(
            resource_type=resource_type,
            resource_id=resource_id,
            version=resource.version,
            archived_revision_id=revision.revision_id,
        )

    async def _resource_context(
        self,
        *,
        actor: LearningActor,
        resource_type: Literal[
            "source_document", "learning_unit", "question", "quiz"
        ],
        resource_id: str,
        for_update: bool,
        use_working_revision: bool,
    ) -> tuple[str, str, Any, Any | None]:
        capability: str
        label: str
        resource_model: Any
        revision_model: Any
        id_column: Any
        capability, label, resource_model, revision_model, id_column = {
            "source_document": (
                "learning.source.manage",
                "原始材料",
                LearningSourceDocument,
                LearningSourceDocumentRevision,
                LearningSourceDocument.document_id,
            ),
            "learning_unit": (
                "learning.content.manage",
                "学习内容",
                LearningUnit,
                LearningUnitRevision,
                LearningUnit.unit_id,
            ),
            "question": (
                "learning.question.manage",
                "题目",
                LearningQuestion,
                LearningQuestionRevision,
                LearningQuestion.question_id,
            ),
            "quiz": (
                "learning.quiz.manage",
                "测验",
                LearningQuiz,
                LearningQuizRevision,
                LearningQuiz.quiz_id,
            ),
        }[resource_type]
        self._require(actor, capability)
        query = select(resource_model).where(id_column == resource_id).limit(1)
        if for_update:
            query = query.with_for_update()
        resource = await self._session.scalar(query)
        resource = self._require_scope(resource, actor.organization_id, label)
        revision_id = (
            resource.working_revision_id
            if use_working_revision
            else resource.published_revision_id
        )
        revision = (
            None
            if revision_id is None
            else await self._session.get(revision_model, revision_id)
        )
        if revision is not None:
            revision = self._require_scope(
                revision, actor.organization_id, f"{label}修订"
            )
        return capability, label, resource, revision

    async def _validate_anchor_references(
        self,
        *,
        actor: LearningActor,
        anchor_ids: tuple[str, ...],
        field: str,
        issues: list[ResourceValidationIssue],
    ) -> None:
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(
                    LearningSourceAnchor.organization_id
                    == actor.organization_id
                )
                .where(LearningSourceAnchor.anchor_id.in_(anchor_ids))
            )
        ).scalars().all()
        if {item.anchor_id for item in anchors} != set(anchor_ids):
            issues.append(
                ResourceValidationIssue(
                    code="source_anchor_invalid",
                    field=field,
                    message="引用了不存在或越权的来源锚点。",
                )
            )
            return
        source_revision_ids = {item.source_revision_id for item in anchors}
        source_revisions = (
            await self._session.execute(
                select(LearningSourceDocumentRevision).where(
                    LearningSourceDocumentRevision.revision_id.in_(
                        source_revision_ids
                    )
                )
            )
        ).scalars().all()
        if len(source_revisions) != len(source_revision_ids) or any(
            item.organization_id != actor.organization_id
            or item.status != "published"
            for item in source_revisions
        ):
            issues.append(
                ResourceValidationIssue(
                    code="source_revision_unpublished",
                    field=field,
                    message="来源锚点必须指向同组织内仍有效的已发布材料修订。",
                )
            )

    async def _validate_exact_source_references(
        self,
        *,
        actor: LearningActor,
        references: tuple[tuple[str, str], ...],
        field: str,
        issues: list[ResourceValidationIssue],
    ) -> None:
        if not references:
            return
        anchor_ids = tuple(dict.fromkeys(anchor_id for _, anchor_id in references))
        anchors = list(
            (
                await self._session.execute(
                    select(LearningSourceAnchor)
                    .where(
                        LearningSourceAnchor.organization_id
                        == actor.organization_id
                    )
                    .where(LearningSourceAnchor.anchor_id.in_(anchor_ids))
                )
            ).scalars()
        )
        by_id = {item.anchor_id: item for item in anchors}
        if any(
            (anchor := by_id.get(anchor_id)) is None
            or anchor.source_revision_id != source_revision_id
            for source_revision_id, anchor_id in references
        ):
            issues.append(
                ResourceValidationIssue(
                    code="exact_source_reference_invalid",
                    field=field,
                    message="内容块的来源修订与来源定位不一致。",
                )
            )

    async def _close_question_candidate(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        target_status: str,
        command: str,
        expected_version: int,
        idempotency_key: str,
        review_reason: str,
    ) -> QuestionCandidateSummary:
        self._require(actor, "learning.question.review")
        if not review_reason.strip():
            raise LearningGovernanceError(
                "[QUESTION_REVIEW_REASON_REQUIRED]", "请填写审核依据。", 422
            )
        candidate = await self._load_candidate_for_update(actor, candidate_id)
        fingerprint = _canonical_hash(
            {
                "candidate_id": candidate_id,
                "command": command,
                "target_status": target_status,
                "expected_version": expected_version,
                "review_reason": review_reason.strip(),
            }
        )
        replay = await self._candidate_command_replay(
            actor=actor,
            candidate_id=candidate_id,
            command=command,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if replay is not None:
            return replay
        self._require_version(candidate.version, expected_version, "候选题")
        if candidate.status not in {"generated", "in_review", "rejected"}:
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_STATE_CONFLICT]",
                "当前候选题状态不能执行此审核操作。",
                409,
            )
        if target_status == "rejected" and candidate.status == "rejected":
            raise LearningGovernanceError(
                "[QUESTION_CANDIDATE_STATE_CONFLICT]", "候选题已经被拒绝。", 409
            )
        before = candidate.version
        candidate.status = target_status
        candidate.version += 1
        candidate.reviewed_by = actor.actor_id
        candidate.review_reason = review_reason.strip()
        candidate.updated_at = _now()
        await self._session.flush([candidate])
        summary = self._question_candidate_summary(candidate)
        await self._audit_candidate_command(
            actor=actor,
            candidate=candidate,
            command=command,
            before_version=before,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            result_snapshot=summary.model_dump(mode="json"),
            reason=review_reason.strip(),
        )
        return summary

    async def _load_candidate_for_update(
        self,
        actor: LearningActor,
        candidate_id: str,
    ) -> LearningQuestionCandidate:
        row = await self._session.scalar(
            select(LearningQuestionCandidate)
            .where(LearningQuestionCandidate.candidate_id == candidate_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "候选题")
        return row

    async def _candidate_command_replay(
        self,
        *,
        actor: LearningActor,
        candidate_id: str,
        command: str,
        idempotency_key: str,
        fingerprint: str,
    ) -> QuestionCandidateSummary | None:
        audit = await self._session.scalar(
            select(LearningCommandAudit)
            .where(LearningCommandAudit.organization_id == actor.organization_id)
            .where(LearningCommandAudit.object_type == "question_candidate")
            .where(LearningCommandAudit.object_id == candidate_id)
            .where(LearningCommandAudit.command == command)
            .where(
                LearningCommandAudit.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if audit is None:
            return None
        if audit.details_json.get("request_fingerprint") != fingerprint:
            self._idempotency_conflict()
        candidate = await self._session.get(LearningQuestionCandidate, candidate_id)
        candidate = self._require_scope(candidate, actor.organization_id, "候选题")
        return self._question_candidate_summary(candidate)

    async def _audit_candidate_command(
        self,
        *,
        actor: LearningActor,
        candidate: LearningQuestionCandidate,
        command: str,
        before_version: int,
        idempotency_key: str,
        fingerprint: str,
        result_snapshot: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        await self._audit(
            actor=actor,
            capability="learning.question.review",
            object_type="question_candidate",
            object_id=candidate.candidate_id,
            command=command,
            before_version=before_version,
            after_version=candidate.version,
            idempotency_key=idempotency_key,
            reason=reason,
            result="succeeded",
            details={
                "request_fingerprint": fingerprint,
                "result_status": result_snapshot["status"],
                "result_version": result_snapshot["version"],
            },
        )

    async def _evaluate_candidate_content(
        self,
        *,
        organization_id: str,
        source_revision_id: str,
        candidate_id: str,
        content: QuestionCandidateContent,
    ) -> tuple[str, dict[str, Any], str]:
        fingerprint = question_fingerprint(content)
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(LearningSourceAnchor.organization_id == organization_id)
                .where(LearningSourceAnchor.anchor_id.in_(content.source_anchor_ids))
            )
        ).scalars().all()
        source_ids = {row.anchor_id for row in anchors}
        sources_valid = source_ids == set(content.source_anchor_ids) and all(
            row.source_revision_id == source_revision_id for row in anchors
        )
        duplicate_revision = await self._session.scalar(
            select(LearningQuestionRevision.revision_id)
            .where(LearningQuestionRevision.organization_id == organization_id)
            .where(
                LearningQuestionRevision.deterministic_fingerprint == fingerprint
            )
            .limit(1)
        )
        duplicate_candidate = await self._session.scalar(
            select(LearningQuestionCandidate.candidate_id)
            .where(LearningQuestionCandidate.organization_id == organization_id)
            .where(LearningQuestionCandidate.candidate_id != candidate_id)
            .where(
                LearningQuestionCandidate.deterministic_fingerprint == fingerprint
            )
            .limit(1)
        )
        gates: dict[str, Any] = {
            "schema": {"passed": True},
            "answer": {"passed": True},
            "source": {"passed": sources_valid},
            "duplicate": {
                "passed": duplicate_revision is None and duplicate_candidate is None,
                "fingerprint": fingerprint,
            },
            "sensitive": {"passed": not contains_sensitive_text(content)},
            "quality": {
                "passed": len(content.stem.strip()) >= 12
                and len(content.explanation.strip()) >= 8
                and bool(content.competency_keys)
            },
        }
        gate_status = (
            "passed"
            if all(bool(result["passed"]) for result in gates.values())
            else "failed"
        )
        return fingerprint, gates, gate_status

    async def _load_document_for_update(
        self, actor: LearningActor, document_id: str
    ) -> LearningSourceDocument:
        row = await self._session.scalar(
            select(LearningSourceDocument)
            .where(LearningSourceDocument.document_id == document_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "原始材料")
        return row

    async def _load_source_revision(
        self, actor: LearningActor, revision_id: str
    ) -> LearningSourceDocumentRevision:
        row = await self._session.get(LearningSourceDocumentRevision, revision_id)
        row = self._require_scope(row, actor.organization_id, "原始材料修订")
        return row

    async def _load_source_revision_for_update(
        self, actor: LearningActor, revision_id: str
    ) -> LearningSourceDocumentRevision:
        row = await self._session.scalar(
            select(LearningSourceDocumentRevision)
            .where(LearningSourceDocumentRevision.revision_id == revision_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "原始材料修订")
        return row

    async def _load_unit_for_update(
        self, actor: LearningActor, unit_id: str
    ) -> LearningUnit:
        row = await self._session.scalar(
            select(LearningUnit)
            .where(LearningUnit.unit_id == unit_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "学习单元")
        return row

    async def _load_unit_revision_for_update(
        self, actor: LearningActor, revision_id: str
    ) -> LearningUnitRevision:
        row = await self._session.scalar(
            select(LearningUnitRevision)
            .where(LearningUnitRevision.revision_id == revision_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "学习内容修订")
        return row

    async def _load_quiz_for_update(
        self, actor: LearningActor, quiz_id: str
    ) -> LearningQuiz:
        row = await self._session.scalar(
            select(LearningQuiz)
            .where(LearningQuiz.quiz_id == quiz_id)
            .with_for_update()
            .limit(1)
        )
        row = self._require_scope(row, actor.organization_id, "测验")
        return row

    @staticmethod
    def _unit_revision_summary(row: LearningUnitRevision) -> LearningUnitRevisionSummary:
        return LearningUnitRevisionSummary(
            revision_id=row.revision_id,
            unit_id=row.unit_id,
            organization_id=row.organization_id,
            revision_no=row.revision_no,
            revision_label=row.revision_label,
            status=row.status,
            content_hash=row.content_hash,
            version=row.version,
            source_anchor_ids=tuple(row.source_anchor_ids_json),
        )

    @staticmethod
    def _question_revision_summary(row: LearningQuestionRevision) -> QuestionRevisionSummary:
        return QuestionRevisionSummary(
            revision_id=row.revision_id,
            question_id=row.question_id,
            organization_id=row.organization_id,
            revision_no=row.revision_no,
            status=row.status,
            version=row.version,
            question_type=row.question_type,
            source_anchor_ids=tuple(row.source_anchor_ids_json),
            competency_keys=tuple(row.competency_keys_json),
            deterministic_fingerprint=row.deterministic_fingerprint,
            content_hash=row.content_hash,
            source_candidate_id=row.source_candidate_id,
            reviewed_by=row.reviewed_by,
        )

    @staticmethod
    def _question_candidate_summary(
        row: LearningQuestionCandidate,
    ) -> QuestionCandidateSummary:
        return QuestionCandidateSummary(
            candidate_id=row.candidate_id,
            batch_id=row.batch_id,
            organization_id=row.organization_id,
            status=row.status,
            version=row.version,
            content=QuestionCandidateContent.model_validate(row.content_json),
            gate_status=row.gate_status,
            gate_results=dict(row.gate_results_json),
            prompt_revision_id=row.prompt_revision_id,
            model_routing_revision_id=row.model_routing_revision_id,
            generation_input_hash=row.generation_input_hash,
            invocation_id=row.invocation_id,
            reviewed_by=row.reviewed_by,
            review_reason=row.review_reason,
            approved_question_revision_id=row.approved_question_revision_id,
        )

    @staticmethod
    def _quiz_revision_summary(row: LearningQuizRevision) -> QuizRevisionSummary:
        return QuizRevisionSummary(
            revision_id=row.revision_id,
            quiz_id=row.quiz_id,
            organization_id=row.organization_id,
            revision_no=row.revision_no,
            revision_label=row.revision_label,
            status=row.status,
            question_revision_ids=tuple(row.question_revision_ids_json),
            content_hash=row.content_hash,
            version=row.version,
        )

    @staticmethod
    def _require(actor: LearningActor, capability: str) -> None:
        if capability not in actor.capabilities:
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]", "没有执行此操作的权限。", 403
            )

    @staticmethod
    def _require_scope(
        row: ScopedRowT | None, organization_id: str, label: str
    ) -> ScopedRowT:
        if row is None or getattr(row, "organization_id", None) != organization_id:
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_NOT_FOUND]", f"{label}不存在或不可访问。", 404
            )
        return row

    @staticmethod
    def _require_version(actual: int, expected: int, label: str) -> None:
        if actual != expected:
            raise LearningGovernanceError(
                "[LEARNING_VERSION_CONFLICT]", f"{label}已被更新，请刷新后重试。", 412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _require_creation_replay(row: Any, idempotency_key: str, fingerprint: str) -> None:
        if (
            row.creation_idempotency_key_hash != _secret_hash(idempotency_key)
            or row.creation_fingerprint != fingerprint
        ):
            LearningGovernanceService._idempotency_conflict()

    @staticmethod
    def _require_fingerprint(actual: str, expected: str) -> None:
        if actual != expected:
            LearningGovernanceService._idempotency_conflict()

    @staticmethod
    def _require_publish_replay(row: Any, idempotency_key: str, fingerprint: str) -> None:
        if (
            row.publish_idempotency_key_hash != _secret_hash(idempotency_key)
            or row.publish_fingerprint != fingerprint
        ):
            raise LearningGovernanceError(
                "[LEARNING_REVISION_IMMUTABLE]", "已发布修订不可原地修改或重复发布。", 409
            )

    @staticmethod
    def _idempotency_conflict() -> Never:
        raise LearningGovernanceError(
            "[LEARNING_IDEMPOTENCY_CONFLICT]", "相同幂等键对应了不同请求。", 409
        )

    async def _audit(
        self,
        *,
        actor: LearningActor,
        capability: str,
        object_type: str,
        object_id: str,
        command: str,
        before_version: int | None,
        after_version: int | None,
        idempotency_key: str | None,
        reason: str | None,
        result: str,
        details: dict[str, Any],
    ) -> None:
        row = LearningCommandAudit(
            audit_id=_id(),
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=capability,
            object_type=object_type,
            object_id=object_id,
            command=command,
            before_version=before_version,
            after_version=after_version,
            idempotency_key_hash=_secret_hash(idempotency_key) if idempotency_key else None,
            reason=reason,
            result=result,
            trace_id=actor.trace_id,
            details_json=details,
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])


__all__ = [
    "LearningGovernanceService",
    "QuestionCandidateBulkItem",
    "QuestionCandidateBulkPreview",
    "QuestionCandidateBulkResult",
    "QuestionCandidateSummary",
    "QuestionSummary",
]
