"""Admin API for governed business-rule configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.response import error_response, success_response
from common.auth.service import get_current_admin_user
from common.business_rules.defaults import (
    SALES_COMBINATIONS_RULESET_KEY,
    get_business_rule_definition,
    get_default_business_rule_value,
    list_business_rule_definitions,
)
from common.business_rules.service import BusinessRuleConfigService
from common.business_rules.validators import (
    BusinessRuleValidationError,
    validate_business_rule_value,
)
from common.db.models import BusinessRuleConfig, User
from common.db.session import get_db
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/business-rules", tags=["admin-business-rules"])


class BusinessRuleValueRequest(BaseModel):
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


class BusinessRulePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str | None = None
    reason: str = Field(..., min_length=1, max_length=500)


class BusinessRuleRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_config_id: str | None = None
    target_version: int | None = Field(default=None, ge=1)
    reason: str = Field(..., min_length=1, max_length=500)


class BusinessRuleDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=500)


class BusinessRuleDeleteDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


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


def _config_payload(row: BusinessRuleConfig) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "domain": row.domain,
        "key": row.key,
        "schema_version": row.schema_version,
        "status": row.status,
        "version": row.version,
        "value": row.value_json,
        "default_value": row.default_value_json,
        "type": row.type,
        "range_or_allowlist": row.range_or_allowlist_json,
        "read_path": row.read_path,
        "admin_entry": row.admin_entry,
        "permission": row.permission,
        "audit_policy": row.audit_policy,
        "fallback_policy": row.fallback_policy,
        "rollback_policy": row.rollback_policy,
        "enabled": bool(row.enabled),
        "validation_errors": row.validation_errors_json,
        "created_by": str(row.created_by) if row.created_by else None,
        "updated_by": str(row.updated_by) if row.updated_by else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _definition_payload(key: str) -> dict[str, Any]:
    definition = get_business_rule_definition(key)
    data = definition.metadata()
    return {"key": definition.key, **data}


def _sales_ruleset_payload(
    row: BusinessRuleConfig | None,
    value: dict[str, Any],
    *,
    status: str,
    audit: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    audit_summary = {
        "published_by": audit.get("actor_id") if audit else None,
        "published_at": audit.get("created_at") if audit else None,
        "reason": audit.get("reason") if audit else fallback_reason,
        "trace_id": audit.get("trace_id") if audit else None,
    }
    return {
        "rule_set_id": value.get("rule_set_id"),
        "version": value.get("version"),
        "status": status
        if status in {"draft", "published", "archived"}
        else "archived",
        "effective_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "combinations": value.get("combinations", []),
        "fallback_policy": value.get("fallback_policy", "client_default_v1"),
        "audit_summary": audit_summary,
    }


def _sales_audit_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "actor": row.get("actor_id"),
        "action": row.get("action"),
        "before_version": str(row.get("before_version"))
        if row.get("before_version")
        else None,
        "after_version": str(row.get("after_version"))
        if row.get("after_version")
        else None,
        "reason": row.get("reason"),
        "trace_id": row.get("trace_id"),
        "created_at": row.get("created_at"),
    }


def _sales_validation_error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "valid": False,
        "errors": [{"path": "ruleset", "message": str(exc)}],
        "warnings": [],
    }


def _find_sales_row_by_ruleset_id(
    rows: list[BusinessRuleConfig],
    ruleset_id: str,
    *,
    statuses: set[str] | None = None,
) -> BusinessRuleConfig | None:
    for row in rows:
        if statuses is not None and row.status not in statuses:
            continue
        value = row.value_json if isinstance(row.value_json, dict) else {}
        if str(row.id) == ruleset_id or value.get("rule_set_id") == ruleset_id:
            return row
    return None


def _sales_preview_payload(value: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    coverage = {
        "total": 0,
        "matched": 0,
        "missing_agent": 0,
        "missing_persona": 0,
        "disabled": 0,
    }
    for item in value.get("combinations", []):
        if not isinstance(item, dict):
            continue
        coverage["total"] += 1
        status = "matched"
        reason = "默认自动匹配可用 Agent 与 Persona。"
        if item.get("enabled") is False:
            status = "disabled"
            reason = "该组合已停用，不会进入用户训练入口。"
        elif item.get("required_agent_match"):
            status = "missing_agent"
            reason = "需要后台 Agent 匹配检查后才能确认覆盖。"
        elif item.get("required_persona_match"):
            status = "missing_persona"
            reason = "需要后台 Persona 匹配检查后才能确认覆盖。"
        coverage[status] += 1
        items.append(
            {
                "combination_id": item.get("id"),
                "capability": item.get("capability"),
                "role": item.get("role"),
                "status": status,
                "matched_agent_name": None,
                "matched_persona_name": None,
                "reason": reason,
            }
        )
    return {
        "valid": True,
        "ruleset_version": value.get("version"),
        "previewed_at": datetime.now(UTC).isoformat(),
        "coverage": coverage,
        "items": items,
        "validation_errors": [],
    }


def _business_rule_error(exc: Exception) -> JSONResponse:
    message = str(exc)
    if message.startswith("[") and "]" in message:
        code = message.split("]", 1)[0] + "]"
    elif isinstance(exc, BusinessRuleValidationError):
        code = "[BUSINESS_RULE_SCHEMA_INVALID]"
    elif isinstance(exc, KeyError):
        code = "[BUSINESS_RULE_KEY_UNSUPPORTED]"
    else:
        code = "[BUSINESS_RULE_OPERATION_FAILED]"
    status = 404 if code.endswith("_NOT_FOUND]") else 400
    return _error(code, status_code=status, message=message)


@router.get("/definitions")
async def list_business_rule_definitions_api(
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, Any]:
    _ = current_user
    return success_response(
        {
            "items": [
                _definition_payload(item.key)
                for item in list_business_rule_definitions()
            ]
        }
    )


@router.post("/seed-defaults")
async def seed_default_business_rules(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        created = await service.seed_defaults(actor_id=str(current_user.user_id))
        await db.commit()
        return success_response(
            {
                "created": [_config_payload(row) for row in created],
                "created_count": len(created),
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("business_rule_seed_defaults_failed", error=str(exc))
        return _error(
            "[BUSINESS_RULE_SEED_DEFAULTS_FAILED]",
            status_code=500,
            message="Failed to seed default business rules",
        )


@router.get("")
async def list_business_rules(
    domain: str | None = Query(default=None),
    key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    include_audit: bool = Query(default=False),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = BusinessRuleConfigService(db)
    try:
        rows = await service.list_configs(domain=domain, key=key, status=status)
        payload: dict[str, Any] = {
            "items": [_config_payload(row) for row in rows],
            "total": len(rows),
        }
        if include_audit:
            audits = await service.list_audit_logs(key=key, limit=50)
            payload["audit_logs"] = [service.audit_snapshot(row) for row in audits]
        return success_response(payload)
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        return _business_rule_error(exc)


@router.get("/active/{config_key}")
async def get_active_business_rule(
    config_key: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = BusinessRuleConfigService(db)
    try:
        resolution = await service.resolve_active_config(config_key)
        return success_response(resolution.as_dict())
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        return _business_rule_error(exc)


@router.get("/sales-combinations")
async def list_sales_combination_rulesets(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    rows = await service.list_configs(key=SALES_COMBINATIONS_RULESET_KEY)
    audit_rows = [
        service.audit_snapshot(row)
        for row in await service.list_audit_logs(
            key=SALES_COMBINATIONS_RULESET_KEY, limit=50
        )
    ]
    latest_audit_by_version: dict[int, dict[str, Any]] = {}
    for audit in audit_rows:
        after_version = audit.get("after_version")
        if (
            isinstance(after_version, int)
            and after_version not in latest_audit_by_version
        ):
            latest_audit_by_version[after_version] = audit

    active_rows = [row for row in rows if row.status in {"published", "disabled"}]
    active_row = active_rows[0] if active_rows else None
    active = None
    if active_row is not None:
        active = _sales_ruleset_payload(
            active_row,
            validate_business_rule_value(
                SALES_COMBINATIONS_RULESET_KEY,
                dict(active_row.value_json or {}),
            ),
            status="published" if active_row.status != "disabled" else "archived",
            audit=latest_audit_by_version.get(active_row.version),
        )
    else:
        resolution = await service.resolve_active_config(SALES_COMBINATIONS_RULESET_KEY)
        active = _sales_ruleset_payload(
            None,
            resolution.value,
            status="published",
            fallback_reason=resolution.fallback_reason,
        )

    drafts = [
        _sales_ruleset_payload(
            row,
            validate_business_rule_value(
                SALES_COMBINATIONS_RULESET_KEY, dict(row.value_json or {})
            ),
            status="draft",
            audit=latest_audit_by_version.get(row.version),
        )
        for row in rows
        if row.status == "draft"
    ]
    history = [
        _sales_ruleset_payload(
            row,
            validate_business_rule_value(
                SALES_COMBINATIONS_RULESET_KEY, dict(row.value_json or {})
            ),
            status="archived",
            audit=latest_audit_by_version.get(row.version),
        )
        for row in rows
        if row.status in {"archived", "disabled"}
    ]
    return success_response(
        {
            "active": active,
            "drafts": drafts,
            "history": history,
            "audit_log": [_sales_audit_payload(row) for row in audit_rows],
            "permissions": {
                "can_view": True,
                "can_mutate": current_user.role == "admin",
                "can_publish": current_user.role == "admin",
                "reason": None if current_user.role == "admin" else "需要管理员权限。",
            },
        }
    )


@router.post("/sales-combinations/validate")
async def validate_sales_combination_ruleset(
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        normalized = await service.validate_config_value(
            key=SALES_COMBINATIONS_RULESET_KEY,
            value=payload,
            actor_id=str(current_user.user_id),
            audit=True,
        )
        await db.commit()
        return success_response(
            {
                "valid": True,
                "errors": [],
                "warnings": [],
                "normalized_value": normalized,
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return success_response(_sales_validation_error_payload(exc))


@router.post("/sales-combinations/preview")
async def preview_sales_combination_ruleset(
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        normalized = await service.validate_config_value(
            key=SALES_COMBINATIONS_RULESET_KEY,
            value=payload,
            actor_id=str(current_user.user_id),
            audit=True,
        )
        await db.commit()
        return success_response(_sales_preview_payload(normalized))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        invalid = _sales_validation_error_payload(exc)
        return success_response(
            {
                "valid": False,
                "ruleset_version": payload.get("version"),
                "coverage": {
                    "total": 0,
                    "matched": 0,
                    "missing_agent": 0,
                    "missing_persona": 0,
                    "disabled": 0,
                },
                "items": [],
                "validation_errors": invalid["errors"],
            }
        )


@router.post("/sales-combinations/{ruleset_id}/publish")
async def publish_sales_combination_ruleset(
    ruleset_id: str,
    payload: BusinessRulePublishRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        rows = await service.list_configs(key=SALES_COMBINATIONS_RULESET_KEY)
        draft = _find_sales_row_by_ruleset_id(rows, ruleset_id, statuses={"draft"})
        if draft is None and ruleset_id == get_default_business_rule_value(
            SALES_COMBINATIONS_RULESET_KEY
        ).get("rule_set_id"):
            draft = await service.create_or_update_draft(
                key=SALES_COMBINATIONS_RULESET_KEY,
                value=get_default_business_rule_value(SALES_COMBINATIONS_RULESET_KEY),
                actor_id=str(current_user.user_id),
                reason=payload.reason,
            )
        row = await service.publish(
            key=SALES_COMBINATIONS_RULESET_KEY,
            actor_id=str(current_user.user_id),
            config_id=str(draft.id) if draft else payload.config_id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        audit = service.audit_snapshot(
            (
                await service.list_audit_logs(
                    key=SALES_COMBINATIONS_RULESET_KEY, limit=1
                )
            )[0]
        )
        return success_response(
            {
                "ruleset": _sales_ruleset_payload(
                    row, dict(row.value_json or {}), status="published", audit=audit
                ),
                "audit": _sales_audit_payload(audit),
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.post("/sales-combinations/{ruleset_id}/rollback")
async def rollback_sales_combination_ruleset(
    ruleset_id: str,
    payload: BusinessRuleRollbackRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        rows = await service.list_configs(key=SALES_COMBINATIONS_RULESET_KEY)
        target = _find_sales_row_by_ruleset_id(
            rows,
            ruleset_id,
            statuses={"archived", "published", "disabled"},
        )
        row = await service.rollback(
            key=SALES_COMBINATIONS_RULESET_KEY,
            actor_id=str(current_user.user_id),
            target_config_id=str(target.id) if target else payload.target_config_id,
            target_version=payload.target_version,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        audit = service.audit_snapshot(
            (
                await service.list_audit_logs(
                    key=SALES_COMBINATIONS_RULESET_KEY, limit=1
                )
            )[0]
        )
        return success_response(
            {
                "ruleset": _sales_ruleset_payload(
                    row, dict(row.value_json or {}), status="published", audit=audit
                ),
                "audit": _sales_audit_payload(audit),
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.get("/{config_key}")
async def get_business_rule_history(
    config_key: str,
    include_audit: bool = Query(default=True),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    _ = current_user
    service = BusinessRuleConfigService(db)
    try:
        rows = await service.list_configs(key=config_key)
        payload: dict[str, Any] = {
            "definition": _definition_payload(config_key),
            "items": [_config_payload(row) for row in rows],
            "total": len(rows),
        }
        if include_audit:
            audits = await service.list_audit_logs(key=config_key, limit=50)
            payload["audit_logs"] = [service.audit_snapshot(row) for row in audits]
        return success_response(payload)
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        return _business_rule_error(exc)


@router.post("/{config_key}/drafts")
async def create_or_update_business_rule_draft(
    config_key: str,
    payload: BusinessRuleValueRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        row = await service.create_or_update_draft(
            key=config_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("business_rule_draft_save_failed", key=config_key, error=str(exc))
        return _error(
            "[BUSINESS_RULE_DRAFT_SAVE_FAILED]",
            status_code=500,
            message="Failed to save business-rule draft",
        )


@router.post("/{config_key}/validate")
async def validate_business_rule(
    config_key: str,
    payload: BusinessRuleValueRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        normalized = await service.validate_config_value(
            key=config_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            audit=True,
        )
        await db.commit()
        return success_response({"valid": True, "normalized_value": normalized})
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.post("/{config_key}/preview")
async def preview_business_rule(
    config_key: str,
    payload: BusinessRuleValueRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        preview = await service.preview(
            key=config_key,
            value=payload.value,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        return success_response(preview)
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.post("/{config_key}/publish")
async def publish_business_rule(
    config_key: str,
    payload: BusinessRulePublishRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        row = await service.publish(
            key=config_key,
            actor_id=str(current_user.user_id),
            config_id=payload.config_id,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("business_rule_publish_failed", key=config_key, error=str(exc))
        return _error(
            "[BUSINESS_RULE_PUBLISH_FAILED]",
            status_code=500,
            message="Failed to publish business rule",
        )


@router.post("/{config_key}/rollback")
async def rollback_business_rule(
    config_key: str,
    payload: BusinessRuleRollbackRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        row = await service.rollback(
            key=config_key,
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
        return _business_rule_error(exc)
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("business_rule_rollback_failed", key=config_key, error=str(exc))
        return _error(
            "[BUSINESS_RULE_ROLLBACK_FAILED]",
            status_code=500,
            message="Failed to roll back business rule",
        )


@router.post("/{config_key}/disable")
async def disable_business_rule(
    config_key: str,
    payload: BusinessRuleDisableRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        row = await service.disable(
            key=config_key,
            actor_id=str(current_user.user_id),
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        return success_response(_config_payload(row))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.delete("/drafts/{config_id}")
async def delete_business_rule_draft(
    config_id: str,
    payload: BusinessRuleDeleteDraftRequest | None = None,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        row = await service.delete_draft(
            config_id=config_id,
            actor_id=str(current_user.user_id),
            reason=payload.reason if payload else None,
        )
        await db.commit()
        return success_response({"deleted": True, "id": str(row.id)})
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)
