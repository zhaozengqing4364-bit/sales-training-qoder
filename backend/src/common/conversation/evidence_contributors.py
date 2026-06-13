from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PresentationEvidenceReview:
    payload: dict[str, Any] | None
    error: str | None = None


PresentationEvidenceReviewContributor = Callable[
    [AsyncSession, str],
    Awaitable[PresentationEvidenceReview],
]

_presentation_review_contributors: dict[str, PresentationEvidenceReviewContributor] = {}


def register_presentation_evidence_review_contributor(
    provider_key: str,
    contributor: PresentationEvidenceReviewContributor,
) -> None:
    _presentation_review_contributors[provider_key] = contributor


async def build_registered_presentation_evidence_review(
    db: AsyncSession,
    session_id: str,
) -> PresentationEvidenceReview:
    for provider_key, contributor in _presentation_review_contributors.items():
        try:
            review = await contributor(db, session_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "presentation_evidence_review_contributor_failed",
                provider_key=provider_key,
                error=str(exc),
                exc_info=True,
            )
            continue
        if review.payload is not None or review.error is not None:
            return review
    return PresentationEvidenceReview(payload=None, error="[PRESENTATION_REVIEW_FAILED]")


def clear_evidence_contributors() -> None:
    _presentation_review_contributors.clear()
