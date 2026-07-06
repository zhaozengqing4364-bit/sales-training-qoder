from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.typing import json_list_or_empty, orm_scalar
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
        unit_id = orm_scalar(attempt.unit_id, str)
        if unit_id in progress:
            continue
        attempt_id = orm_scalar(attempt.attempt_id, str)
        progress[unit_id] = UnitProgress(
            status=orm_scalar(attempt.status, str),
            passed=orm_scalar(attempt.passed, bool, nullable=True),
            score=_decimal_to_float(
                orm_scalar(attempt.total_score, Decimal, nullable=True)
            ),
            max_score=_decimal_to_float(
                orm_scalar(attempt.max_score, Decimal, nullable=True)
            ),
            submitted_at=orm_scalar(attempt.submitted_at, datetime, nullable=True),
            result_id=attempt_id,
            target_path=f"/sales-trainer/quiz/result/{attempt_id}",
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
        unit_id = orm_scalar(submission.unit_id, str, nullable=True) or ""
        if not unit_id or unit_id in progress:
            continue
        submission_id = orm_scalar(submission.submission_id, str)
        progress[unit_id] = UnitProgress(
            status=orm_scalar(submission.status, str),
            passed=(
                orm_scalar(score.passed, bool, nullable=True)
                if score is not None
                else None
            ),
            score=(
                _decimal_to_float(
                    orm_scalar(score.total_score, Decimal, nullable=True)
                )
                if score is not None
                else None
            ),
            max_score=None,
            submitted_at=orm_scalar(submission.created_at, datetime, nullable=True),
            result_id=submission_id,
            target_path=f"/sales-trainer/audio/result/{submission_id}",
            improvements=_string_tuple(score.improvements if score is not None else []),
        )
    return progress


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _string_tuple(values: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in json_list_or_empty(values) if str(item).strip())
