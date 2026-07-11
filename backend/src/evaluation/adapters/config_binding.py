"""Evaluation-owned read adapter for immutable ConfigBundle lineage."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ConfigBundle, ConfigVersion
from configuration_governance.contracts import ConfigVersionBinding


async def resolve_active_config_binding(
    db: AsyncSession,
    *,
    bundle_key: str,
) -> ConfigVersionBinding | None:
    result = await db.execute(
        select(ConfigVersion, ConfigBundle)
        .join(ConfigBundle, ConfigBundle.bundle_id == ConfigVersion.bundle_id)
        .where(
            ConfigBundle.bundle_key == bundle_key,
            ConfigVersion.status.in_(("published", "disabled")),
        )
        .order_by(ConfigVersion.version_number.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    version, bundle = row
    return ConfigVersionBinding(
        bundle_id=str(bundle.bundle_id),
        version_id=str(version.version_id),
        source_config_id=(
            str(version.source_config_id) if version.source_config_id else None
        ),
        version_number=int(version.version_number or 0),
        version_label=str(version.version_label),
        status=str(version.status),
    )
