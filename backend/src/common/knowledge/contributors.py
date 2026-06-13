from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

KnowledgeReferenceChecker = Callable[
    [AsyncSession, str],
    Awaitable[str | None],
]
KnowledgeGovernanceSummaryContributor = Callable[
    [AsyncSession, Any, list[Any], datetime],
    Awaitable[dict[str, Any] | None],
]

_reference_checkers: dict[str, KnowledgeReferenceChecker] = {}
_governance_summary_contributors: dict[str, KnowledgeGovernanceSummaryContributor] = {}


def register_knowledge_reference_checker(
    provider_key: str,
    checker: KnowledgeReferenceChecker,
) -> None:
    _reference_checkers[provider_key] = checker


async def check_registered_knowledge_references(
    db: AsyncSession,
    kb_id: str,
) -> str | None:
    for provider_key, checker in _reference_checkers.items():
        try:
            result = await checker(db, kb_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "knowledge_reference_checker_failed",
                provider_key=provider_key,
                kb_id=kb_id,
                error=str(exc),
                exc_info=True,
            )
            continue
        if result:
            return result
    return None


def register_knowledge_governance_summary_contributor(
    provider_key: str,
    contributor: KnowledgeGovernanceSummaryContributor,
) -> None:
    _governance_summary_contributors[provider_key] = contributor


async def build_registered_knowledge_governance_summary(
    db: AsyncSession,
    *,
    item: Any,
    documents: list[Any],
    now: datetime,
) -> dict[str, Any] | None:
    for provider_key, contributor in _governance_summary_contributors.items():
        try:
            summary = await contributor(db, item, documents, now)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "knowledge_governance_summary_contributor_failed",
                provider_key=provider_key,
                item_id=str(getattr(item, "id", "")),
                error=str(exc),
                exc_info=True,
            )
            continue
        if summary:
            return summary
    return None


def clear_knowledge_contributors() -> None:
    _reference_checkers.clear()
    _governance_summary_contributors.clear()
