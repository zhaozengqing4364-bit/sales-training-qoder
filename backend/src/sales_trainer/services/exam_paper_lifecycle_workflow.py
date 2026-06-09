from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerUnit
from sales_trainer.schemas import ExamPaperCreate, ExamPaperUpdate
from sales_trainer.services.audit_metadata import (
    paper_lifecycle_metadata,
    paper_lifecycle_snapshot,
)
from sales_trainer.services.exam_paper_config import decimal_or_none
from sales_trainer.services.exam_paper_store import (
    ensure_unique_paper_key,
    require_backing_unit,
    require_paper,
)
from sales_trainer.services.exam_paper_unit_adapter import (
    paper_unit_create,
    paper_unit_update,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


class ExamPaperLifecycleWorkflow:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)

    async def create_paper(
        self,
        payload: ExamPaperCreate,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        await ensure_unique_paper_key(self._db, payload.paper_key)
        unit = await self._create_backing_unit(payload, actor=actor)
        paper = SalesTrainerExamPaper(
            paper_key=payload.paper_key,
            title=payload.title,
            description=payload.description,
            module_key=payload.module_key,
            unit_id=unit.unit_id,
            pass_threshold=decimal_or_none(payload.pass_threshold),
            created_by=str(actor.user_id),
            updated_by=str(actor.user_id),
        )
        self._db.add(paper)
        await self._db.flush()
        questions = await UnitService(self._db).get_unit_questions(unit.unit_id)
        await self._logs.record(
            actor=actor,
            action="exam_paper_created",
            target_type="sales_trainer_exam_paper",
            target_id=paper.paper_id,
            metadata={
                "paper_key": paper.paper_key,
                "unit_id": unit.unit_id,
                "next": paper_lifecycle_snapshot(
                    paper,
                    questions,
                    unit_status=str(unit.status),
                ),
            },
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper

    async def update_draft_paper(
        self,
        paper: SalesTrainerExamPaper,
        payload: ExamPaperUpdate,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        unit = await require_backing_unit(self._db, paper)
        unit_service = UnitService(self._db)
        previous_snapshot = paper_lifecycle_snapshot(
            paper,
            await unit_service.get_unit_questions(unit.unit_id),
            unit_status=str(unit.status),
        )
        data = payload.model_dump(exclude_unset=True)
        if "paper_key" in data and data["paper_key"] != paper.paper_key:
            await ensure_unique_paper_key(self._db, str(data["paper_key"]))
            paper.paper_key = str(data["paper_key"])
        if "title" in data:
            paper.title = data["title"]
        if "description" in data:
            paper.description = data["description"]
        if "module_key" in data:
            paper.module_key = data["module_key"]
        if "pass_threshold" in data:
            paper.pass_threshold = decimal_or_none(data["pass_threshold"])
        paper.updated_by = str(actor.user_id)
        try:
            await unit_service.update_unit(unit, paper_unit_update(payload), actor=actor)
        except SalesTrainerUnitError as exc:
            raise _paper_error(exc) from exc
        await self._logs.record(
            actor=actor,
            action="exam_paper_updated",
            target_type="sales_trainer_exam_paper",
            target_id=paper.paper_id,
            metadata=paper_lifecycle_metadata(
                previous_snapshot,
                paper_lifecycle_snapshot(
                    paper,
                    await unit_service.get_unit_questions(unit.unit_id),
                    unit_status=str(unit.status),
                ),
            ),
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper

    async def archive_paper(
        self,
        paper_id: str,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        paper = await require_paper(self._db, paper_id)
        unit_service = UnitService(self._db)
        unit = await self._db.get(SalesTrainerUnit, paper.unit_id)
        previous_questions = await unit_service.get_unit_questions(paper.unit_id)
        previous_snapshot = paper_lifecycle_snapshot(
            paper,
            previous_questions,
            unit_status=str(unit.status) if unit is not None else None,
        )
        paper.status = "archived"
        paper.updated_by = str(actor.user_id)
        if unit is not None:
            unit.status = "archived"
            unit.updated_by = str(actor.user_id)
        await self._logs.record(
            actor=actor,
            action="exam_paper_archived",
            target_type="sales_trainer_exam_paper",
            target_id=paper.paper_id,
            metadata=paper_lifecycle_metadata(
                previous_snapshot,
                paper_lifecycle_snapshot(
                    paper,
                    previous_questions,
                    unit_status=str(unit.status) if unit is not None else None,
                ),
            ),
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper

    async def _create_backing_unit(
        self,
        payload: ExamPaperCreate,
        *,
        actor: User,
    ) -> SalesTrainerUnit:
        try:
            return await UnitService(self._db).create_unit(
                paper_unit_create(payload),
                actor=actor,
            )
        except SalesTrainerUnitError as exc:
            raise _paper_error(exc) from exc


def _paper_error(exc: SalesTrainerUnitError) -> Exception:
    from sales_trainer.services.exam_paper_config import ExamPaperServiceError

    return ExamPaperServiceError(exc.code, exc.message, exc.status_code)
