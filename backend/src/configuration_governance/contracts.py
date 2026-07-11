"""Neutral contracts for governed configuration bundles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Literal, Protocol, TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJson: TypeAlias = JsonScalar | tuple["FrozenJson", ...] | Mapping[str, "FrozenJson"]
LifecycleAction: TypeAlias = Literal[
    "create_draft",
    "validate",
    "preview",
    "publish",
    "rollback",
    "disable",
]


@dataclass(frozen=True, slots=True)
class ConfigVersionSnapshot:
    source_config_id: str | None
    version: int | None
    version_label: str
    status: str
    snapshot: Mapping[str, Any]
    created_at: datetime | None
    updated_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot", freeze_json_mapping(self.snapshot))


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
    overview: Mapping[str, Any]
    active_version: ConfigVersionSnapshot | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "overview", freeze_json_mapping(self.overview))


class ConfigBundleAdapter(Protocol):
    """Session-bound projection adapter supplied by the application composition root."""

    adapter_key: str
    bundle_key: str

    async def bundle(self, db: Any) -> ConfigBundleSnapshot: ...

    async def versions(self, db: Any) -> list[ConfigVersionSnapshot]: ...


@dataclass(frozen=True, slots=True)
class ConfigLifecycleResult:
    """Immutable lifecycle output with no persistence entity leakage."""

    version: ConfigVersionRecord | None
    audit: ConfigAuditRecord | None = None
    preview: Mapping[str, FrozenJson] | None = None
    validation: Mapping[str, FrozenJson] | None = None

    def __post_init__(self) -> None:
        if self.preview is not None:
            object.__setattr__(self, "preview", freeze_json_mapping(self.preview))
        if self.validation is not None:
            object.__setattr__(
                self,
                "validation",
                freeze_json_mapping(self.validation),
            )


@dataclass(frozen=True, slots=True)
class ConfigVersionRecord:
    version_id: str
    source_config_id: str | None
    version_number: int | None
    version_label: str
    status: str
    snapshot: Mapping[str, FrozenJson]
    updated_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot", freeze_json_mapping(self.snapshot))

    def as_payload(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "source_config_id": self.source_config_id,
            "version": self.version_number,
            "version_label": self.version_label,
            "status": self.status,
            "snapshot": thaw_json(self.snapshot),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def snapshot_json(self) -> Mapping[str, FrozenJson]:
        """Gate 4 compatibility name; retire with legacy lifecycle consumers in Gate 6."""

        return self.snapshot


@dataclass(frozen=True, slots=True)
class ConfigAuditDecision:
    action: LifecycleAction
    bundle_key: str
    actor_id: str | None
    version_id: str | None
    before_version: int | None
    after_version: int | None
    before_snapshot: Mapping[str, FrozenJson] | None
    after_snapshot: Mapping[str, FrozenJson] | None
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", self.reason.strip() or "not-provided")
        if self.before_snapshot is not None:
            object.__setattr__(
                self,
                "before_snapshot",
                freeze_json_mapping(self.before_snapshot),
            )
        if self.after_snapshot is not None:
            object.__setattr__(
                self,
                "after_snapshot",
                freeze_json_mapping(self.after_snapshot),
            )


@dataclass(frozen=True, slots=True)
class ConfigAuditRecord:
    audit_id: str
    bundle_key: str
    version_id: str | None
    action: LifecycleAction
    actor_id: str | None
    before_version: int | None
    after_version: int | None
    reason: str
    trace_id: str | None
    created_at: datetime | None
    before_snapshot: Mapping[str, FrozenJson] | None = None
    after_snapshot: Mapping[str, FrozenJson] | None = None

    def __post_init__(self) -> None:
        if self.before_snapshot is not None:
            object.__setattr__(
                self,
                "before_snapshot",
                freeze_json_mapping(self.before_snapshot),
            )
        if self.after_snapshot is not None:
            object.__setattr__(
                self,
                "after_snapshot",
                freeze_json_mapping(self.after_snapshot),
            )

    @property
    def before_snapshot_json(self) -> Mapping[str, FrozenJson] | None:
        """Gate 4 compatibility name; retire with legacy lifecycle consumers in Gate 6."""

        return self.before_snapshot

    @property
    def after_snapshot_json(self) -> Mapping[str, FrozenJson] | None:
        """Gate 4 compatibility name; retire with legacy lifecycle consumers in Gate 6."""

        return self.after_snapshot


class ConfigLifecyclePersistence(Protocol):
    async def ensure_bundle(self, bundle_key: str) -> None: ...

    async def create_draft_version(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigVersionRecord: ...

    async def validate_value(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
    ) -> Mapping[str, FrozenJson]: ...

    async def preview_value(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        reason: str | None,
    ) -> Mapping[str, FrozenJson]: ...

    async def load_active_version(
        self, bundle_key: str
    ) -> ConfigVersionRecord | None: ...

    async def publish_version(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        config_id: str | None,
        reason: str | None,
    ) -> ConfigVersionRecord: ...

    async def rollback_version(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        target_config_id: str | None,
        target_version: int | None,
        reason: str | None,
    ) -> ConfigVersionRecord: ...

    async def disable_version(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        reason: str | None,
    ) -> ConfigVersionRecord: ...

    async def sync_projection(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        version: ConfigVersionRecord,
        lifecycle_action: Literal["publish", "rollback"],
    ) -> Mapping[str, FrozenJson] | None: ...

    async def append_audit(
        self, decision: ConfigAuditDecision
    ) -> ConfigAuditRecord: ...


@dataclass(frozen=True, slots=True)
class ConfigVersionBinding:
    bundle_id: str
    version_id: str
    source_config_id: str | None
    version_number: int
    version_label: str
    status: str


def freeze_json(value: object) -> FrozenJson:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return freeze_json_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, FrozenJson]:
    return MappingProxyType(
        {str(key): freeze_json(item) for key, item in value.items()}
    )


def thaw_json(value: FrozenJson) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
