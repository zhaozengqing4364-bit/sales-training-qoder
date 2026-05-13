from __future__ import annotations

import pytest

from curriculum_practice.schemas import PracticeTemplatePublishCandidate
from curriculum_practice.services.publishing_gates import PublishingGateService


@pytest.mark.asyncio
async def test_should_fail_publish_when_child_template_is_unpublished() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template" and asset_id == "child-template-1":
            return {"template_id": asset_id, "status": "draft"}
        return {"id": asset_id, "status": "published"}

    service = PublishingGateService(reference_reader=reference_reader)
    candidate = _candidate_with_plan()

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "child_template_unpublished" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_stage_duration_exceeds_limit() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: {
            "id": asset_id,
            "status": "published",
            "voice_mode": "stepfun_realtime",
        }
    )
    candidate = _candidate_with_plan(max_stage_duration_seconds=300)

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "stage_duration_exceeds_limit" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_completion_policy_min_score_is_impossible() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template":
            return _child_template(asset_id, scoring_ruleset_id="child-ruleset-1")
        if asset_type == "scoring_ruleset" and asset_id == "child-ruleset-1":
            return {
                "ruleset_id": asset_id,
                "status": "published",
                "definition_json": {"score_scale": {"max_score": 5.0}},
            }
        return {
            "id": asset_id,
            "status": "published",
            "voice_mode": "stepfun_realtime",
        }

    service = PublishingGateService(reference_reader=reference_reader)
    candidate = _candidate_with_plan()

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "completion_policy_impossible" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_curriculum_plan_has_cycle() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: _child_template(asset_id)
    )
    candidate = _candidate_with_plan(two_stage=True)
    assert candidate.curriculum_plan is not None
    candidate.curriculum_plan.stages[0].prerequisites = [
        {"template_stage_key": "template_stage_objection", "required_result": "completed"}
    ]

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "curriculum_plan_cycle" in [result.reason_code for result in decision.results]


@pytest.mark.asyncio
async def test_should_fail_publish_when_curriculum_stage_is_unreachable() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: _child_template(asset_id)
    )
    candidate = _candidate_with_plan()
    assert candidate.curriculum_plan is not None
    candidate.curriculum_plan.stages[0].prerequisites = [
        {"template_stage_key": "template_stage_opening", "required_result": "completed"}
    ]

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "curriculum_stage_unreachable" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_child_template_has_wrong_voice_mode() -> None:
    service = PublishingGateService(
        reference_reader=lambda asset_type, asset_id: _child_template(
            asset_id, voice_mode="legacy"
        )
    )
    candidate = _candidate_with_plan()

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "child_template_wrong_voice_mode" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_adjacent_stages_switch_runtime_voice() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template" and asset_id == "child-template-2":
            return _child_template(asset_id, runtime_profile_id="runtime-2")
        return _child_template(asset_id)

    service = PublishingGateService(reference_reader=reference_reader)
    candidate = _candidate_with_plan(two_stage=True)

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "cross_stage_voice_hot_switch_unsupported" in [
        result.reason_code for result in decision.results
    ]


@pytest.mark.asyncio
async def test_should_fail_publish_when_adjacent_stages_switch_role_voice_id() -> None:
    def reference_reader(asset_type: str, asset_id: str) -> object | None:
        if asset_type == "practice_template" and asset_id == "child-template-2":
            return _child_template(asset_id, role_profile_voice_id="custom_voice_b")
        return _child_template(asset_id, role_profile_voice_id="custom_voice_a")

    service = PublishingGateService(reference_reader=reference_reader)
    candidate = _candidate_with_plan(two_stage=True)

    decision = await service.validate(candidate)

    assert decision.can_publish is False
    assert "cross_stage_voice_hot_switch_unsupported" in [
        result.reason_code for result in decision.results
    ]


def _candidate_with_plan(
    *, max_stage_duration_seconds: int = 900, two_stage: bool = False
) -> PracticeTemplatePublishCandidate:
    stages = [
        {
            "template_stage_key": "template_stage_opening",
            "order": 1,
            "name": "开场",
            "template_ref": {
                "asset_type": "practice_template",
                "asset_id": "child-template-1",
                "version": 1,
                "hash": "sha256:child",
                "snapshot_label": "published",
            },
            "completion_policy": {
                "min_score": 7.0,
                "min_rounds": 2,
                "max_duration_seconds": 600,
            },
            "failure_policy": "retry_current",
            "prerequisites": [],
        }
    ]
    if two_stage:
        stages.append(
            {
                "template_stage_key": "template_stage_objection",
                "order": 2,
                "name": "异议处理",
                "template_ref": {
                    "asset_type": "practice_template",
                    "asset_id": "child-template-2",
                    "version": 1,
                    "hash": "sha256:child-2",
                    "snapshot_label": "published",
                },
                "completion_policy": {
                    "min_score": 7.0,
                    "min_rounds": 2,
                    "max_duration_seconds": 600,
                },
                "failure_policy": "retry_current",
                "prerequisites": [
                    {
                        "template_stage_key": "template_stage_opening",
                        "required_result": "completed",
                    }
                ],
            }
        )
    return PracticeTemplatePublishCandidate(
        name="多阶段销售训练",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-1",
        persona_id="persona-1",
        runtime_profile_id="runtime-1",
        voice_mode="stepfun_realtime",
        scoring_ruleset_id="ruleset-1",
        curriculum_plan={
            "name": "多阶段销售训练",
            "max_stage_duration_seconds": 900,
            "stages": stages,
        },
        max_stage_duration_seconds=max_stage_duration_seconds,
    )


def _child_template(
    asset_id: str,
    *,
    voice_mode: str = "stepfun_realtime",
    runtime_profile_id: str = "runtime-1",
    scoring_ruleset_id: str = "ruleset-1",
    role_profile_voice_id: str | None = None,
) -> dict[str, object]:
    return {
        "template_id": asset_id,
        "status": "published",
        "voice_mode": voice_mode,
        "runtime_profile_id": runtime_profile_id,
        "scoring_ruleset_id": scoring_ruleset_id,
        "role_profile_voice_id": role_profile_voice_id,
    }
