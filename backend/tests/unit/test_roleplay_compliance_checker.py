from __future__ import annotations

from curriculum_practice.services.roleplay_contracts import RoleplayContractCompiler
from sales_bot.services.roleplay_compliance_checker import (
    check_realtime_roleplay_output,
)


def _first_visit_contract() -> dict[str, object]:
    return RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "relationship_context": {
                        "prior_interactions": "none",
                        "has_prior_meeting": False,
                    },
                    "visible_information_keys": ["industry", "company_profile"],
                    "hidden_information_keys": ["hidden_information"],
                }
            },
        },
        actor_id="actor-1",
        compiled_at="2026-05-26T00:00:00Z",
    )


def test_should_block_first_visit_history_contradiction() -> None:
    decision = check_realtime_roleplay_output(
        roleplay_contract=_first_visit_contract(),
        text="上次拜访的时候你已经说过预算了。",
    )

    assert decision["allowed"] is False
    assert decision["severity"] == "blocking"
    assert decision["violation_code"] == "ROLEPLAY_HISTORY_CONTRADICTION"
    assert decision["action"] == "regenerate_once"


def test_should_mark_legacy_contract_for_report() -> None:
    contract = RoleplayContractCompiler().legacy_contract(
        source_track="direct_practice",
        actor_id="actor-1",
    )

    decision = check_realtime_roleplay_output(
        roleplay_contract=contract,
        text="正常输出",
    )

    assert decision["allowed"] is True
    assert decision["severity"] == "warning"
    assert decision["violation_code"] == "ROLEPLAY_CONTRACT_LEGACY"


def test_should_allow_follow_up_history_reference() -> None:
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "follow_up",
                    "relationship_context": {
                        "prior_interactions": "one_meeting",
                        "has_prior_meeting": True,
                        "meeting_history_summary": "上次沟通确认了质检效率问题。",
                    },
                }
            },
        },
        actor_id="actor-1",
    )

    decision = check_realtime_roleplay_output(
        roleplay_contract=contract,
        text="上次沟通你们确实提到过质检效率。",
    )

    assert decision["allowed"] is True
    assert decision["severity"] == "none"
