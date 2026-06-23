from __future__ import annotations

from copy import deepcopy
from typing import Any

from common.roleplay_contracts import ROLEPLAY_COMPLIANCE_METRICS_KEY
from sales_bot.services.roleplay_state_card import (
    RoleplayStateCardUpdateResult,
    StateCardUpdateStatus,
    apply_state_card_update,
    default_roleplay_state_card,
)
from sales_bot.websocket.components.stepfun_knowledge_helpers import (
    merge_runtime_metrics_snapshot,
)
from sales_bot.websocket.components.stepfun_roleplay_state_card_adapter import (
    normalize_state_card_payload,
    state_card_from_payload,
    state_card_payload_from_state,
    state_card_update_from_payload,
    state_card_version,
)

V1_ROLEPLAY_RUNTIME_METRICS_KEY = "it_leader_roleplay_v1"
V1_ROLEPLAY_RUNTIME_STATE_KEY = "it_leader_roleplay_v1"
_V1_CONTRACT_VERSION = "it_leader_roleplay_v1"
_KNOWLEDGE_DEGRADATION_FLAG = "knowledge_gap_degradation"
_KNOWLEDGE_DEGRADATION_STATUSES = {
    "miss",
    "search_failed",
    "kb_not_ready",
    "blocked_search_timeout",
}


def record_v1_knowledge_degradation(
    effective_policy: dict[str, Any],
    *,
    status: str,
    error_message: str | None,
) -> None:
    if not _is_v1_roleplay_policy(effective_policy):
        return
    normalized_status = str(status or "").strip()
    if normalized_status not in _KNOWLEDGE_DEGRADATION_STATUSES and not error_message:
        return
    runtime_metrics = _runtime_metrics(effective_policy)
    observability = _as_dict(runtime_metrics.get(V1_ROLEPLAY_RUNTIME_METRICS_KEY))
    observability["knowledge_timeout_count"] = (
        _as_int(observability.get("knowledge_timeout_count")) + 1
    )
    observability["quality_flags"] = _merge_quality_flags(
        _as_string_list(observability.get("quality_flags")),
        [_KNOWLEDGE_DEGRADATION_FLAG],
    )
    runtime_metrics[V1_ROLEPLAY_RUNTIME_METRICS_KEY] = observability


