"""Controlled storage and state transitions for uploaded learning sources."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.knowledge.processor import PARSE_ARTIFACT_VERSION
from common.storage import DocumentStorageService, get_document_storage_service
from learning.models import (
    LearningSourceAnchor,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
)
from learning.multimedia import (
    PREVIEW_VERSION,
    SUPPORTED_SOURCE_FILE_TYPES,
    SourceContentKind,
    SourceFileType,
    SourceProcessingResult,
    process_source_file,
)

SOURCE_DOCUMENT_PARSE_TASK_TYPE = "learning.source_document.parse"
SOURCE_DOCUMENT_PARSER_VERSION = PARSE_ARTIFACT_VERSION


def source_document_storage_namespace(organization_id: str) -> str:
    """Return an opaque, traversal-safe storage partition for one tenant."""

    digest = hashlib.sha256(organization_id.encode("utf-8")).hexdigest()
    return f"learning-sources-{digest[:24]}"


def source_document_storage_object_id(document_id: str, file_hash: str) -> str:
    """Keep immutable source bytes separate across document revisions."""

    return f"{document_id}-{file_hash}"


def source_document_artifact_uri(
    *,
    document_id: str,
    file_hash: str,
    file_type: SourceFileType,
) -> str:
    return f"artifact://learning/source/{document_id}/{file_hash}.{file_type}"


def source_document_file_path(
    *,
    storage: DocumentStorageService,
    organization_id: str,
    document_id: str,
    file_hash: str,
    file_type: SourceFileType,
) -> Path:
    return storage.get_document_path(
        source_document_storage_namespace(organization_id),
        source_document_storage_object_id(document_id, file_hash),
        file_type,
    )


def source_revision_content_hash(
    revision: LearningSourceDocumentRevision,
) -> str:
    payload = {
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
        "preview_manifest": revision.preview_manifest_json,
        "manual_content": revision.manual_content,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _source_fingerprint(revision: LearningSourceDocumentRevision) -> str:
    """Fence processing against same-hash metadata or pointer changes."""

    payload = {
        "revision_id": revision.revision_id,
        "document_id": revision.document_id,
        "source_type": revision.source_type,
        "content_kind": revision.content_kind,
        "source_uri": revision.source_uri,
        "file_hash": revision.file_hash,
        "file_extension": revision.file_extension,
        "trusted_mime_type": revision.trusted_mime_type,
        "original_filename": revision.original_filename,
        "manual_content": revision.manual_content,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceParsePlan:
    revision_id: str
    document_id: str
    organization_id: str
    file_hash: str
    file_type: SourceFileType
    content_kind: SourceContentKind
    file_path: Path
    already_ready: bool
    prepared_revision_version: int
    apply_revision_version: int
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class SourceParseOutcome:
    revision_id: str
    document_id: str
    parse_status: Literal["ready", "failed"]
    processing_state: Literal["partial", "ready", "failed"]
    chunk_count: int
    artifact_available: bool
    anchor_count: int
    page_count: int | None = None
    duration_ms: int | None = None
    missing_pages: tuple[int, ...] = ()
    error_code: str | None = None


class SourceDocumentIngestionProcessor:
    """Apply parser output to the single formal learning-source authority."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: DocumentStorageService | None = None,
    ) -> None:
        self._session = session
        self._storage = storage or get_document_storage_service()

    async def prepare(
        self,
        *,
        organization_id: str,
        revision_id: str,
        file_hash: str,
        file_type: SourceFileType,
    ) -> SourceParsePlan:
        revision = await self._session.get(
            LearningSourceDocumentRevision,
            revision_id,
        )
        if revision is None or revision.organization_id != organization_id:
            raise SourceIngestionError(
                "source_document_revision_not_found",
                "原始材料修订不存在或不可访问。",
            )
        if revision.source_type != "file":
            raise SourceIngestionError(
                "source_document_type_invalid",
                "该原始材料不是文件来源。",
            )
        if revision.status != "working" and revision.processing_state != "ready":
            raise SourceIngestionError(
                "source_document_revision_not_working",
                "只能解析尚未发布的原始材料修订。",
            )
        if revision.file_hash != file_hash:
            raise SourceIngestionError(
                "source_document_file_changed",
                "材料文件已发生变化，请重新提交解析任务。",
            )
        document = await self._session.get(
            LearningSourceDocument, revision.document_id
        )
        if (
            document is None
            or document.organization_id != organization_id
            or (
                revision.status == "working"
                and document.working_revision_id != revision.revision_id
            )
        ):
            raise SourceIngestionError(
                "source_document_revision_changed",
                "材料工作修订已变化，本次任务已停止。",
            )
        if revision.file_extension and revision.file_extension != file_type:
            raise SourceIngestionError(
                "source_document_file_type_changed",
                "材料格式与登记信息不一致，请重新上传。",
            )
        expected_uri = source_document_artifact_uri(
            document_id=revision.document_id,
            file_hash=file_hash,
            file_type=file_type,
        )
        if revision.source_uri != expected_uri:
            raise SourceIngestionError(
                "source_document_artifact_mismatch",
                "材料文件引用与修订记录不一致。",
            )
        file_path = source_document_file_path(
            storage=self._storage,
            organization_id=organization_id,
            document_id=revision.document_id,
            file_hash=file_hash,
            file_type=file_type,
        )
        if not file_path.is_file():
            raise SourceIngestionError(
                "source_document_artifact_missing",
                "材料文件不存在，请重新上传。",
            )
        return SourceParsePlan(
            revision_id=revision.revision_id,
            document_id=revision.document_id,
            organization_id=organization_id,
            file_hash=file_hash,
            file_type=file_type,
            content_kind=cast(SourceContentKind, revision.content_kind),
            file_path=file_path,
            already_ready=revision.processing_state == "ready",
            prepared_revision_version=revision.version,
            apply_revision_version=revision.version,
            source_fingerprint=_source_fingerprint(revision),
        )

    async def mark_processing(self, *, plan: SourceParsePlan) -> SourceParsePlan:
        """Persist a truthful running state in its own short transaction."""

        revision = await self._session.scalar(
            select(LearningSourceDocumentRevision)
            .where(LearningSourceDocumentRevision.revision_id == plan.revision_id)
            .with_for_update()
            .limit(1)
        )
        if revision is None or revision.organization_id != plan.organization_id:
            raise SourceIngestionError(
                "source_document_revision_not_found",
                "原始材料修订不存在或不可访问。",
            )
        if revision.processing_state == "ready":
            return replace(
                plan,
                already_ready=True,
                apply_revision_version=revision.version,
            )
        if (
            revision.status != "working"
            or revision.file_hash != plan.file_hash
            or revision.version != plan.prepared_revision_version
            or _source_fingerprint(revision) != plan.source_fingerprint
        ):
            raise SourceIngestionError(
                "source_document_revision_changed",
                "原始材料修订已变化，本次任务已停止。",
            )
        revision.processing_state = "processing"
        revision.processing_stage = "extracting"
        revision.parse_status = "pending"
        revision.failure_code = None
        revision.failure_message = None
        revision.processed_at = None
        revision.version += 1
        revision.content_hash = source_revision_content_hash(revision)
        document = await self._load_document(plan)
        if document.working_revision_id != revision.revision_id:
            raise SourceIngestionError(
                "source_document_revision_changed",
                "材料工作修订已变化，本次任务已停止。",
            )
        document.version += 1
        document.updated_at = datetime.now(UTC)
        await self._session.flush([revision, document])
        return replace(plan, apply_revision_version=revision.version)

    async def apply(
        self,
        *,
        plan: SourceParsePlan,
        parser_result: SourceProcessingResult,
    ) -> SourceParseOutcome:
        revision = await self._session.scalar(
            select(LearningSourceDocumentRevision)
            .where(
                LearningSourceDocumentRevision.revision_id == plan.revision_id
            )
            .with_for_update()
            .limit(1)
        )
        if revision is None or revision.organization_id != plan.organization_id:
            raise SourceIngestionError(
                "source_document_revision_not_found",
                "原始材料修订不存在或不可访问。",
            )
        if (
            revision.file_hash != plan.file_hash
            or revision.version != plan.apply_revision_version
            or _source_fingerprint(revision) != plan.source_fingerprint
        ):
            raise SourceIngestionError(
                "source_document_revision_changed",
                "原始材料修订已变化，本次解析结果没有写入。",
            )
        if revision.processing_state == "ready":
            return self.ready_outcome(plan)
        if revision.status != "working":
            raise SourceIngestionError(
                "source_document_revision_changed",
                "原始材料修订已变化，本次解析结果没有写入。",
            )

        processing_state = parser_result.processing_state
        ready = processing_state == "ready"
        revision.parse_status = "ready" if ready else "failed"
        revision.processing_state = processing_state
        revision.processing_stage = "completed" if ready else "preview_incomplete"
        revision.parser_version = SOURCE_DOCUMENT_PARSER_VERSION
        revision.preview_version = PREVIEW_VERSION
        revision.preview_manifest_json = dict(parser_result.manifest)
        revision.page_count = parser_result.page_count
        revision.duration_ms = parser_result.duration_ms
        revision.failure_code = parser_result.error_code
        revision.failure_message = parser_result.error_message
        revision.processed_at = datetime.now(UTC)
        revision.version += 1
        revision.content_hash = source_revision_content_hash(revision)

        document = await self._load_document(plan)
        if document.working_revision_id != revision.revision_id:
            raise SourceIngestionError(
                "source_document_revision_changed",
                "材料工作修订已变化，本次处理结果没有写入。",
            )
        await self._persist_anchors(plan=plan, anchors=parser_result.anchors)
        document.version += 1
        document.updated_at = datetime.now(UTC)
        await self._session.flush([revision, document])

        if ready:
            return self.ready_outcome(plan, parser_result=parser_result)
        return SourceParseOutcome(
            revision_id=plan.revision_id,
            document_id=plan.document_id,
            parse_status="failed",
            processing_state=processing_state,
            chunk_count=parser_result.chunk_count,
            artifact_available=parser_result.artifact_available,
            anchor_count=len(parser_result.anchors),
            page_count=parser_result.page_count,
            duration_ms=parser_result.duration_ms,
            missing_pages=tuple(
                int(item)
                for item in parser_result.manifest.get("missing_pages", [])
                if isinstance(item, int) and item > 0
            ),
            error_code=parser_result.error_code,
        )

    def ready_outcome(
        self,
        plan: SourceParsePlan,
        *,
        parser_result: SourceProcessingResult | None = None,
    ) -> SourceParseOutcome:
        chunk_count = 0
        artifact_available = False
        if parser_result is not None:
            chunk_count = parser_result.chunk_count
            artifact_available = parser_result.artifact_available
        else:
            artifact = self._storage.load_parse_artifact(plan.file_path)
            if artifact is not None:
                chunks = artifact.get("chunks")
                chunk_count = len(chunks) if isinstance(chunks, list) else 0
                artifact_available = True
        return SourceParseOutcome(
            revision_id=plan.revision_id,
            document_id=plan.document_id,
            parse_status="ready",
            processing_state="ready",
            chunk_count=chunk_count,
            artifact_available=artifact_available,
            anchor_count=(len(parser_result.anchors) if parser_result is not None else 0),
            page_count=(parser_result.page_count if parser_result is not None else None),
            duration_ms=(parser_result.duration_ms if parser_result is not None else None),
            missing_pages=(),
        )

    async def _load_document(self, plan: SourceParsePlan) -> LearningSourceDocument:
        document = await self._session.scalar(
            select(LearningSourceDocument)
            .where(LearningSourceDocument.document_id == plan.document_id)
            .with_for_update()
            .limit(1)
        )
        if document is None or document.organization_id != plan.organization_id:
            raise SourceIngestionError(
                "source_document_not_found",
                "原始材料不存在或不可访问。",
            )
        return document

    async def _persist_anchors(
        self,
        *,
        plan: SourceParsePlan,
        anchors: tuple[dict[str, Any], ...],
    ) -> None:
        if not anchors:
            return
        existing = list(
            (
                await self._session.execute(
                    select(LearningSourceAnchor).where(
                        LearningSourceAnchor.source_revision_id == plan.revision_id
                    )
                )
            ).scalars()
        )
        by_key = {item.anchor_key: item for item in existing}
        for raw in anchors:
            anchor_key = str(raw["anchor_key"])
            locator = dict(raw["locator"])
            fingerprint = hashlib.sha256(
                json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            current = by_key.get(anchor_key)
            if current is not None:
                if current.fingerprint != fingerprint:
                    raise SourceIngestionError(
                        "source_anchor_changed",
                        "来源定位与同一文件的历史处理结果不一致，本次结果没有写入。",
                    )
                continue
            self._session.add(
                LearningSourceAnchor(
                    anchor_id=str(uuid.uuid4()),
                    organization_id=plan.organization_id,
                    source_revision_id=plan.revision_id,
                    anchor_key=anchor_key,
                    label=str(raw["label"]),
                    locator_type=str(locator["type"]),
                    locator_json=locator,
                    excerpt_hash=str(raw["excerpt_hash"]),
                    idempotency_key_hash=hashlib.sha256(
                        f"source-process:{plan.revision_id}:{anchor_key}".encode()
                    ).hexdigest(),
                    fingerprint=fingerprint,
                    created_by="source-processing-task",
                    created_at=datetime.now(UTC),
                )
            )


class SourceIngestionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


async def parse_source_document(plan: SourceParsePlan) -> SourceProcessingResult:
    return await process_source_file(
        file_path=plan.file_path,
        file_type=plan.file_type,
        content_kind=plan.content_kind,
        storage=get_document_storage_service(),
    )


__all__ = [
    "SOURCE_DOCUMENT_PARSE_TASK_TYPE",
    "SOURCE_DOCUMENT_PARSER_VERSION",
    "SUPPORTED_SOURCE_FILE_TYPES",
    "SourceDocumentIngestionProcessor",
    "SourceFileType",
    "SourceIngestionError",
    "SourceParseOutcome",
    "SourceParsePlan",
    "parse_source_document",
    "source_document_artifact_uri",
    "source_document_file_path",
    "source_document_storage_namespace",
    "source_document_storage_object_id",
]
