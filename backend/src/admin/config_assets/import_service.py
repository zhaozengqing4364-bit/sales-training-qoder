"""Apply config-asset-export-v1 bundles through service-layer writes."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.audit import record_import_audit
from admin.config_assets.importers import IMPORTERS
from admin.config_assets.natural_keys import parse_topology_ref, topology_ref
from admin.config_assets.publish_after_import import publish_imported_assets
from admin.config_assets.schema import ConfigAssetSchemaError, validate_export_bundle
from admin.config_assets.types import ImportAssetResult, ImportOptions, ImportReport


class ConfigAssetImportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def import_bundle(
        self,
        export_json: dict[str, Any],
        *,
        options: ImportOptions,
        actor_id: str,
        actor_identifier: str,
    ) -> ImportReport:
        try:
            validate_export_bundle(export_json)
        except ConfigAssetSchemaError as exc:
            return ImportReport(
                total=0,
                imported=0,
                skipped=0,
                failed=0,
                dry_run=options.dry_run,
                errors=[str(exc)],
            )

        assets = export_json.get("assets") or []
        topology_order = list(export_json.get("topology_order") or [])
        try:
            self._validate_topology(assets, topology_order)
        except ValueError as exc:
            return ImportReport(
                total=0,
                imported=0,
                skipped=0,
                failed=0,
                dry_run=options.dry_run,
                errors=[str(exc)],
            )

        assets_by_ref = {
            topology_ref(str(item["asset_type"]), str(item["natural_key"])): item
            for item in assets
        }

        id_mapping: dict[str, str] = {}
        results: list[ImportAssetResult] = []
        errors: list[str] = []

        for ref in topology_order:
            entry = assets_by_ref.get(ref)
            if entry is None:
                errors.append(f"missing asset for topology ref {ref}")
                continue
            asset_type = str(entry["asset_type"])
            importer = IMPORTERS.get(asset_type)
            if importer is None:
                results.append(
                    ImportAssetResult(
                        asset_type,
                        str(entry.get("namespace") or "default"),
                        str(entry["natural_key"]),
                        "failed",
                        message=f"unsupported asset_type: {asset_type}",
                    )
                )
                continue
            try:
                result = await importer(
                    self._db,
                    entry=entry,
                    conflict_strategy=options.conflict_strategy,
                    actor_id=actor_id,
                    id_mapping=id_mapping,
                    dry_run=options.dry_run,
                )
            except Exception as exc:  # noqa: BLE001 — collect per-asset failure
                result = ImportAssetResult(
                    asset_type,
                    str(entry.get("namespace") or "default"),
                    str(entry["natural_key"]),
                    "failed",
                    message=str(exc),
                )
            results.append(result)

        imported = sum(1 for item in results if item.status == "imported")
        skipped = sum(1 for item in results if item.status == "skipped")
        failed = sum(1 for item in results if item.status == "failed")
        report = ImportReport(
            total=len(results),
            imported=imported,
            skipped=skipped,
            failed=failed,
            dry_run=options.dry_run,
            id_mapping=id_mapping,
            results=results,
            errors=errors,
        )

        if not options.dry_run:
            if options.publish_after_import:
                publish_errors = await publish_imported_assets(
                    self._db,
                    assets=assets,
                    results=results,
                    id_mapping=id_mapping,
                    actor_id=actor_id,
                    import_reason=options.import_reason,
                )
                report.errors.extend(publish_errors)

            await record_import_audit(
                self._db,
                actor_id=actor_id,
                actor_identifier=actor_identifier,
                report=report,
                bundle_version=str(
                    (export_json.get("export_meta") or {}).get("version")
                    or "config-asset-export-v1"
                ),
                reason=options.import_reason,
            )
            report.audit_recorded = True
            await self._db.commit()
        else:
            await self._db.rollback()

        return report

    @staticmethod
    def _validate_topology(
        assets: list[dict[str, Any]], topology_order: list[str]
    ) -> None:
        asset_refs = {
            topology_ref(str(item["asset_type"]), str(item["natural_key"]))
            for item in assets
        }
        if set(topology_order) != asset_refs:
            raise ValueError(
                "[TOPOLOGY_MISMATCH] topology_order must match exported asset refs"
            )
        for ref in topology_order:
            parse_topology_ref(ref)
        seen: set[str] = set()
        assets_by_ref = {
            topology_ref(str(item["asset_type"]), str(item["natural_key"])): item
            for item in assets
        }
        for ref in topology_order:
            entry = assets_by_ref[ref]
            for dependency in entry.get("depends_on") or []:
                dependency_ref = topology_ref(
                    str(dependency["asset_type"]),
                    str(dependency["natural_key"]),
                )
                if dependency_ref in asset_refs and dependency_ref not in seen:
                    raise ValueError(
                        "[TOPOLOGY_DEPENDENCY_ORDER] "
                        f"{dependency_ref} must be imported before {ref}"
                    )
            seen.add(ref)
