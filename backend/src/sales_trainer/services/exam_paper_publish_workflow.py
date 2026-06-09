from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerExamPaper,
    SalesTrainerUnit,
)
from sales_trainer.services.asset_revision_service import (
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
)
from sales_trainer.services.exam_paper_revision_payloads import (
    freeze_paper_question_revisions,
)
from sales_trainer.services.exam_paper_store import require_backing_unit, require_paper
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.unit_service import SalesTrainerUnitError, UnitService


class ExamPaperPublishWorkflow:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._payloads = ExamPaperRevisionPayloadBuilder(db)

    async def publish_paper(
        self,
        paper_id: str,
        *,
        actor: User,
    ) -> SalesTrainerExamPaper:
        paper = await require_paper(self._db, paper_id)
        if paper.status == "archived":
            raise ExamPaperServiceError("[PAPER_ARCHIVED]", "已归档考卷不能发布。", 409)
        unit = await require_backing_unit(self._db, paper)
        unit_service = UnitService(self._db)
        previous_snapshot = paper_lifecycle_snapshot(
            paper,
            await unit_service.get_unit_questions(unit.unit_id),
            unit_status=str(unit.status),
        )
        revision_service = SalesTrainerAssetRevisionService(self._db)
        working_revision = None
        if paper.status == "published":
            working_revision = await revision_service.latest_working_revision(
                resource_type=PAPER_RESOURCE_TYPE,
                logical_id=paper.paper_id,
            )
        if working_revision is not None:
            return await self._publish_working_revision(
                paper,
                unit,
                working_revision,
                previous_snapshot=previous_snapshot,
                actor=actor,
                unit_service=unit_service,
                revision_service=revision_service,
            )
        return await self._publish_initial_revision(
            paper,
            unit,
            previous_snapshot=previous_snapshot,
            actor=actor,
            unit_service=unit_service,
            revision_service=revision_service,
        )

    async def _publish_initial_revision(
        self,
        paper: SalesTrainerExamPaper,
        unit: SalesTrainerUnit,
        *,
        previous_snapshot: dict[str, Any],
        actor: User,
        unit_service: UnitService,
        revision_service: SalesTrainerAssetRevisionService,
    ) -> SalesTrainerExamPaper:
        trace_id = get_trace_id()
        try:
            await unit_service.publish_unit(unit, actor=actor)
        except SalesTrainerUnitError as exc:
            raise ExamPaperServiceError(exc.code, exc.message, exc.status_code) from exc
        paper.status = "published"
        paper.updated_by = str(actor.user_id)
        next_snapshot = await freeze_paper_question_revisions(
            self._db,
            paper_lifecycle_snapshot(
                paper,
                await unit_service.get_unit_questions(unit.unit_id),
                unit_status=str(unit.status),
            ),
        )
        publish_result = await revision_service.create_published_revision(
            resource_type=PAPER_RESOURCE_TYPE,
            logical_id=paper.paper_id,
            payload=next_snapshot,
            actor=actor,
            change_class="scoring_high_risk",
            reason="initial exam paper publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="exam_paper_published",
            target_type="sales_trainer_exam_paper",
            target_id=paper.paper_id,
            request_id=trace_id,
            metadata=paper_lifecycle_metadata(previous_snapshot, next_snapshot)
            | {
                "before_revision_id": publish_result.previous_revision_id,
                "after_revision_id": publish_result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper

    async def _publish_working_revision(
        self,
        paper: SalesTrainerExamPaper,
        unit: SalesTrainerUnit,
        working_revision: SalesTrainerAssetRevision,
        *,
        previous_snapshot: dict[str, Any],
        actor: User,
        unit_service: UnitService,
        revision_service: SalesTrainerAssetRevisionService,
    ) -> SalesTrainerExamPaper:
        trace_id = get_trace_id()
        await self._payloads.apply(
            paper,
            unit,
            working_revision.payload_json,
            actor=actor,
            unit_service=unit_service,
        )
        publish_result = await revision_service.publish_working_revision(
            working_revision,
            actor=actor,
            reason="publish edited exam paper revision",
            trace_id=trace_id,
        )
        next_snapshot = (
            working_revision.payload_json
            if isinstance(working_revision.payload_json, dict)
            else paper_lifecycle_snapshot(
                paper,
                await unit_service.get_unit_questions(unit.unit_id),
                unit_status=str(unit.status),
            )
        )
        await self._logs.record(
            actor=actor,
            action="exam_paper_revision_published",
            target_type="sales_trainer_exam_paper",
            target_id=paper.paper_id,
            request_id=trace_id,
            metadata={
                **paper_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": publish_result.previous_revision_id,
                "after_revision_id": working_revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        await self._db.commit()
        await self._db.refresh(paper)
        return paper
