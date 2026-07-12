"""Snapshot-first audio assessment activity."""

from __future__ import annotations

from typing import Any, cast

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
    activity_snapshot,
)
from sales_trainer.orchestration.contracts import AudioAssessmentConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.services.audio_submission_service import AudioSubmissionService


class AudioAssessmentActivityHandler:
    type_key = "audio_assessment"

    def __init__(
        self,
        db: AsyncSession,
        *,
        audio: AudioSubmissionService | None = None,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._audio = audio or AudioSubmissionService(db)
        self._attempts = attempts or AttemptRepository(db)

    async def submit_file(
        self,
        context: ActivityExecutionContext,
        *,
        file: UploadFile,
        confirmed_material_version_id: str | None,
        client_token: str,
        actor: User,
        auto_process: bool = True,
    ) -> NewcomerTrainingActivityAttempt:
        self._config(context)
        attempt = await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=activity_snapshot(context),
            client_token=client_token,
        )
        submission = await self._audio.save_uploaded_file(
            file=file,
            unit_id=None,
            purpose="activity_audio_assessment",
            source_page="newcomer_training_activity",
            confirmed_material_version_id=confirmed_material_version_id,
            actor=actor,
            auto_process=auto_process,
            execution_context=context,
        )
        status = "completed" if str(submission.status) == "scored" else "in_progress"
        return await self._attempts.attach_evidence(
            attempt_id=str(attempt.attempt_id),
            evidence_type="audio_submission",
            evidence_id=str(submission.submission_id),
            status=status,
        )

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
            None if status == "completed" else {"action": "record_audio"},
            None,
        )

    @staticmethod
    def _config(context: ActivityExecutionContext) -> AudioAssessmentConfig:
        if context.activity.type != "audio_assessment":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_CONTEXT_MISMATCH]", "当前活动不是录音讲解。", 409
            )
        return cast(AudioAssessmentConfig, context.activity.config)

    async def validate_config(self, activity: Any) -> tuple[Any, ...]:
        return ()

    async def check_access(self, context: ActivityExecutionContext) -> None:
        del context

    async def refresh_attempt(
        self, context: ActivityExecutionContext, attempt: Any
    ) -> Any:
        del context
        return attempt


__all__ = ["AudioAssessmentActivityHandler"]
