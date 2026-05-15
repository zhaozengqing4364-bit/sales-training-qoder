"""
Evaluation API Routes
Staged Evaluation and Comprehensive Report endpoints (C6-C7)
"""

from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.scoring_rulesets import router as admin_scoring_rulesets_router
from common.ai.llm_service import LLMService
from common.api.response import error_response
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import PracticeSession, User
from common.db.session import get_db
from evaluation.schemas import (
    ComprehensiveReportDimensionScore,
    ComprehensiveReportResponse,
    ComprehensiveReportStageSummary,
    RealtimeEvaluationFeedback,
)
from evaluation.services.comprehensive_report import ComprehensiveReportService
from evaluation.services.staged_evaluation import StagedEvaluationService
from prompt_templates.service import PromptTemplateService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
router.include_router(admin_scoring_rulesets_router)

REPORT_GENERATION_GENERIC_MESSAGE = "报告生成失败，请稍后重试。"
REPORT_STORAGE_GENERIC_MESSAGE = "报告生成失败，存储服务暂时不可用，请稍后重试。"


def _evaluation_error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message),
    )


async def verify_session_access(
    session_id: str, current_user: User, db: AsyncSession
) -> bool:
    if str(current_user.role) == "admin":
        return True

    result = await db.execute(
        select(PracticeSession).where(
            PracticeSession.session_id == session_id,
            PracticeSession.user_id == current_user.user_id,
        )
    )
    session = result.scalar_one_or_none()
    return session is not None


def _build_report_service(db: AsyncSession) -> ComprehensiveReportService:
    """Build ComprehensiveReportService with all dependencies."""
    llm_service = LLMService()
    prompt_service = PromptTemplateService(db)
    staged_eval_service = StagedEvaluationService(
        db_session=db, prompt_service=prompt_service, llm_service=llm_service
    )
    return ComprehensiveReportService(
        db_session=db,
        staged_eval_service=staged_eval_service,
        prompt_service=prompt_service,
        llm_service=llm_service,
    )


def _build_response(report: Any) -> ComprehensiveReportResponse:
    """Convert internal ComprehensiveReport to API response."""
    generated_at = ""
    if hasattr(report, "generated_at") and report.generated_at:
        generated_at = (
            report.generated_at.isoformat()
            if hasattr(report.generated_at, "isoformat")
            else str(report.generated_at)
        )

    return ComprehensiveReportResponse(
        session_id=report.session_id,
        generated_at=generated_at,
        overall_score=report.overall_score,
        dimension_scores=[
            ComprehensiveReportDimensionScore(
                name=ds.name,
                score=ds.score,
                weight=ds.weight,
                description=ds.description,
            )
            for ds in report.dimension_scores
        ],
        key_strengths=report.key_strengths,
        key_improvements=report.key_improvements,
        recommendations=report.recommendations,
        detailed_feedback=report.detailed_feedback,
        stage_summaries=[
            ComprehensiveReportStageSummary(
                stage_number=s.get("stage_number", 0),
                start_turn=s.get("start_turn", 0),
                end_turn=s.get("end_turn", 0),
                average_score=s.get("average_score", 0.0),
                key_points=s.get("key_points", []),
                summary=s.get("summary", ""),
            )
            for s in report.stage_summaries
        ],
        ruleset_id=getattr(report, "ruleset_id", None),
        ruleset_version=getattr(report, "ruleset_version", None),
        score_basis=getattr(report, "score_basis", None),
        ruleset_source=getattr(report, "ruleset_source", None),
        scoring_metadata=getattr(report, "scoring_metadata", None),
    )


def _report_generation_error_response(
    *,
    detail: str,
    session_id: str,
) -> JSONResponse:
    if "NO_STAGE_RESULTS" in detail:
        return _evaluation_error_response(
            status_code=422,
            error_code="[NO_STAGE_RESULTS]",
            message="缺少阶段评估结果，无法生成综合报告。",
        )
    if "DATABASE_ERROR" in detail:
        return build_server_error(
            "[DATABASE_ERROR]",
            message=REPORT_GENERATION_GENERIC_MESSAGE,
            exc=ValueError(detail),
            session_id=session_id,
        )
    if "STORAGE_ERROR" in detail:
        return build_server_error(
            "[STORAGE_ERROR]",
            message=REPORT_STORAGE_GENERIC_MESSAGE,
            exc=ValueError(detail),
            session_id=session_id,
        )
    return build_server_error(
        "[REPORT_GENERATION_FAILED]",
        message=REPORT_GENERATION_GENERIC_MESSAGE,
        exc=ValueError(detail),
        session_id=session_id,
    )


@router.get("/sessions/{session_id}/report", response_model=ComprehensiveReportResponse)
async def get_comprehensive_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComprehensiveReportResponse | JSONResponse:
    """Get existing comprehensive report for a session."""
    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        return _evaluation_error_response(
            status_code=403,
            error_code="[ACCESS_DENIED]",
            message="你没有权限访问该会话。",
        )

    service = _build_report_service(db)
    report_result = await service.get_report(session_id)

    if not report_result.is_success or report_result.value is None:
        detail = report_result.fallback or "Report not found"
        if "REPORT_NOT_FOUND" in detail:
            return _evaluation_error_response(
                status_code=404,
                error_code="[REPORT_NOT_FOUND]",
                message="报告不存在。",
            )
        return build_server_error(
            "[REPORT_FETCH_FAILED]",
            message=detail,
            session_id=session_id,
        )

    return _build_response(report_result.value)


@router.post(
    "/sessions/{session_id}/report", response_model=ComprehensiveReportResponse
)
async def generate_comprehensive_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComprehensiveReportResponse | JSONResponse:
    """Generate a new comprehensive report for a session using AI evaluation."""
    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        return _evaluation_error_response(
            status_code=403,
            error_code="[ACCESS_DENIED]",
            message="你没有权限访问该会话。",
        )

    service = _build_report_service(db)
    result = await service.generate_report(session_id)

    if not result.is_success:
        message = result.fallback or "Report generation failed"
        return _report_generation_error_response(detail=message, session_id=session_id)

    if result.value is None:
        return build_server_error(
            "[REPORT_GENERATION_FAILED]",
            message="Report generation returned no payload",
            session_id=session_id,
        )

    return _build_response(result.value)


@router.get(
    "/sessions/{session_id}/feedback",
    response_model=list[RealtimeEvaluationFeedback],
)
async def get_realtime_feedback(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RealtimeEvaluationFeedback] | JSONResponse:
    from common.db.models import StagedEvaluationResult

    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        return _evaluation_error_response(
            status_code=403,
            error_code="[ACCESS_DENIED]",
            message="你没有权限访问该会话。",
        )

    result = await db.execute(
        select(StagedEvaluationResult)
        .where(StagedEvaluationResult.session_id == session_id)
        .order_by(StagedEvaluationResult.stage_number)
    )
    evaluations = result.scalars().all()

    feedback_list = []
    for eval_item in evaluations:
        eval_row = cast(Any, eval_item)
        feedback_list.append(
            RealtimeEvaluationFeedback(
                stage_number=int(eval_row.stage_number or 0),
                timestamp=eval_row.created_at.isoformat(),
                scores=dict(eval_row.scores or {}),
                feedback=str(eval_row.summary or ""),
                suggestions=list(eval_row.suggestions or []),
                trigger_type="turn_count",
            )
        )

    return feedback_list
