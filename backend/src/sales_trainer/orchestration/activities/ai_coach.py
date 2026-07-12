"""Governed AI Coach activity handler."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    SalesTrainerAiCoachSession,
)
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
    activity_snapshot,
)
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.services.ai_coach_session_service import AiCoachSessionService


class AiCoachActivityHandler:
    type_key = "ai_coach"

    def __init__(
        self,
        db: AsyncSession,
        *,
        sessions: AiCoachSessionService | None = None,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._sessions = sessions or AiCoachSessionService(db)
        self._attempts = attempts or AttemptRepository(db)

    async def start(
        self, context: ActivityExecutionContext, *, actor: User, client_token: str
    ) -> NewcomerTrainingActivityAttempt:
        attempt, _ = await self.start_session(
            context, actor=actor, client_token=client_token
        )
        return attempt

    async def start_session(
        self, context: ActivityExecutionContext, *, actor: User, client_token: str
    ) -> tuple[NewcomerTrainingActivityAttempt, SalesTrainerAiCoachSession]:
        attempt = await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=activity_snapshot(context),
            client_token=client_token,
        )
        session = await self._sessions.create_activity_session(
            context=context, actor=actor
        )
        attempt = await self._attempts.attach_evidence(
            attempt_id=str(attempt.attempt_id),
            evidence_type="ai_coach_session",
            evidence_id=str(session.session_id),
            status="in_progress",
        )
        return attempt, session

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
            float(attempt.score) if attempt and attempt.score is not None else None,
            float(attempt.max_score)
            if attempt and attempt.max_score is not None
            else None,
            bool(attempt.passed) if attempt and attempt.passed is not None else None,
            None if status == "completed" else {"action": "start_ai_coach"},
            None,
        )

    async def submit_turn(
        self,
        context: ActivityExecutionContext,
        *,
        session_id: str,
        actor: User,
        answer: str,
        client_token: str,
    ) -> dict[str, Any]:
        if context.activity.type != "ai_coach":
            raise RuntimeError("activity context is not ai_coach")
        return await self._sessions.submit_activity_turn(
            session_id=session_id,
            actor=actor,
            answer=answer,
            client_token=client_token,
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


__all__ = ["AiCoachActivityHandler"]
