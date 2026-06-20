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
            await db.rollback()
            logger.error(
                "sales_trainer_audio_submission_background_error",
                submission_id=submission_id,
                actor_id=actor_id,
                error_type=type(exc).__name__,
            )
