from __future__ import annotations

import pytest

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.schemas import PracticeTemplatePublishCandidate
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.roleplay_contracts import (
    RoleplayContractCompileError,
    RoleplayContractCompiler,
    initial_roleplay_disclosure_state,
    resolve_roleplay_disclosure_state,
    roleplay_compliance_summary_from_session,
    roleplay_compliance_timeline_from_session,
    visible_case_payload,
)


def _references() -> dict[tuple[str, str], object]:
    return {
        ("practice_template", "template-1"): {
            "template_id": "template-1",
            "status": "published",
            "scenario_type": "sales",
            "mode": "customer_roleplay",
            "agent_id": "agent-1",
            "persona_id": "persona-1",
            "runtime_profile_id": "runtime-1",
            "voice_mode": "stepfun_realtime",
            "scoring_ruleset_id": "ruleset-1",
            "case_item_id": "case-1",
            "role_profile_id": "role-1",
        },
        ("persona", "persona-1"): {
            "id": "persona-1",
            "status": "active",
            "system_prompt": "首次拜访需求挖掘，不要进入报价。",
            "persona_policy": {"roleplay_contract_version": "v1"},
        },
        ("case_item", "case-1"): {
            "case_item_id": "case-1",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:case",
            "allowed_disclosure_policy": {
                "phases": [{"trigger": "ask_budget", "disclose": "budget"}],
                "roleplay_contract_version": "v1",
                "roleplay": {
                    "situation_code": "first_visit",
                    "hidden_information_keys": ["hidden_information"],
                },
            },
        },
        ("role_profile", "role-1"): {
            "role_profile_id": "role-1",
            "status": "published",
            "version": 1,
            "content_hash": "sha256:role",
            "behavior_rules": ["保持谨慎，不主动透露预算。"],
        },
        ("scoring_ruleset", "ruleset-1"): {
            "ruleset_id": "ruleset-1",
            "status": "published",
            "version": "v1",
            "definition_json": {"roleplay_contract_version": "v1"},
        },
    }


def _reader(overrides: dict[tuple[str, str], object] | None = None):
    refs = _references()
    if overrides:
        refs.update(overrides)

    def read(asset_type: str, asset_id: str) -> object | None:
        return refs.get((asset_type, asset_id))

    return read


@pytest.mark.asyncio
async def test_should_compile_first_visit_contract_from_template() -> None:
    contract = await RoleplayContractCompiler(_reader()).compile_from_template(
        "template-1",
        actor_id="actor-1",
        compiled_at="2026-05-26T00:00:00Z",
    )

    assert contract["schema_version"] == "roleplay_contract_v1"
    assert contract["source_track"] == "curriculum_template"
    assert contract["situation"]["code"] == "first_visit"
    assert contract["relationship_context"]["has_prior_meeting"] is False
    assert "上次拜访" in contract["forbidden_claim_patterns"]
    assert "hidden_information" in contract["visible_information_scope"]["hidden_by_default_keys"]
    assert contract["audit"]["contract_hash"].startswith("sha256:")


@pytest.mark.asyncio
async def test_should_fail_when_first_visit_has_prior_meeting() -> None:
    with pytest.raises(RoleplayContractCompileError) as exc_info:
        await RoleplayContractCompiler(
            _reader(
                {
                    ("case_item", "case-1"): _references()[("case_item", "case-1")]
                    | {
                        "allowed_disclosure_policy": {
                            "phases": [{"trigger": "ask", "disclose": "budget"}],
                            "roleplay": {
                                "situation_code": "first_visit",
                                "relationship_context_override": {
                                    "has_prior_meeting": True
                                },
                            },
                        }
                    }
                }
            )
        ).compile_from_template("template-1", actor_id="actor-1")

    assert exc_info.value.reason_code == "first_visit_has_prior_meeting"


