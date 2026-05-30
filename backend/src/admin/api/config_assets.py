"""Admin API for Config Asset Center bulk import/export."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.permissions import (
    CONFIG_ASSET_EXPORT_PERMISSION,
    CONFIG_ASSET_IMPORT_PERMISSION,
    require_admin_permission,
)
from admin.config_assets import ConfigAssetExportService, ConfigAssetImportService
from admin.config_assets.schema import ConfigAssetSchemaError
from admin.config_assets.types import AssetRef, ImportOptions
from common.api.response import error_response, success_response
from common.db.models import User
from common.db.session import get_db

router = APIRouter(tags=["admin-config-assets"])


class ConfigAssetRefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_type: str = Field(..., min_length=1, max_length=40)
    natural_key: str = Field(..., min_length=1, max_length=120)
    namespace: str = Field(default="default", min_length=1, max_length=60)


class ConfigAssetExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_refs: list[ConfigAssetRefRequest] = Field(..., min_length=1)
    source_instance: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    record_export_audit: bool = False


class ConfigAssetImportOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = False
    conflict_strategy: Literal[
        "skip", "fail", "new_version", "replace_draft"
    ] = "new_version"
    publish_after_import: bool = False
    import_reason: str | None = Field(default=None, max_length=500)


class ConfigAssetImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_json: dict[str, Any]
    options: ConfigAssetImportOptionsRequest = Field(
        default_factory=ConfigAssetImportOptionsRequest
    )


def _export_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, ConfigAssetSchemaError):
        return JSONResponse(
            status_code=400,
            content=error_response("[CONFIG_ASSET_SCHEMA_INVALID]", message=str(exc)),
        )
    message = str(exc)
    code = (
        message.strip("[]").split("]", 1)[0]
        if message.startswith("[")
        else "CONFIG_ASSET_EXPORT_FAILED"
    )
    return JSONResponse(
        status_code=400,
        content=error_response(f"[{code}]", message=message),
    )


@router.post("/export")
async def export_config_assets(
    body: ConfigAssetExportRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_ASSET_EXPORT_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    service = ConfigAssetExportService(db)
    refs = [
        AssetRef(
            asset_type=item.asset_type,
            natural_key=item.natural_key,
            namespace=item.namespace,
        )
        for item in body.asset_refs
    ]
    try:
        bundle = await service.export_bundle(
            asset_refs=refs,
            actor_id=str(current_user.user_id),
            actor_identifier=str(current_user.email or current_user.user_id),
            source_instance=body.source_instance,
            notes=body.notes,
            record_audit=body.record_export_audit,
        )
    except (ConfigAssetSchemaError, ValueError) as exc:
        return _export_error(exc)

    if body.record_export_audit:
        await db.commit()
    return JSONResponse(content=success_response(bundle))


@router.post("/import")
async def import_config_assets(
    body: ConfigAssetImportRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_ASSET_IMPORT_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    options = ImportOptions(
        dry_run=body.options.dry_run,
        conflict_strategy=body.options.conflict_strategy,
        publish_after_import=body.options.publish_after_import,
        import_reason=body.options.import_reason,
    )
    report = await ConfigAssetImportService(db).import_bundle(
        body.export_json,
        options=options,
        actor_id=str(current_user.user_id),
        actor_identifier=str(current_user.email or current_user.user_id),
    )
    return JSONResponse(content=success_response(report.as_dict()))
