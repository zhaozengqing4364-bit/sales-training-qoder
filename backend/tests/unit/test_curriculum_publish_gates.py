from __future__ import annotations

import pytest

from curriculum_practice.schemas import PracticeTemplatePublishCandidate
from curriculum_practice.services.publishing_gates import PublishingGateService


@pytest.mark.asyncio
async def test_should_fail_publish_gate_when_reference_is_missing() -> None:
    service = PublishingGateService(reference_reader=lambda asset_type, asset_id: None)
    candidate = PracticeTemplatePublishCandidate(
        name="客户对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-missing",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "reference_missing" in [result.reason_code for result in decision.results]
    assert decision.results[0].gate_name == "reference_integrity"
    assert "agent" in decision.results[0].message


@pytest.mark.asyncio
async def test_should_fail_publish_gate_when_voice_mode_is_not_stepfun_realtime() -> (
    None
):
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: {"id": asset_id}
    )
    candidate = PracticeTemplatePublishCandidate(
        name="客户对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="legacy",
        scoring_ruleset_id="ruleset-1",
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert [result.reason_code for result in decision.results] == [
        "voice_mode_not_stepfun_realtime"
    ]
    assert decision.results[0].gate_name == "voice_runtime_policy"


@pytest.mark.asyncio
async def test_should_fail_publish_gate_when_scenario_type_is_not_supported() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: {"id": asset_id}
    )
    candidate = PracticeTemplatePublishCandidate.model_construct(
        name="客户对练模板",
        scenario_type="coaching",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=[],
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert [result.reason_code for result in decision.results] == [
        "scenario_type_not_supported"
    ]
    assert decision.results[0].gate_name == "scenario_type_policy"


@pytest.mark.asyncio
async def test_should_fail_publish_gate_with_distinct_scoring_rubric_reason() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "scoring_ruleset":
            return None
        return {"id": asset_id}

    service = PublishingGateService(reference_reader=reference_reader)
    candidate = PracticeTemplatePublishCandidate(
        name="客户对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-missing",
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert [result.reason_code for result in decision.results] == [
        "scoring_rubric_missing"
    ]
    assert decision.results[0].gate_name == "scoring_rubric_reference"


@pytest.mark.asyncio
async def test_should_return_all_known_publish_gate_failures() -> None:
    service = PublishingGateService(reference_reader=lambda asset_type, asset_id: None)
    candidate = PracticeTemplatePublishCandidate.model_construct(
        name="客户对练模板",
        scenario_type="coaching",
        mode="customer_roleplay",
        agent_id="agent-missing",
        persona_id="persona-missing",
        runtime_profile_id="runtime-missing",
        voice_mode="legacy",
        scoring_ruleset_id="ruleset-missing",
        knowledge_base_refs=["kb-missing"],
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert [result.reason_code for result in decision.results] == [
        "scenario_type_not_supported",
        "reference_missing",
        "reference_missing",
        "reference_missing",
        "scoring_rubric_missing",
        "reference_missing",
        "voice_mode_not_stepfun_realtime",
    ]


@pytest.mark.asyncio
async def test_should_pass_publish_gate_when_template_is_publishable() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: {"id": asset_id}
    )
    candidate = PracticeTemplatePublishCandidate(
        name="客户对练模板",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        knowledge_base_refs=["kb-1"],
    )

    decision = await service.validate(candidate)

    assert decision.can_publish is True
    assert decision.results == []
