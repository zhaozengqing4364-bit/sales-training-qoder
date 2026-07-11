"""Deep lifecycle module over a persistence capability supplied at composition time."""

from __future__ import annotations

from typing import Any

from configuration_governance.contracts import (
    ConfigLifecycleBackend,
    ConfigLifecycleResult,
)


class ConfigBundleLifecycleService:
    """Own the public lifecycle while delegating persistence mechanics to one backend."""

    def __init__(self, backend: ConfigLifecycleBackend) -> None:
        self._backend = backend

    async def create_draft(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._backend.create_draft(
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
        return await self._backend.validate(
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
        return await self._backend.preview(
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
        return await self._backend.publish(
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
        return await self._backend.rollback(
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
        return await self._backend.disable(
            bundle_key=bundle_key,
            actor_id=actor_id,
            reason=reason,
        )

    async def resolve_active_version(self, bundle_key: str) -> Any | None:
        return await self._backend.resolve_active_version(bundle_key)

    def version_snapshot(self, version: Any | None) -> dict[str, Any] | None:
        return self._backend.version_snapshot(version)
