"""ConfigBundle lifecycle service built on legacy config adapters."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.adapters import (
    ConfigBundleAdapter,
    list_config_bundle_adapters,
)
from common.business_rules.defaults import SALES_COMBINATION_RULES_KEY
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import ConfigBundle, ConfigBundleAuditLog, ConfigVersion
from common.monitoring.logger import get_trace_id


@dataclass(frozen=True)
class ConfigLifecycleResult:
    version: ConfigVersion | None
    audit: ConfigBundleAuditLog | None = None
    preview: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


class ConfigBundleLifecycleService:
    """Explicit lifecycle operations for ConfigBundle versions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_draft(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        self._adapter_for(bundle_key)
        row = await BusinessRuleConfigService(self._db).create_or_update_draft(
            key=bundle_key,
            value=value,
            actor_id=actor_id,
            reason=reason,
        )
        version = await self._sync_business_rule_version(bundle_key, row)
        audit = self._queue_audit(
            action="create_draft",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=None,
            after_snapshot=self.version_snapshot(version),
            reason=reason,
            version=version,
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
        self._adapter_for(bundle_key)
        normalized = await BusinessRuleConfigService(self._db).validate_config_value(
            key=bundle_key,
            value=value,
            actor_id=actor_id,
            audit=False,
        )
        audit = self._queue_audit(
            action="validate",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=None,
            after_snapshot={"value": normalized},
            reason=reason,
            version=None,
        )
        return ConfigLifecycleResult(
            version=None,
            audit=audit,
            validation={"valid": True, "normalized_value": normalized},
        )

    async def preview(
        self,
        *,
        bundle_key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        self._adapter_for(bundle_key)
        preview = await BusinessRuleConfigService(self._db).preview(
            key=bundle_key,
            value=value,
            actor_id=None,
            reason=reason,
        )
        active = await self._active_version(bundle_key)
        audit = self._queue_audit(
            action="preview",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=self.version_snapshot(active),
            after_snapshot={"value": deepcopy(value), "summary": preview.get("summary")},
            reason=reason,
            version=active,
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
        before = await self._active_version(bundle_key)
        row = await BusinessRuleConfigService(self._db).publish(
            key=bundle_key,
            actor_id=actor_id,
            config_id=config_id,
            reason=reason,
        )
        version = await self._sync_business_rule_version(bundle_key, row)
        await self._sync_active_history(bundle_key)
        audit = self._queue_audit(
            action="publish",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=self.version_snapshot(before),
            after_snapshot=self.version_snapshot(version),
            reason=reason,
            version=version,
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    async def rollback(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        target_config_id: str | None,
        target_version: int | None,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        before = await self._active_version(bundle_key)
        row = await BusinessRuleConfigService(self._db).rollback(
            key=bundle_key,
            actor_id=actor_id,
            target_config_id=target_config_id,
            target_version=target_version,
            reason=reason,
        )
        version = await self._sync_business_rule_version(bundle_key, row)
        await self._sync_active_history(bundle_key)
        audit = self._queue_audit(
            action="rollback",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=self.version_snapshot(before),
            after_snapshot=self.version_snapshot(version),
            reason=reason,
            version=version,
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    async def disable(
        self,
        *,
        bundle_key: str,
        actor_id: str,
        reason: str | None,
    ) -> ConfigLifecycleResult:
        before = await self._active_version(bundle_key)
        row = await BusinessRuleConfigService(self._db).disable(
            key=bundle_key,
            actor_id=actor_id,
            reason=reason,
        )
        version = await self._sync_business_rule_version(bundle_key, row)
        audit = self._queue_audit(
            action="disable",
            bundle_key=bundle_key,
            actor_id=actor_id,
            before_snapshot=self.version_snapshot(before),
            after_snapshot=self.version_snapshot(version),
            reason=reason,
            version=version,
        )
        return ConfigLifecycleResult(version=version, audit=audit)

    async def resolve_active_version(self, bundle_key: str) -> ConfigVersion | None:
        """Return the current active immutable ConfigVersion row for binding."""

        return await self._active_version(bundle_key)

    def _adapter_for(self, bundle_key: str) -> ConfigBundleAdapter:
        adapter = next(
            (item for item in list_config_bundle_adapters() if item.bundle_key == bundle_key),
            None,
        )
        if adapter is None:
            raise ValueError("[CONFIG_BUNDLE_NOT_FOUND]")
        return adapter

    async def _sync_business_rule_version(
        self,
        bundle_key: str,
        row: object,
    ) -> ConfigVersion:
        if bundle_key != SALES_COMBINATION_RULES_KEY:
            raise ValueError("[CONFIG_BUNDLE_LIFECYCLE_UNSUPPORTED]")
        adapter = self._adapter_for(bundle_key)
        bundle = await adapter.bundle(self._db)
        bundle_row = await self._bundle_row(bundle_key)
        snapshot = dict(getattr(row, "value_json") or {})
        version = await self._version_row(str(getattr(row, "id")))
        if version is None:
            version = ConfigVersion(
                bundle_id=str(bundle_row.bundle_id),
                source_config_id=str(getattr(row, "id")),
                version_number=int(getattr(row, "version")),
                version_label=str(snapshot.get("version") or f"v{getattr(row, 'version')}"),
                status=str(getattr(row, "status")),
                snapshot_json=deepcopy(snapshot),
                source_updated_at=getattr(row, "updated_at", None),
            )
            self._db.add(version)
        else:
            version.version_number = int(getattr(row, "version"))
            version.version_label = str(snapshot.get("version") or f"v{getattr(row, 'version')}")
            version.status = str(getattr(row, "status"))
            version.snapshot_json = deepcopy(snapshot)
            version.source_updated_at = getattr(row, "updated_at", None)
        _ = bundle
        await self._db.flush()
        return version

    async def _bundle_row(self, bundle_key: str) -> ConfigBundle:
        result = await self._db.execute(
            select(ConfigBundle).where(ConfigBundle.bundle_key == bundle_key).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        adapter = self._adapter_for(bundle_key)
        snapshot = await adapter.bundle(self._db)
        row = ConfigBundle(
            bundle_key=snapshot.bundle_key,
            domain=snapshot.domain,
            display_name=snapshot.display_name,
            adapter_key=snapshot.adapter_key,
            legacy_domain=snapshot.legacy_domain,
            read_path=snapshot.read_path,
            admin_entry=snapshot.admin_entry,
            enabled=snapshot.status != "disabled",
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def _version_row(self, source_config_id: str) -> ConfigVersion | None:
        result = await self._db.execute(
            select(ConfigVersion)
            .where(ConfigVersion.source_config_id == source_config_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _active_version(self, bundle_key: str) -> ConfigVersion | None:
        adapter = self._adapter_for(bundle_key)
        versions = await adapter.versions(self._db)
        active = next(
            (item for item in versions if item.status in {"published", "disabled"}),
            None,
        )
        if active is None or active.source_config_id is None:
            return None
        row = await BusinessRuleConfigService(self._db).get_config(active.source_config_id)
        if row is None:
            return None
        return await self._sync_business_rule_version(bundle_key, row)

    async def _sync_active_history(self, bundle_key: str) -> None:
        rows = await BusinessRuleConfigService(self._db).list_configs(key=bundle_key)
        for row in rows:
            await self._sync_business_rule_version(bundle_key, row)

    @staticmethod
    def version_snapshot(version: ConfigVersion | None) -> dict[str, Any] | None:
        if version is None:
            return None
        return {
            "version_id": str(version.version_id),
            "source_config_id": version.source_config_id,
            "version": version.version_number,
            "version_label": version.version_label,
            "status": version.status,
            "snapshot": deepcopy(version.snapshot_json),
            "updated_at": version.source_updated_at.isoformat()
            if version.source_updated_at
            else None,
        }

    def _queue_audit(
        self,
        *,
        action: str,
        bundle_key: str,
        actor_id: str | None,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
        reason: str | None,
        version: ConfigVersion | None,
    ) -> ConfigBundleAuditLog:
        audit = ConfigBundleAuditLog(
            bundle_key=bundle_key,
            version_id=str(version.version_id) if version is not None else None,
            action=action,
            actor_id=actor_id,
            before_version=(before_snapshot or {}).get("version"),
            after_version=(after_snapshot or {}).get("version"),
            before_snapshot_json=before_snapshot,
            after_snapshot_json=after_snapshot,
            reason=(reason or "").strip() or "not-provided",
            trace_id=get_trace_id(),
            created_at=datetime.now(UTC),
        )
        self._db.add(audit)
        return audit
