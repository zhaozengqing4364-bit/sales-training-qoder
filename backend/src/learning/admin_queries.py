"""Organization-scoped query models for the slice-2 governance workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.contracts import LearningActor, QuestionCandidateContent
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestion,
    LearningQuestionCandidate,
    LearningQuestionGenerationBatch,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningSourceDocument,
    LearningSourceDocumentRevision,
    LearningUnit,
    LearningUnitRevision,
)

LearningResourceType = Literal[
    "source_document", "learning_unit", "question", "quiz"
]


class PageResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[Any, ...]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool


class LearningResourceListItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: LearningResourceType
    resource_id: str
    stable_key: str
    title: str
    status: str
    working_revision_id: str | None
    published_revision_id: str | None
    version: int
    updated_at: datetime


class LearningResourceDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["learning_resource_detail_v1"] = (
        "learning_resource_detail_v1"
    )
    generated_at: datetime
    data_freshness: Literal["fresh"] = "fresh"
    capabilities: tuple[str, ...]
    resource: LearningResourceListItem
    working_revision: dict[str, Any] | None
    published_revision: dict[str, Any] | None


class QuestionCandidateListItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    batch_id: str
    status: str
    version: int
    risk_level: Literal["normal", "high"]
    content: QuestionCandidateContent
    gate_status: str
    gate_results: dict[str, Any]
    source_revision_id: str
    learning_unit_revision_id: str
    prompt_revision_id: str
    model_routing_revision_id: str
    invocation_id: str
    reviewed_by: str | None
    review_reason: str | None
    created_at: datetime


class LearningAdminQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_resources(
        self,
        *,
        actor: LearningActor,
        resource_type: LearningResourceType,
        status: str | None,
        search: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> PageResult:
        capability: str
        model: Any
        id_column: Any
        title_column: Any
        capability, model, id_column, title_column = {
            "source_document": (
                "learning.source.manage",
                LearningSourceDocument,
                LearningSourceDocument.document_id,
                LearningSourceDocument.title,
            ),
            "learning_unit": (
                "learning.content.manage",
                LearningUnit,
                LearningUnit.unit_id,
                LearningUnit.title,
            ),
            "question": (
                "learning.question.review",
                LearningQuestion,
                LearningQuestion.question_id,
                LearningQuestion.stable_key,
            ),
            "quiz": (
                "learning.quiz.manage",
                LearningQuiz,
                LearningQuiz.quiz_id,
                LearningQuiz.title,
            ),
        }[resource_type]
        self._require(actor, capability)
        if sort not in {"-updated_at", "updated_at", "title"}:
            self._invalid_query("sort")
        query = select(model).where(model.organization_id == actor.organization_id)
        count_query = select(func.count(id_column)).where(
            model.organization_id == actor.organization_id
        )
        if status:
            query = query.where(model.status == status)
            count_query = count_query.where(model.status == status)
        if search and search.strip():
            pattern = f"%{search.strip().casefold()}%"
            predicate = or_(
                func.lower(model.stable_key).like(pattern),
                func.lower(title_column).like(pattern),
            )
            query = query.where(predicate)
            count_query = count_query.where(predicate)
        order = {
            "-updated_at": (model.updated_at.desc(), id_column.asc()),
            "updated_at": (model.updated_at.asc(), id_column.asc()),
            "title": (title_column.asc(), id_column.asc()),
        }[sort]
        total = int(await self._session.scalar(count_query) or 0)
        rows = (
            await self._session.execute(
                query.order_by(*order).offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        items = tuple(
            LearningResourceListItem(
                resource_type=resource_type,
                resource_id=str(getattr(row, id_column.key)),
                stable_key=row.stable_key,
                title=str(getattr(row, title_column.key)),
                status=row.status,
                working_revision_id=row.working_revision_id,
                published_revision_id=row.published_revision_id,
                version=row.version,
                updated_at=row.updated_at,
            )
            for row in rows
        )
        return PageResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

    async def get_resource_detail(
        self,
        *,
        actor: LearningActor,
        resource_type: LearningResourceType,
        resource_id: str,
    ) -> LearningResourceDetail:
        capability: str
        model: Any
        revision_model: Any
        id_column: Any
        title_column: Any
        capability, model, revision_model, id_column, title_column = {
            "source_document": (
                "learning.source.manage",
                LearningSourceDocument,
                LearningSourceDocumentRevision,
                LearningSourceDocument.document_id,
                LearningSourceDocument.title,
            ),
            "learning_unit": (
                "learning.content.manage",
                LearningUnit,
                LearningUnitRevision,
                LearningUnit.unit_id,
                LearningUnit.title,
            ),
            "question": (
                "learning.question.review",
                LearningQuestion,
                LearningQuestionRevision,
                LearningQuestion.question_id,
                LearningQuestion.stable_key,
            ),
            "quiz": (
                "learning.quiz.manage",
                LearningQuiz,
                LearningQuizRevision,
                LearningQuiz.quiz_id,
                LearningQuiz.title,
            ),
        }[resource_type]
        self._require(actor, capability)
        resource = await self._session.get(model, resource_id)
        if resource is None or resource.organization_id != actor.organization_id:
            raise LearningGovernanceError(
                "[LEARNING_RESOURCE_NOT_FOUND]",
                "训练资源不存在或不可访问。",
                404,
            )
        revision_ids = tuple(
            value
            for value in (
                resource.working_revision_id,
                resource.published_revision_id,
            )
            if value is not None
        )
        revisions = (
            []
            if not revision_ids
            else (
                await self._session.execute(
                    select(revision_model).where(
                        revision_model.revision_id.in_(revision_ids)
                    )
                )
            ).scalars().all()
        )
        by_id = {revision.revision_id: revision for revision in revisions}
        item = LearningResourceListItem(
            resource_type=resource_type,
            resource_id=str(getattr(resource, id_column.key)),
            stable_key=resource.stable_key,
            title=str(getattr(resource, title_column.key)),
            status=resource.status,
            working_revision_id=resource.working_revision_id,
            published_revision_id=resource.published_revision_id,
            version=resource.version,
            updated_at=resource.updated_at,
        )
        return LearningResourceDetail(
            generated_at=datetime.now(UTC),
            capabilities=("view", "edit", "validate", "archive"),
            resource=item,
            working_revision=self._revision_detail(
                resource_type,
                by_id.get(resource.working_revision_id),
            ),
            published_revision=self._revision_detail(
                resource_type,
                by_id.get(resource.published_revision_id),
            ),
        )

    async def list_question_candidates(
        self,
        *,
        actor: LearningActor,
        status: str | None,
        batch_id: str | None,
        source_revision_id: str | None,
        question_type: str | None,
        risk_level: str | None,
        search: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> PageResult:
        self._require(actor, "learning.question.review")
        if sort not in {"-created_at", "risk_level", "status"}:
            self._invalid_query("sort")
        if risk_level not in {None, "normal", "high"}:
            self._invalid_query("risk_level")
        risk_expression = case(
            (
                or_(
                    LearningQuestionCandidate.question_type == "short_answer",
                    LearningQuestionCandidate.gate_status == "failed",
                ),
                "high",
            ),
            else_="normal",
        )
        query = (
            select(LearningQuestionCandidate, LearningQuestionGenerationBatch)
            .join(
                LearningQuestionGenerationBatch,
                LearningQuestionGenerationBatch.batch_id
                == LearningQuestionCandidate.batch_id,
            )
            .where(
                LearningQuestionCandidate.organization_id == actor.organization_id
            )
        )
        filters = []
        if status:
            filters.append(LearningQuestionCandidate.status == status)
        if batch_id:
            filters.append(LearningQuestionCandidate.batch_id == batch_id)
        if source_revision_id:
            filters.append(
                LearningQuestionGenerationBatch.source_revision_id
                == source_revision_id
            )
        if question_type:
            filters.append(
                LearningQuestionCandidate.question_type == question_type
            )
        if risk_level:
            filters.append(risk_expression == risk_level)
        if search and search.strip():
            filters.append(
                func.lower(cast(LearningQuestionCandidate.content_json, String)).like(
                    f"%{search.strip().casefold()}%"
                )
            )
        if filters:
            query = query.where(*filters)
        count_query = select(func.count()).select_from(query.subquery())
        total = int(await self._session.scalar(count_query) or 0)
        order = {
            "-created_at": (
                LearningQuestionCandidate.created_at.desc(),
                LearningQuestionCandidate.candidate_id.asc(),
            ),
            "risk_level": (
                risk_expression.desc(),
                LearningQuestionCandidate.created_at.desc(),
                LearningQuestionCandidate.candidate_id.asc(),
            ),
            "status": (
                LearningQuestionCandidate.status.asc(),
                LearningQuestionCandidate.created_at.desc(),
                LearningQuestionCandidate.candidate_id.asc(),
            ),
        }[sort]
        rows = (
            await self._session.execute(
                query.order_by(*order).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        items = tuple(
            QuestionCandidateListItem(
                candidate_id=candidate.candidate_id,
                batch_id=candidate.batch_id,
                status=candidate.status,
                version=candidate.version,
                risk_level=(
                    "high"
                    if candidate.question_type == "short_answer"
                    or candidate.gate_status == "failed"
                    else "normal"
                ),
                content=QuestionCandidateContent.model_validate(
                    candidate.content_json
                ),
                gate_status=candidate.gate_status,
                gate_results=dict(candidate.gate_results_json),
                source_revision_id=batch.source_revision_id,
                learning_unit_revision_id=batch.learning_unit_revision_id,
                prompt_revision_id=candidate.prompt_revision_id,
                model_routing_revision_id=candidate.model_routing_revision_id,
                invocation_id=candidate.invocation_id,
                reviewed_by=candidate.reviewed_by,
                review_reason=candidate.review_reason,
                created_at=candidate.created_at,
            )
            for candidate, batch in rows
        )
        return PageResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

    @staticmethod
    def _require(actor: LearningActor, capability: str) -> None:
        if capability not in actor.capabilities:
            raise LearningGovernanceError(
                "[LEARNING_PERMISSION_DENIED]", "没有查看此训练资源的权限。", 403
            )

    @staticmethod
    def _invalid_query(field: str) -> None:
        raise LearningGovernanceError(
            "[QUERY_PARAMETER_INVALID]",
            "筛选或排序条件无效，请调整后重试。",
            422,
            details={"field": field},
        )

    @staticmethod
    def _revision_detail(
        resource_type: LearningResourceType,
        revision: Any | None,
    ) -> dict[str, Any] | None:
        if revision is None:
            return None
        common = {
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "status": revision.status,
            "version": revision.version,
            "content_hash": revision.content_hash,
        }
        if resource_type == "source_document":
            manifest = (
                revision.preview_manifest_json
                if isinstance(revision.preview_manifest_json, dict)
                else {}
            )
            pages = manifest.get("pages")
            safe_pages = [
                {
                    "page": item.get("page"),
                    "status": item.get("status"),
                    "text": item.get("text", ""),
                }
                for item in (pages if isinstance(pages, list) else [])
                if isinstance(item, dict)
            ]
            sections = manifest.get("sections")
            safe_sections = [
                {
                    "index": item.get("index"),
                    "text": item.get("text", ""),
                    "locator": item.get("locator", {}),
                }
                for item in (sections if isinstance(sections, list) else [])
                if isinstance(item, dict)
            ]
            access_base = (
                "/api/v1/admin/newcomer-training/source-revisions/"
                f"{revision.revision_id}"
            )
            return {
                **common,
                "revision_label": revision.revision_label,
                "working_revision": {
                    "revision_label": revision.revision_label,
                    "source_type": revision.source_type,
                    "content_kind": revision.content_kind,
                    **(
                        {"external_url": revision.source_uri}
                        if revision.source_type == "url"
                        else {}
                    ),
                    "parse_status": revision.parse_status,
                    "processing_state": revision.processing_state,
                    "processing_stage": revision.processing_stage,
                    "original_filename": revision.original_filename,
                    "trusted_mime_type": revision.trusted_mime_type,
                    "file_size_bytes": revision.file_size_bytes,
                    "language": revision.language,
                    "page_count": revision.page_count,
                    "duration_ms": revision.duration_ms,
                    "failure_message": revision.failure_message,
                    **(
                        {"manual_content": revision.manual_content}
                        if revision.source_type == "manual"
                        else {}
                    ),
                },
                "preview": {
                    "kind": manifest.get("kind", revision.content_kind),
                    "version": manifest.get("version"),
                    "pages": safe_pages,
                    "sections": safe_sections,
                    "missing_pages": list(manifest.get("missing_pages") or []),
                    "duration_ms": revision.duration_ms,
                },
                "access": {
                    "original": (
                        f"{access_base}/original"
                        if revision.source_type == "file"
                        else None
                    ),
                    "preview_page_template": (
                        f"{access_base}/preview/pages/{{page}}"
                        if revision.content_kind == "slide_deck"
                        else None
                    ),
                    "playback": (
                        f"{access_base}/playback"
                        if revision.content_kind in {"demo_video", "example_audio"}
                        else None
                    ),
                },
            }
        if resource_type == "learning_unit":
            return {
                **common,
                "revision_label": revision.revision_label,
                "working_revision": dict(revision.snapshot_json),
                "source_anchor_ids": list(revision.source_anchor_ids_json),
            }
        if resource_type == "question":
            return {
                **common,
                "question_type": revision.question_type,
                "working_revision": dict(revision.content_json),
                "source_anchor_ids": list(revision.source_anchor_ids_json),
                "competency_keys": list(revision.competency_keys_json),
                "source_candidate_id": revision.source_candidate_id,
                "reviewed_by": revision.reviewed_by,
                "review_reason": revision.review_reason,
            }
        return {
            **common,
            "revision_label": revision.revision_label,
            "working_revision": dict(revision.snapshot_json),
            "question_revision_ids": list(
                revision.question_revision_ids_json
            ),
        }


__all__ = [
    "LearningAdminQueryService",
    "LearningResourceListItem",
    "LearningResourceDetail",
    "LearningResourceType",
    "PageResult",
    "QuestionCandidateListItem",
]
