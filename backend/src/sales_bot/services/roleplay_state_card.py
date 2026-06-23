from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum, unique
from typing import Final, TypedDict, assert_never


@unique
class RoleplayPhase(StrEnum):
    OPENING = "opening"
    DISCOVERY = "discovery"
    CREDIBILITY = "credibility"
    NEXT_STEP = "next_step"


@unique
class StateCardUpdateStatus(StrEnum):
    ACCEPTED = "accepted"
    STALE = "stale"
    INVALID = "invalid"


class StateCardPayload(TypedDict):
    state_card_version: int
    current_phase: str
    customer_attitude: str
    learner_actions: list[str]
    objections: list[str]
    quality_flags: list[str]


DEFAULT_CUSTOMER_ATTITUDE: Final = "谨慎但愿意继续听"


@dataclass(frozen=True, slots=True)
class RoleplayStateCard:
    state_card_version: int
    update_sequence: int
    current_phase: RoleplayPhase
    customer_attitude: str
    learner_actions: tuple[str, ...]
    objections: tuple[str, ...]
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoleplayStateCardUpdate:
    state_card_version: int
    update_sequence: int
    current_phase: RoleplayPhase | str | None = None
    customer_attitude: str | None = None
    learner_actions: tuple[str, ...] | None = None
    objections: tuple[str, ...] | None = None
    quality_flags: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class RoleplayStateCardUpdateResult:
    status: StateCardUpdateStatus
    state: RoleplayStateCard
    reason_code: str | None = None


def default_roleplay_state_card() -> RoleplayStateCard:
    return RoleplayStateCard(
        state_card_version=0,
        update_sequence=0,
        current_phase=RoleplayPhase.OPENING,
        customer_attitude=DEFAULT_CUSTOMER_ATTITUDE,
        learner_actions=(),
        objections=(),
        quality_flags=(),
    )


def apply_state_card_update(
    state: RoleplayStateCard,
    update: RoleplayStateCardUpdate,
) -> RoleplayStateCardUpdateResult:
    if _is_stale_update(state, update):
        return RoleplayStateCardUpdateResult(
            status=StateCardUpdateStatus.STALE,
            state=state,
            reason_code="stale_update",
        )

    invalid_reason = _invalid_update_reason(update)
    if invalid_reason is not None:
        return RoleplayStateCardUpdateResult(
            status=StateCardUpdateStatus.INVALID,
            state=state,
            reason_code=invalid_reason,
        )

    next_phase = _parse_phase(update.current_phase) or state.current_phase
    next_state = replace(
        state,
        state_card_version=update.state_card_version,
        update_sequence=update.update_sequence,
        current_phase=next_phase,
        customer_attitude=update.customer_attitude or state.customer_attitude,
        learner_actions=(
            state.learner_actions
            if update.learner_actions is None
            else update.learner_actions
        ),
        objections=state.objections if update.objections is None else update.objections,
        quality_flags=(
            state.quality_flags if update.quality_flags is None else update.quality_flags
        ),
    )
    return RoleplayStateCardUpdateResult(
        status=StateCardUpdateStatus.ACCEPTED,
        state=next_state,
    )


def serialize_state_card(state: RoleplayStateCard) -> StateCardPayload:
    return {
        "state_card_version": state.state_card_version,
        "current_phase": state.current_phase.value,
        "customer_attitude": state.customer_attitude,
        "learner_actions": list(state.learner_actions),
        "objections": list(state.objections),
        "quality_flags": list(state.quality_flags),
    }


def _is_stale_update(
    state: RoleplayStateCard,
    update: RoleplayStateCardUpdate,
) -> bool:
    return (
        update.state_card_version <= state.state_card_version
        or update.update_sequence <= state.update_sequence
    )


def _invalid_update_reason(update: RoleplayStateCardUpdate) -> str | None:
    if update.current_phase is not None and _parse_phase(update.current_phase) is None:
        return "unsupported_phase"
    if update.customer_attitude is not None and not update.customer_attitude.strip():
        return "blank_customer_attitude"
    if update.learner_actions is not None and _has_blank_item(update.learner_actions):
        return "blank_learner_action"
    if update.objections is not None and _has_blank_item(update.objections):
        return "blank_objection"
    if update.quality_flags is not None and _has_blank_item(update.quality_flags):
        return "blank_quality_flag"
    return None


def _parse_phase(raw_phase: RoleplayPhase | str | None) -> RoleplayPhase | None:
    if raw_phase is None:
        return None
    if isinstance(raw_phase, RoleplayPhase):
        return raw_phase
    if isinstance(raw_phase, str):
        try:
            return RoleplayPhase(raw_phase)
        except ValueError:
            return None
    assert_never(raw_phase)


def _has_blank_item(items: tuple[str, ...]) -> bool:
    return any(not item.strip() for item in items)
