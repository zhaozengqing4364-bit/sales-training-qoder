from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.typing import json_dict_or_empty, orm_scalar
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.exam_paper_revision_constants import PAPER_RESOURCE_TYPE
from sales_trainer.services.exam_paper_store import require_paper


class ExamPaperRevisionHistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_paper_revisions(self, paper_id: str) -> list[dict[str, object]]:
        paper = await require_paper(self._db, paper_id)
        revision_service = SalesTrainerAssetRevisionService(self._db)
        active_revision = await revision_service.active_revision(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=orm_scalar(paper.paper_id, str),
        )
        revisions = await revision_service.list_revisions(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=orm_scalar(paper.paper_id, str),
        )
        active_revision_id = (
            str(active_revision.revision_id) if active_revision is not None else None
        )
        return [
            _paper_revision_response_item(
                revision,
                active_revision_id=active_revision_id,
            )
            for revision in revisions
        ]


def _paper_revision_response_item(
    revision: SalesTrainerAssetRevision,
    *,
    active_revision_id: str | None,
) -> dict[str, object]:
    payload: dict[str, Any] = json_dict_or_empty(revision.payload_json)
    questions = payload.get("questions")
    question_count = len(questions) if isinstance(questions, list) else 0
    revision_id = str(revision.revision_id)
    status = str(revision.status)
    return {
        "revision_id": revision_id,
        "revision_no": int(revision.revision_no),
        "status": status,
        "change_class": str(revision.change_class),
        "title": payload.get("title") if isinstance(payload.get("title"), str) else None,
        "question_count": question_count,
        "is_active": revision_id == active_revision_id,
        "is_working": status == "working",
        "source_revision_id": revision.source_revision_id,
        "payload_hash": str(revision.payload_hash),
        "reason": revision.reason,
        "trace_id": revision.trace_id,
        "created_by": revision.created_by,
        "published_by": revision.published_by,
        "created_at": revision.created_at,
        "published_at": revision.published_at,
    }
