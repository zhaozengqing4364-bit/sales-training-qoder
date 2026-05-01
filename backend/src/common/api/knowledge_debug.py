from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import KnowledgeAnswerRun, KnowledgeAnswerRunStep
from common.db.session import get_db
from common.monitoring.logger import get_trace_id

router = APIRouter(prefix="/knowledge-debug", tags=["knowledge-debug"])


def success_response(data: Any) -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "trace_id": get_trace_id(),
    }


def error_response(
    error_code: str,
    *,
    status_code: int,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_code,
            "message": message or error_code,
            "trace_id": get_trace_id(),
        },
    )


class KnowledgeDebugRunListItem(BaseModel):
    id: str
    session_id: str
    config_version_id: str | None = None
    entrypoint: str
    query_text: str
    answerability: str
    final_status: str
    blocked_reason: str | None = None
    step_count: int = 0
    created_at: datetime
    updated_at: datetime


class KnowledgeDebugRunDetail(BaseModel):
    id: str
    session_id: str
    config_version_id: str | None = None
    entrypoint: str
    query_text: str
    answerability: str
    final_status: str
    blocked_reason: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeDebugRunStepItem(BaseModel):
    id: str
    answer_run_id: str
    step_name: str
    step_order: int
    status: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDebugRunListResponse(BaseModel):
    items: list[KnowledgeDebugRunListItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    page: int = 1
    offset: int = 0
    session_id: str | None = None


class KnowledgeDebugRunStepsResponse(BaseModel):
    run_id: str
    items: list[KnowledgeDebugRunStepItem] = Field(default_factory=list)
    total: int = 0


class KnowledgeDebugEnvelope(BaseModel):
    success: bool = True
    data: dict[str, Any]
    trace_id: str | None = None


@router.get("/runs", response_model=KnowledgeDebugEnvelope)
async def list_answer_runs(
    limit: int = Query(20, ge=1, le=100, description="Max runs to return"),
    page: int = Query(1, ge=1, description="1-indexed results page"),
    session_id: str | None = Query(
        None,
        description="Optional session filter for one practice session",
    ),
    query: str | None = Query(
        None, description="Optional substring filter for query text"
    ),
    answerability: str | None = Query(
        None, description="Optional answerability filter"
    ),
    final_status: str | None = Query(None, description="Optional final status filter"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    filters = []
    if session_id:
        filters.append(KnowledgeAnswerRun.session_id == session_id)
    if query:
        filters.append(KnowledgeAnswerRun.query_text.ilike(f"%{query.strip()}%"))
    if answerability:
        filters.append(KnowledgeAnswerRun.answerability == answerability)
    if final_status:
        filters.append(KnowledgeAnswerRun.final_status == final_status)

    total_stmt = select(func.count()).select_from(KnowledgeAnswerRun)
    if filters:
        total_stmt = total_stmt.where(*filters)
    total = int((await db.execute(total_stmt)).scalar_one() or 0)
    offset = (page - 1) * limit

    runs_stmt = (
        select(KnowledgeAnswerRun)
        .where(*filters)
        .order_by(KnowledgeAnswerRun.created_at.desc(), KnowledgeAnswerRun.id.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = list((await db.execute(runs_stmt)).scalars())
    run_ids = [str(run.id) for run in runs]

    step_counts: dict[str, int] = {}
    if run_ids:
        count_rows = await db.execute(
            select(
                KnowledgeAnswerRunStep.answer_run_id,
                func.count(KnowledgeAnswerRunStep.id),
            )
            .where(KnowledgeAnswerRunStep.answer_run_id.in_(run_ids))
            .group_by(KnowledgeAnswerRunStep.answer_run_id)
        )
        step_counts = {
            str(answer_run_id): int(step_count or 0)
            for answer_run_id, step_count in count_rows.all()
        }

    payload = KnowledgeDebugRunListResponse(
        items=[
            KnowledgeDebugRunListItem(
                id=str(run.id),
                session_id=str(run.session_id),
                config_version_id=(
                    str(run.config_version_id) if run.config_version_id else None
                ),
                entrypoint=str(run.entrypoint),
                query_text=str(run.query_text),
                answerability=str(run.answerability),
                final_status=str(run.final_status),
                blocked_reason=run.blocked_reason,
                step_count=step_counts.get(str(run.id), 0),
                created_at=run.created_at,
                updated_at=run.updated_at,
            )
            for run in runs
        ],
        total=total,
        limit=limit,
        page=page,
        offset=offset,
        session_id=session_id,
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/runs/{run_id}", response_model=KnowledgeDebugEnvelope)
async def get_answer_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    run = await _get_answer_run(db, run_id)
    if run is None:
        return error_response(
            "[KNOWLEDGE_RUN_NOT_FOUND]",
            status_code=404,
            message="Knowledge answer run not found",
        )

    payload = KnowledgeDebugRunDetail(
        id=str(run.id),
        session_id=str(run.session_id),
        config_version_id=str(run.config_version_id) if run.config_version_id else None,
        entrypoint=str(run.entrypoint),
        query_text=str(run.query_text),
        answerability=str(run.answerability),
        final_status=str(run.final_status),
        blocked_reason=run.blocked_reason,
        citations=_normalize_json_list(run.citations_json),
        retrieval_summary=_normalize_json_dict(run.retrieval_summary_json),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )
    return success_response(payload.model_dump(mode="json"))


@router.get("/runs/{run_id}/steps", response_model=KnowledgeDebugEnvelope)
async def get_answer_run_steps(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    run = await _get_answer_run(db, run_id)
    if run is None:
        return error_response(
            "[KNOWLEDGE_RUN_NOT_FOUND]",
            status_code=404,
            message="Knowledge answer run not found",
        )

    steps = list(
        (
            await db.execute(
                select(KnowledgeAnswerRunStep)
                .where(KnowledgeAnswerRunStep.answer_run_id == run_id)
                .order_by(
                    KnowledgeAnswerRunStep.step_order.asc(),
                    KnowledgeAnswerRunStep.created_at.asc(),
                )
            )
        ).scalars()
    )

    payload = KnowledgeDebugRunStepsResponse(
        run_id=run_id,
        items=[
            KnowledgeDebugRunStepItem(
                id=str(step.id),
                answer_run_id=str(step.answer_run_id),
                step_name=str(step.step_name),
                step_order=int(step.step_order),
                status=str(step.status),
                input_payload=_normalize_json_dict(step.input_payload),
                output_payload=_normalize_json_dict(step.output_payload),
                duration_ms=(
                    None if step.duration_ms is None else int(step.duration_ms)
                ),
                created_at=step.created_at,
                updated_at=step.updated_at,
            )
            for step in steps
        ],
        total=len(steps),
    )
    return success_response(payload.model_dump(mode="json"))


async def _get_answer_run(
    db: AsyncSession,
    run_id: str,
) -> KnowledgeAnswerRun | None:
    result = await db.execute(
        select(KnowledgeAnswerRun).where(KnowledgeAnswerRun.id == run_id)
    )
    return result.scalar_one_or_none()


def _normalize_json_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_json_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
