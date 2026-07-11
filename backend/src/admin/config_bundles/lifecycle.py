"""Compatibility import for the neutral configuration-governance lifecycle."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.composition import (
    LegacyConfigBundleLifecycleService,
    build_config_bundle_lifecycle,
)
from configuration_governance.contracts import (
    ConfigLifecycleResult,
    ConfigVersionRecord,
)


class ConfigBundleLifecycleService:
    """Forward old construction to the single selected lifecycle authority."""

    def __init__(self, db: AsyncSession) -> None:
        self._authority = build_config_bundle_lifecycle(db)

    async def create_draft(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.create_draft(
            bundle_key=bundle_key,
            value=value,
            actor_id=actor_id,
            reason=reason,
        )

    async def validate(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.validate(
            bundle_key=bundle_key,
            value=value,
            actor_id=actor_id,
            reason=reason,
        )

    async def preview(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.preview(
            bundle_key=bundle_key,
            value=value,
            actor_id=actor_id,
            reason=reason,
        )

    async def publish(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        config_id: str | None,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.publish(
            bundle_key=bundle_key,
            actor_id=actor_id,
            config_id=config_id,
            reason=reason,
        )

    async def rollback(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        target_config_id: str | None,
        target_version: int | None,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.rollback(
            bundle_key=bundle_key,
            actor_id=actor_id,
            target_config_id=target_config_id,
            target_version=target_version,
            reason=reason,
        )

    async def disable(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._authority.disable(
            bundle_key=bundle_key,
            actor_id=actor_id,
            reason=reason,
        )

    async def resolve_active_version(
        self, bundle_key: str
    ) -> ConfigVersionRecord | None:
        return await self._authority.resolve_active_version(bundle_key)

    def version_snapshot(
        self, version: ConfigVersionRecord | None
    ) -> dict[str, Any] | None:
        return self._authority.version_snapshot(version)


__all__ = [
    "ConfigBundleLifecycleService",
    "ConfigLifecycleResult",
    "LegacyConfigBundleLifecycleService",
    "build_config_bundle_lifecycle",
]
