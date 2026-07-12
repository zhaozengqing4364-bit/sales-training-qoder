"""StepAudio realtime roleplay activity handler."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
)
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.services.realtime_roleplay_start_service import (
    RealtimeRoleplayStartService,
)


class RealtimeRoleplayActivityHandler:
    type_key = "realtime_roleplay"

    def __init__(self, db: AsyncSession) -> None:
        self._start = RealtimeRoleplayStartService(db)
        self._attempts = AttemptRepository(db)

    async def start(
        self, context: ActivityExecutionContext, *, actor: User, client_token: str
    ) -> NewcomerTrainingActivityAttempt:
        await self.start_session(context, actor=actor, client_token=client_token)
        attempt = await self._attempts.latest_for_activity(
            enrollment_id=context.enrollment_id,
            activity_id=context.activity.activity_id,
        )
        if attempt is None:
            raise RuntimeError("realtime start returned without activity attempt")
        return attempt

    async def start_session(
        self, context: ActivityExecutionContext, *, actor: User, client_token: str
    ) -> dict[str, object]:
        result = await self._start.start(
            actor=actor, execution_context=context, client_token=client_token
        )
        return result

    async def project(self, context: ActivityExecutionContext) -> ActivityProjection:
        attempt = await self._attempts.latest_for_activity(
            enrollment_id=context.enrollment_id,
            activity_id=context.activity.activity_id,
        )
        status = str(attempt.status) if attempt else "not_started"
        return ActivityProjection(
            context.activity.activity_id,
            self.type_key,
            status,
            status == "completed",
            None,
            None,
            bool(attempt.passed) if attempt and attempt.passed is not None else None,
            None if status == "completed" else {"action": "start_realtime_roleplay"},
            None,
        )

    async def validate_config(self, activity: Any) -> tuple[Any, ...]:
        return ()

    async def check_access(self, context: ActivityExecutionContext) -> None:
        del context

    async def refresh_attempt(
        self,
        context: ActivityExecutionContext,
        attempt: NewcomerTrainingActivityAttempt,
    ) -> NewcomerTrainingActivityAttempt:
        del context
        return attempt


__all__ = ["RealtimeRoleplayActivityHandler"]
