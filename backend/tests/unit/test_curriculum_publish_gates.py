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
    assert [result.reason_code for result in decision.results] == ["reference_missing"]
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
