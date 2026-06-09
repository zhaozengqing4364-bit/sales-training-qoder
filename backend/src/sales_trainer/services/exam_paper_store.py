from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerUnit
from sales_trainer.services.exam_paper_config import ExamPaperServiceError


async def get_paper(
    db: AsyncSession,
    paper_id: str,
) -> SalesTrainerExamPaper | None:
    return await db.get(SalesTrainerExamPaper, paper_id)


async def require_paper(
    db: AsyncSession,
    paper_id: str,
) -> SalesTrainerExamPaper:
    paper = await get_paper(db, paper_id)
    if paper is None:
        raise ExamPaperServiceError("[PAPER_NOT_FOUND]", "考卷不存在。", 404)
    return paper


async def require_published_paper(
    db: AsyncSession,
    paper_id: str,
) -> SalesTrainerExamPaper:
    paper = await require_paper(db, paper_id)
    if paper.status != "published":
        raise ExamPaperServiceError(
            "[PAPER_NOT_PUBLISHED]",
            "考卷不存在或未发布。",
            404,
        )
    return paper


async def require_backing_unit(
    db: AsyncSession,
    paper: SalesTrainerExamPaper,
) -> SalesTrainerUnit:
    unit = await db.get(SalesTrainerUnit, paper.unit_id)
    if unit is None:
        raise ExamPaperServiceError(
            "[PAPER_BACKING_UNIT_MISSING]",
            "考卷执行单元缺失。",
            409,
        )
    return unit


async def ensure_unique_paper_key(
    db: AsyncSession,
    paper_key: str,
) -> None:
    result = await db.execute(
        select(SalesTrainerExamPaper).where(
            SalesTrainerExamPaper.paper_key == paper_key
        )
    )
    if result.scalar_one_or_none() is not None:
        raise ExamPaperServiceError("[PAPER_KEY_EXISTS]", "考卷标识已存在。", 409)
