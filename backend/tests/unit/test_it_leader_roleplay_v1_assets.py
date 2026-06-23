from __future__ import annotations

import pytest

from sales_bot.services.it_leader_roleplay_v1 import (
    REQUIRED_SAMPLE_COVERAGE_TAGS,
    ROLEPLAY_PHASE_IDS,
    ItLeaderRoleplayV1ValidationError,
    get_default_state_card,
    get_knowledge_visibility_rules,
    get_regression_sample_metadata,
    get_roleplay_contract,
    get_scoring_rubric,
    get_state_card_schema,
    validate_knowledge_visibility_rules,
    validate_regression_sample_metadata,
    validate_roleplay_contract,
    validate_scoring_rubric,
    validate_v1_assets,
)


def test_should_expose_valid_v1_asset_contracts() -> None:
    validate_v1_assets()

    contract = get_roleplay_contract()
    state_card = get_default_state_card()
    state_card_schema = get_state_card_schema()

    assert contract["scenario_code"] == "it_leader_first_visit_shixi_v1"
    assert contract["audit"]["contract_hash"].startswith("sha256:")
    assert state_card["current_phase_id"] == ROLEPLAY_PHASE_IDS[0]
    assert state_card["current_phase_type"] == "roleplay_phase"
    assert state_card_schema["phase_id_source"] == "roleplay_phase"
    assert state_card_schema["sales_stage_authority"] == "SalesStageCapability"


def test_should_keep_visible_and_hidden_knowledge_boundaries() -> None:
    contract = get_roleplay_contract()
    scope = contract["visible_information_scope"]

    visible = set(scope["initial_visible_keys"])
    hidden = set(scope["hidden_by_default_keys"])

    assert {"customer_background", "product_facts_limited"}.issubset(visible)
    assert {
        "scoring_coach",
        "standard_answers",
        "internal_sales_playbook",
        "hidden_budget",
        "decision_chain",
    }.issubset(hidden)
    assert visible.isdisjoint(hidden)

    bad_contract = get_roleplay_contract()
    bad_contract["visible_information_scope"]["hidden_by_default_keys"] = []
    with pytest.raises(ItLeaderRoleplayV1ValidationError) as exc_info:
        validate_roleplay_contract(bad_contract)
    assert exc_info.value.reason_code == "missing_hidden_scope"


def test_should_keep_scorer_only_knowledge_out_of_realtime_customer_context() -> None:
    rules = get_knowledge_visibility_rules()
    validate_knowledge_visibility_rules(rules)

    layers = {layer["id"]: layer for layer in rules["layers"]}

    assert layers["customer_background"]["realtime_customer_visible"] is True
    assert layers["product_facts_limited"]["realtime_customer_visible"] is True
    assert layers["scoring_coach"]["realtime_customer_visible"] is False
    assert "realtime_customer" not in layers["scoring_coach"]["allowed_consumers"]
    assert (
        rules["degradation_policy"]["on_product_fact_missing"]
        == "ask_for_verifiable_material_or_poc_metric"
    )
    assert rules["degradation_policy"]["forbid_unsupported_product_claims"] is True


def test_should_pin_forbidden_roleplay_behaviors() -> None:
    contract = get_roleplay_contract()
    forbidden_ids = {item["id"] for item in contract["forbidden_behaviors"]}

    assert {
        "leak_answer_key",
        "act_as_coach",
        "answer_for_learner",
        "reveal_scoring_rubric",
        "invent_product_capability",
    }.issubset(forbidden_ids)


def test_should_treat_four_phase_ids_as_roleplay_phases_not_sales_stages() -> None:
    contract = get_roleplay_contract()
    phase_model = contract["phase_model"]
    phases = phase_model["phases"]

    assert phase_model["phase_type"] == "roleplay_phase"
    assert phase_model["sales_stage_authority"] == "SalesStageCapability"
    assert tuple(phase["id"] for phase in phases) == ROLEPLAY_PHASE_IDS
    assert all("sales_stage_id" not in phase for phase in phases)

    bad_contract = get_roleplay_contract()
    bad_contract["phase_model"]["phases"][0]["sales_stage_id"] = "prospecting"
    with pytest.raises(ItLeaderRoleplayV1ValidationError) as exc_info:
        validate_roleplay_contract(bad_contract)
    assert exc_info.value.reason_code == "phase_declares_sales_stage"


def test_should_validate_six_item_rubric_total_is_100() -> None:
    rubric = get_scoring_rubric()
    validate_scoring_rubric(rubric)

    assert len(rubric["dimensions"]) == 6
    assert sum(item["max_score"] for item in rubric["dimensions"]) == 100
    assert rubric["total_score"] == 100
    assert rubric["evidence_policy"]["required_source"] == "learner_utterance"

    bad_rubric = get_scoring_rubric()
    bad_rubric["dimensions"][0]["max_score"] = 14
    with pytest.raises(ItLeaderRoleplayV1ValidationError) as exc_info:
        validate_scoring_rubric(bad_rubric)
    assert exc_info.value.reason_code == "invalid_rubric_total"


def test_should_define_nine_regression_samples_with_required_coverage() -> None:
    samples = get_regression_sample_metadata()
    validate_regression_sample_metadata(samples)

    tier_counts = {
        tier: sum(sample["quality_tier"] == tier for sample in samples)
        for tier in ("excellent", "average", "poor")
    }
    coverage = {
        tag
        for sample in samples
        for tag in sample["coverage_tags"]
    }

    assert len(samples) == 9
    assert tier_counts == {"excellent": 3, "average": 3, "poor": 3}
    assert REQUIRED_SAMPLE_COVERAGE_TAGS.issubset(coverage)
    assert all(sample["fixture_type"] == "metadata_only" for sample in samples)

    bad_samples = get_regression_sample_metadata()[:-1]
    with pytest.raises(ItLeaderRoleplayV1ValidationError) as exc_info:
        validate_regression_sample_metadata(bad_samples)
    assert exc_info.value.reason_code == "invalid_sample_count"
