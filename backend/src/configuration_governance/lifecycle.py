"""Lifecycle policy and audit orchestration over persistence capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from configuration_governance.contracts import (
    ConfigAuditDecision,
    ConfigLifecyclePersistence,
    ConfigLifecycleResult,
    ConfigVersionRecord,
    FrozenJson,
    freeze_json_mapping,
)


class ConfigBundleLifecycleService:
    """Own lifecycle sequencing, audit decisions and stable immutable outputs."""

    def __init__(self, persistence: ConfigLifecyclePersistence) -> None:
        self._persistence = persistence

    async def create_draft(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        await self._persistence.ensure_bundle(bundle_key)
        version = await self._persistence.create_draft_version(
            bundle_key=bundle_key,
            value=value,
            actor_id=actor_id,
            reason=reason,
        )
        audit = await self._persistence.append_audit(
            self._audit_decision(
                action="create_draft",
                bundle_key=bundle_key,
                actor_id=actor_id,
                reason=reason,
                before=None,
                after=version,
            )
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    async def validate(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        await self._persistence.ensure_bundle(bundle_key)
        normalized = await self._persistence.validate_value(
            bundle_key=bundle_key,
            value=value,
            actor_id=actor_id,
        )
        validation = freeze_json_mapping(
            {"valid": True, "normalized_value": normalized}
        )
        audit = await self._persistence.append_audit(
            ConfigAuditDecision(
                action="validate",
                bundle_key=bundle_key,
                actor_id=actor_id,
                version_id=None,
                before_version=None,
                after_version=None,
                before_snapshot=None,
                after_snapshot=freeze_json_mapping({"value": normalized}),
                reason=reason or "",
            )
        )
        return ConfigLifecycleResult(
            version=None,
            audit=audit,
            validation=validation,
        )

    async def preview(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        await self._persistence.ensure_bundle(bundle_key)
        preview = await self._persistence.preview_value(
            bundle_key=bundle_key,
            value=value,
            reason=reason,
        )
        active = await self._persistence.load_active_version(bundle_key)
        audit = await self._persistence.append_audit(
            ConfigAuditDecision(
                action="preview",
                bundle_key=bundle_key,
                actor_id=actor_id,
                version_id=active.version_id if active is not None else None,
                before_version=(
                    active.version_number if active is not None else None
                ),
                after_version=None,
                before_snapshot=self._snapshot(active),
                after_snapshot=freeze_json_mapping(
                    {"value": value, "summary": preview.get("summary")}
                ),
                reason=reason or "",
            )
        )
        return ConfigLifecycleResult(version=active, audit=audit, preview=preview)

    async def publish(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        config_id: str | None,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        return await self._activate(
            action="publish",
            bundle_key=bundle_key,
            actor_id=actor_id,
            reason=reason,
            config_id=config_id,
            target_version=None,
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
        return await self._activate(
            action="rollback",
            bundle_key=bundle_key,
            actor_id=actor_id,
            reason=reason,
            config_id=target_config_id,
            target_version=target_version,
        )

    async def disable(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        await self._persistence.ensure_bundle(bundle_key)
        before = await self._persistence.load_active_version(bundle_key)
        version = await self._persistence.disable_version(
            bundle_key=bundle_key,
            actor_id=actor_id,
            reason=reason,
        )
        audit = await self._persistence.append_audit(
            self._audit_decision(
                action="disable",
                bundle_key=bundle_key,
                actor_id=actor_id,
                reason=reason,
                before=before,
                after=version,
            )
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    async def resolve_active_version(
        self, bundle_key: str
    ) -> ConfigVersionRecord | None:
        await self._persistence.ensure_bundle(bundle_key)
        return await self._persistence.load_active_version(bundle_key)

    @staticmethod
    def version_snapshot(
        version: ConfigVersionRecord | None,
    ) -> dict[str, Any] | None:
        return version.as_payload() if version is not None else None

    async def _activate(
        self,
        *,
        action: Literal["publish", "rollback"],
        bundle_key: str,
        actor_id: str,
        reason: str | None,
        config_id: str | None,
        target_version: int | None,
    ) -> ConfigLifecycleResult:
        await self._persistence.ensure_bundle(bundle_key)
        before = await self._persistence.load_active_version(bundle_key)
        if action == "publish":
            version = await self._persistence.publish_version(
                bundle_key=bundle_key,
                actor_id=actor_id,
                config_id=config_id,
                reason=reason,
            )
        else:
            version = await self._persistence.rollback_version(
                bundle_key=bundle_key,
                actor_id=actor_id,
                target_config_id=config_id,
                target_version=target_version,
                reason=reason,
            )
        projection = await self._persistence.sync_projection(
            bundle_key=bundle_key,
            actor_id=actor_id,
            version=version,
            lifecycle_action=action,
        )
        audit = await self._persistence.append_audit(
            self._audit_decision(
                action=action,
                bundle_key=bundle_key,
                actor_id=actor_id,
                reason=reason,
                before=before,
                after=version,
                projection=projection,
            )
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    @classmethod
    def _audit_decision(
        cls,
        *,
        action: Literal[
            "create_draft", "publish", "rollback", "disable"
        ],
        bundle_key: str,
        actor_id: str,
        reason: str | None,
        before: ConfigVersionRecord | None,
        after: ConfigVersionRecord,
        projection: Mapping[str, FrozenJson] | None = None,
    ) -> ConfigAuditDecision:
        after_snapshot = cls._snapshot(after)
        if projection is not None and after_snapshot is not None:
            after_snapshot = freeze_json_mapping(
                {**after_snapshot, "projection_sync": projection}
            )
        return ConfigAuditDecision(
            action=action,
            bundle_key=bundle_key,
            actor_id=actor_id,
            version_id=after.version_id,
            before_version=before.version_number if before is not None else None,
            after_version=after.version_number,
            before_snapshot=cls._snapshot(before),
            after_snapshot=after_snapshot,
            reason=reason or "",
        )

    @staticmethod
    def _snapshot(
        version: ConfigVersionRecord | None,
    ) -> Mapping[str, FrozenJson] | None:
        if version is None:
            return None
        return freeze_json_mapping(version.as_payload())
