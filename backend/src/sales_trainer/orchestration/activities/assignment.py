"""Text/file assignment activity."""

from __future__ import annotations

from typing import Any, cast

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
)
from sales_trainer.orchestration.assignment_storage import (
    AssignmentStorage,
    ConfiguredAssignmentStorage,
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
        storage: AssignmentStorage | None = None,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._attempts = attempts or AttemptRepository(db)
        self._storage = storage or ConfiguredAssignmentStorage()

    async def submit(
        self,
        context: ActivityExecutionContext,
        *,
        text: str | None,
        file: UploadFile | None,
        client_token: str,
        actor: User,
    ) -> NewcomerTrainingActivityAttempt:
        config = self._config(context)
        if str(actor.user_id) != context.learner_id:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]", "不能替其他学员提交作业。", 403
            )
        clean_text = (text or "").strip()
        if config.submission_type == "text" and (not clean_text or file is not None):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_SUBMISSION_INVALID]", "请提交文字作业。", 422
            )
        if config.submission_type == "file" and (file is None or clean_text):
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_SUBMISSION_INVALID]", "请提交附件作业。", 422
            )
        if config.submission_type == "text_or_file" and not clean_text and file is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ASSIGNMENT_SUBMISSION_INVALID]",
                "请填写内容或上传附件。",
                422,
            )
        stored = (
            await self._storage.store(
                file=file,
                learner_id=context.learner_id,
                max_size_bytes=config.max_file_size_bytes,
            )
            if file
            else None
        )
        attempt = await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=context.activity.model_dump(mode="json"),
            client_token=client_token,
        )
        setattr(
            attempt,
            "result_snapshot",
            {"text": clean_text or None, "file": stored.as_dict() if stored else None},
        )
        status = (
            "completed"
            if config.review_mode == "automatic_complete"
            else "needs_review"
        )
        setattr(attempt, "status", status)
        setattr(attempt, "passed", True if status == "completed" else None)
        return attempt

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
