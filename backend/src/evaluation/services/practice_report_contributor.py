from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.monitoring.logger import get_logger
from common.services.practice_report_contributors import (
    register_comprehensive_sales_report_contributor,
)
from evaluation.services.comprehensive_report import ComprehensiveReportService
from evaluation.services.staged_evaluation import StagedEvaluationService
from prompt_templates.service import PromptTemplateService

EVALUATION_PRACTICE_REPORT_CONTRIBUTOR = "evaluation.comprehensive_sales_report"

logger = get_logger(__name__)


async def generate_comprehensive_sales_report(
    db: AsyncSession,
    session_id: str,
) -> None:
    llm_service = LLMService()
    prompt_service = PromptTemplateService(db)
    staged_eval_service = StagedEvaluationService(
        db_session=db,
        prompt_service=prompt_service,
        llm_service=llm_service,
    )
    report_service = ComprehensiveReportService(
        db_session=db,
        staged_eval_service=staged_eval_service,
        prompt_service=prompt_service,
        llm_service=llm_service,
    )
    comprehensive_result = await report_service.generate_report(
        session_id,
        scenario_type="sales",
    )
    if comprehensive_result.is_success:
        logger.info(
            "Comprehensive report generated",
            session_id=session_id,
        )
        return
    logger.warning(
        "Comprehensive report generation failed",
        session_id=session_id,
        error_code=comprehensive_result.fallback,
    )


def register_evaluation_practice_report_contributor() -> None:
    register_comprehensive_sales_report_contributor(
        EVALUATION_PRACTICE_REPORT_CONTRIBUTOR,
        generate_comprehensive_sales_report,
    )
