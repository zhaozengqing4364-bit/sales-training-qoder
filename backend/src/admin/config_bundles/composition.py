"""Admin composition root for configuration-governance lifecycle capabilities."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.adapters import list_config_bundle_adapters
from admin.config_bundles.sqlalchemy_adapter import (
    SqlAlchemyConfigLifecycleAdapter,
)
from common.config import Settings
from configuration_governance.lifecycle import (
    ConfigBundleLifecycleService as NeutralConfigBundleLifecycleService,
)
from configuration_governance.rollout import select_configuration_authority


class LegacyConfigBundleLifecycleService(SqlAlchemyConfigLifecycleAdapter):
    """Named rollback authority retained until Gate 6 consumer proof is empty."""


LifecycleAuthority = (
    NeutralConfigBundleLifecycleService | LegacyConfigBundleLifecycleService
)


def build_config_bundle_lifecycle(
    db: AsyncSession,
    *,
    governance_enabled: bool | None = None,
) -> LifecycleAuthority:
    enabled = (
        Settings().CONFIGURATION_GOVERNANCE_ENABLED
        if governance_enabled is None
        else governance_enabled
    )
    adapters = list_config_bundle_adapters()
    def neutral_factory() -> LifecycleAuthority:
        return NeutralConfigBundleLifecycleService(
            SqlAlchemyConfigLifecycleAdapter(db, adapters=adapters)
        )

    def legacy_factory() -> LifecycleAuthority:
        return LegacyConfigBundleLifecycleService(db, adapters=adapters)

    return select_configuration_authority(
        enabled=enabled,
        neutral_factory=neutral_factory,
        legacy_factory=legacy_factory,
    )
