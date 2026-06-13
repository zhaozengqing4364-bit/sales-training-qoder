from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

AssetRevisionLineageProvider = Callable[
    [AsyncSession, str, str],
    Awaitable[dict[str, Any]],
]

_providers: dict[str, AssetRevisionLineageProvider] = {}


def register_asset_revision_lineage_provider(
    provider_key: str,
    provider: AssetRevisionLineageProvider,
) -> None:
    normalized_key = provider_key.strip()
    if not normalized_key:
        raise ValueError("asset revision lineage provider_key is required")
    _providers[normalized_key] = provider


def clear_asset_revision_lineage_providers() -> None:
    _providers.clear()


async def resolve_active_revision_lineage(
    db: AsyncSession,
    *,
    asset_type: str,
    logical_id: str,
) -> dict[str, Any]:
    for provider in tuple(_providers.values()):
        lineage = await provider(db, asset_type, logical_id)
        if lineage:
            return lineage
    return {}
