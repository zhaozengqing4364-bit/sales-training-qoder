"""Audit helpers for config asset import/export."""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.types import ImportReport
from common.db.models import SystemLog
from common.monitoring.logger import get_trace_id


async def record_import_audit(
    db: AsyncSession,
    *,
    actor_id: str,
    actor_identifier: str,
    report: ImportReport,
    bundle_version: str,
    reason: str | None,
) -> None:
    details = {
        "bundle_version": bundle_version,
        "dry_run": report.dry_run,
        "total": report.total,
        "imported": report.imported,
        "skipped": report.skipped,
        "failed": report.failed,
        "id_mapping": report.id_mapping,
        "errors": report.errors,
        "trace_id": get_trace_id(),
        "reason": reason,
    }
    db.add(
        SystemLog(
            action="config_asset_import",
            user_id=actor_id,
            user_identifier=actor_identifier,
            status="success" if report.failed == 0 else "warning",
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )
    await db.flush()


async def record_export_audit(
    db: AsyncSession,
    *,
    actor_id: str,
    actor_identifier: str,
    asset_count: int,
    topology_order: list[str],
    notes: str | None,
) -> None:
    details = {
        "asset_count": asset_count,
        "topology_order": topology_order,
        "notes": notes,
        "trace_id": get_trace_id(),
    }
    db.add(
        SystemLog(
            action="config_asset_export",
            user_id=actor_id,
            user_identifier=actor_identifier,
            status="success",
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )
    await db.flush()
