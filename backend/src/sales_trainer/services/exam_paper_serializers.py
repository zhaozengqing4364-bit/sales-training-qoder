from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.typing import json_dict_or_empty, orm_scalar
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerExamPaper,
    SalesTrainerQuizAttempt,
)
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.exam_paper_revision_payloads import (
    paper_revision_questions_for_learner,
)
from sales_trainer.services.quiz_service import QuizService
from sales_trainer.services.unit_service import UnitService


async def serialize_exam_paper(
    db: AsyncSession,
    paper: SalesTrainerExamPaper,
) -> dict[str, Any]:
    unit = await UnitService(db).get_unit(orm_scalar(paper.unit_id, str))
    if unit is None:
        raise ExamPaperSerializationError(
            "[PAPER_BACKING_UNIT_MISSING]",
            "考卷执行单元缺失。",
            409,
        )
    unit_payload = await UnitService(db).serialize_unit(unit)
    revision_service = SalesTrainerAssetRevisionService(db)
    active_revision = await revision_service.active_revision(
        resource_type="sales_trainer_exam_paper",
        logical_id=str(paper.paper_id),
    )
    working_revision = await revision_service.latest_working_revision(
        resource_type="sales_trainer_exam_paper",
        logical_id=str(paper.paper_id),
    )
    active_payload = (
        json_dict_or_empty(active_revision.payload_json)
        if active_revision is not None
        else {}
    )
    revision_questions = (
        paper_revision_questions_for_learner(active_payload)
        if active_payload
        else []
    )
    pass_threshold = orm_scalar(paper.pass_threshold, Decimal, nullable=True)
    return {
        "paper_id": paper.paper_id,
        "paper_key": paper.paper_key,
        "title": paper.title,
        "description": paper.description,
        "module_key": paper.module_key,
        "unit_id": paper.unit_id,
        "pass_threshold": _decimal_to_float(pass_threshold),
        "status": paper.status,
        "created_by": paper.created_by,
        "updated_by": paper.updated_by,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at,
        "questions": revision_questions or unit_payload["questions"],
        "active_revision_id": (
            str(active_revision.revision_id) if active_revision is not None else None
        ),
        "active_revision_no": (
            int(active_revision.revision_no) if active_revision is not None else None
        ),
        "working_revision_id": (
            str(working_revision.revision_id) if working_revision is not None else None
        ),
        "working_revision_no": (
            int(working_revision.revision_no) if working_revision is not None else None
        ),
        "has_unpublished_revision": working_revision is not None,
    }


async def serialize_paper_attempt(
    db: AsyncSession,
    attempt: SalesTrainerQuizAttempt,
) -> dict[str, Any]:
    paper = await _paper_by_unit_id(db, str(attempt.unit_id))
    if paper is None:
        raise ExamPaperSerializationError("[PAPER_NOT_FOUND]", "考卷不存在。", 404)
    revision = await _paper_revision_by_id(db, str(attempt.paper_revision_id))
    payload = await QuizService(db).serialize_attempt(attempt)
    paper_payload: dict[str, Any] = (
        json_dict_or_empty(revision.payload_json) if revision is not None else {}
    )
    attempt_context = _attempt_context_from_answers(payload.get("answers"))
    return {
        **payload,
        "paper_id": paper.paper_id,
        "paper_title": str(paper_payload.get("title") or paper.title),
        "paper_revision_id": (
            str(revision.revision_id) if revision is not None else None
        ),
        "path_key": _context_str(attempt_context, "path_key"),
        "path_revision_id": _context_str(attempt_context, "path_revision_id"),
        "path_revision_no": _context_int(attempt_context, "path_revision_no"),
        "module_key": _context_str(attempt_context, "module_key"),
        "legacy_snapshot_only": _legacy_snapshot_only(attempt_context),
    }


class ExamPaperSerializationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def _paper_by_unit_id(
    db: AsyncSession,
    unit_id: str,
) -> SalesTrainerExamPaper | None:
    result = await db.execute(
        select(SalesTrainerExamPaper).where(SalesTrainerExamPaper.unit_id == unit_id)
    )
    return result.scalar_one_or_none()


async def _paper_revision_by_id(
    db: AsyncSession,
    revision_id: str,
) -> SalesTrainerAssetRevision | None:
    if not revision_id or revision_id == "None":
        return None
    return await db.get(SalesTrainerAssetRevision, revision_id)


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _attempt_context_from_answers(value: object) -> dict[str, Any] | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        context = item.get("attempt_context")
        if isinstance(context, dict):
            return context
    return None


def _context_str(context: dict[str, Any] | None, key: str) -> str | None:
    if context is None:
        return None
    value = context.get(key)
    return value if isinstance(value, str) else None


def _context_int(context: dict[str, Any] | None, key: str) -> int | None:
    if context is None:
        return None
    value = context.get(key)
    return value if isinstance(value, int) else None


def _legacy_snapshot_only(context: dict[str, Any] | None) -> bool:
    if context is None:
        return True
    value = context.get("legacy_snapshot_only")
    return value if isinstance(value, bool) else True
