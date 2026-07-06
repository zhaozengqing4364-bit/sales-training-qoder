from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import json_dict_or_empty
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.curriculum_practice_adapter import (
    LearningChapterCreate,
    LearningContentContract,
    archive_draft_learning_content,
    create_learning_content_with_chapters,
)
from sales_trainer.services.operation_log_service import OperationLogService

BUSINESS_ETIQUETTE_RESOURCE_TYPE = "business_etiquette_training_pack"
DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY = "business_etiquette_v1"
DEFAULT_BUSINESS_ETIQUETTE_CONTENT_TITLE = "商务礼仪：新人的第一本职业素养手册"
DEFAULT_BUSINESS_ETIQUETTE_OWNER = "新人训练路径 / 商务礼仪训练包"
DEFAULT_BUSINESS_ETIQUETTE_SOURCE = "sales_trainer.business_etiquette_import"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class BusinessEtiquetteImportSettings:
    training_pack_key: str = DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY
    supported_extensions: tuple[str, ...] = (".md", ".markdown")
    supported_content_types: tuple[str, ...] = (
        "text/markdown",
        "text/plain",
        "application/octet-stream",
    )
    max_file_size_bytes: int = 2 * 1024 * 1024
    allow_overwrite_draft: bool = True
    expected_original_chapter_count: int = 8
    content_title: str = DEFAULT_BUSINESS_ETIQUETTE_CONTENT_TITLE
    owner: str = DEFAULT_BUSINESS_ETIQUETTE_OWNER
    source: str = DEFAULT_BUSINESS_ETIQUETTE_SOURCE

    def validate(self) -> None:
        if not self.training_pack_key.strip():
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]",
                "商务礼仪训练包 key 不能为空。",
                500,
            )
        if not self.supported_extensions:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]",
                "商务礼仪导入格式配置缺失。",
                500,
            )
        if self.max_file_size_bytes <= 0:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]",
                "商务礼仪导入文件大小配置非法。",
                500,
            )
        if self.expected_original_chapter_count <= 0:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]",
                "商务礼仪原始章节数量配置非法。",
                500,
            )


@dataclass(frozen=True, slots=True)
class ParsedKnowledgePoint:
    title: str
    order_index: int
    line_number: int


@dataclass(frozen=True, slots=True)
class ParsedMicroChapter:
    title: str
    order_index: int
    line_number: int
    knowledge_points: list[ParsedKnowledgePoint]


@dataclass(frozen=True, slots=True)
class ParsedOriginalChapter:
    title: str
    order_index: int
    line_number: int
    markdown: str
    micro_chapters: list[ParsedMicroChapter]


@dataclass(frozen=True, slots=True)
class ParsedBusinessEtiquetteDocument:
    title: str
    front_matter_markdown: str
    original_chapters: list[ParsedOriginalChapter]
    micro_chapter_count: int
    knowledge_point_count: int


class BusinessEtiquetteImportServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessEtiquetteImportService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        settings: BusinessEtiquetteImportSettings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or BusinessEtiquetteImportSettings()
        self._asset_revisions = SalesTrainerAssetRevisionService(db)
        self._logs = OperationLogService(db)

    async def import_markdown(
        self,
        *,
        file_bytes: bytes,
        source_filename: str,
        content_type: str | None,
        actor: User,
        training_pack_key: str | None = None,
        allow_overwrite_draft: bool | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        settings = self._settings
        settings.validate()
        logical_id = (training_pack_key or settings.training_pack_key).strip()
        if not logical_id:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_CONFIG_INVALID]",
                "商务礼仪训练包 key 不能为空。",
                500,
            )

        overwrite_draft = (
            settings.allow_overwrite_draft
            if allow_overwrite_draft is None
            else allow_overwrite_draft
        )
        self._validate_file(
            file_bytes=file_bytes,
            source_filename=source_filename,
            content_type=content_type,
            settings=settings,
        )
        raw_markdown = _decode_markdown(file_bytes)
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        parsed = parse_business_etiquette_markdown(
            raw_markdown,
            expected_original_chapter_count=settings.expected_original_chapter_count,
        )

        try:
            existing_working_revision = (
                await self._asset_revisions.latest_working_revision(
                    resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                    logical_id=logical_id,
                )
            )
            if existing_working_revision is not None and not overwrite_draft:
                raise BusinessEtiquetteImportServiceError(
                    "[BUSINESS_ETIQUETTE_DRAFT_EXISTS]",
                    "商务礼仪训练包已有未发布草稿，请先发布、回滚或允许覆盖草稿。",
                    409,
                )
            if existing_working_revision is not None and overwrite_draft:
                await self._archive_previous_draft_content(existing_working_revision)

            imported_at = datetime.now(UTC)
            learning_content = await create_learning_content_with_chapters(
                self._db,
                title=parsed.title or settings.content_title,
                summary="商务礼仪训练包导入草稿，发布前不会对学员生效。",
                owner=settings.owner,
                source=_source_value(settings.source, logical_id, source_filename),
                status="draft",
                content_hash=content_hash,
                actor_id=str(actor.user_id),
                chapters=[
                    LearningChapterCreate(
                        title=chapter.title,
                        content=chapter.markdown,
                        order_index=chapter.order_index,
                    )
                    for chapter in parsed.original_chapters
                ],
            )

            payload = _revision_payload(
                parsed=parsed,
                logical_id=logical_id,
                learning_content=learning_content,
                source_filename=source_filename,
                content_type=content_type,
                file_size_bytes=len(file_bytes),
                content_hash=content_hash,
                imported_at=imported_at,
                actor=actor,
                ai_suggestions_enabled=False,
            )
            revision = await self._asset_revisions.save_working_revision(
                resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                logical_id=logical_id,
                payload=payload,
                actor=actor,
                change_class="semantic",
                source_revision_id=(
                    str(existing_working_revision.revision_id)
                    if existing_working_revision is not None
                    else None
                ),
                reason=reason or "导入商务礼仪 Markdown 资料草稿",
                trace_id=trace_id,
            )
            active_revision = await self._asset_revisions.active_revision(
                resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                logical_id=logical_id,
            )
            await self._logs.record(
                actor=actor,
                action="business_etiquette_training_pack.markdown_imported",
                target_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
                target_id=logical_id,
                request_id=trace_id,
                metadata={
                    "training_pack_key": logical_id,
                    "learning_content_id": learning_content.learning_content_id,
                    "working_revision_id": str(revision.revision_id),
                    "working_revision_no": revision.revision_no,
                    "active_revision_id": (
                        str(active_revision.revision_id)
                        if active_revision is not None
                        else None
                    ),
                    "source_filename": source_filename,
                    "content_hash": content_hash,
                    "file_size_bytes": len(file_bytes),
                    "original_chapter_count": len(parsed.original_chapters),
                    "micro_chapter_count": parsed.micro_chapter_count,
                    "knowledge_point_count": parsed.knowledge_point_count,
                    "overwrite_draft": overwrite_draft,
                    "trace_id": trace_id,
                },
            )
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise

        return _import_response(
            parsed=parsed,
            logical_id=logical_id,
            learning_content=learning_content,
            revision=revision,
            active_revision=active_revision,
            source_filename=source_filename,
            content_type=content_type,
            file_size_bytes=len(file_bytes),
            content_hash=content_hash,
            imported_at=imported_at,
            allow_overwrite_draft=overwrite_draft,
            ai_suggestions_enabled=False,
        )

    def _validate_file(
        self,
        *,
        file_bytes: bytes,
        source_filename: str,
        content_type: str | None,
        settings: BusinessEtiquetteImportSettings,
    ) -> None:
        if not source_filename.strip():
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_FILE_INVALID]",
                "导入文件名不能为空。",
            )
        extension = PurePath(source_filename).suffix.lower()
        if extension not in settings.supported_extensions:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_FORMAT_UNSUPPORTED]",
                "仅支持导入 Markdown 文件。",
                415,
            )
        normalized_content_type = (content_type or "").split(";")[0].strip().lower()
        if (
            normalized_content_type
            and normalized_content_type not in settings.supported_content_types
        ):
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_FORMAT_UNSUPPORTED]",
                "导入文件类型不是已配置的 Markdown 类型。",
                415,
            )
        if not file_bytes:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_FILE_EMPTY]",
                "导入文件不能为空。",
            )
        if len(file_bytes) > settings.max_file_size_bytes:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_FILE_TOO_LARGE]",
                "导入文件超过后台配置的最大大小。",
                413,
            )

    async def _archive_previous_draft_content(
        self,
        revision: SalesTrainerAssetRevision,
    ) -> None:
        payload = json_dict_or_empty(revision.payload_json)
        learning_content_id = payload.get("learning_content_id")
        if not isinstance(learning_content_id, str) or not learning_content_id:
            return
        await archive_draft_learning_content(self._db, learning_content_id)


