from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import (
    SalesTrainerAudioScoreResult,
    SalesTrainerAudioSubmission,
    SalesTrainerQuizAttempt,
)


@dataclass(frozen=True, slots=True)
class UnitProgress:
    status: str
    passed: bool | None
    score: float | None
    max_score: float | None
    submitted_at: datetime | None
    result_id: str | None
    target_path: str | None
    improvements: tuple[str, ...] = ()


async def load_latest_quiz_progress(
    db: AsyncSession,
    user_id: str,
) -> dict[str, UnitProgress]:
    result = await db.execute(
        select(SalesTrainerQuizAttempt)
        .where(SalesTrainerQuizAttempt.user_id == user_id)
        .order_by(SalesTrainerQuizAttempt.submitted_at.desc())
    )
    progress: dict[str, UnitProgress] = {}
    for attempt in result.scalars().all():
        unit_id = str(attempt.unit_id)
        if unit_id in progress:
            continue
        progress[unit_id] = UnitProgress(
            status=str(attempt.status),
            passed=attempt.passed,
            score=_decimal_to_float(attempt.total_score),
            max_score=_decimal_to_float(attempt.max_score),
            submitted_at=attempt.submitted_at,
            result_id=str(attempt.attempt_id),
            target_path=f"/sales-trainer/quiz/result/{attempt.attempt_id}",
        )
    return progress


async def load_latest_audio_progress(
    db: AsyncSession,
    user_id: str,
) -> dict[str, UnitProgress]:
    result = await db.execute(
        select(SalesTrainerAudioSubmission, SalesTrainerAudioScoreResult)
        .outerjoin(
            SalesTrainerAudioScoreResult,
            SalesTrainerAudioSubmission.submission_id
            == SalesTrainerAudioScoreResult.submission_id,
        )
        .where(SalesTrainerAudioSubmission.user_id == user_id)
        .order_by(
            SalesTrainerAudioSubmission.created_at.desc(),
            SalesTrainerAudioScoreResult.created_at.desc(),
        )
    )
    progress: dict[str, UnitProgress] = {}
    for submission, score in result.all():
        unit_id = str(submission.unit_id or "")
        if not unit_id or unit_id in progress:
            continue
        progress[unit_id] = UnitProgress(
            status=str(submission.status),
            passed=score.passed if score is not None else None,
            score=_decimal_to_float(score.total_score) if score is not None else None,
            max_score=None,
            submitted_at=submission.created_at,
            result_id=str(submission.submission_id),
            target_path=f"/sales-trainer/audio/result/{submission.submission_id}",
            improvements=_string_tuple(score.improvements if score is not None else []),
        )
    return progress


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _string_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(item) for item in values if str(item).strip())
