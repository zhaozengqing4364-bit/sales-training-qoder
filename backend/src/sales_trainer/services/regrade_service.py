from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerQuizAttempt
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.exam_paper_revision_constants import PAPER_RESOURCE_TYPE
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.regrade_calculator import (
    QuizRegradePreview,
    build_quiz_regrade_preview,
)


class SalesTrainerRegradeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def preview_quiz_attempt(
        self,
        attempt_id: str,
        *,
        target_revision_id: str | None = None,
    ) -> QuizRegradePreview:
        attempt = await self._require_attempt(attempt_id)
        target_revision = await self._resolve_target_revision(
            attempt,
            target_revision_id=target_revision_id,
        )
        return await build_quiz_regrade_preview(
            self._db,
            attempt,
            target_revision,
        )

    async def run_quiz_attempt_regrade(
        self,
        attempt_id: str,
        *,
        target_revision_id: str | None,
        reason: str,
        actor: User,
    ) -> SalesTrainerRegradeRun:
        trace_id = get_trace_id()
        preview = await self.preview_quiz_attempt(
            attempt_id,
            target_revision_id=target_revision_id,
        )
        run = SalesTrainerRegradeRun(
            target_type=preview.target_type,
            target_id=preview.target_id,
            target_revision_id=preview.target_revision_id,
            status="completed",
            reason=reason,
            impact_scope_json=preview.impact_scope,
            before_snapshot_json=preview.before_snapshot,
            after_snapshot_json=preview.after_snapshot,
            trace_id=trace_id,
            created_by=str(actor.user_id),
            created_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self._db.add(run)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="historical_regrade.completed",
            target_type="sales_trainer_quiz_attempt",
            target_id=preview.target_id,
            request_id=trace_id,
            metadata={
                "regrade_run_id": run.run_id,
                "target_type": preview.target_type,
                "target_id": preview.target_id,
                "target_revision_id": preview.target_revision_id,
                "reason": reason,
                "impact_scope": preview.impact_scope,
                "before_snapshot": preview.before_snapshot,
                "after_snapshot": preview.after_snapshot,
                "trace_id": trace_id,
                "append_only": True,
                "history_overwrite": False,
            },
        )
        await self._db.commit()
        await self._db.refresh(run)
        return run

    async def _require_attempt(self, attempt_id: str) -> SalesTrainerQuizAttempt:
        attempt = await self._db.get(SalesTrainerQuizAttempt, attempt_id)
        if attempt is None:
            raise SalesTrainerRegradeServiceError(
                "[REGRADING_TARGET_NOT_FOUND]",
                "历史考试记录不存在，无法重新评分。",
                404,
            )
        return attempt

    async def _resolve_target_revision(
        self,
        attempt: SalesTrainerQuizAttempt,
        *,
        target_revision_id: str | None,
    ) -> SalesTrainerAssetRevision:
        source_revision = await self._source_revision(attempt)
        if target_revision_id is not None:
            target_revision = await self._revisions.revision_by_id(target_revision_id)
        elif source_revision is not None:
            target_revision = await self._revisions.active_revision(
                resource_type=PAPER_RESOURCE_TYPE,
                logical_id=source_revision.logical_id,
            )
        else:
            target_revision = None
        if target_revision is None:
            raise SalesTrainerRegradeServiceError(
                "[REGRADING_TARGET_REVISION_NOT_FOUND]",
                "未找到可用于重评的已发布考卷修订。",
                404,
            )
        if target_revision.resource_type != PAPER_RESOURCE_TYPE:
            raise SalesTrainerRegradeServiceError(
                "[REGRADING_TARGET_REVISION_INVALID]",
                "目标修订不是新人训练路径考卷修订。",
                409,
            )
        if target_revision.status != "published":
            raise SalesTrainerRegradeServiceError(
                "[REGRADING_TARGET_REVISION_NOT_PUBLISHED]",
                "只能使用已发布考卷修订进行历史重评。",
                409,
            )
        if source_revision is not None and target_revision.logical_id != source_revision.logical_id:
            raise SalesTrainerRegradeServiceError(
                "[REGRADING_TARGET_REVISION_MISMATCH]",
                "目标修订不属于该历史考试记录的考卷。",
                409,
            )
        return target_revision

    async def _source_revision(
        self,
        attempt: SalesTrainerQuizAttempt,
    ) -> SalesTrainerAssetRevision | None:
        if attempt.paper_revision_id is None:
            return None
        return await self._db.get(SalesTrainerAssetRevision, attempt.paper_revision_id)


class SalesTrainerRegradeServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