def parse_business_etiquette_markdown(
    raw_markdown: str,
    *,
    expected_original_chapter_count: int,
) -> ParsedBusinessEtiquetteDocument:
    lines = raw_markdown.splitlines()
    headings = _collect_headings(lines)
    if not headings:
        raise BusinessEtiquetteImportServiceError(
            "[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]",
            "Markdown 中没有可解析的标题。",
            422,
        )
    h1_headings = [heading for heading in headings if heading["level"] == 1]
    if len(h1_headings) < expected_original_chapter_count + 1:
        raise BusinessEtiquetteImportServiceError(
            "[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]",
            "Markdown 未包含完整的商务礼仪全书标题和 8 个原始章节。",
            422,
        )

    book_heading = h1_headings[0]
    original_headings = h1_headings[1:]
    if len(original_headings) != expected_original_chapter_count:
        raise BusinessEtiquetteImportServiceError(
            "[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]",
            f"Markdown 原始章节数量应为 {expected_original_chapter_count} 个。",
            422,
        )

    front_matter_markdown = "\n".join(
        lines[book_heading["line_index"] + 1 : original_headings[0]["line_index"]]
    ).strip()
    original_chapters: list[ParsedOriginalChapter] = []
    micro_chapter_count = 0
    knowledge_point_count = 0
    for index, heading in enumerate(original_headings, start=1):
        next_line_index = (
            original_headings[index]["line_index"]
            if index < len(original_headings)
            else len(lines)
        )
        body_lines = lines[heading["line_index"] + 1 : next_line_index]
        micro_chapters = _parse_micro_chapters(
            body_lines,
            line_offset=heading["line_index"] + 2,
        )
        if not micro_chapters:
            raise BusinessEtiquetteImportServiceError(
                "[BUSINESS_ETIQUETTE_IMPORT_STRUCTURE_INVALID]",
                f"原始章节“{heading['title']}”缺少 H2 微章节。",
                422,
            )
        micro_chapter_count += len(micro_chapters)
        knowledge_point_count += sum(
            len(micro.knowledge_points) for micro in micro_chapters
        )
        original_chapters.append(
            ParsedOriginalChapter(
                title=str(heading["title"]),
                order_index=index,
                line_number=int(heading["line_index"]) + 1,
                markdown="\n".join(body_lines).strip(),
                micro_chapters=micro_chapters,
            )
        )

    return ParsedBusinessEtiquetteDocument(
        title=str(book_heading["title"]),
        front_matter_markdown=front_matter_markdown,
        original_chapters=original_chapters,
        micro_chapter_count=micro_chapter_count,
        knowledge_point_count=knowledge_point_count,
    )


def _collect_headings(lines: list[str]) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match is None:
            continue
        headings.append(
            {
                "level": len(match.group(1)),
                "title": _clean_heading_title(match.group(2)),
                "line_index": line_index,
            }
        )
    return headings


def _parse_micro_chapters(
    body_lines: list[str],
    *,
    line_offset: int,
) -> list[ParsedMicroChapter]:
    headings = _collect_headings(body_lines)
    h2_headings = [heading for heading in headings if heading["level"] == 2]
    micro_chapters: list[ParsedMicroChapter] = []
    for index, heading in enumerate(h2_headings, start=1):
        next_line_index = (
            h2_headings[index]["line_index"]
            if index < len(h2_headings)
            else len(body_lines)
        )
        knowledge_points = [
            ParsedKnowledgePoint(
                title=str(inner["title"]),
                order_index=knowledge_index,
                line_number=line_offset + int(inner["line_index"]),
            )
            for knowledge_index, inner in enumerate(
                (
                    inner
                    for inner in headings
                    if inner["level"] == 3
                    and int(heading["line_index"])
                    < int(inner["line_index"])
                    < next_line_index
                ),
                start=1,
            )
        ]
        micro_chapters.append(
            ParsedMicroChapter(
                title=str(heading["title"]),
                order_index=index,
                line_number=line_offset + int(heading["line_index"]),
                knowledge_points=knowledge_points,
            )
        )
    return micro_chapters