def sync_roleplay_runtime_observability(
    effective_policy: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_v1_roleplay_policy(effective_policy):
        return None
    runtime_metrics = _runtime_metrics(effective_policy)
    roleplay_metrics = _as_dict(runtime_metrics.get(ROLEPLAY_COMPLIANCE_METRICS_KEY))
    previous = _as_dict(runtime_metrics.get(V1_ROLEPLAY_RUNTIME_METRICS_KEY))
    state_card = normalize_state_card_payload(effective_policy.get("session_state_card"))
    if state_card is not None:
        effective_policy["session_state_card"] = state_card

    blocking_count = _as_int(roleplay_metrics.get("blocking_violation_count"))
    quality_flags = _merge_quality_flags(
        _as_string_list(previous.get("quality_flags")),
        _as_string_list(state_card.get("quality_flags") if state_card else None),
        [f"blocking_violation_count:{blocking_count}"] if blocking_count > 0 else [],
        [_KNOWLEDGE_DEGRADATION_FLAG]
        if _as_int(previous.get("knowledge_timeout_count")) > 0
        else [],
    )
    manual_review_reasons = (
        ["blocking_roleplay_violation"] if blocking_count > 0 else []
    )
    observability = {
        "roleplay_contract_hash": _roleplay_contract_hash(effective_policy),
        "state_card_version": state_card_version(state_card),
        "violation_count": _as_int(roleplay_metrics.get("violation_count")),
        "blocking_violation_count": blocking_count,
        "knowledge_timeout_count": _as_int(previous.get("knowledge_timeout_count")),
        "quality_flags": quality_flags,
        "manual_review_required": bool(manual_review_reasons),
        "manual_review_reasons": manual_review_reasons,
    }
    runtime_metrics[V1_ROLEPLAY_RUNTIME_METRICS_KEY] = observability
    return observability


def build_roleplay_runtime_state_patch(
    effective_policy: dict[str, Any],
) -> dict[str, Any] | None:
    observability = sync_roleplay_runtime_observability(effective_policy)
    if observability is None:
        return None
    state_card = normalize_state_card_payload(effective_policy.get("session_state_card"))
    return {
        V1_ROLEPLAY_RUNTIME_STATE_KEY: {
            "roleplay_contract_hash": observability["roleplay_contract_hash"],
            "session_state_card": deepcopy(state_card) if state_card else None,
            "runtime_observability": deepcopy(observability),
        }
    }


def restore_roleplay_runtime_state(
    effective_policy: dict[str, Any],
    runtime_state: dict[str, Any],
) -> dict[str, Any] | None:
    if not _is_v1_roleplay_policy(effective_policy):
        return None
    roleplay_state = _as_dict(runtime_state.get(V1_ROLEPLAY_RUNTIME_STATE_KEY))
    state_card = _as_dict(roleplay_state.get("session_state_card"))
    if state_card:
        apply_roleplay_state_card_update_to_policy(effective_policy, state_card)
    persisted = _as_dict(roleplay_state.get("runtime_observability"))
    if persisted:
        _runtime_metrics(effective_policy)[V1_ROLEPLAY_RUNTIME_METRICS_KEY] = deepcopy(
            persisted
        )
    return sync_roleplay_runtime_observability(effective_policy)


def apply_roleplay_state_card_update_to_policy(
    effective_policy: dict[str, Any],
    update_payload: dict[str, Any],
) -> RoleplayStateCardUpdateResult:
    if not _is_v1_roleplay_policy(effective_policy):
        return RoleplayStateCardUpdateResult(
            status=StateCardUpdateStatus.INVALID,
            state=default_roleplay_state_card(),
            reason_code="v1_disabled",
        )
    current = state_card_from_payload(effective_policy.get("session_state_card"))
    result = apply_state_card_update(
        current,
        state_card_update_from_payload(update_payload),
    )
    if result.status is StateCardUpdateStatus.ACCEPTED:
        existing = _as_dict(effective_policy.get("session_state_card"))
        effective_policy["session_state_card"] = state_card_payload_from_state(
            result.state,
            base_payload=existing,
        )
        sync_roleplay_runtime_observability(effective_policy)
    return result


def merge_runtime_metrics_snapshot_with_roleplay(
    *,
    base_snapshot: dict[str, Any],
    runtime_metrics: dict[str, Any],
    effective_policy: dict[str, Any],
) -> dict[str, Any] | None:
    knowledge_metrics = runtime_metrics.get("knowledge_retrieval")
    snapshot: dict[str, Any] | None = None
    if isinstance(knowledge_metrics, dict):
        snapshot = merge_runtime_metrics_snapshot(
            base_snapshot=base_snapshot,
            runtime_metrics=runtime_metrics,
        )
        if snapshot is None:
            return None
    if snapshot is None:
        snapshot = deepcopy(base_snapshot)

    snapshot_runtime = _as_dict(snapshot.get("runtime_metrics"))
    changed = isinstance(knowledge_metrics, dict)
    observability = runtime_metrics.get(V1_ROLEPLAY_RUNTIME_METRICS_KEY)
    if isinstance(observability, dict):
        snapshot_runtime[V1_ROLEPLAY_RUNTIME_METRICS_KEY] = deepcopy(observability)
        snapshot["runtime_metrics"] = snapshot_runtime
        state_card = normalize_state_card_payload(
            effective_policy.get("session_state_card")
        )
        if state_card is not None:
            snapshot["session_state_card"] = state_card
        contract_hash = _roleplay_contract_hash(effective_policy)
        if contract_hash:
            snapshot["roleplay_contract_hash"] = contract_hash
        changed = True
    return snapshot if changed else None


def _runtime_metrics(policy: dict[str, Any]) -> dict[str, Any]:
    runtime_metrics = policy.get("runtime_metrics")
    if not isinstance(runtime_metrics, dict):
        runtime_metrics = {}
        policy["runtime_metrics"] = runtime_metrics
    return runtime_metrics


def _is_v1_roleplay_policy(policy: dict[str, Any]) -> bool:
    if str(policy.get("roleplay_contract_hash") or "").strip():
        contract = _as_dict(policy.get("roleplay_contract"))
        return not contract or contract.get("contract_version") == _V1_CONTRACT_VERSION
    return _as_dict(policy.get("roleplay_contract")).get(
        "contract_version"
    ) == _V1_CONTRACT_VERSION


def _roleplay_contract_hash(policy: dict[str, Any]) -> str:
    direct_hash = str(policy.get("roleplay_contract_hash") or "").strip()
    if direct_hash:
        return direct_hash
    audit = _as_dict(_as_dict(policy.get("roleplay_contract")).get("audit"))
    return str(audit.get("contract_hash") or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _merge_quality_flags(*flag_groups: list[str]) -> list[str]:
    flags: list[str] = []
    for group in flag_groups:
        flags.extend(flag for flag in group if flag and flag not in flags)
    return flags
