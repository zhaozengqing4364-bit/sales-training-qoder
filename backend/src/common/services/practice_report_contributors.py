from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

RoleplayComplianceSummaryContributor = Callable[[PracticeSession], dict[str, Any]]
ComprehensiveSalesReportContributor = Callable[
    [AsyncSession, str],
    Awaitable[None],
]

_roleplay_compliance_summary_contributors: dict[
    str,
    RoleplayComplianceSummaryContributor,
] = {}
_comprehensive_sales_report_contributors: dict[
    str,
    ComprehensiveSalesReportContributor,
] = {}


def register_roleplay_compliance_summary_contributor(
    provider_key: str,
    contributor: RoleplayComplianceSummaryContributor,
) -> None:
    _roleplay_compliance_summary_contributors[provider_key] = contributor


def build_registered_roleplay_compliance_summary(
    session: PracticeSession,
) -> dict[str, Any]:
    for provider_key, contributor in _roleplay_compliance_summary_contributors.items():
        try:
            summary = contributor(session)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "roleplay_compliance_summary_contributor_failed",
                provider_key=provider_key,
                error=str(exc),
                exc_info=True,
            )
            continue
        if summary:
            return summary
    return {}


def register_comprehensive_sales_report_contributor(
    provider_key: str,
    contributor: ComprehensiveSalesReportContributor,
) -> None:
    _comprehensive_sales_report_contributors[provider_key] = contributor


async def maybe_generate_registered_comprehensive_sales_report(
    db: AsyncSession,
    session_id: str,
) -> None:
    for provider_key, contributor in _comprehensive_sales_report_contributors.items():
        try:
            await contributor(db, session_id)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "comprehensive_sales_report_contributor_failed",
                provider_key=provider_key,
                session_id=session_id,
                error=str(exc),
                exc_info=True,
            )


def clear_practice_report_contributors() -> None:
    _roleplay_compliance_summary_contributors.clear()
    _comprehensive_sales_report_contributors.clear()
