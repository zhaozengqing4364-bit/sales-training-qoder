"""Admin API for governed business-rule configuration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.api.business_rules import sales_combination_ruleset_payload
from common.api.response import error_response, success_response
from common.auth.service import get_current_admin_user
from common.business_rules.defaults import (
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
    list_business_rule_definitions,
)
from common.business_rules.service import (
    BusinessRuleConfigService,
    BusinessRuleResolution,
)
from common.business_rules.validators import (
    BusinessRuleValidationError,
    validate_business_rule_value,
)
from common.db.models import BusinessRuleConfig, BusinessRuleConfigAuditLog, User
from common.db.session import get_db
from common.monitoring.logger import get_logger

from admin.api.permissions import (
    BUSINESS_RULE_PUBLISH_PERMISSION,
    require_admin_permission,
)

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


def _validation_issue(message: str) -> dict[str, str]:
    path = "value"
    if "." in message:
        path = message.split(" ", 1)[0]
    return {"path": path, "message": message}


def _audit_entry(row: BusinessRuleConfigAuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "actor": str(row.actor_id) if row.actor_id else None,
        "action": row.action,
        "before_version": str(row.before_version)
        if row.before_version is not None
        else None,
        "after_version": str(row.after_version)
        if row.after_version is not None
        else None,
        "reason": row.reason,
        "trace_id": row.trace_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _row_to_sales_ruleset(
    row: BusinessRuleConfig,
    *,
    audits: list[BusinessRuleConfigAuditLog],
) -> dict[str, Any]:
    resolution = BusinessRuleResolution(
        key=row.key,
        domain=row.domain,
        value=dict(row.value_json or {}),
        source="database",
        config_id=str(row.id),
        version=int(row.version),
        status=str(row.status),
    )
    payload = sales_combination_ruleset_payload(resolution)
    payload["effective_at"] = (
        row.updated_at.isoformat() if row.status in {"published", "disabled"} else None
    )

    matching_audits = [audit for audit in audits if str(audit.config_id) == str(row.id)]
    publish_audit = next(
        (
            audit
            for audit in matching_audits
            if audit.action in {"publish", "rollback", "seed_default"}
        ),
        matching_audits[0] if matching_audits else None,
    )
    if publish_audit is not None:
        payload["audit_summary"] = {
            "published_by": str(publish_audit.actor_id)
            if publish_audit.actor_id
            else None,
            "published_at": publish_audit.created_at.isoformat()
            if publish_audit.created_at
            else None,
            "reason": publish_audit.reason,
            "trace_id": publish_audit.trace_id,
        }
    return payload


def _sales_combination_permissions(current_user: User) -> dict[str, Any]:
    can_publish = getattr(current_user, "role", None) == "admin"
    return {
        "can_view": can_publish,
        "can_mutate": can_publish,
        "can_publish": can_publish,
        "reason": None if can_publish else "需要业务规则发布权限",
    }


async def _sales_ruleset_row_by_public_id(
    service: BusinessRuleConfigService,
    ruleset_id: str,
    *,
    statuses: set[str],
) -> BusinessRuleConfig | None:
    rows = await service.list_configs(key=SALES_COMBINATION_RULES_KEY)
    for row in rows:
        if row.status not in statuses:
            continue
        value = row.value_json if isinstance(row.value_json, dict) else {}
        if (
            str(row.id) == ruleset_id
            or str(value.get("rule_set_id") or "") == ruleset_id
        ):
            return row
    return None


def _sales_combination_preview_payload(value: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    coverage = {
        "total": 0,
        "matched": 0,
        "missing_agent": 0,
        "missing_persona": 0,
        "disabled": 0,
    }
    for combination in value.get("combinations", []):
        if not isinstance(combination, dict):
            continue
        coverage["total"] += 1
        status = "matched"
        reason = None
        if combination.get("enabled") is False:
            status = "disabled"
            reason = "组合已停用。"
        elif combination.get("required_agent_match"):
            status = "missing_agent"
            reason = "需要匹配包含指定能力标签的训练智能体。"
        elif combination.get("required_persona_match"):
            status = "missing_persona"
            reason = "需要匹配包含指定标签的客户画像。"
        coverage[status] += 1
        items.append(
            {
                "combination_id": combination.get("id"),
                "capability": combination.get("capability"),
                "role": combination.get("role"),
                "status": status,
                "matched_agent_name": None,
                "matched_persona_name": None,
                "reason": reason,
            }
        )
    return {
        "valid": True,
        "ruleset_version": value["version"],
        "previewed_at": None,
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


@router.get("/sales-combinations")
async def list_sales_combination_rulesets(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    rows = await service.list_configs(key=SALES_COMBINATION_RULES_KEY)
    audits = await service.list_audit_logs(key=SALES_COMBINATION_RULES_KEY, limit=100)
    resolution = await service.resolve_active_config(SALES_COMBINATION_RULES_KEY)
    active_payload = sales_combination_ruleset_payload(resolution)
    if resolution.config_id:
        active_row = next(
            (row for row in rows if str(row.id) == resolution.config_id), None
        )
        if active_row is not None:
            active_payload = _row_to_sales_ruleset(active_row, audits=audits)

    return success_response(
        {
            "active": active_payload,
            "drafts": [
                _row_to_sales_ruleset(row, audits=audits)
                for row in rows
                if row.status == "draft"
            ],
            "history": [
                _row_to_sales_ruleset(row, audits=audits)
                for row in rows
                if row.status in {"published", "archived", "disabled"}
                and str(row.id) != resolution.config_id
            ],
            "audit_log": [_audit_entry(row) for row in audits],
            "permissions": _sales_combination_permissions(current_user),
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
        validate_business_rule_value(SALES_COMBINATION_RULES_KEY, payload)
        await service.validate_config_value(
            key=SALES_COMBINATION_RULES_KEY,
            value=payload,
            actor_id=str(current_user.user_id),
            audit=True,
        )
        await db.commit()
        return success_response({"valid": True, "errors": [], "warnings": []})
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return success_response(
            {
                "valid": False,
                "errors": [_validation_issue(str(exc))],
                "warnings": [],
            }
        )


@router.post("/sales-combinations/preview")
async def preview_sales_combination_ruleset(
    payload: dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        normalized = validate_business_rule_value(SALES_COMBINATION_RULES_KEY, payload)
        await service.preview(
            key=SALES_COMBINATION_RULES_KEY,
            value=normalized,
            actor_id=str(current_user.user_id),
            reason="sales-combination coverage preview",
        )
        await db.commit()
        return success_response(_sales_combination_preview_payload(normalized))
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return success_response(
            {
                "valid": False,
                "ruleset_version": str(payload.get("version") or ""),
                "coverage": {
                    "total": 0,
                    "matched": 0,
                    "missing_agent": 0,
                    "missing_persona": 0,
                    "disabled": 0,
                },
                "items": [],
                "validation_errors": [_validation_issue(str(exc))],
            }
        )


@router.post("/sales-combinations/{ruleset_id}/publish")
async def publish_sales_combination_ruleset(
    ruleset_id: str,
    payload: BusinessRulePublishRequest,
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        target = await _sales_ruleset_row_by_public_id(
            service,
            ruleset_id,
            statuses={"draft"},
        )
        if target is None:
            raise ValueError("[BUSINESS_RULE_DRAFT_NOT_FOUND]")
        row = await service.publish(
            key=SALES_COMBINATION_RULES_KEY,
            actor_id=str(current_user.user_id),
            config_id=str(target.id),
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        audits = await service.list_audit_logs(
            key=SALES_COMBINATION_RULES_KEY, limit=20
        )
        latest_audit = audits[0] if audits else None
        return success_response(
            {
                "ruleset": _row_to_sales_ruleset(row, audits=audits),
                "audit": _audit_entry(latest_audit) if latest_audit else None,
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
        return _business_rule_error(exc)


@router.post("/sales-combinations/{ruleset_id}/rollback")
async def rollback_sales_combination_ruleset(
    ruleset_id: str,
    payload: BusinessRuleRollbackRequest,
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = BusinessRuleConfigService(db)
    try:
        target = await _sales_ruleset_row_by_public_id(
            service,
            ruleset_id,
            statuses={"published", "archived", "disabled"},
        )
        if target is None:
            raise ValueError("[BUSINESS_RULE_ROLLBACK_TARGET_NOT_FOUND]")
        row = await service.rollback(
            key=SALES_COMBINATION_RULES_KEY,
            actor_id=str(current_user.user_id),
            target_config_id=str(target.id),
            target_version=payload.target_version,
            reason=payload.reason,
        )
        await db.commit()
        await db.refresh(row)
        audits = await service.list_audit_logs(
            key=SALES_COMBINATION_RULES_KEY, limit=20
        )
        latest_audit = audits[0] if audits else None
        return success_response(
            {
                "ruleset": _row_to_sales_ruleset(row, audits=audits),
                "audit": _audit_entry(latest_audit) if latest_audit else None,
            }
        )
    except (BusinessRuleValidationError, KeyError, ValueError) as exc:
        await db.rollback()
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
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
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
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
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
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
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
    current_user: User = Depends(
        require_admin_permission(BUSINESS_RULE_PUBLISH_PERMISSION)
    ),
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
