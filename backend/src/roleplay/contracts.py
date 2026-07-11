"""Stable Roleplay Contract schema, hash and compliance decisions."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from typing import Any

ROLEPLAY_CONTRACT_SCHEMA_VERSION = "roleplay_contract_v1"
ROLEPLAY_CONTRACT_COMPILER_VERSION = "roleplay_contract_compiler_v1"
ROLEPLAY_STAGE_AUTHORITY = "SalesStageCapability"
LEGACY_ROLEPLAY_STATUS = "legacy_unstructured_roleplay"

BLOCKING_VIOLATION_ACTIONS = {
    "cancel_or_regenerate_once",
    "regenerate_once",
    "cancel_stream",
    "hard_fail",
}

ROLEPLAY_DISCLOSURE_STATE_KEY = "roleplay_disclosure_state"
ROLEPLAY_COMPLIANCE_METRICS_KEY = "roleplay_compliance"
_VOLATILE_HASH_FIELDS = {
    "actor_id",
    "created_at",
    "compiled_at",
    "compiled_by",
    "published_at",
    "snapshot_hash",
    "trace_id",
    "updated_at",
}


@dataclass(frozen=True, slots=True)
class RoleplayComplianceDecision:
    """Immutable internal decision with the historical dict projection."""

    allowed: bool
    severity: str = "none"
    violation_code: str | None = None
    matched_pattern: str | None = None
    action: str = "allow"
    audit_payload: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "severity": self.severity,
            "violation_code": self.violation_code,
            "matched_pattern": self.matched_pattern,
            "action": self.action,
            "audit_payload": dict(self.audit_payload or {}),
        }


def roleplay_contract_hash(payload: object) -> str:
    return (
        "sha256:"
        + sha256(
            dumps(
                _without_volatile_fields(payload),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    )


def roleplay_audit_hash(contract: dict[str, Any]) -> str | None:
    audit = contract.get("audit")
    if isinstance(audit, dict) and audit.get("contract_hash"):
        return str(audit["contract_hash"])
    contract_id = contract.get("contract_id")
    return str(contract_id) if contract_id else None


def check_roleplay_output(
    *,
    contract: dict[str, Any],
    text: str,
    runtime_state: dict[str, Any] | None = None,
    current_visible_keys: list[str] | None = None,
    current_sales_stage: str | None = None,
) -> dict[str, Any]:
    normalized = str(text or "").strip()
    if not normalized:
        return _compliance_decision(allowed=True)
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != ROLEPLAY_CONTRACT_SCHEMA_VERSION
    ):
        return _compliance_decision(
            allowed=True,
            severity="warning",
            violation_code="ROLEPLAY_CONTRACT_MISSING",
            action="mark_for_report",
            audit_payload={"reason": "missing_or_invalid_contract"},
        )
    if contract.get("legacy_status") == LEGACY_ROLEPLAY_STATUS:
        return _compliance_decision(
            allowed=True,
            severity="warning",
            violation_code="ROLEPLAY_CONTRACT_LEGACY",
            action="mark_for_report",
            audit_payload={"contract_hash": roleplay_audit_hash(contract)},
        )

    runtime_state = runtime_state if isinstance(runtime_state, dict) else {}
    relationship_context = _as_dict(contract.get("relationship_context"))
    visible_keys = set(
        current_visible_keys or _as_string_list(runtime_state.get("visible_keys"))
    )
    if not visible_keys:
        scope = _as_dict(contract.get("visible_information_scope"))
        visible_keys = set(_as_string_list(scope.get("initial_visible_keys")))
    hidden_keys = set(
        _as_string_list(
            _as_dict(contract.get("visible_information_scope")).get(
                "hidden_by_default_keys"
            )
        )
    )

    for pattern in _as_string_list(contract.get("forbidden_claim_patterns")):
        if pattern and pattern in normalized:
            violation_code = (
                "ROLEPLAY_HISTORY_CONTRADICTION"
                if relationship_context.get("has_prior_meeting") is False
                else "ROLEPLAY_FORBIDDEN_CLAIM"
            )
            return _blocking_decision(
                contract,
                violation_code=violation_code,
                matched_pattern=pattern,
                policy_key="relationship_history_contradiction",
            )

    hidden_patterns = _as_string_list(
        _as_dict(contract.get("disclosure_policy")).get("never_disclose_keys")
    )
    for hidden_key in hidden_keys:
        if hidden_key not in visible_keys and hidden_key and hidden_key in normalized:
            return _blocking_decision(
                contract,
                violation_code="ROLEPLAY_HIDDEN_INFORMATION_LEAK",
                matched_pattern=hidden_key,
                policy_key="hidden_information_leak",
            )
    for hidden_pattern in hidden_patterns:
        if hidden_pattern and hidden_pattern in normalized:
            return _blocking_decision(
                contract,
                violation_code="ROLEPLAY_HIDDEN_INFORMATION_LEAK",
                matched_pattern=hidden_pattern,
                policy_key="hidden_information_leak",
            )

    sales_stage = current_sales_stage or str(
        runtime_state.get("current_sales_stage") or ""
    )
    forbidden_stages = set(
        _as_string_list(
            _as_dict(contract.get("sales_stage_policy")).get("forbidden_stage_codes")
        )
    )
    if sales_stage and sales_stage in forbidden_stages:
        return _blocking_decision(
            contract,
            violation_code="ROLEPLAY_FORBIDDEN_STAGE",
            matched_pattern=sales_stage,
            policy_key="forbidden_topic",
        )

    return _compliance_decision(
        allowed=True,
        audit_payload={"contract_hash": roleplay_audit_hash(contract)},
    )


def _without_volatile_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_volatile_fields(value)
            for key, value in payload.items()
            if key not in _VOLATILE_HASH_FIELDS
        }
    if isinstance(payload, list):
        return [_without_volatile_fields(item) for item in payload]
    return payload


def _compliance_decision(
    *,
    allowed: bool,
    severity: str = "none",
    violation_code: str | None = None,
    matched_pattern: str | None = None,
    action: str = "allow",
    audit_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return RoleplayComplianceDecision(
        allowed=allowed,
        severity=severity,
        violation_code=violation_code,
        matched_pattern=matched_pattern,
        action=action,
        audit_payload=audit_payload,
    ).as_dict()


def _blocking_decision(
    contract: dict[str, Any],
    *,
    violation_code: str,
    matched_pattern: str,
    policy_key: str,
) -> dict[str, Any]:
    policy = _as_dict(contract.get("runtime_violation_policy"))
    configured_action = str(policy.get(policy_key) or "mark_for_report")
    action = "mark_for_report"
    severity = "warning"
    allowed = True
    if configured_action in BLOCKING_VIOLATION_ACTIONS:
        action = (
            "regenerate_once" if "regenerate" in configured_action else "cancel_stream"
        )
        severity = "blocking"
        allowed = False
    elif configured_action == "mark_and_continue":
        action = "mark_for_report"
        severity = "warning"
    return _compliance_decision(
        allowed=allowed,
        severity=severity,
        violation_code=violation_code,
        matched_pattern=matched_pattern,
        action=action,
        audit_payload={
            "contract_hash": roleplay_audit_hash(contract),
            "policy_key": policy_key,
            "configured_action": configured_action,
        },
    )


def _as_dict(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    instance_dict = getattr(value, "__dict__", None)
    if isinstance(instance_dict, dict):
        return {
            key: item for key, item in instance_dict.items() if not key.startswith("_")
        }
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
