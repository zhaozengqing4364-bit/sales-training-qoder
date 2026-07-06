from __future__ import annotations

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import SalesTrainerExamPaper
from sales_trainer.schemas import ExamPaperUpdate, PaperRollbackRequest
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionError,
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audit_metadata import (
    paper_lifecycle_metadata,
    paper_lifecycle_snapshot,
)
from sales_trainer.services.exam_paper_config import ExamPaperServiceError
from sales_trainer.services.exam_paper_revision_constants import PAPER_RESOURCE_TYPE
from sales_trainer.services.exam_paper_revision_payload_builder import (
    ExamPaperRevisionPayloadBuilder,
    paper_change_class,
)
from sales_trainer.services.exam_paper_store import (
    require_backing_unit,
    require_paper,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_service import UnitService


class ExamPaperRevisionWorkflow:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._payloads = ExamPaperRevisionPayloadBuilder(db)

    async def save_published_paper_revision(
        self,
        paper: SalesTrainerExamPaper,
        payload: ExamPaperUpdate,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        trace_id = get_trace_id()
        unit = await require_backing_unit(self._db, paper)
        paper_id = str(paper.paper_id)
        unit_id = str(unit.unit_id)
        unit_service = UnitService(self._db)
        revision_service = SalesTrainerAssetRevisionService(self._db)
        active_revision = await revision_service.active_revision(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=paper_id,
        )
        previous_snapshot: dict[str, Any] = (
            cast(dict[str, Any], active_revision.payload_json)
            if active_revision is not None
            else paper_lifecycle_snapshot(
                paper,
                await unit_service.get_unit_questions(unit_id),
                unit_status=str(unit.status),
            )
        )
        next_snapshot = await self._payloads.build(
            paper,
            unit,
            previous_snapshot,
            payload,
            actor=actor,
            unit_service=unit_service,
        )
        revision = await revision_service.save_working_revision(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=paper_id,
            payload=next_snapshot,
            actor=actor,
            change_class=paper_change_class(previous_snapshot, next_snapshot),
            source_revision_id=(
                str(active_revision.revision_id) if active_revision is not None else None
            ),
            reason="save edited exam paper revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="exam_paper_revision_saved",
            target_type="sales_trainer_exam_paper",
            target_id=paper_id,
            request_id=trace_id,
            metadata={
                **paper_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper

    async def rollback_paper(
        self,
        paper_id: str,
        payload: PaperRollbackRequest,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        trace_id = get_trace_id()
        paper = await require_paper(self._db, paper_id)
        if paper.status == "archived":
            raise ExamPaperServiceError("[PAPER_ARCHIVED]", "已归档考卷不能回滚。", 409)
        unit = await require_backing_unit(self._db, paper)
        current_paper_id = str(paper.paper_id)
        unit_id = str(unit.unit_id)
        unit_service = UnitService(self._db)
        previous_snapshot = paper_lifecycle_snapshot(
            paper,
            await unit_service.get_unit_questions(unit_id),
            unit_status=str(unit.status),
        )
        revision_service = SalesTrainerAssetRevisionService(self._db)
        target_revision = await revision_service.revision_by_id(
            payload.target_revision_id
        )
        if (
            target_revision is None
            or target_revision.resource_type != PAPER_RESOURCE_TYPE
            or target_revision.logical_id != current_paper_id
        ):
            raise ExamPaperServiceError(
                "[PAPER_REVISION_NOT_FOUND]",
                "目标考卷修订不存在或不属于当前考卷。",
                404,
            )
        try:
            rollback_result = await revision_service.rollback_to_revision(
                target_revision,
                actor=actor,
                reason=payload.reason,
                trace_id=trace_id,
            )
        except SalesTrainerAssetRevisionError as exc:
            raise ExamPaperServiceError(exc.code, exc.message, exc.status_code) from exc
        target_revision_payload = cast(dict[str, Any], target_revision.payload_json)
        await self._payloads.apply(
            paper,
            unit,
            target_revision_payload,
            actor=actor,
            unit_service=unit_service,
        )
        next_snapshot = (
            target_revision_payload
            if isinstance(target_revision.payload_json, dict)
            else paper_lifecycle_snapshot(
                paper,
                await unit_service.get_unit_questions(unit_id),
                unit_status=str(unit.status),
            )
        )
        await self._logs.record(
            actor=actor,
            action="exam_paper_revision_rolled_back",
            target_type="sales_trainer_exam_paper",
            target_id=current_paper_id,
            request_id=trace_id,
            metadata={
                **paper_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": rollback_result.previous_revision_id,
                "after_revision_id": target_revision.revision_id,
                "reason": payload.reason,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper
