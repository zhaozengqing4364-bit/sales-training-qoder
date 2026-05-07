"""Async service for governed business-rule CRUD and active resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    ADMIN_SETTINGS_GENERAL_KEY,
    ADMIN_SETTINGS_NOTIFICATIONS_KEY,
    ADMIN_SETTINGS_SECURITY_KEY,
    OBJECTION_LEDGER_RULES_KEY,
    SALES_COMBINATION_RULES_KEY,
    get_business_rule_definition,
    get_default_business_rule_value,
    list_business_rule_definitions,
)
from common.business_rules.validators import (
    BusinessRuleValidationError,
    validate_business_rule_value,
)
from common.db.models import BusinessRuleConfig, BusinessRuleConfigAuditLog
from common.monitoring.logger import get_logger, get_trace_id

logger = get_logger(__name__)

_ACTIVE_STATUSES = {"published", "disabled"}
_HISTORY_STATUSES = {"published", "archived", "disabled"}


def _orm_field(row: object, name: str) -> Any:
    return cast(Any, getattr(row, name))


def _set_orm_field(row: object, name: str, value: object) -> None:
    setattr(row, name, value)


def _orm_dict(row: object, name: str) -> dict[str, Any]:
    return dict(_orm_field(row, name) or {})


def _orm_str(row: object, name: str) -> str:
    return str(_orm_field(row, name))


def _orm_int(row: object, name: str) -> int:
    return int(_orm_field(row, name))


def _orm_datetime(row: object, name: str) -> datetime | None:
    value = getattr(row, name, None)
    return value if isinstance(value, datetime) else None


@dataclass(frozen=True)
class BusinessRuleResolution:
    key: str
    domain: str
    value: dict[str, Any]
    source: str
    config_id: str | None = None
    version: int | None = None
    status: str | None = None
    fallback_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "domain": self.domain,
            "value": deepcopy(self.value),
            "source": self.source,
            "config_id": self.config_id,
            "version": self.version,
            "status": self.status,
            "fallback_reason": self.fallback_reason,
        }


class BusinessRuleConfigService:
    """Manage draft/published business-rule configs and runtime resolution."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_configs(
        self,
        *,
        domain: str | None = None,
        key: str | None = None,
        status: str | None = None,
    ) -> list[BusinessRuleConfig]:
        statement = select(BusinessRuleConfig)
        if domain:
            statement = statement.where(BusinessRuleConfig.domain == domain)
        if key:
            get_business_rule_definition(key)
            statement = statement.where(BusinessRuleConfig.key == key)
        if status:
            statement = statement.where(BusinessRuleConfig.status == status)
        statement = statement.order_by(
            BusinessRuleConfig.domain.asc(),
            BusinessRuleConfig.key.asc(),
            BusinessRuleConfig.version.desc(),
        )
        result = await self._db.execute(statement)
        return list(result.scalars().all())

    async def get_config(self, config_id: str) -> BusinessRuleConfig | None:
        return await self._db.get(BusinessRuleConfig, config_id)

    async def seed_defaults(
        self, *, actor_id: str | None = None
    ) -> list[BusinessRuleConfig]:
        created: list[BusinessRuleConfig] = []
        for definition in list_business_rule_definitions():
            existing = await self._latest_config_for_key(definition.key)
            if existing is not None:
                continue
            value = validate_business_rule_value(
                definition.key,
                deepcopy(definition.default_value),
            )
            row = BusinessRuleConfig(
                domain=definition.domain,
                key=definition.key,
                schema_version=definition.schema_version,
                status="published",
                version=1,
                value_json=value,
                default_value_json=deepcopy(definition.default_value),
                type=definition.type,
                range_or_allowlist_json=deepcopy(definition.range_or_allowlist),
                read_path=definition.read_path,
                admin_entry=definition.admin_entry,
                permission=definition.permission,
                audit_policy=definition.audit_policy,
                fallback_policy=definition.fallback_policy,
                rollback_policy=definition.rollback_policy,
                enabled=value.get("enabled") is not False,
                validation_errors_json=[],
                created_by=actor_id,
                updated_by=actor_id,
            )
            self._db.add(row)
            await self._db.flush()
            self._queue_audit(
                action="seed_default",
                config=row,
                actor_id=actor_id,
                before=None,
                after=row,
                reason="seed bundled default business rule config",
            )
            created.append(row)
        return created

    async def create_or_update_draft(
        self,
        *,
        key: str,
        value: dict[str, Any],
        actor_id: str,
        reason: str | None = None,
    ) -> BusinessRuleConfig:
        definition = get_business_rule_definition(key)
        normalized = validate_business_rule_value(key, value)
        draft = await self._latest_draft_for_key(key)
        if draft is None:
            version = await self._next_version(key)
            draft = BusinessRuleConfig(
                domain=definition.domain,
                key=definition.key,
                schema_version=definition.schema_version,
                status="draft",
                version=version,
                value_json=normalized,
                default_value_json=deepcopy(definition.default_value),
                type=definition.type,
                range_or_allowlist_json=deepcopy(definition.range_or_allowlist),
                read_path=definition.read_path,
                admin_entry=definition.admin_entry,
                permission=definition.permission,
                audit_policy=definition.audit_policy,
                fallback_policy=definition.fallback_policy,
                rollback_policy=definition.rollback_policy,
                enabled=normalized.get("enabled") is not False,
                validation_errors_json=[],
                created_by=actor_id,
                updated_by=actor_id,
            )
            self._db.add(draft)
            await self._db.flush()
            self._queue_audit(
                action="create_draft",
                config=draft,
                actor_id=actor_id,
                before=None,
                after=draft,
                reason=reason,
            )
            return draft

        before = self.snapshot(draft)
        _set_orm_field(draft, "value_json", normalized)
        _set_orm_field(draft, "default_value_json", deepcopy(definition.default_value))
        _set_orm_field(draft, "schema_version", definition.schema_version)
        _set_orm_field(draft, "enabled", normalized.get("enabled") is not False)
        _set_orm_field(draft, "validation_errors_json", [])
        _set_orm_field(draft, "updated_by", actor_id)
        _set_orm_field(draft, "updated_at", datetime.now(UTC))
        await self._db.flush()
        self._queue_audit(
            action="update_draft",
            config=draft,
            actor_id=actor_id,
            before=before,
            after=draft,
            reason=reason,
        )
        return draft

    async def validate_config_value(
        self,
        *,
        key: str,
        value: dict[str, Any],
        actor_id: str | None = None,
        audit: bool = False,
    ) -> dict[str, Any]:
        normalized = validate_business_rule_value(key, value)
        if audit:
            definition = get_business_rule_definition(key)
            self._queue_audit(
                action="validate",
                config_key=key,
                domain=definition.domain,
                actor_id=actor_id,
                before=None,
                after_snapshot={"value": normalized},
                reason="schema validation",
            )
        return cast(dict[str, Any], normalized)

    async def preview(
        self,
        *,
        key: str,
        value: dict[str, Any],
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        normalized = validate_business_rule_value(key, value)
        active = await self._active_config_for_key(key)
        summary = self._preview_summary(key, normalized)
        definition = get_business_rule_definition(key)
        self._queue_audit(
            action="preview",
            config_key=key,
            domain=definition.domain,
            actor_id=actor_id,
            before=active,
            after_snapshot={"value": normalized, "summary": summary},
            reason=reason or "preview business rule config",
        )
        return {
            "valid": True,
            "summary": summary,
            "active_version": _orm_int(active, "version") if active is not None else None,
            "active_config_id": _orm_str(active, "id") if active is not None else None,
        }

    async def publish(
        self,
        *,
        key: str,
        actor_id: str,
        config_id: str | None = None,
        reason: str | None = None,
    ) -> BusinessRuleConfig:
        draft = await self._target_draft(key=key, config_id=config_id)
        if draft is None:
            raise ValueError("[BUSINESS_RULE_DRAFT_NOT_FOUND]")
        normalized = validate_business_rule_value(key, _orm_dict(draft, "value_json"))
        current_active = await self._active_config_for_key(key)
        before_snapshot = self.snapshot(current_active) if current_active else None

        active_rows = await self._active_configs_for_key(key)
        for row in active_rows:
            if _orm_str(row, "id") != _orm_str(draft, "id"):
                _set_orm_field(row, "status", "archived")
                _set_orm_field(row, "enabled", False)
                _set_orm_field(row, "updated_by", actor_id)
                _set_orm_field(row, "updated_at", datetime.now(UTC))

        _set_orm_field(draft, "value_json", normalized)
        _set_orm_field(
            draft,
            "status",
            "published" if normalized.get("enabled") is not False else "disabled"
        )
        _set_orm_field(draft, "enabled", normalized.get("enabled") is not False)
        _set_orm_field(draft, "validation_errors_json", [])
        _set_orm_field(draft, "updated_by", actor_id)
        _set_orm_field(draft, "updated_at", datetime.now(UTC))
        await self._db.flush()
        self._queue_audit(
            action="publish",
            config=draft,
            actor_id=actor_id,
            before_snapshot=before_snapshot,
            after=draft,
            reason=reason,
        )
        return draft

    async def rollback(
        self,
        *,
        key: str,
        actor_id: str,
        target_config_id: str | None = None,
        target_version: int | None = None,
        reason: str | None = None,
    ) -> BusinessRuleConfig:
        target = await self._rollback_target(
            key=key,
            target_config_id=target_config_id,
            target_version=target_version,
        )
        if target is None:
            raise ValueError("[BUSINESS_RULE_ROLLBACK_TARGET_NOT_FOUND]")
        normalized = validate_business_rule_value(key, _orm_dict(target, "value_json"))
        current_active = await self._active_config_for_key(key)
        if current_active is not None and _orm_str(current_active, "id") == _orm_str(
            target, "id"
        ):
            raise ValueError("[BUSINESS_RULE_ROLLBACK_TARGET_ALREADY_ACTIVE]")
        before_snapshot = self.snapshot(current_active) if current_active else None

        active_rows = await self._active_configs_for_key(key)
        for row in active_rows:
            if _orm_str(row, "id") != _orm_str(target, "id"):
                _set_orm_field(row, "status", "archived")
                _set_orm_field(row, "enabled", False)
                _set_orm_field(row, "updated_by", actor_id)
                _set_orm_field(row, "updated_at", datetime.now(UTC))

        _set_orm_field(target, "value_json", normalized)
        _set_orm_field(
            target,
            "status",
            "published" if normalized.get("enabled") is not False else "disabled"
        )
        _set_orm_field(target, "enabled", normalized.get("enabled") is not False)
        _set_orm_field(target, "validation_errors_json", [])
        _set_orm_field(target, "updated_by", actor_id)
        _set_orm_field(target, "updated_at", datetime.now(UTC))
        await self._db.flush()
        self._queue_audit(
            action="rollback",
            config=target,
            actor_id=actor_id,
            before_snapshot=before_snapshot,
            after=target,
            reason=reason,
        )
        return target

    async def disable(
        self,
        *,
        key: str,
        actor_id: str,
        reason: str | None = None,
    ) -> BusinessRuleConfig:
        active = await self._active_config_for_key(key)
        if active is None:
            raise ValueError("[BUSINESS_RULE_ACTIVE_NOT_FOUND]")
        before = self.snapshot(active)
        value = _orm_dict(active, "value_json")
        value["enabled"] = False
        _set_orm_field(active, "value_json", validate_business_rule_value(key, value))
        _set_orm_field(active, "status", "disabled")
        _set_orm_field(active, "enabled", False)
        _set_orm_field(active, "updated_by", actor_id)
        _set_orm_field(active, "updated_at", datetime.now(UTC))
        await self._db.flush()
        self._queue_audit(
            action="disable",
            config=active,
            actor_id=actor_id,
            before_snapshot=before,
            after=active,
            reason=reason,
        )
        return active

    async def delete_draft(
        self,
        *,
        config_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> BusinessRuleConfig:
        row = await self.get_config(config_id)
        if row is None or _orm_str(row, "status") != "draft":
            raise ValueError("[BUSINESS_RULE_DRAFT_NOT_FOUND]")
        before = self.snapshot(row)
        self._queue_audit(
            action="delete_draft",
            config=row,
            actor_id=actor_id,
            before_snapshot=before,
            after_snapshot=None,
            reason=reason,
        )
        await self._db.delete(row)
        return row

    async def resolve_active_config(
        self,
        key: str,
        *,
        fallback_value: dict[str, Any] | None = None,
        fallback_source: str = "default",
    ) -> BusinessRuleResolution:
        definition = get_business_rule_definition(key)
        active = await self._active_config_for_key(key)
        if active is not None:
            try:
                value = validate_business_rule_value(key, _orm_dict(active, "value_json"))
                source = (
                    "database_disabled" if value.get("enabled") is False else "database"
                )
                return BusinessRuleResolution(
                    key=key,
                    domain=definition.domain,
                    value=value,
                    source=source,
                    config_id=_orm_str(active, "id"),
                    version=_orm_int(active, "version"),
                    status=_orm_str(active, "status"),
                )
            except (
                BusinessRuleValidationError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                logger.warning(
                    "business_rule_active_invalid_fallback",
                    key=key,
                    config_id=_orm_str(active, "id"),
                    version=_orm_int(active, "version"),
                    error=str(exc),
                )
                previous = await self._latest_valid_history_before(
                    key=key,
                    before_version=_orm_int(active, "version"),
                )
                if previous is not None:
                    return previous
                fallback_reason = f"active_invalid:{exc}"
        else:
            fallback_reason = "active_missing"

        fallback = (
            fallback_value
            if fallback_value is not None
            else get_default_business_rule_value(key)
        )
        try:
            value = validate_business_rule_value(key, deepcopy(fallback))
        except (BusinessRuleValidationError, KeyError, TypeError, ValueError):
            value = validate_business_rule_value(
                key, get_default_business_rule_value(key)
            )
            fallback_source = "default"
            fallback_reason = "fallback_invalid_used_default"
        return BusinessRuleResolution(
            key=key,
            domain=definition.domain,
            value=value,
            source=fallback_source,
            fallback_reason=fallback_reason,
        )

    async def list_audit_logs(
        self,
        *,
        key: str | None = None,
        limit: int = 50,
    ) -> list[BusinessRuleConfigAuditLog]:
        statement = select(BusinessRuleConfigAuditLog)
        if key:
            statement = statement.where(BusinessRuleConfigAuditLog.config_key == key)
        statement = statement.order_by(
            BusinessRuleConfigAuditLog.created_at.desc()
        ).limit(limit)
        result = await self._db.execute(statement)
        return list(result.scalars().all())

    @staticmethod
    def snapshot(row: BusinessRuleConfig | None) -> dict[str, Any] | None:
        if row is None:
            return None
        updated_at = _orm_datetime(row, "updated_at")
        return {
            "id": _orm_str(row, "id"),
            "domain": _orm_str(row, "domain"),
            "key": _orm_str(row, "key"),
            "schema_version": _orm_str(row, "schema_version"),
            "status": _orm_str(row, "status"),
            "version": _orm_int(row, "version"),
            "enabled": bool(_orm_field(row, "enabled")),
            "value": deepcopy(_orm_field(row, "value_json")),
            "default_value": deepcopy(_orm_field(row, "default_value_json")),
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    @staticmethod
    def audit_snapshot(row: BusinessRuleConfigAuditLog) -> dict[str, Any]:
        created_at = _orm_datetime(row, "created_at")
        return {
            "id": _orm_str(row, "id"),
            "config_id": str(_orm_field(row, "config_id"))
            if _orm_field(row, "config_id")
            else None,
            "domain": _orm_str(row, "domain"),
            "config_key": _orm_str(row, "config_key"),
            "action": _orm_str(row, "action"),
            "actor_id": str(_orm_field(row, "actor_id"))
            if _orm_field(row, "actor_id")
            else None,
            "before_version": _orm_field(row, "before_version"),
            "after_version": _orm_field(row, "after_version"),
            "before_snapshot": deepcopy(_orm_field(row, "before_snapshot_json")),
            "after_snapshot": deepcopy(_orm_field(row, "after_snapshot_json")),
            "reason": _orm_str(row, "reason"),
            "trace_id": _orm_field(row, "trace_id"),
            "created_at": created_at.isoformat() if created_at else None,
        }

    async def _latest_config_for_key(self, key: str) -> BusinessRuleConfig | None:
        result = await self._db.execute(
            select(BusinessRuleConfig)
            .where(BusinessRuleConfig.key == key)
            .order_by(
                BusinessRuleConfig.version.desc(), BusinessRuleConfig.updated_at.desc()
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_draft_for_key(self, key: str) -> BusinessRuleConfig | None:
        result = await self._db.execute(
            select(BusinessRuleConfig)
            .where(BusinessRuleConfig.key == key, BusinessRuleConfig.status == "draft")
            .order_by(
                BusinessRuleConfig.version.desc(), BusinessRuleConfig.updated_at.desc()
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _next_version(self, key: str) -> int:
        result = await self._db.execute(
            select(func.max(BusinessRuleConfig.version)).where(
                BusinessRuleConfig.key == key
            )
        )
        latest = result.scalar() or 0
        return int(latest) + 1

    async def _active_configs_for_key(self, key: str) -> list[BusinessRuleConfig]:
        result = await self._db.execute(
            select(BusinessRuleConfig).where(
                BusinessRuleConfig.key == key,
                BusinessRuleConfig.status.in_(_ACTIVE_STATUSES),
            )
        )
        return list(result.scalars().all())

    async def _active_config_for_key(self, key: str) -> BusinessRuleConfig | None:
        result = await self._db.execute(
            select(BusinessRuleConfig)
            .where(
                BusinessRuleConfig.key == key,
                BusinessRuleConfig.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(
                desc(BusinessRuleConfig.updated_at),
                desc(BusinessRuleConfig.version),
                desc(BusinessRuleConfig.created_at),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _target_draft(
        self,
        *,
        key: str,
        config_id: str | None,
    ) -> BusinessRuleConfig | None:
        if config_id:
            row = await self.get_config(config_id)
            if (
                row is None
                or _orm_str(row, "key") != key
                or _orm_str(row, "status") != "draft"
            ):
                return None
            return row
        return await self._latest_draft_for_key(key)

    async def _rollback_target(
        self,
        *,
        key: str,
        target_config_id: str | None,
        target_version: int | None,
    ) -> BusinessRuleConfig | None:
        if target_config_id:
            row = await self.get_config(target_config_id)
            if (
                row is None
                or _orm_str(row, "key") != key
                or _orm_str(row, "status") not in _HISTORY_STATUSES
            ):
                return None
            return row
        if target_version is not None:
            result = await self._db.execute(
                select(BusinessRuleConfig)
                .where(
                    BusinessRuleConfig.key == key,
                    BusinessRuleConfig.version == target_version,
                    BusinessRuleConfig.status.in_(_HISTORY_STATUSES),
                )
                .limit(1)
            )
            return result.scalar_one_or_none()

        active = await self._active_config_for_key(key)
        statement = select(BusinessRuleConfig).where(
            BusinessRuleConfig.key == key,
            BusinessRuleConfig.status == "archived",
        )
        if active is not None:
            statement = statement.where(
                BusinessRuleConfig.version < _orm_int(active, "version")
            )
        statement = statement.order_by(BusinessRuleConfig.version.desc()).limit(1)
        result = await self._db.execute(statement)
        return result.scalar_one_or_none()

    async def _latest_valid_history_before(
        self,
        *,
        key: str,
        before_version: int,
    ) -> BusinessRuleResolution | None:
        definition = get_business_rule_definition(key)
        result = await self._db.execute(
            select(BusinessRuleConfig)
            .where(
                BusinessRuleConfig.key == key,
                BusinessRuleConfig.status.in_(_HISTORY_STATUSES),
                BusinessRuleConfig.version < before_version,
            )
            .order_by(
                BusinessRuleConfig.version.desc(), BusinessRuleConfig.updated_at.desc()
            )
        )
        for row in result.scalars().all():
            try:
                value = validate_business_rule_value(key, _orm_dict(row, "value_json"))
            except (BusinessRuleValidationError, KeyError, TypeError, ValueError):
                continue
            return BusinessRuleResolution(
                key=key,
                domain=definition.domain,
                value=value,
                source="database_previous",
                config_id=_orm_str(row, "id"),
                version=_orm_int(row, "version"),
                status=_orm_str(row, "status"),
                fallback_reason="active_invalid_used_previous",
            )
        return None

    def _queue_audit(
        self,
        *,
        action: str,
        actor_id: str | None,
        reason: str | None,
        config: BusinessRuleConfig | None = None,
        config_key: str | None = None,
        domain: str | None = None,
        before: BusinessRuleConfig | dict[str, Any] | None = None,
        after: BusinessRuleConfig | dict[str, Any] | None = None,
        before_snapshot: dict[str, Any] | None = None,
        after_snapshot: dict[str, Any] | None = None,
    ) -> None:
        resolved_key = _orm_str(config, "key") if config is not None else config_key
        if resolved_key is None:
            raise ValueError("config key is required for audit")
        resolved_domain = (
            _orm_str(config, "domain") if config is not None else domain
        )
        if resolved_domain is None:
            resolved_domain = get_business_rule_definition(resolved_key).domain

        before_payload = before_snapshot
        if before_payload is None and before is not None:
            before_payload = (
                before if isinstance(before, dict) else self.snapshot(before)
            )
        after_payload = after_snapshot
        if after_payload is None and after is not None:
            after_payload = after if isinstance(after, dict) else self.snapshot(after)

        self._db.add(
            BusinessRuleConfigAuditLog(
                config_id=_orm_str(config, "id") if config is not None else None,
                domain=resolved_domain,
                config_key=resolved_key,
                action=action,
                actor_id=actor_id,
                before_version=(before_payload or {}).get("version"),
                after_version=(after_payload or {}).get("version"),
                before_snapshot_json=before_payload,
                after_snapshot_json=after_payload,
                reason=(reason or "").strip() or "not-provided",
                trace_id=get_trace_id(),
            )
        )

    @staticmethod
    def _preview_summary(key: str, value: dict[str, Any]) -> dict[str, Any]:
        if key == SALES_COMBINATION_RULES_KEY:
            combinations = [
                item for item in value.get("combinations", []) if isinstance(item, dict)
            ]
            enabled = [
                item for item in combinations if item.get("enabled", True) is not False
            ]
            return {
                "enabled": True,
                "ruleset_version": value.get("version"),
                "combination_count": len(combinations),
                "enabled_combination_count": len(enabled),
                "fallback_policy": value.get("fallback_policy"),
            }
        if key.endswith("achievement.rules"):
            achievements = [
                item for item in value.get("achievements", []) if isinstance(item, dict)
            ]
            return {
                "enabled": value.get("enabled") is not False,
                "ruleset_version": value.get("version"),
                "achievement_count": len(achievements),
                "enabled_achievement_count": sum(
                    1 for item in achievements if item.get("enabled", True) is not False
                ),
                "condition_types": sorted(
                    {
                        str((item.get("condition") or {}).get("type"))
                        for item in achievements
                        if isinstance(item.get("condition"), dict)
                    }
                ),
            }
        if key.endswith("ai_coach.rules"):
            dimensions = [
                item for item in value.get("dimensions", []) if isinstance(item, dict)
            ]
            return {
                "enabled": value.get("enabled") is not False,
                "ruleset_version": value.get("version"),
                "dimension_count": len(dimensions),
                "weak_score_threshold": value.get("weak_score_threshold"),
                "notification_template_configured": isinstance(
                    value.get("notification_template"),
                    dict,
                ),
            }
        if key.endswith("sales.training.combinations.ruleset"):
            combinations = [
                item for item in value.get("combinations", []) if isinstance(item, dict)
            ]
            enabled_count = sum(
                1 for item in combinations if item.get("enabled", True) is not False
            )
            return {
                "enabled": value.get("enabled") is not False,
                "ruleset_version": value.get("version"),
                "combination_count": len(combinations),
                "enabled_combination_count": enabled_count,
                "fallback_policy": value.get("fallback_policy"),
            }
        if key == OBJECTION_LEDGER_RULES_KEY:
            families = value.get("families")
            family_count = len(families) if isinstance(families, dict) else 0
            return {
                "enabled": value.get("enabled") is not False,
                "ruleset_version": value.get("version"),
                "family_count": family_count,
                "ack_pattern_count": len(value.get("ack_patterns") or []),
                "admin_entry": get_business_rule_definition(key).admin_entry,
                "fallback_policy": get_business_rule_definition(key).fallback_policy,
            }
        if key == ADMIN_SETTINGS_GENERAL_KEY:
            return {
                "enabled": value.get("enabled") is not False,
                "settings_version": value.get("version"),
                "platform_name": value.get("platform_name"),
                "support_email": value.get("support_email"),
                "timezone": value.get("timezone"),
                "date_format": value.get("date_format"),
            }
        if key == ADMIN_SETTINGS_SECURITY_KEY:
            return {
                "enabled": value.get("enabled") is not False,
                "settings_version": value.get("version"),
                "enforce_admin_2fa": bool(value.get("enforce_admin_2fa")),
                "new_device_login_alert": bool(value.get("new_device_login_alert")),
                "password_min_length": value.get("password_min_length"),
                "password_expiry_days": value.get("password_expiry_days"),
            }
        if key == ADMIN_SETTINGS_NOTIFICATIONS_KEY:
            notifications = value.get("email_notifications")
            notification_count = len(notifications) if isinstance(notifications, dict) else 0
            enabled_count = (
                sum(1 for enabled in notifications.values() if enabled)
                if isinstance(notifications, dict)
                else 0
            )
            return {
                "enabled": value.get("enabled") is not False,
                "settings_version": value.get("version"),
                "email_notification_count": notification_count,
                "enabled_email_notification_count": enabled_count,
            }
        raw_recommendation_dimensions = value.get("dimensions")
        recommendation_dimensions: dict[str, Any] = (
            raw_recommendation_dimensions
            if isinstance(raw_recommendation_dimensions, dict)
            else {}
        )
        return {
            "enabled": value.get("enabled") is not False,
            "ruleset_version": value.get("version"),
            "dimension_count": len(recommendation_dimensions),
            "weak_score_threshold": value.get("weak_score_threshold"),
            "fallback_title": (value.get("fallback") or {}).get("title")
            if isinstance(value.get("fallback"), dict)
            else None,
        }
