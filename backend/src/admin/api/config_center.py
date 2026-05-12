"""Admin Config Center domain architecture API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.config_bundles import _bundle_payload
from admin.config_bundles.adapters import list_config_bundle_adapters
from admin.config_bundles.domains import DOMAIN_REGISTRY
from common.api.response import success_response
from common.auth.service import get_current_admin_user
from common.db.models import User
from common.db.session import get_db

router = APIRouter(prefix="/config-center", tags=["admin-config-center"])


@router.get("/domains")
async def list_config_center_domains(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    bundle_map: dict[str, dict[str, Any]] = {}
    for adapter in list_config_bundle_adapters():
        bundle = await adapter.bundle(db)
        bundle_map[bundle.bundle_key] = _bundle_payload(bundle)

    domain_items: list[dict[str, Any]] = []
    for domain_info in DOMAIN_REGISTRY:
        domain_bundles: list[dict[str, Any]] = []
        active_version_summary: dict[str, Any] | None = None
        for bundle_key in domain_info.bundles:
            if bundle_key in bundle_map:
                domain_bundles.append(bundle_map[bundle_key])
                if bundle_map[bundle_key].get("active_version") and active_version_summary is None:
                    active_version_summary = {
                        "bundle_key": bundle_key,
                        "version_label": bundle_map[bundle_key]["active_version"]["version_label"],
                        "status": bundle_map[bundle_key]["active_version"]["status"],
                    }

        domain_items.append({
            "domain": domain_info.domain,
            "display_name": domain_info.display_name,
            "description": domain_info.description,
            "migration_status": domain_info.migration_status,
            "legacy_pages": [
                {"path": page.path, "label": page.label}
                for page in domain_info.legacy_pages
            ],
            "bundles": domain_bundles,
            "active_version_summary": active_version_summary,
        })

    return success_response({"items": domain_items, "total": len(domain_items)})
