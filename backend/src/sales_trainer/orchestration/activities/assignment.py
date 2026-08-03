"""Text/file assignment activity."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
)
from sales_trainer.orchestration.contracts import AssignmentConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.repository import AttemptRepository


class AssignmentActivityHandler:
    type_key = "assignment"

    def __init__(
        self,
        db: AsyncSession,
        *,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._attempts = attempts or AttemptRepository(db)

    async def project(self, context: ActivityExecutionContext) -> ActivityProjection:
        attempt = context.latest_attempt
        if not context.latest_attempt_loaded:
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
            None if status == "completed" else {"action": "submit_assignment"},
            "等待管理员审核" if status == "needs_review" else None,
        )

    @staticmethod
    def _config(context: ActivityExecutionContext) -> AssignmentConfig:
        if context.activity.type != "assignment":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_CONTEXT_MISMATCH]", "当前活动不是作业。", 409
            )
        return cast(AssignmentConfig, context.activity.config)

    async def validate_config(self, activity: Any) -> tuple[Any, ...]:
        return ()

    async def check_access(self, context: ActivityExecutionContext) -> None:
        del context

    async def refresh_attempt(
        self, context: ActivityExecutionContext, attempt: Any
    ) -> Any:
        del context
        return attempt


__all__ = ["AssignmentActivityHandler"]