@pytest.mark.asyncio
async def test_should_fail_when_hidden_key_is_initially_visible() -> None:
    with pytest.raises(RoleplayContractCompileError) as exc_info:
        await RoleplayContractCompiler(
            _reader(
                {
                    ("case_item", "case-1"): _references()[("case_item", "case-1")]
                    | {
                        "allowed_disclosure_policy": {
                            "phases": [{"trigger": "ask", "disclose": "budget"}],
                            "roleplay": {
                                "situation_code": "first_visit",
                                "visible_information_keys": [
                                    "industry",
                                    "hidden_information",
                                ],
                                "hidden_information_keys": ["hidden_information"],
                            },
                        }
                    }
                }
            )
        ).compile_from_template("template-1", actor_id="actor-1")

    assert exc_info.value.reason_code == "hidden_key_initially_visible"


@pytest.mark.asyncio
async def test_should_compile_legacy_contract_when_persona_has_no_defaults() -> None:
    contract = await RoleplayContractCompiler().compile_from_persona(
        {"id": "persona-1", "persona_policy": {}},
        actor_id="actor-1",
    )

    assert contract["source_track"] == "direct_practice"
    assert contract["legacy_status"] == "legacy_unstructured_roleplay"


@pytest.mark.asyncio
async def test_should_return_gate_results_for_invalid_template_candidate() -> None:
    candidate = PracticeTemplatePublishCandidate(
        name="客户对练",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        case_item_id="case-1",
    )

    results = await RoleplayContractCompiler(
        _reader({("case_item", "case-1"): None})
    ).validate_template_candidate(candidate, actor_id="actor-1")

    assert [item.reason_code for item in results] == ["case_item_required"]


@pytest.mark.asyncio
async def test_should_load_published_situation_packs_from_business_rule_config(
    test_db,
) -> None:
    value = DEFAULT_ROLEPLAY_SITUATION_PACKS | {"version": "roleplay_pack_custom_v2"}
    value["packs"] = [
        pack | {"label": "首次拜访-数据库发布版"}
        if pack["code"] == "first_visit"
        else pack
        for pack in DEFAULT_ROLEPLAY_SITUATION_PACKS["packs"]
    ]
    service = BusinessRuleConfigService(test_db)
    draft = await service.create_or_update_draft(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        value=value,
        actor_id="admin-1",
        reason="customize first_visit label",
    )
    await service.publish(
        key=ROLEPLAY_SITUATION_PACKS_KEY,
        actor_id="admin-1",
        config_id=str(draft.id),
        reason="publish custom packs",
    )
    await test_db.commit()

    repo = await SituationPackRepository.from_database(test_db)
    contract = await RoleplayContractCompiler(
        _reader(),
        situation_packs=repo,
    ).compile_from_template("template-1", actor_id="actor-1")

    assert contract["situation"]["label"] == "首次拜访-数据库发布版"


def test_disclosure_state_initializes_from_initial_visible_keys() -> None:
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "visible_information_keys": ["industry", "company_profile"],
                    "hidden_information_keys": ["budget"],
                }
            },
        },
        actor_id="actor-1",
    )

    state = initial_roleplay_disclosure_state(
        contract,
        now_iso="2026-05-26T00:00:00+00:00",
    )

    assert state["status"] == "ready"
    assert state["visible_keys"] == ["industry", "company_profile"]
    assert state["disclosed_keys"] == []
    assert state["contract_hash"] == contract["audit"]["contract_hash"]


def test_disclosure_state_keyword_trigger_reveals_single_key() -> None:
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "visible_information_keys": ["industry"],
                    "hidden_information_keys": ["budget", "decision_chain"],
                    "disclosure_policy": {
                        "phases": [
                            {
                                "keywords": ["预算"],
                                "disclose_keys": ["budget"],
                                "disclose": {"text": "预算仍需采购委员会确认。"},
                            }
                        ]
                    },
                }
            },
        },
        actor_id="actor-1",
    )
    state = initial_roleplay_disclosure_state(contract)

    updated = resolve_roleplay_disclosure_state(
        contract=contract,
        previous_state=state,
        learner_message="这次项目预算大概多少？",
        current_sales_stage="discovery",
        turn_number=2,
        now_iso="2026-05-26T00:01:00+00:00",
    )

    assert "budget" in updated["visible_keys"]
    assert updated["disclosed_keys"] == ["budget"]
    assert updated["disclosed_payload"] == {"budget": "预算仍需采购委员会确认。"}
    assert "decision_chain" not in updated["visible_keys"]


