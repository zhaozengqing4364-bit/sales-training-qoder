from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import orm_scalar
from common.monitoring.logger import get_logger, get_trace_id
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

logger = get_logger(__name__)


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
        # R1: regrade 不能只写审计行——必须把新分回写业务表 + 更新 submission 状态，
        # 否则学员结果页轮询 submission 永远看不到重判结果。追加新的 score_result
        # 行（保留历史评分轨迹），并把 submission 推到 scored 终态。
        await self._apply_regrade_to_score_result(
            submission_id=preview.target_id,
            after_snapshot=preview.after_snapshot,
            actor=actor,
            regrade_run_id=str(run.run_id),
            trace_id=trace_id,
        )
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

    async def _apply_regrade_to_score_result(
        self,
        *,
        submission_id: str,
        after_snapshot: dict[str, object],
        actor: User,
        regrade_run_id: str,
        trace_id: str,
    ) -> None:
        """把重判后的新分追加为新的 SalesTrainerAudioScoreResult 行，并把 submission
        置 scored 终态。

        追加而非覆盖原行：保留历史评分轨迹，符合"审计 + 业务可见"双重要求。
        学员结果页 list_score_results 已支持多条历史，最新一行即为重判后的分。
        事务由调用方 commit；失败抛出，整体 rollback 不污染原分。
        """

        submission = await self._db.get(SalesTrainerAudioSubmission, submission_id)
        if submission is None:
            logger.error(
                "sales_trainer_audio_regrade_apply_no_submission",
                submission_id=submission_id,
                regrade_run_id=regrade_run_id,
                trace_id=trace_id,
            )
            return

        def _str(value: object) -> str | None:
            return str(value) if value is not None else None

        def _int(value: object) -> int | None:
            if value is None:
                return None
            return int(str(value))

        prompt_id_raw = after_snapshot.get("prompt_id")
        if prompt_id_raw is None:
            logger.error(
                "sales_trainer_audio_regrade_apply_no_prompt",
                submission_id=submission_id,
                regrade_run_id=regrade_run_id,
                trace_id=trace_id,
            )
            return

        prompt_version_value = _int(after_snapshot.get("prompt_version"))
        if prompt_version_value is None:
            logger.error(
                "sales_trainer_audio_regrade_apply_no_prompt_version",
                submission_id=submission_id,
                regrade_run_id=regrade_run_id,
                trace_id=trace_id,
            )
            return

        new_score = SalesTrainerAudioScoreResult(
            submission_id=submission_id,
            prompt_id=str(prompt_id_raw),
            prompt_version=prompt_version_value,
            prompt_hash=str(after_snapshot.get("prompt_hash") or ""),
            deucate_model=_str(after_snapshot.get("deucate_model")),
            transcript_snapshot=_str(after_snapshot.get("transcript_snapshot")),
            total_score=after_snapshot.get("total_score"),  # type: ignore[arg-type]
            passed=after_snapshot.get("passed"),  # type: ignore[arg-type]
            summary=_str(after_snapshot.get("summary")),
            strengths=after_snapshot.get("strengths") or [],
            improvements=after_snapshot.get("improvements") or [],
            dimension_scores=after_snapshot.get("dimension_scores") or {},
            raw_response=after_snapshot.get("raw_response"),
            error_code=_str(after_snapshot.get("error_code")),
            error_message=_str(after_snapshot.get("error_message")),
            latency_ms=_int(after_snapshot.get("latency_ms")),
        )
        self._db.add(new_score)

        # 重判成功（无 error_code）才置 scored；判分失败置 scoring_failed，不卡中间态。
        error_code = after_snapshot.get("error_code")
        if error_code:
            setattr(submission, "status", "scoring_failed")
            setattr(submission, "error_code", str(error_code))
            setattr(submission, "error_message", _str(after_snapshot.get("error_message")))
        else:
            setattr(submission, "status", "scored")
            setattr(submission, "error_code", None)
            setattr(submission, "error_message", None)
        await self._db.flush()
        await self._logs.record(
            actor=actor,
            action="audio_regrade_applied",
            target_type="sales_trainer_audio_submission",
            target_id=submission_id,
            request_id=trace_id,
            metadata={
                "regrade_run_id": regrade_run_id,
                "new_status": submission.status,
                "trace_id": trace_id,
            },
        )

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
