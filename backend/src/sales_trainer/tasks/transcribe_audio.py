from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import SalesTrainerAudioSubmission
from sales_trainer.services.audio_submission_service import AudioSubmissionService


async def transcribe_audio_submission(
    db: AsyncSession,
    submission_id: str,
    *,
    actor: User | None = None,
) -> SalesTrainerAudioSubmission:
    """Thin task wrapper so queues can call transcription without API coupling."""

    service = AudioSubmissionService(db)
    return await service.transcribe_submission(submission_id, actor=actor)