def test_visible_case_payload_never_injects_hidden_blob_before_trigger() -> None:
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "visible_information_keys": ["industry", "company_profile"],
                    "hidden_information_keys": ["hidden_information"],
                }
            },
        },
        actor_id="actor-1",
    )
    case_item = type(
        "CaseItemStub",
        (),
        {
            "industry": "制造业",
            "company_profile": "客户扩产中。",
            "customer_role": "采购总监",
            "pain_points": ["返工率高"],
            "objections": ["预算紧张"],
            "success_criteria": ["试点范围"],
            "hidden_information": "隐藏预算不能进入初始 prompt",
        },
    )()

    payload = visible_case_payload(
        case_item,
        contract,
        disclosure_state=initial_roleplay_disclosure_state(contract),
    )

    assert payload == {
        "industry": "制造业",
        "company_profile": "客户扩产中。",
    }
    assert "hidden_information" not in payload


def test_roleplay_compliance_summary_and_timeline_are_sanitized_by_default() -> None:
    contract = RoleplayContractCompiler().compile_from_persona_sync(
        {
            "id": "persona-1",
            "persona_policy": {
                "roleplay_defaults": {
                    "situation_code": "first_visit",
                    "visible_information_keys": ["industry"],
                    "hidden_information_keys": ["hidden_information"],
                }
            },
        },
        actor_id="actor-1",
        compiled_at="2026-05-26T00:00:00Z",
    )
    voice_snapshot = {
        "roleplay_contract": contract,
        "runtime_metrics": {
            "roleplay_compliance": {
                "violation_count": 1,
                "blocking_violation_count": 1,
                "regenerate_count": 1,
                "cancel_stream_count": 1,
                "hidden_leak_prevented_count": 1,
                "last_action_at": "2026-05-26T00:02:00+00:00",
                "timeline": [
                    {
                        "turn_number": 2,
                        "response_id": "resp-1",
                        "action": "cancel_stream",
                        "sales_stage": "opening",
                        "visible_keys": ["industry"],
                        "disclosed_keys": [],
                        "created_at": "2026-05-26T00:02:00+00:00",
                        "trace_id": "trace-1",
                        "decision": {
                            "severity": "blocking",
                            "violation_code": "ROLEPLAY_HISTORY_CONTRADICTION",
                            "matched_pattern": "上次拜访",
                        },
                    }
                ],
            }
        },
    }
    runtime_state = {
        "roleplay_disclosure_state": {
            **initial_roleplay_disclosure_state(contract),
            "events": [
                {
                    "turn_number": 1,
                    "sales_stage": "discovery",
                    "matched_keys": ["hidden_information"],
                    "created_at": "2026-05-26T00:01:00+00:00",
                    "trace_id": "trace-0",
                    "trigger": "预算",
                }
            ],
        }
    }

    summary = roleplay_compliance_summary_from_session(
        curriculum_snapshot={},
        voice_policy_snapshot=voice_snapshot,
        runtime_state=runtime_state,
    )
    timeline = roleplay_compliance_timeline_from_session(
        voice_policy_snapshot=voice_snapshot,
        runtime_state=runtime_state,
    )
    admin_timeline = roleplay_compliance_timeline_from_session(
        voice_policy_snapshot=voice_snapshot,
        runtime_state=runtime_state,
        include_internal_details=True,
    )

    assert summary["status"] == "ready"
    assert summary["situation_code"] == "first_visit"
    assert summary["violation_count"] == 1
    assert summary["hidden_leak_prevented_count"] == 1
    assert len(summary["timeline"]) == 1
    assert timeline[0]["event_type"] == "disclosure"
    assert timeline[1]["event_type"] == "compliance_decision"
    assert "matched_pattern" not in timeline[1]
    assert admin_timeline[1]["matched_pattern"] == "上次拜访"
    assert admin_timeline[1]["visible_keys"] == ["industry"]
