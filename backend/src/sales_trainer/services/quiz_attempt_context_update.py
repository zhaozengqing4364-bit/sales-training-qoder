from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerQuizAnswer
from sales_trainer.services.path_attempt_context_service import (
    PathAttemptContextPayload,
)


async def attach_attempt_context_to_answers(
    db: AsyncSession,
    *,
    attempt_id: str,
    attempt_context: PathAttemptContextPayload,
) -> None:
    result = await db.execute(
        select(SalesTrainerQuizAnswer).where(
            SalesTrainerQuizAnswer.attempt_id == attempt_id
        )
    )
    for answer in result.scalars().all():
        answer.answer_payload = answer_payload_with_context(
            answer.answer_payload,
            attempt_context,
        )


def answer_payload_with_context(
    payload: Any,
    attempt_context: PathAttemptContextPayload,
) -> Any:
    if not isinstance(payload, dict):
        return payload
    return {**payload, "attempt_context": attempt_context}
