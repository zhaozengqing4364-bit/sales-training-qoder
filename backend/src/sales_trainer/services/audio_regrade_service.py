from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import orm_scalar
from common.monitoring.logger import get_trace_id
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
)
from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.audio_regrade_calculator import (
    AudioRegradePreview,
    build_audio_regrade_preview,
)
from sales_trainer.services.deucate_scoring_service import DeucateScoringService
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.prompt_revision_payloads import PROMPT_RESOURCE_TYPE
from sales_trainer.services.training_record_service import TrainingRecordService


class SalesTrainerAudioRegradeService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        scoring_service: DeucateScoringService | None = None,
    ) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)
        self._scoring = scoring_service or DeucateScoringService()

    async def preview_audio_submission(
        self,
        submission_id: str,
        *,
        target_revision_id: str | None,
        viewer: User,
        team_department: str | None,
    ) -> AudioRegradePreview:
        await self._require_submission_for_viewer(
            submission_id,
            viewer=viewer,
            team_department=team_department,
        )
        submission = await self._require_submission(submission_id)
        score = await self._require_latest_score(submission_id)
        target_revision = await self._resolve_target_revision(
            score,
            target_revision_id=target_revision_id,
        )
        return await build_audio_regrade_preview(
            self._db,
            submission,
            score,
            target_revision,
            scoring_service=self._scoring,
        )

    async def run_audio_submission_regrade(
        self,
        submission_id: str,
        *,
        target_revision_id: str | None,
        reason: str,
        actor: User,
        team_department: str | None,
    ) -> SalesTrainerRegradeRun:
        trace_id = get_trace_id()
        preview = await self.preview_audio_submission(
            submission_id,
            target_revision_id=target_revision_id,
            viewer=actor,
            team_department=team_department,
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
            target_type="sales_trainer_audio_submission",
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

    async def _require_submission_for_viewer(
        self,
        submission_id: str,
        *,
        viewer: User,
        team_department: str | None,
    ) -> None:
        record = await TrainingRecordService(self._db).get_record_for_viewer(
            "audio_submission",
            submission_id,
            viewer=viewer,
            team_department=team_department,
        )
        if record is None:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_NOT_FOUND]",
                "历史录音提交不存在，无法重新评分。",
                404,
            )

    async def _require_submission(
        self,
        submission_id: str,
    ) -> SalesTrainerAudioSubmission:
        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_NOT_FOUND]",
                "历史录音提交不存在，无法重新评分。",
                404,
            )
        return submission

    async def _require_latest_score(
        self,
        submission_id: str,
    ) -> SalesTrainerAudioScoreResult:
        result = await self._db.execute(
            select(SalesTrainerAudioScoreResult)
            .where(SalesTrainerAudioScoreResult.submission_id == submission_id)
            .order_by(SalesTrainerAudioScoreResult.created_at.desc())
            .limit(1)
        )
        score = result.scalar_one_or_none()
        if score is None:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_SOURCE_SCORE_NOT_FOUND]",
                "历史录音尚无可用于重评的评分结果。",
                409,
            )
        if not str(score.transcript_snapshot or "").strip():
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TRANSCRIPT_SNAPSHOT_REQUIRED]",
                "历史评分缺少转写快照，无法保证重评可追溯。",
                409,
            )
        return score

    async def _resolve_target_revision(
        self,
        score: SalesTrainerAudioScoreResult,
        *,
        target_revision_id: str | None,
    ) -> SalesTrainerAssetRevision:
        if target_revision_id is not None:
            target_revision = await self._revisions.revision_by_id(target_revision_id)
        else:
            target_revision = await self._revisions.active_revision(
                resource_type=PROMPT_RESOURCE_TYPE,
                logical_id=orm_scalar(score.prompt_id, str),
            )
        if target_revision is None:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_REVISION_NOT_FOUND]",
                "未找到可用于重评的已发布录音评分标准修订。",
                404,
            )
        if target_revision.resource_type != PROMPT_RESOURCE_TYPE:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_REVISION_INVALID]",
                "目标修订不是新人训练路径录音评分标准修订。",
                409,
            )
        if target_revision.status != "published":
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_REVISION_NOT_PUBLISHED]",
                "只能使用已发布录音评分标准修订进行历史重评。",
                409,
            )
        if target_revision.logical_id != score.prompt_id:
            raise SalesTrainerAudioRegradeServiceError(
                "[REGRADING_TARGET_REVISION_MISMATCH]",
                "目标修订不属于该历史录音评分标准。",
                409,
            )
        return target_revision


class SalesTrainerAudioRegradeServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
