"""ConfigBundle admin API — read-only, lifecycle, and version management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.permissions import (
    CONFIG_BUNDLE_DISABLE_PERMISSION,
    CONFIG_BUNDLE_DRAFT_PERMISSION,
    CONFIG_BUNDLE_PREVIEW_PERMISSION,
    CONFIG_BUNDLE_PUBLISH_PERMISSION,
    CONFIG_BUNDLE_READ_PERMISSION,
    CONFIG_BUNDLE_ROLLBACK_PERMISSION,
    CONFIG_BUNDLE_VALIDATE_PERMISSION,
    require_admin_permission,
)
from admin.config_bundles.adapters import (
    ConfigBundleSnapshot,
    ConfigVersionSnapshot,
    list_config_bundle_adapters,
)
from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.api.response import error_response, success_response
from common.business_rules.validators import BusinessRuleValidationError
from common.db.models import User
from common.db.session import get_db

router = APIRouter(prefix="/config-bundles", tags=["admin-config-bundles"])


class ConfigBundleValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ConfigBundlePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str | None = None
    reason: str = Field(..., min_length=1, max_length=500)


class ConfigBundleRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_config_id: str | None = None
    target_version: int | None = Field(default=None, ge=1)
    reason: str = Field(..., min_length=1, max_length=500)


class ConfigBundleDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)


def _version_payload(snapshot: ConfigVersionSnapshot) -> dict[str, Any]:
    return {
        "source_config_id": snapshot.source_config_id,
        "version": snapshot.version,
        "version_label": snapshot.version_label,
        "status": snapshot.status,
        "snapshot": snapshot.snapshot,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
    }


def _bundle_payload(bundle: ConfigBundleSnapshot) -> dict[str, Any]:
    return {
        "bundle_key": bundle.bundle_key,
        "display_name": bundle.display_name,
        "domain": bundle.domain,
        "legacy_domain": bundle.legacy_domain,
        "adapter_key": bundle.adapter_key,
        "read_path": bundle.read_path,
        "admin_entry": bundle.admin_entry,
        "status": bundle.status,
        "overview": bundle.overview,
        "active_version": _version_payload(bundle.active_version)
        if bundle.active_version
        else None,
    }


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_response(
            "[CONFIG_BUNDLE_NOT_FOUND]",
            message="Config bundle adapter was not found",
        ),
    )


def _audit_payload(audit) -> dict[str, Any] | None:
    if audit is None:
        return None
    return {
        "id": str(audit.id),
        "bundle_key": audit.bundle_key,
        "version_id": str(audit.version_id) if audit.version_id else None,
        "action": audit.action,
        "actor": str(audit.actor_id) if audit.actor_id else None,
        "before_version": audit.before_version,
        "after_version": audit.after_version,
        "reason": audit.reason,
        "trace_id": audit.trace_id,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
    }


def _operation_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, BusinessRuleValidationError):
        return JSONResponse(
            status_code=400,
            content=error_response("[CONFIG_BUNDLE_SCHEMA_INVALID]", message=str(exc)),
        )
    message = str(exc)
    if message == "[CONFIG_BUNDLE_NOT_FOUND]":
        return _not_found()
    return JSONResponse(
        status_code=400,
        content=error_response(message, message=message),
    )


@router.get("")
async def list_config_bundles(
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_READ_PERMISSION)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    bundles = [
        _bundle_payload(await adapter.bundle(db))
        for adapter in list_config_bundle_adapters()
    ]
    return success_response({"items": bundles, "total": len(bundles)})


@router.get("/{bundle_key}/versions")
async def list_config_bundle_versions(
    bundle_key: str,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_READ_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    adapter = next(
        (
            candidate
            for candidate in list_config_bundle_adapters()
            if candidate.bundle_key == bundle_key
        ),
        None,
    )
    if adapter is None:
        return _not_found()
    versions = [_version_payload(item) for item in await adapter.versions(db)]
    return success_response(
        {
            "bundle_key": adapter.bundle_key,
            "adapter_key": adapter.adapter_key,
            "items": versions,
            "total": len(versions),
        }
    )


@router.post("/{bundle_key}/drafts")
async def create_config_bundle_draft(
    bundle_key: str,
    payload: ConfigBundleValueRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_DRAFT_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.create_draft(
            bundle_key=bundle_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        if result.version is not None:
            await db.refresh(result.version)
        if result.audit is not None:
            await db.refresh(result.audit)
        return success_response(
            {
                "version": service.version_snapshot(result.version),
                "audit": _audit_payload(result.audit),
            }
        )
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)


@router.post("/{bundle_key}/validate")
async def validate_config_bundle_value(
    bundle_key: str,
    payload: ConfigBundleValueRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_VALIDATE_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.validate(
            bundle_key=bundle_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        if result.audit is not None:
            await db.refresh(result.audit)
        data = dict(result.validation or {})
        data["audit"] = _audit_payload(result.audit)
        return success_response(data)
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)


@router.post("/{bundle_key}/preview")
async def preview_config_bundle_value(
    bundle_key: str,
    payload: ConfigBundleValueRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_PREVIEW_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.preview(
            bundle_key=bundle_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        if result.audit is not None:
            await db.refresh(result.audit)
        data = dict(result.preview or {})
        data["audit"] = _audit_payload(result.audit)
        return success_response(data)
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)


@router.post("/{bundle_key}/publish")
async def publish_config_bundle_version(
    bundle_key: str,
    payload: ConfigBundlePublishRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_PUBLISH_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.publish(
            bundle_key=bundle_key,
            actor_id=str(current_user.user_id),
            config_id=payload.config_id,
            reason=payload.reason,
        )
        await db.commit()
        if result.version is not None:
            await db.refresh(result.version)
        if result.audit is not None:
            await db.refresh(result.audit)
        return success_response(
            {
                "version": service.version_snapshot(result.version),
                "audit": _audit_payload(result.audit),
            }
        )
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)


@router.post("/{bundle_key}/rollback")
async def rollback_config_bundle_version(
    bundle_key: str,
    payload: ConfigBundleRollbackRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_ROLLBACK_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.rollback(
            bundle_key=bundle_key,
            actor_id=str(current_user.user_id),
            target_config_id=payload.target_config_id,
            target_version=payload.target_version,
            reason=payload.reason,
        )
        await db.commit()
        if result.version is not None:
            await db.refresh(result.version)
        if result.audit is not None:
            await db.refresh(result.audit)
        return success_response(
            {
                "version": service.version_snapshot(result.version),
                "audit": _audit_payload(result.audit),
            }
        )
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)


@router.post("/{bundle_key}/disable")
async def disable_config_bundle_version(
    bundle_key: str,
    payload: ConfigBundleDisableRequest,
    current_user: User = Depends(require_admin_permission(CONFIG_BUNDLE_DISABLE_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    service = ConfigBundleLifecycleService(db)
    try:
        result = await service.disable(
            bundle_key=bundle_key,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        if result.version is not None:
            await db.refresh(result.version)
        if result.audit is not None:
            await db.refresh(result.audit)
        return success_response(
            {
                "version": service.version_snapshot(result.version),
                "audit": _audit_payload(result.audit),
            }
        )
    except (BusinessRuleValidationError, ValueError) as exc:
        await db.rollback()
        return _operation_error(exc)
