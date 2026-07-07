from __future__ import annotations

from common.db.models import User
from common.db.session import AsyncSessionLocal
from common.monitoring.logger import get_logger
from sales_trainer.services.audio_submission_service import (
    AudioSubmissionService,
    AudioSubmissionServiceError,
)

logger = get_logger(__name__)


async def process_audio_submission_background(
    submission_id: str,
    *,
    actor_id: str | None = None,
) -> None:
    """Run transcription and scoring outside the learner upload request."""

    async with AsyncSessionLocal() as db:
        actor = await db.get(User, actor_id) if actor_id else None
        try:
            await AudioSubmissionService(db).process_submission(
                submission_id,
                actor=actor,
            )
        except AudioSubmissionServiceError as exc:
            await db.rollback()
            logger.warning(
                "sales_trainer_audio_submission_background_failed",
                submission_id=submission_id,
                actor_id=actor_id,
                error_code=exc.code,
                status_code=exc.status_code,
            )
        except Exception as exc:
            # 兜底：未预期异常（DB flush 失败、_score 前中断等）会把状态卡在
            # transcribing/scoring。先 rollback 释放脏会话，再开新事务把
            # submission 推到 scoring_failed 终态，避免前端无限轮询。
            await db.rollback()
            logger.error(
                "sales_trainer_audio_submission_background_error",
                submission_id=submission_id,
                actor_id=actor_id,
                error_type=type(exc).__name__,
            )
            await _mark_submission_unexpected_failure(
                submission_id,
                actor_id=actor_id,
                error=exc,
            )


async def _mark_submission_unexpected_failure(
    submission_id: str,
    *,
    actor_id: str | None,
    error: BaseException,
) -> None:
    """单独事务把未预期异常的 submission 推到 scoring_failed 终态。

    与主流程隔离，主事务已 rollback。失败仅 log，不抛出，避免吞掉原异常。
    """

    try:
        async with AsyncSessionLocal() as recovery_db:
            actor = await recovery_db.get(User, actor_id) if actor_id else None
            await AudioSubmissionService(recovery_db).mark_unexpected_failure(
                submission_id,
                actor=actor,
                error=error,
            )
            await recovery_db.commit()
    except Exception as recovery_exc:
        logger.error(
            "sales_trainer_audio_submission_mark_failure_failed",
            submission_id=submission_id,
            actor_id=actor_id,
            original_error_type=type(error).__name__,
            recovery_error_type=type(recovery_exc).__name__,
        )
