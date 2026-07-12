"""LearningContent-backed lesson activity."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
)
from sales_trainer.orchestration.contracts import LessonConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.services.curriculum_practice_adapter import LearningProgressAdapter


class LessonActivityHandler:
    type_key = "lesson"

    def __init__(
        self,
        db: AsyncSession,
        *,
        progress: LearningProgressAdapter | None = None,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._progress = progress or LearningProgressAdapter(db)
        self._attempts = attempts or AttemptRepository(db)

    async def project(self, context: ActivityExecutionContext) -> ActivityProjection:
        config = self._config(context)
        result = await self._progress.study_content(
            user_id=context.learner_id, content_id=config.learning_content_id
        )
        if not result.is_success or result.value is None:
            raise NewcomerOrchestrationError(
                result.fallback or "[NEWCOMER_LESSON_UNAVAILABLE]",
                "学习内容暂不可用，请联系管理员。",
                409,
            )
        progress = result.value.progress
        completed = bool(progress.is_completed)
        return ActivityProjection(
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            status="completed" if completed else str(progress.state),
            completed=completed,
            score=None,
            max_score=None,
            passed=None,
            next_action=None if completed else {"action": "continue_lesson"},
            message=None,
        )

    async def mark_chapter_complete(
        self,
        context: ActivityExecutionContext,
        *,
        chapter_id: str,
        actor: User,
        client_token: str,
    ) -> ActivityProjection:
        if str(actor.user_id) != context.learner_id:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]",
                "不能修改其他学员的训练进度。",
                403,
            )
        config = self._config(context)
        result = await self._progress.complete_chapter(
            user_id=context.learner_id,
            content_id=config.learning_content_id,
            chapter_id=chapter_id,
        )
        if not result.is_success:
            raise NewcomerOrchestrationError(
                result.fallback or "[NEWCOMER_LESSON_PROGRESS_FAILED]",
                "章节进度保存失败，请重试。",
                409,
            )
        attempt = await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=context.activity.model_dump(mode="json"),
            client_token=client_token,
        )
        projection = await self.project(context)
        if projection.completed:
            await self._attempts.attach_evidence(
                attempt_id=str(attempt.attempt_id),
                evidence_type="learning_progress",
                evidence_id=config.learning_content_id,
                status="completed",
            )
        return projection

    @staticmethod
    def _config(context: ActivityExecutionContext) -> LessonConfig:
        if context.activity.type != "lesson":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_CONTEXT_MISMATCH]", "当前活动不是内容学习。", 409
            )
        return cast(LessonConfig, context.activity.config)

    async def validate_config(self, activity: Any) -> tuple[Any, ...]:
        return ()

    async def check_access(self, context: ActivityExecutionContext) -> None:
        del context

    async def refresh_attempt(
        self, context: ActivityExecutionContext, attempt: Any
    ) -> Any:
        del context
        return attempt


__all__ = ["LessonActivityHandler"]
