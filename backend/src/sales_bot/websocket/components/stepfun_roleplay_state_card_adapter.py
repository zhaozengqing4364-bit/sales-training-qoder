from __future__ import annotations

from copy import deepcopy
from typing import Any

from sales_bot.services.roleplay_state_card import (
    RoleplayPhase,
    RoleplayStateCard,
    RoleplayStateCardUpdate,
    default_roleplay_state_card,
    serialize_state_card,
)

_V1_PHASE_TO_CARD_PHASE = {
    "opening_intent": RoleplayPhase.OPENING,
    "current_state_discovery": RoleplayPhase.DISCOVERY,
    "solution_credibility": RoleplayPhase.CREDIBILITY,
    "next_step_advancement": RoleplayPhase.NEXT_STEP,
}
_CARD_PHASE_TO_V1_PHASE = {
    RoleplayPhase.OPENING: "opening_intent",
    RoleplayPhase.DISCOVERY: "current_state_discovery",
    RoleplayPhase.CREDIBILITY: "solution_credibility",
    RoleplayPhase.NEXT_STEP: "next_step_advancement",
}


def normalize_state_card_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return state_card_payload_from_state(
        state_card_from_payload(value),
        base_payload=value,
    )


def state_card_from_payload(value: Any) -> RoleplayStateCard:
    default_state = default_roleplay_state_card()
    if not isinstance(value, dict):
        return default_state
    return RoleplayStateCard(
        state_card_version=_as_int(
            value.get("version", value.get("state_card_version"))
        ),
        update_sequence=_as_int(value.get("sequence", value.get("update_sequence"))),
        current_phase=parse_state_card_phase(
            value.get("current_phase_id", value.get("current_phase"))
        ),
        customer_attitude=str(value.get("customer_attitude") or "").strip()
        or default_state.customer_attitude,
        learner_actions=tuple(_as_string_list(value.get("learner_actions_done")))
        or tuple(_as_string_list(value.get("learner_actions"))),
        objections=tuple(_as_string_list(value.get("objections_raised")))
        or tuple(_as_string_list(value.get("objections"))),
        quality_flags=tuple(_as_string_list(value.get("quality_flags"))),
    )


def state_card_update_from_payload(value: dict[str, Any]) -> RoleplayStateCardUpdate:
    return RoleplayStateCardUpdate(
        state_card_version=_as_int(
            value.get("version", value.get("state_card_version"))
        ),
        update_sequence=_as_int(value.get("sequence", value.get("update_sequence"))),
        current_phase=state_card_update_phase(
            value.get("current_phase_id", value.get("current_phase"))
        ),
        customer_attitude=_optional_str(value.get("customer_attitude")),
        learner_actions=_optional_tuple(
            value.get("learner_actions_done", value.get("learner_actions"))
        ),
        objections=_optional_tuple(
            value.get("objections_raised", value.get("objections"))
        ),
        quality_flags=_optional_tuple(value.get("quality_flags")),
    )


def state_card_payload_from_state(
    state: RoleplayStateCard,
    *,
    base_payload: dict[str, Any],
) -> dict[str, Any]:
    serialized = serialize_state_card(state)
    payload = deepcopy(base_payload)
    payload.setdefault("schema_version", "session_state_card_v1")
    payload["version"] = serialized["state_card_version"]
    payload["sequence"] = state.update_sequence
    payload["current_phase_id"] = _CARD_PHASE_TO_V1_PHASE[state.current_phase]
    payload["current_phase_type"] = "roleplay_phase"
    payload["customer_attitude"] = serialized["customer_attitude"]
    payload["learner_actions_done"] = serialized["learner_actions"]
    payload["objections_raised"] = serialized["objections"]
    payload["quality_flags"] = serialized["quality_flags"]
    return payload


def parse_state_card_phase(value: Any) -> RoleplayPhase:
    if isinstance(value, RoleplayPhase):
        return value
    normalized = str(value or "").strip()
    if normalized in _V1_PHASE_TO_CARD_PHASE:
        return _V1_PHASE_TO_CARD_PHASE[normalized]
    try:
        return RoleplayPhase(normalized)
    except ValueError:
        return default_roleplay_state_card().current_phase


def state_card_update_phase(value: Any) -> RoleplayPhase | str | None:
    if value is None or isinstance(value, RoleplayPhase):
        return value
    normalized = str(value or "").strip()
    return _V1_PHASE_TO_CARD_PHASE.get(normalized, normalized or None)


def state_card_version(state_card: dict[str, Any] | None) -> int:
    if not state_card:
        return 0
    return _as_int(state_card.get("version", state_card.get("state_card_version")))


def _optional_tuple(value: Any) -> tuple[str, ...] | None:
    return None if value is None else tuple(_as_string_list(value))


def _optional_str(value: Any) -> str | None:
    return str(value).strip() if value is not None else None


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
