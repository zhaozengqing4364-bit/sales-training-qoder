"""Async service for governed business-rule CRUD and active resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
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
        draft.value_json = normalized
        draft.default_value_json = deepcopy(definition.default_value)
        draft.schema_version = definition.schema_version
        draft.enabled = normalized.get("enabled") is not False
        draft.validation_errors_json = []
        draft.updated_by = actor_id
        draft.updated_at = datetime.now(UTC)
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
            "active_version": active.version if active is not None else None,
            "active_config_id": str(active.id) if active is not None else None,
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
        normalized = validate_business_rule_value(key, dict(draft.value_json or {}))
        current_active = await self._active_config_for_key(key)
        before_snapshot = self.snapshot(current_active) if current_active else None

        active_rows = await self._active_configs_for_key(key)
        for row in active_rows:
            if row.id != draft.id:
                row.status = "archived"
                row.enabled = False
                row.updated_by = actor_id
                row.updated_at = datetime.now(UTC)

        draft.value_json = normalized
        draft.status = (
            "published" if normalized.get("enabled") is not False else "disabled"
        )
        draft.enabled = normalized.get("enabled") is not False
        draft.validation_errors_json = []
        draft.updated_by = actor_id
        draft.updated_at = datetime.now(UTC)
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
        normalized = validate_business_rule_value(key, dict(target.value_json or {}))
        current_active = await self._active_config_for_key(key)
        if current_active is not None and current_active.id == target.id:
            raise ValueError("[BUSINESS_RULE_ROLLBACK_TARGET_ALREADY_ACTIVE]")
        before_snapshot = self.snapshot(current_active) if current_active else None

        active_rows = await self._active_configs_for_key(key)
        for row in active_rows:
            if row.id != target.id:
                row.status = "archived"
                row.enabled = False
                row.updated_by = actor_id
                row.updated_at = datetime.now(UTC)

        target.value_json = normalized
        target.status = (
            "published" if normalized.get("enabled") is not False else "disabled"
        )
        target.enabled = normalized.get("enabled") is not False
        target.validation_errors_json = []
        target.updated_by = actor_id
        target.updated_at = datetime.now(UTC)
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
        value = dict(active.value_json or {})
        value["enabled"] = False
        active.value_json = validate_business_rule_value(key, value)
        active.status = "disabled"
        active.enabled = False
        active.updated_by = actor_id
        active.updated_at = datetime.now(UTC)
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
        if row is None or row.status != "draft":
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
                value = validate_business_rule_value(key, dict(active.value_json or {}))
                source = (
                    "database_disabled" if value.get("enabled") is False else "database"
                )
                return BusinessRuleResolution(
                    key=key,
                    domain=definition.domain,
                    value=value,
                    source=source,
                    config_id=str(active.id),
                    version=int(active.version),
                    status=str(active.status),
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
                    config_id=str(active.id),
                    version=active.version,
                    error=str(exc),
                )
                previous = await self._latest_valid_history_before(
                    key=key,
                    before_version=active.version,
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
        return {
            "id": str(row.id),
            "domain": row.domain,
            "key": row.key,
            "schema_version": row.schema_version,
            "status": row.status,
            "version": row.version,
            "enabled": bool(row.enabled),
            "value": deepcopy(row.value_json),
            "default_value": deepcopy(row.default_value_json),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def audit_snapshot(row: BusinessRuleConfigAuditLog) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "config_id": str(row.config_id) if row.config_id else None,
            "domain": row.domain,
            "config_key": row.config_key,
            "action": row.action,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "before_version": row.before_version,
            "after_version": row.after_version,
            "before_snapshot": deepcopy(row.before_snapshot_json),
            "after_snapshot": deepcopy(row.after_snapshot_json),
            "reason": row.reason,
            "trace_id": row.trace_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
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
            if row is None or row.key != key or row.status != "draft":
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
            if row is None or row.key != key or row.status not in _HISTORY_STATUSES:
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
            statement = statement.where(BusinessRuleConfig.version < active.version)
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
                value = validate_business_rule_value(key, dict(row.value_json or {}))
            except (BusinessRuleValidationError, KeyError, TypeError, ValueError):
                continue
            return BusinessRuleResolution(
                key=key,
                domain=definition.domain,
                value=value,
                source="database_previous",
                config_id=str(row.id),
                version=int(row.version),
                status=str(row.status),
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
        resolved_key = config.key if config is not None else config_key
        if resolved_key is None:
            raise ValueError("config key is required for audit")
        resolved_domain = config.domain if config is not None else domain
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
                config_id=str(config.id) if config is not None else None,
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
        if key.endswith("sales.training.combinations.ruleset") or key.startswith(
            "sales."
        ):
            combinations = [
                item for item in value.get("combinations", []) if isinstance(item, dict)
            ]
            return {
                "enabled": value.get("enabled") is not False,
                "ruleset_version": value.get("version"),
                "rule_set_id": value.get("rule_set_id"),
                "combination_count": len(combinations),
                "enabled_combination_count": sum(
                    1 for item in combinations if item.get("enabled", True) is not False
                ),
                "fallback_policy": value.get("fallback_policy"),
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
