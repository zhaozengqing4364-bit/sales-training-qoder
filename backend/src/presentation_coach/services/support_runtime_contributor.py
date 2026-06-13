from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.evidence_contributors import (
    PresentationEvidenceReview,
    register_presentation_evidence_review_contributor,
)
from presentation_coach.services.presentation_report_service import (
    PresentationReportService,
)
from support.services.runtime_contributors import (
    RuntimePresentationReview,
    register_presentation_review_contributor,
)

PRESENTATION_COACH_SUPPORT_RUNTIME_CONTRIBUTOR = (
    "presentation_coach.presentation_review"
)


async def build_presentation_coach_review(
    db: AsyncSession,
    session_id: str,
) -> RuntimePresentationReview:
    review_result = await PresentationReportService(db).build_presentation_review(
        session_id
    )
    if review_result.is_success:
        return RuntimePresentationReview(payload=review_result.value)
    return RuntimePresentationReview(
        payload=None,
        error=review_result.fallback or "[PRESENTATION_REVIEW_FAILED]",
    )


async def build_presentation_coach_evidence_review(
    db: AsyncSession,
    session_id: str,
) -> PresentationEvidenceReview:
    review_result = await PresentationReportService(db).build_presentation_review(
        session_id
    )
    if review_result.is_success:
        return PresentationEvidenceReview(payload=review_result.value)
    return PresentationEvidenceReview(
        payload=None,
        error=review_result.fallback or "[PRESENTATION_REVIEW_FAILED]",
    )


def register_presentation_coach_support_runtime_contributor() -> None:
    register_presentation_review_contributor(
        PRESENTATION_COACH_SUPPORT_RUNTIME_CONTRIBUTOR,
        build_presentation_coach_review,
    )
    register_presentation_evidence_review_contributor(
        PRESENTATION_COACH_SUPPORT_RUNTIME_CONTRIBUTOR,
        build_presentation_coach_evidence_review,
    )
