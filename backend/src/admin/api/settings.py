"""Governed admin settings API.

The settings surfaces reuse the existing BusinessRuleConfig lifecycle so
defaults, validation, audit logs, publish, rollback, and fallback behavior stay
centralized instead of becoming a one-off settings store.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from admin.api.permissions import (
    ADMIN_SETTINGS_MANAGE_PERMISSION,
    require_admin_permission,
)
from common.api.response import error_response, success_response
from common.business_rules.defaults import (
    ADMIN_SETTINGS_GENERAL_KEY,
    ADMIN_SETTINGS_NOTIFICATIONS_KEY,
    ADMIN_SETTINGS_SECURITY_KEY,
    get_business_rule_definition,
)
from common.business_rules.service import BusinessRuleConfigService
from common.business_rules.validators import (
    BusinessRuleValidationError,
)
from common.db.models import BusinessRuleConfig, BusinessRuleConfigAuditLog, User
from common.db.session import get_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["admin-settings"])

SettingsSurface = Literal["general", "security", "notifications"]

_SURFACE_KEYS: dict[str, str] = {
    "general": ADMIN_SETTINGS_GENERAL_KEY,
    "security": ADMIN_SETTINGS_SECURITY_KEY,
    "notifications": ADMIN_SETTINGS_NOTIFICATIONS_KEY,
}


class AdminSettingsValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class AdminSettingsPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str | None = None
    reason: str = Field(..., min_length=1, max_length=500)


class AdminSettingsRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_config_id: str | None = None
    target_version: int | None = Field(default=None, ge=1)
    reason: str = Field(..., min_length=1, max_length=500)


def _config_key(surface: SettingsSurface) -> str:
    return _SURFACE_KEYS[surface]


def _error(
    error_code: str,
    *,
    status_code: int,
    message: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(error_code, message=message),
    )


def _settings_error(exc: Exception) -> JSONResponse:
    message = str(exc)
    if message.startswith("[") and "]" in message:
        code = message.split("]", 1)[0] + "]"
    elif isinstance(exc, BusinessRuleValidationError):
        code = "[ADMIN_SETTINGS_SCHEMA_INVALID]"
    elif isinstance(exc, KeyError):
        code = "[ADMIN_SETTINGS_SURFACE_UNSUPPORTED]"
    else:
        code = "[ADMIN_SETTINGS_OPERATION_FAILED]"
    status = 404 if code.endswith("_NOT_FOUND]") else 400
    return _error(code, status_code=status, message=message)


def _config_payload(row: BusinessRuleConfig) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "key": row.key,
        "status": row.status,
        "version": row.version,
        "value": row.value_json,
        "default_value": row.default_value_json,
        "enabled": bool(row.enabled),
        "validation_errors": row.validation_errors_json,
        "created_by": str(row.created_by) if row.created_by else None,
        "updated_by": str(row.updated_by) if row.updated_by else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _audit_payload(row: BusinessRuleConfigAuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "config_id": str(row.config_id) if row.config_id else None,
        "action": row.action,
        "actor_id": str(row.actor_id) if row.actor_id else None,
        "before_version": row.before_version,
        "after_version": row.after_version,
        "reason": row.reason,
        "trace_id": row.trace_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _surface_payload(
    *,
    surface: SettingsSurface,
    service: BusinessRuleConfigService,
    include_audit: bool,
) -> dict[str, Any]:
    key = _config_key(surface)
    definition = get_business_rule_definition(key)
    resolution = await service.resolve_active_config(key)
    rows = await service.list_configs(key=key)
    drafts = [_config_payload(row) for row in rows if row.status == "draft"]
    history = [
        _config_payload(row)
        for row in rows
        if row.status in {"published", "archived", "disabled"}
    ]
    payload: dict[str, Any] = {
        "surface": surface,
        "key": key,
        "definition": definition.metadata(),
        "active": {
            "value": resolution.value,
            "source": resolution.source,
            "config_id": resolution.config_id,
            "version": resolution.version,
            "status": resolution.status,
            "fallback_reason": resolution.fallback_reason,
        },
        "drafts": drafts,
        "history": history,
        "permissions": {
            "can_view": True,
            "can_mutate": True,
            "can_publish": True,
            "permission": ADMIN_SETTINGS_MANAGE_PERMISSION,
        },
    }
    if include_audit:
        audits = await service.list_audit_logs(key=key, limit=50)
        payload["audit_logs"] = [_audit_payload(row) for row in audits]
    return payload


@router.get("/{surface}")
async def get_admin_settings_surface(
    surface: SettingsSurface,
    include_audit: bool = True,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    service = BusinessRuleConfigService(db)
    return success_response(
        await _surface_payload(
            surface=surface,
            service=service,
            include_audit=include_audit,
        )
    )


@router.post("/{surface}/drafts", response_model=None)
async def create_or_update_admin_settings_draft(
    surface: SettingsSurface,
    payload: AdminSettingsValueRequest,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    try:
        row = await service.create_or_update_draft(
            key=key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _settings_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("admin_settings_draft_save_failed", surface=surface, error=str(exc))
        return _error(
            "[ADMIN_SETTINGS_DRAFT_SAVE_FAILED]",
            status_code=500,
            message="Failed to save admin settings draft",
        )


@router.post("/{surface}/validate", response_model=None)
async def validate_admin_settings(
    surface: SettingsSurface,
    payload: AdminSettingsValueRequest,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    try:
        normalized = await service.validate_config_value(
            key=key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            audit=True,
        )
        await db.commit()
        return success_response({"valid": True, "normalized_value": normalized})
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _settings_error(exc)


@router.post("/{surface}/preview", response_model=None)
async def preview_admin_settings(
    surface: SettingsSurface,
    payload: AdminSettingsValueRequest,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    try:
        preview = await service.preview(
            key=key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        return success_response(preview)
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _settings_error(exc)


@router.post("/{surface}/publish", response_model=None)
async def publish_admin_settings(
    surface: SettingsSurface,
    payload: AdminSettingsPublishRequest,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    try:
        row = await service.publish(
            key=key,
            actor_id=str(current_user.user_id),
            config_id=payload.config_id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _settings_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("admin_settings_publish_failed", surface=surface, error=str(exc))
        return _error(
            "[ADMIN_SETTINGS_PUBLISH_FAILED]",
            status_code=500,
            message="Failed to publish admin settings",
        )


@router.post("/{surface}/rollback", response_model=None)
async def rollback_admin_settings(
    surface: SettingsSurface,
    payload: AdminSettingsRollbackRequest,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    try:
        row = await service.rollback(
            key=key,
            actor_id=str(current_user.user_id),
            target_config_id=payload.target_config_id,
            target_version=payload.target_version,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _settings_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("admin_settings_rollback_failed", surface=surface, error=str(exc))
        return _error(
            "[ADMIN_SETTINGS_ROLLBACK_FAILED]",
            status_code=500,
            message="Failed to roll back admin settings",
        )


@router.get("/{surface}/audit")
async def list_admin_settings_audit(
    surface: SettingsSurface,
    current_user: User = Depends(
        require_admin_permission(ADMIN_SETTINGS_MANAGE_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    key = _config_key(surface)
    service = BusinessRuleConfigService(db)
    audits = await service.list_audit_logs(key=key, limit=50)
    return success_response({"items": [_audit_payload(row) for row in audits]})
