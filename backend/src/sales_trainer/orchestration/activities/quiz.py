"""ExamPaper-backed quiz activity."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.activities.base import (
    ActivityExecutionContext,
    ActivityProjection,
    activity_snapshot,
)
from sales_trainer.orchestration.contracts import QuizConfig
from sales_trainer.orchestration.errors import NewcomerOrchestrationError
from sales_trainer.orchestration.repository import AttemptRepository
from sales_trainer.schemas import PaperAttemptCreate, QuizAnswerSubmit
from sales_trainer.services.exam_paper_service import ExamPaperService


class QuizActivityHandler:
    type_key = "quiz"

    def __init__(
        self,
        db: AsyncSession,
        *,
        papers: ExamPaperService | None = None,
        attempts: AttemptRepository | None = None,
    ) -> None:
        self._papers = papers or ExamPaperService(db)
        self._attempts = attempts or AttemptRepository(db)

    async def submit(
        self,
        context: ActivityExecutionContext,
        *,
        answers: list[QuizAnswerSubmit],
        client_token: str,
        actor: User,
    ) -> NewcomerTrainingActivityAttempt:
        config = self._config(context)
        if str(actor.user_id) != context.learner_id:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]", "不能替其他学员提交考试。", 403
            )
        unified = await self._attempts.create(
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity.activity_id,
            activity_type=self.type_key,
            activity_snapshot=activity_snapshot(context),
            client_token=client_token,
        )
        evidence = await self._papers.submit_paper_attempt(
            PaperAttemptCreate(
                paper_id=config.exam_paper_id,
                answers=answers,
                client_token=client_token,
            ),
            actor=actor,
            execution_context=context,
        )
        passed = bool(evidence.passed)
        setattr(unified, "score", _decimal(evidence.total_score))
        setattr(unified, "max_score", _decimal(evidence.max_score))
        setattr(unified, "passed", passed)
        return await self._attempts.attach_evidence(
            attempt_id=str(unified.attempt_id),
            evidence_type="quiz_attempt",
            evidence_id=str(evidence.attempt_id),
            status="completed" if passed else "failed",
        )

    async def project(self, context: ActivityExecutionContext) -> ActivityProjection:
        attempt = await self._attempts.latest_for_activity(
            enrollment_id=context.enrollment_id,
            activity_id=context.activity.activity_id,
        )
        if attempt is None:
            return ActivityProjection(
                context.activity.activity_id,
                self.type_key,
                "not_started",
                False,
                None,
                None,
                None,
                {"action": "start_quiz"},
                None,
            )
        return ActivityProjection(
            context.activity.activity_id,
            self.type_key,
            str(attempt.status),
            bool(attempt.passed),
            float(attempt.score) if attempt.score is not None else None,
            float(attempt.max_score) if attempt.max_score is not None else None,
            bool(attempt.passed) if attempt.passed is not None else None,
            None if attempt.passed else {"action": "retry_quiz"},
            None,
        )

    @staticmethod
    def _config(context: ActivityExecutionContext) -> QuizConfig:
        if context.activity.type != "quiz":
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_CONTEXT_MISMATCH]", "当前活动不是考试。", 409
            )
        return cast(QuizConfig, context.activity.config)

    async def validate_config(self, activity: Any) -> tuple[Any, ...]:
        return ()

    async def check_access(self, context: ActivityExecutionContext) -> None:
        del context

    async def refresh_attempt(
        self, context: ActivityExecutionContext, attempt: Any
    ) -> Any:
        del context
        return attempt


def _decimal(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


__all__ = ["QuizActivityHandler"]
