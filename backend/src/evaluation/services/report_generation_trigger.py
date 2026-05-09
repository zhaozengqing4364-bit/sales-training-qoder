"""
Report Generation Trigger Service

Automatically triggers comprehensive report generation when a session ends.
Implements retry mechanism and status tracking.

Story 3.1: 会话结束自动生成训练报告
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import PracticeSession, ReportGenerationStatus, SessionStatus
from common.db.session import AsyncSessionLocal
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from evaluation.services.comprehensive_report import ComprehensiveReportService

logger = get_logger(__name__)


def _set_runtime_field(row: object, name: str, value: object) -> None:
    setattr(row, name, value)


def _runtime_field(row: object, name: str) -> Any:
    return cast(Any, getattr(row, name))


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Create an async DB session for fire-and-forget report generation."""
    async with AsyncSessionLocal() as db:
        yield db


class ReportGenerationError(Exception):
    """Raised when report generation fails after all retries."""

    pass


class ReportGenerationTrigger:
    """
    Triggers report generation when sessions end.

    Features:
    - Async trigger on session end
    - Retry mechanism with exponential backoff
    - Status tracking (pending/processing/completed/failed)
    - Non-blocking session end response
    """

    def __init__(
        self,
        db: AsyncSession,
        report_service: ComprehensiveReportService | None = None,
        *,
        owns_db_session: bool = False,
    ):
        self.db = db
        self.report_service = report_service
        self.owns_db_session = owns_db_session
        self._init_report_service()

    def _init_report_service(self) -> None:
        """Initialize report service if not provided."""
        if self.report_service is None:
            from common.ai.llm_service import LLMService
            from evaluation.services.staged_evaluation import StagedEvaluationService
            from prompt_templates.service import PromptTemplateService

            prompt_service = PromptTemplateService(self.db)
            llm_service = LLMService()
            staged_eval = StagedEvaluationService(
                db_session=self.db,
                prompt_service=prompt_service,
                llm_service=llm_service,
            )

            self.report_service = ComprehensiveReportService(
                db_session=self.db,
                staged_eval_service=staged_eval,
                prompt_service=prompt_service,
                llm_service=llm_service,
            )

    async def trigger_on_session_end(
        self,
        session_id: str,
        scenario_type: str = "sales",
    ) -> None:
        """
        Trigger report generation when session ends.

        This method is designed to be called asynchronously (fire-and-forget)
        so it doesn't block the session end response.

        Args:
            session_id: The practice session ID
            scenario_type: Type of scenario (sales/presentation)
        """
        try:
            # Update status to processing
            session = await self._update_report_status(
                session_id,
                ReportGenerationStatus.PROCESSING,
            )
            if session is None:
                return
            await self._commit_if_owned()

            # Generate report with retry
            result = await self._generate_report_with_retry(session_id, scenario_type)

            if result.is_success:
                generated_report = result.value
                await self._update_report_status(
                    session_id,
                    ReportGenerationStatus.COMPLETED,
                )
                await self._finalize_session_status_if_ready(
                    session_id,
                    scenario_type=scenario_type,
                )
                await self._commit_if_owned()
                logger.info(
                    "report_generation_completed",
                    session_id=session_id,
                    overall_score=getattr(generated_report, "overall_score", None),
                )
            else:
                error_msg = result.fallback or "Unknown error"
                await self._update_report_status(
                    session_id,
                    ReportGenerationStatus.FAILED,
                    error=error_msg,
                )
                await self._finalize_session_status_if_ready(
                    session_id,
                    scenario_type=scenario_type,
                )
                await self._commit_if_owned()
                logger.error(
                    "report_generation_failed",
                    session_id=session_id,
                    error=error_msg,
                )

        except Exception as e:
            if self.owns_db_session:
                await self.db.rollback()
            await self._update_report_status(
                session_id,
                ReportGenerationStatus.FAILED,
                error=str(e),
            )
            await self._finalize_session_status_if_ready(
                session_id,
                scenario_type=scenario_type,
            )
            await self._commit_if_owned()
            logger.error(
                "report_generation_exception",
                session_id=session_id,
                error=str(e),
                exc_info=True,
            )

    async def _commit_if_owned(self) -> None:
        if not self.owns_db_session:
            return

        await self.db.commit()

    async def _finalize_session_status_if_ready(
        self,
        session_id: str,
        *,
        scenario_type: str,
    ) -> None:
        """Promote a sales session from scoring to completed once canonical evidence is readable."""
        if (scenario_type or "").lower() != "sales":
            return

        stmt = select(PracticeSession).where(PracticeSession.session_id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if (
            session is None
            or _runtime_field(session, "status") != SessionStatus.SCORING.value
        ):
            return

        projection_result = await SessionEvidenceService(self.db).get_projection(
            session_id=session_id,
            session=session,
            require_completed=False,
            scenario_type="sales",
        )
        if not projection_result.is_success:
            logger.info(
                "sales_session_finalization_deferred",
                session_id=session_id,
                reason=projection_result.fallback,
            )
            return

        projection = projection_result.value
        if projection is None:
            logger.info(
                "sales_session_finalization_deferred",
                session_id=session_id,
                reason="missing_projection",
            )
            return
        if not projection.evidence_completeness.get("session_scores", False):
            logger.info(
                "sales_session_finalization_deferred",
                session_id=session_id,
                reason="missing_session_scores",
            )
            return

        _set_runtime_field(session, "status", SessionStatus.COMPLETED.value)
        await self.db.flush()
        logger.info(
            "sales_session_finalized",
            session_id=session_id,
            report_status=_runtime_field(session, "report_status"),
            message_count=projection.evidence_completeness.get("message_count"),
            projection_complete=projection.evidence_completeness.get("complete"),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def _generate_report_with_retry(
        self,
        session_id: str,
        scenario_type: str,
    ) -> Result[Any]:
        """
        Generate report with retry mechanism.

        Args:
            session_id: The practice session ID
            scenario_type: Type of scenario

        Returns:
            Result with report or error
        """
        logger.info(
            "report_generation_attempt",
            session_id=session_id,
            scenario_type=scenario_type,
        )

        # Get realtime scoring context from Track D (if available)
        scoring_context: dict[str, Any] | None = None
        try:
            from evaluation.services.realtime_scoring import RealtimeScoringService

            scoring_result = await RealtimeScoringService.get_scoring_context_from_db(
                session_id=session_id,
                db_session=self.db,
            )
            if scoring_result.is_success and isinstance(scoring_result.value, dict):
                scoring_context = scoring_result.value
                logger.info(
                    "scoring_context_loaded",
                    session_id=session_id,
                    final_score=scoring_context.get("final_score"),
                )
            else:
                logger.info(
                    "no_scoring_context_available",
                    session_id=session_id,
                    fallback=scoring_result.fallback,
                )
        except Exception as e:
            logger.warning(
                "scoring_context_load_failed",
                session_id=session_id,
                error=str(e),
            )

        kwargs: dict[str, Any] = {
            "session_id": session_id,
            "scenario_type": scenario_type,
        }
        if scoring_context is not None:
            kwargs["scoring_context"] = scoring_context

        report_service = self.report_service
        if report_service is None:
            return Result.fail("[REPORT_SERVICE_UNAVAILABLE]")

        result = await report_service.generate_report(**kwargs)

        return result

    async def _update_report_status(
        self,
        session_id: str,
        status: ReportGenerationStatus,
        error: str | None = None,
    ) -> PracticeSession | None:
        """
        Update report generation status in database.

        Args:
            session_id: The practice session ID
            status: New report generation status
            error: Error message if failed
        """
        stmt = select(PracticeSession).where(PracticeSession.session_id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            logger.warning(
                "report_generation_session_missing",
                session_id=session_id,
                report_status=status.value,
            )
            return None

        _set_runtime_field(session, "report_status", status.value)
        if status == ReportGenerationStatus.COMPLETED:
            _set_runtime_field(session, "report_generated_at", datetime.now(UTC))
        if error:
            _set_runtime_field(session, "report_error", error)
        elif status != ReportGenerationStatus.FAILED:
            _set_runtime_field(session, "report_error", None)
        await self.db.flush()
        return session

    async def get_report_status(
        self,
        session_id: str,
    ) -> Result[dict[str, Any]]:
        """
        Get report generation status for a session.

        Args:
            session_id: The practice session ID

        Returns:
            Result with status info
        """
        stmt = select(PracticeSession).where(PracticeSession.session_id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return Result.fail("[SESSION_NOT_FOUND]")

        return Result.ok(
            {
                "session_id": session_id,
                "report_status": _runtime_field(session, "report_status"),
                "report_generated_at": _runtime_field(
                    session, "report_generated_at"
                ).isoformat()
                if _runtime_field(session, "report_generated_at")
                else None,
                "report_error": _runtime_field(session, "report_error"),
            }
        )


# Singleton instance for fire-and-forget triggers
_report_trigger_instances: dict[str, ReportGenerationTrigger] = {}


async def trigger_report_generation(
    session_id: str,
    scenario_type: str = "sales",
    db: AsyncSession | None = None,
) -> None:
    """
    Fire-and-forget function to trigger report generation.

    Usage:
        # In session lifecycle service
        asyncio.create_task(trigger_report_generation(session_id, scenario_type))

    Args:
        session_id: The practice session ID
        scenario_type: Type of scenario
        db: Database session (optional, will create new if not provided)
    """
    try:
        if db is None:
            db_session: AsyncSession
            async with get_db_session() as db_session:
                trigger = ReportGenerationTrigger(db_session, owns_db_session=True)
                await trigger.trigger_on_session_end(session_id, scenario_type)
        else:
            trigger = ReportGenerationTrigger(db)
            await trigger.trigger_on_session_end(session_id, scenario_type)

    except Exception as e:
        logger.error(
            "trigger_report_generation_failed",
            session_id=session_id,
            error=str(e),
            exc_info=True,
        )
