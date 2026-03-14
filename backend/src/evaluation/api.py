"""
Evaluation API Routes
Staged Evaluation and Comprehensive Report endpoints (C6-C7)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.ai.llm_service import LLMService
from common.api.server_error import build_server_error
from common.auth.service import get_current_user
from common.db.models import PracticeSession, User
from common.db.session import get_db
from evaluation.schemas import (
    ComprehensiveReportResponse,
    ComprehensiveReportDimensionScore,
    ComprehensiveReportStageSummary,
    RealtimeEvaluationFeedback,
)
from evaluation.services.comprehensive_report import ComprehensiveReportService
from evaluation.services.staged_evaluation import StagedEvaluationService
from prompt_templates.service import PromptTemplateService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


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


def _build_response(report) -> ComprehensiveReportResponse:
    """Convert internal ComprehensiveReport to API response."""
    generated_at = ""
    if hasattr(report, "generated_at") and report.generated_at:
        generated_at = report.generated_at.isoformat() if hasattr(report.generated_at, "isoformat") else str(report.generated_at)

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
    )


@router.get("/sessions/{session_id}/report", response_model=ComprehensiveReportResponse)
async def get_comprehensive_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get existing comprehensive report for a session."""
    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    service = _build_report_service(db)
    report_result = await service.get_report(session_id)

    if not report_result.is_success or report_result.value is None:
        detail = report_result.fallback or "Report not found"
        if "REPORT_NOT_FOUND" in detail:
            raise HTTPException(status_code=404, detail=detail)
        return build_server_error(
            "[REPORT_FETCH_FAILED]",
            message=detail,
            session_id=session_id,
        )

    return _build_response(report_result.value)


@router.post("/sessions/{session_id}/report", response_model=ComprehensiveReportResponse)
async def generate_comprehensive_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new comprehensive report for a session using AI evaluation."""
    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    service = _build_report_service(db)
    result = await service.generate_report(session_id)

    if not result.is_success:
        message = result.fallback or "Report generation failed"
        return build_server_error(
            "[REPORT_GENERATION_FAILED]",
            message=message,
            session_id=session_id,
        )

    return _build_response(result.value)


@router.get("/sessions/{session_id}/feedback")
async def get_realtime_feedback(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from common.db.models import StagedEvaluationResult

    has_access = await verify_session_access(session_id, current_user, db)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(StagedEvaluationResult)
        .where(StagedEvaluationResult.session_id == session_id)
        .order_by(StagedEvaluationResult.stage_number)
    )
    evaluations = result.scalars().all()

    feedback_list = []
    for eval_item in evaluations:
        feedback_list.append(
            RealtimeEvaluationFeedback(
                stage_number=eval_item.stage_number,
                timestamp=eval_item.created_at.isoformat(),
                scores=eval_item.scores or {},
                feedback=eval_item.summary or "",
                suggestions=eval_item.suggestions or [],
                trigger_type="turn_count",
            )
        )

    return feedback_list
