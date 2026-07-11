"""Curriculum adapter for immutable configuration-version lineage bindings."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ConfigBundle, ConfigVersion
from configuration_governance.contracts import ConfigVersionBinding


async def resolve_config_version_binding(
    db: AsyncSession,
    *,
    bundle_key: str,
    source_config_id: str,
) -> ConfigVersionBinding | None:
    """Resolve an existing immutable binding without invoking lifecycle writes."""

    result = await db.execute(
        select(ConfigVersion, ConfigBundle)
        .join(ConfigBundle, ConfigBundle.bundle_id == ConfigVersion.bundle_id)
        .where(
            ConfigBundle.bundle_key == bundle_key,
            ConfigVersion.source_config_id == source_config_id,
        )
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