def _clean_heading_title(raw_title: str) -> str:
    title = raw_title.strip().strip("#").strip()
    title = re.sub(r"^\*{1,3}(.+?)\*{1,3}$", r"\1", title).strip()
    return title


def _decode_markdown(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BusinessEtiquetteImportServiceError(
            "[BUSINESS_ETIQUETTE_IMPORT_ENCODING_INVALID]",
            "Markdown 文件必须使用 UTF-8 编码。",
            415,
        ) from exc


def _source_value(source: str, logical_id: str, source_filename: str) -> str:
    value = f"{source}:{logical_id}:{PurePath(source_filename).name}"
    return value[:300]


def _revision_payload(
    *,
    parsed: ParsedBusinessEtiquetteDocument,
    logical_id: str,
    learning_content: LearningContentContract,
    source_filename: str,
    content_type: str | None,
    file_size_bytes: int,
    content_hash: str,
    imported_at: datetime,
    actor: User,
    ai_suggestions_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "training_pack_key": logical_id,
        "learning_content_id": learning_content.learning_content_id,
        "learning_content_status": learning_content.status,
        "book_title": parsed.title,
        "front_matter_markdown": parsed.front_matter_markdown,
        "source_filename": source_filename,
        "content_type": content_type,
        "file_size_bytes": file_size_bytes,
        "content_hash": content_hash,
        "imported_by": str(actor.user_id),
        "imported_at": imported_at.isoformat(),
        "ai_suggestions_enabled": ai_suggestions_enabled,
        "original_chapters": [
            _chapter_payload(chapter) for chapter in parsed.original_chapters
        ],
        "original_chapter_count": len(parsed.original_chapters),
        "micro_chapter_count": parsed.micro_chapter_count,
        "knowledge_point_count": parsed.knowledge_point_count,
    }


def _chapter_payload(chapter: ParsedOriginalChapter) -> dict[str, Any]:
    return {
        "title": chapter.title,
        "order_index": chapter.order_index,
        "line_number": chapter.line_number,
        "content_hash": hashlib.sha256(chapter.markdown.encode("utf-8")).hexdigest(),
        "micro_chapters": [
            {
                "title": micro.title,
                "order_index": micro.order_index,
                "line_number": micro.line_number,
                "knowledge_points": [
                    {
                        "title": knowledge.title,
                        "order_index": knowledge.order_index,
                        "line_number": knowledge.line_number,
                    }
                    for knowledge in micro.knowledge_points
                ],
            }
            for micro in chapter.micro_chapters
        ],
    }


def _import_response(
    *,
    parsed: ParsedBusinessEtiquetteDocument,
    logical_id: str,
    learning_content: LearningContentContract,
    revision: SalesTrainerAssetRevision,
    active_revision: SalesTrainerAssetRevision | None,
    source_filename: str,
    content_type: str | None,
    file_size_bytes: int,
    content_hash: str,
    imported_at: datetime,
    allow_overwrite_draft: bool,
    ai_suggestions_enabled: bool,
) -> dict[str, Any]:
    return {
        "training_pack_key": logical_id,
        "learning_content_id": learning_content.learning_content_id,
        "learning_content_status": learning_content.status,
        "working_revision_id": str(revision.revision_id),
        "working_revision_no": revision.revision_no,
        "active_revision_id": (
            str(active_revision.revision_id) if active_revision is not None else None
        ),
        "active_revision_no": (
            active_revision.revision_no if active_revision is not None else None
        ),
        "has_unpublished_revision": True,
        "source_filename": source_filename,
        "content_type": content_type,
        "file_size_bytes": file_size_bytes,
        "content_hash": content_hash,
        "imported_at": imported_at.isoformat(),
        "allow_overwrite_draft": allow_overwrite_draft,
        "ai_suggestions_enabled": ai_suggestions_enabled,
        "book_title": parsed.title,
        "original_chapter_count": len(parsed.original_chapters),
        "micro_chapter_count": parsed.micro_chapter_count,
        "knowledge_point_count": parsed.knowledge_point_count,
        "chapters": [_chapter_payload(chapter) for chapter in parsed.original_chapters],
    }
