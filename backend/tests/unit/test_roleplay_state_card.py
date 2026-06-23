from __future__ import annotations

from sales_bot.services.roleplay_state_card import (
    RoleplayPhase,
    RoleplayStateCardUpdate,
    StateCardUpdateStatus,
    apply_state_card_update,
    default_roleplay_state_card,
    serialize_state_card,
)


def test_should_serialize_default_state_card_when_created() -> None:
    state = default_roleplay_state_card()
    payload = serialize_state_card(state)

    assert payload == {
        "state_card_version": 0,
        "current_phase": "opening",
        "customer_attitude": "谨慎但愿意继续听",
        "learner_actions": [],
        "objections": [],
        "quality_flags": [],
    }


def test_should_apply_update_when_version_and_sequence_advance() -> None:
    state = default_roleplay_state_card()
    update = RoleplayStateCardUpdate(
        state_card_version=1,
        update_sequence=10,
        current_phase=RoleplayPhase.DISCOVERY,
        customer_attitude="谨慎，开始追问现状",
        learner_actions=("说明拜访目的", "询问现有系统边界"),
        objections=("担心和现有 API 网关重复",),
        quality_flags=("knowledge_timeout",),
    )

    result = apply_state_card_update(state, update)
    payload = serialize_state_card(result.state)

    assert result.status is StateCardUpdateStatus.ACCEPTED
    assert result.reason_code is None
    assert result.state.state_card_version == 1
    assert result.state.update_sequence == 10
    assert payload == {
        "state_card_version": 1,
        "current_phase": "discovery",
        "customer_attitude": "谨慎，开始追问现状",
        "learner_actions": ["说明拜访目的", "询问现有系统边界"],
        "objections": ["担心和现有 API 网关重复"],
        "quality_flags": ["knowledge_timeout"],
    }


def test_should_ignore_stale_update_when_sequence_does_not_advance() -> None:
    state = apply_state_card_update(
        default_roleplay_state_card(),
        RoleplayStateCardUpdate(
            state_card_version=1,
            update_sequence=10,
            current_phase=RoleplayPhase.DISCOVERY,
            customer_attitude="谨慎，开始追问现状",
        ),
    ).state
    stale_update = RoleplayStateCardUpdate(
        state_card_version=1,
        update_sequence=9,
        current_phase=RoleplayPhase.CREDIBILITY,
        customer_attitude="错误覆盖为认可",
    )

    result = apply_state_card_update(state, stale_update)

    assert result.status is StateCardUpdateStatus.STALE
    assert result.reason_code == "stale_update"
    assert result.state == state


def test_should_keep_previous_state_when_update_is_invalid() -> None:
    state = apply_state_card_update(
        default_roleplay_state_card(),
        RoleplayStateCardUpdate(
            state_card_version=1,
            update_sequence=10,
            current_phase=RoleplayPhase.DISCOVERY,
            customer_attitude="谨慎，开始追问现状",
        ),
    ).state
    invalid_update = RoleplayStateCardUpdate(
        state_card_version=2,
        update_sequence=11,
        current_phase="unsupported_phase",
        customer_attitude="不应覆盖",
    )

    result = apply_state_card_update(state, invalid_update)

    assert result.status is StateCardUpdateStatus.INVALID
    assert result.reason_code == "unsupported_phase"
    assert result.state == state
