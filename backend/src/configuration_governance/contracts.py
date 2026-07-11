"""Neutral contracts for governed configuration bundles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ConfigVersionSnapshot:
    source_config_id: str | None
    version: int | None
    version_label: str
    status: str
    snapshot: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ConfigBundleSnapshot:
    bundle_key: str
    display_name: str
    domain: str
    legacy_domain: str
    adapter_key: str
    read_path: str
    admin_entry: str
    status: str
    overview: dict[str, Any]
    active_version: ConfigVersionSnapshot | None


class ConfigBundleAdapter(Protocol):
    """Session-bound projection adapter supplied by the application composition root."""

    adapter_key: str
    bundle_key: str

    async def bundle(self, db: Any) -> ConfigBundleSnapshot: ...

    async def versions(self, db: Any) -> list[ConfigVersionSnapshot]: ...


@dataclass(frozen=True, slots=True)
class ConfigLifecycleResult:
    """Compatibility result; persistence entities remain inside the SQL adapter boundary."""

    version: Any | None
    audit: Any | None = None
    preview: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


class ConfigLifecycleBackend(Protocol):
    async def create_draft(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def validate(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def preview(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def publish(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        config_id: str | None,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def rollback(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        target_config_id: str | None,
        target_version: int | None,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def disable(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult: ...

    async def resolve_active_version(self, bundle_key: str) -> Any | None: ...

    def version_snapshot(self, version: Any | None) -> dict[str, Any] | None: ...


@dataclass(frozen=True, slots=True)
class ConfigVersionBinding:
    bundle_id: str
    version_id: str
    source_config_id: str | None
    version_number: int
    version_label: str
    status: str
