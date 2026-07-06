"""Build config-asset-export-v1 bundles from live assets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.audit import record_export_audit
from admin.config_assets.exporters import export_asset, sort_topology
from admin.config_assets.natural_keys import topology_ref
from admin.config_assets.schema import validate_export_bundle
from admin.config_assets.types import AssetRef


class ConfigAssetExportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def export_bundle(
        self,
        *,
        asset_refs: list[AssetRef],
        actor_id: str,
        actor_identifier: str,
        source_instance: str | None = None,
        notes: str | None = None,
        record_audit: bool = True,
    ) -> dict[str, Any]:
        if not asset_refs:
            raise ValueError("[EXPORT_REFS_REQUIRED] at least one asset ref is required")

        # Export audit is mandatory; keep the flag only for backward-compatible callers.
        should_record_audit = True
        assets: list[dict[str, Any]] = []
        missing: list[str] = []
        for ref in asset_refs:
            entry = await export_asset(
                self._db,
                asset_type=ref.asset_type,
                namespace=ref.namespace,
                natural_key=ref.natural_key,
            )
            token = topology_ref(ref.asset_type, ref.natural_key)
            if entry is None:
                missing.append(token)
                continue
            assets.append(entry)

        if missing:
            raise ValueError(f"[EXPORT_ASSETS_NOT_FOUND] {', '.join(missing)}")

        topology_order = sort_topology(assets)
        export_meta: dict[str, Any] = {
            "version": "config-asset-export-v1",
            "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "exported_by": actor_id,
            "export_audit_recorded": should_record_audit,
        }
        bundle: dict[str, Any] = {
            "export_meta": export_meta,
            "assets": assets,
            "topology_order": topology_order,
        }
        if source_instance:
            export_meta["source_instance"] = source_instance
        if notes:
            export_meta["notes"] = notes

        validate_export_bundle(bundle)

        if should_record_audit:
            await record_export_audit(
                self._db,
                actor_id=actor_id,
                actor_identifier=actor_identifier,
                asset_count=len(assets),
                topology_order=topology_order,
                notes=notes,
            )
            export_meta["export_audit_recorded"] = True

        return bundle
