from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
    get_default_business_rule_value,
)
from common.business_rules.service import BusinessRuleConfigService
from common.business_rules.validators import validate_business_rule_value


@dataclass(frozen=True, slots=True)
class SalesTrainerPhase2Policy:
    low_score_threshold: float
    repeat_practice_threshold: int
    dashboard_record_limit: int
    manager_actions: dict[str, dict[str, str]]
    remediation_actions: dict[str, dict[str, str]]

    def manager_action(self, reason_codes: set[str]) -> dict[str, str]:
        for code in ("not_passed", "low_score", "repeated_practice"):
            if code in reason_codes:
                return self.manager_actions[code]
        return self.manager_actions["fallback"]

    def remediation_action(self, record_type: str, *, needed: bool) -> dict[str, str]:
        if not needed:
            return self.remediation_actions["no_action"]
        return (
            self.remediation_actions.get(record_type)
            or self.remediation_actions["default"]
        )


async def resolve_phase2_policy(
    db: AsyncSession | None = None,
) -> tuple[SalesTrainerPhase2Policy, dict[str, Any]]:
    if db is None:
        value = _default_value()
        return _policy_from_value(value), _payload_from_value(
            value,
            source="default",
            fallback_applied=True,
            fallback_reason="db_not_provided",
        )

    resolution = await BusinessRuleConfigService(db).resolve_active_config(
        SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
    )
    value = deepcopy(resolution.value)
    source = resolution.source
    fallback_reason = resolution.fallback_reason
    fallback_applied = source != "database"
    if source == "database_disabled" or value.get("enabled") is False:
        value = _default_value()
        source = "default"
        fallback_applied = True
        fallback_reason = "active_disabled"

    return _policy_from_value(value), _payload_from_value(
        value,
        source=source,
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
        config_id=resolution.config_id,
        config_version=resolution.version,
        status=resolution.status,
    )


def _default_value() -> dict[str, Any]:
    return validate_business_rule_value(
        SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
        get_default_business_rule_value(SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY),
    )


def _policy_from_value(value: dict[str, Any]) -> SalesTrainerPhase2Policy:
    manager_actions = {
        str(item["code"]): {
            "code": str(item["code"]),
            "label": str(item["label"]),
            "priority": str(item["priority"]),
        }
        for item in value["manager_actions"]
    }
    remediation_actions = {
        str(item["record_type"]): {
            "record_type": str(item["record_type"]),
            "action_label": str(item["action_label"]),
            "reason_template": str(item["reason_template"]),
            "target_path_template": str(item["target_path_template"]),
            "priority": str(item["priority"]),
        }
        for item in value["remediation_actions"]
    }
    return SalesTrainerPhase2Policy(
        low_score_threshold=float(value["low_score_threshold"]),
        repeat_practice_threshold=int(value["repeat_practice_threshold"]),
        dashboard_record_limit=int(value["dashboard_record_limit"]),
        manager_actions=manager_actions,
        remediation_actions=remediation_actions,
    )


def _payload_from_value(
    value: dict[str, Any],
    *,
    source: str,
    fallback_applied: bool,
    fallback_reason: str | None,
    config_id: str | None = None,
    config_version: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "key": SALES_TRAINER_PHASE2_CLOSED_LOOP_POLICY_KEY,
        "version": value["version"],
        "enabled": value.get("enabled") is not False,
        "low_score_threshold": float(value["low_score_threshold"]),
        "repeat_practice_threshold": int(value["repeat_practice_threshold"]),
        "dashboard_record_limit": int(value["dashboard_record_limit"]),
        "source": source,
        "config_id": config_id,
        "config_version": config_version,
        "status": status,
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason,
        "management_entry": "/admin/business-rules/sales-trainer-phase2",
        "permission": "admin_publish_only",
        "effective_timing": "request_time",
    }
