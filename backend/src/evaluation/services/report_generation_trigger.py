"""
Report Generation Trigger Service

Automatically triggers comprehensive report generation when a session ends.
Implements retry mechanism and status tracking.

Story 3.1: 会话结束自动生成训练报告
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from common.db.models import PracticeSession, ReportGenerationStatus
from common.db.session import AsyncSessionLocal
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from evaluation.services.comprehensive_report import ComprehensiveReportService
from prompt_templates.service import PromptTemplateService
from common.ai.llm_service import LLMService

logger = get_logger(__name__)


@asynccontextmanager
async def get_db_session() -> AsyncSession:
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
    ):
        self.db = db
        self.report_service = report_service
        self._init_report_service()

    def _init_report_service(self) -> None:
        """Initialize report service if not provided."""
        if self.report_service is None:
            from evaluation.services.staged_evaluation import StagedEvaluationService
            from common.ai.llm_service import LLMService
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
            await self._update_report_status(
                session_id,
                ReportGenerationStatus.PROCESSING,
            )

            # Generate report with retry
            result = await self._generate_report_with_retry(session_id, scenario_type)

            if result.is_success:
                await self._update_report_status(
                    session_id,
                    ReportGenerationStatus.COMPLETED,
                )
                logger.info(
                    "report_generation_completed",
                    session_id=session_id,
                    overall_score=result.value.overall_score if hasattr(result.value, 'overall_score') else None,
                )
            else:
                error_msg = result.fallback or "Unknown error"
                await self._update_report_status(
                    session_id,
                    ReportGenerationStatus.FAILED,
                    error=error_msg,
                )
                logger.error(
                    "report_generation_failed",
                    session_id=session_id,
                    error=error_msg,
                )

        except Exception as e:
            await self._update_report_status(
                session_id,
                ReportGenerationStatus.FAILED,
                error=str(e),
            )
            logger.error(
                "report_generation_exception",
                session_id=session_id,
                error=str(e),
                exc_info=True,
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
        scoring_context = None
        try:
            from evaluation.services.realtime_scoring import RealtimeScoringService
            scoring_result = await RealtimeScoringService.get_scoring_context_from_db(
                session_id=session_id,
                db_session=self.db,
            )
            if scoring_result.is_success:
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

        result = await self.report_service.generate_report(**kwargs)

        return result

    async def _update_report_status(
        self,
        session_id: str,
        status: ReportGenerationStatus,
        error: str | None = None,
    ) -> None:
        """
        Update report generation status in database.

        Args:
            session_id: The practice session ID
            status: New report generation status
            error: Error message if failed
        """
        stmt = select(PracticeSession).where(
            PracticeSession.session_id == session_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            session.report_status = status.value
            if status == ReportGenerationStatus.COMPLETED:
                session.report_generated_at = datetime.now(timezone.utc)
            if error:
                session.report_error = error
            await self.db.flush()

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
        stmt = select(PracticeSession).where(
            PracticeSession.session_id == session_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return Result.fail("[SESSION_NOT_FOUND]")

        return Result.ok({
            "session_id": session_id,
            "report_status": session.report_status,
            "report_generated_at": session.report_generated_at.isoformat() if session.report_generated_at else None,
            "report_error": session.report_error,
        })


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
            async with get_db_session() as db_session:
                trigger = ReportGenerationTrigger(db_session)
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
