from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.monitoring.logger import get_logger

DashboardRecommendationPayload = dict[str, Any]
DashboardRecommendationProvider = Callable[
    [AsyncSession, str],
    Awaitable[DashboardRecommendationPayload | None],
]

logger = get_logger(__name__)

_providers: dict[str, DashboardRecommendationProvider] = {}


def register_dashboard_recommendation_provider(
    provider_key: str,
    provider: DashboardRecommendationProvider,
) -> None:
    """Register a domain-owned dashboard recommendation provider.

    The shared dashboard endpoint owns ordering and response validation; domains own
    their own recommendation assembly.
    """

    normalized_key = provider_key.strip()
    if not normalized_key:
        raise ValueError("dashboard recommendation provider_key is required")
    _providers[normalized_key] = provider


def clear_dashboard_recommendation_providers() -> None:
    """Reset providers for focused unit tests."""

    _providers.clear()


async def first_dashboard_recommendation(
    db: AsyncSession,
    user_id: str,
) -> DashboardRecommendationPayload | None:
    for provider_key, provider in tuple(_providers.items()):
        try:
            recommendation = await provider(db, user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "dashboard_recommendation_provider_failed",
                provider_key=provider_key,
                error_type=type(exc).__name__,
            )
            continue
        if recommendation is not None:
            return recommendation
    return None
