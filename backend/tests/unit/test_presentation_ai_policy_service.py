"""Unit tests for PresentationAIPolicyService."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import PresentationAIPolicy
from presentation_coach.services.presentation_ai_policy_service import (
    PresentationAIPolicyService,
)


@pytest.mark.asyncio
async def test_get_scope_policy_returns_defaults_when_missing(test_db: AsyncSession):
    service = PresentationAIPolicyService(test_db)

    result = await service.get_scope_policy(scope_type="global")

    assert result["scope_type"] == "global"
    assert result["exists"] is False
    assert result["policy"]["enabled"] is True
    assert result["policy"]["prompt_config"]["enable_prompt_first"] is True
    assert result["policy"]["rule_config"]["similarity_threshold"] == 0.75


@pytest.mark.asyncio
async def test_get_scope_policy_result_fails_for_invalid_scope_type(
    test_db: AsyncSession,
):
    service = PresentationAIPolicyService(test_db)

    result = await service.get_scope_policy_result(scope_type="tenant")

    assert result.is_success is False
    assert result.fallback == "[INVALID_SCOPE_TYPE]"


@pytest.mark.asyncio
async def test_get_scope_policy_result_requires_scope_id_for_specific_scope(
    test_db: AsyncSession,
):
    service = PresentationAIPolicyService(test_db)

    result = await service.get_scope_policy_result(scope_type="presentation")

    assert result.is_success is False
    assert result.fallback == "[SCOPE_ID_REQUIRED]"


@pytest.mark.asyncio
async def test_resolve_effective_policy_for_session_result_returns_missing_session(
    test_db: AsyncSession,
):
    service = PresentationAIPolicyService(test_db)

    result = await service.resolve_effective_policy_for_session_result(
        session_id="missing-session"
    )

    assert result.is_success is False
    assert result.fallback == "[SESSION_NOT_FOUND]"


@pytest.mark.asyncio
async def test_resolve_effective_policy_merges_by_scope_precedence(test_db: AsyncSession):
    scenario_id = str(uuid.uuid4())
    presentation_id = str(uuid.uuid4())

    global_policy = PresentationAIPolicy(
        id=str(uuid.uuid4()),
        scope_type="global",
        scope_id=None,
        enabled=True,
        prompt_config={"enable_prompt_first": False},
        rule_config={"similarity_threshold": 0.6},
        fallback_config={"enable_interruption_detector_fallback": False},
    )
    scenario_policy = PresentationAIPolicy(
        id=str(uuid.uuid4()),
        scope_type="scenario",
        scope_id=scenario_id,
        enabled=True,
        prompt_config={"interruption_template_id": str(uuid.uuid4())},
        rule_config={"missing_points_interrupt_ratio_threshold": 0.45},
        fallback_config={"allow_scenario_prompt_fallback": False},
    )
    presentation_policy = PresentationAIPolicy(
        id=str(uuid.uuid4()),
        scope_type="presentation",
        scope_id=presentation_id,
        enabled=True,
        prompt_config={"enable_prompt_first": True},
        rule_config={"similarity_threshold": 0.88},
        fallback_config={"fallback_when_template_missing": False},
    )
    test_db.add_all([global_policy, scenario_policy, presentation_policy])
    await test_db.commit()

    service = PresentationAIPolicyService(test_db)
    effective = await service.resolve_effective_policy(
        scenario_id=scenario_id,
        presentation_id=presentation_id,
    )

    assert effective["prompt_config"]["enable_prompt_first"] is True
    assert effective["prompt_config"]["interruption_template_id"] == scenario_policy.prompt_config["interruption_template_id"]
    assert effective["rule_config"]["similarity_threshold"] == 0.88
    assert effective["rule_config"]["missing_points_interrupt_ratio_threshold"] == 0.45
    assert effective["fallback_config"]["enable_interruption_detector_fallback"] is False
    assert effective["fallback_config"]["allow_scenario_prompt_fallback"] is False
    assert effective["fallback_config"]["fallback_when_template_missing"] is False
    assert effective["source"]["applied_scopes"] == ["global", "scenario", "presentation"]


@pytest.mark.asyncio
async def test_resolve_effective_policy_disabled_specific_scope_rolls_back_default(
    test_db: AsyncSession,
):
    scenario_id = str(uuid.uuid4())

    global_policy = PresentationAIPolicy(
        id=str(uuid.uuid4()),
        scope_type="global",
        scope_id=None,
        enabled=True,
        prompt_config={"interruption_template_id": str(uuid.uuid4())},
        rule_config={"similarity_threshold": 0.61},
        fallback_config={"enable_interruption_detector_fallback": False},
    )
    scenario_disabled_policy = PresentationAIPolicy(
        id=str(uuid.uuid4()),
        scope_type="scenario",
        scope_id=scenario_id,
        enabled=False,
        prompt_config={},
        rule_config={},
        fallback_config={},
    )
    test_db.add_all([global_policy, scenario_disabled_policy])
    await test_db.commit()

    service = PresentationAIPolicyService(test_db)
    effective = await service.resolve_effective_policy(scenario_id=scenario_id)

    assert effective["prompt_config"]["interruption_template_id"] is None
    assert effective["rule_config"]["similarity_threshold"] == 0.75
    assert effective["fallback_config"]["enable_interruption_detector_fallback"] is True
    assert effective["source"]["resolution"] == "default_guardrail"
    assert effective["source"]["disabled_scope"] == "scenario"


@pytest.mark.asyncio
async def test_upsert_scope_policy_creates_and_updates_record(test_db: AsyncSession):
    service = PresentationAIPolicyService(test_db)

    created = await service.upsert_scope_policy(
        scope_type="presentation",
        scope_id="ppt-123",
        payload={
            "enabled": True,
            "prompt_config": {"interruption_template_id": "tpl-001"},
            "rule_config": {"feedback_cooldown_seconds": 12},
            "fallback_config": {"allow_scenario_prompt_fallback": False},
        },
        updated_by="user-admin",
    )
    await test_db.commit()

    assert created["exists"] is True
    assert created["policy"]["prompt_config"]["interruption_template_id"] == "tpl-001"
    assert created["policy"]["rule_config"]["feedback_cooldown_seconds"] == 12
    assert created["policy"]["fallback_config"]["allow_scenario_prompt_fallback"] is False

    updated = await service.upsert_scope_policy(
        scope_type="presentation",
        scope_id="ppt-123",
        payload={
            "rule_config": {"similarity_threshold": 0.9},
        },
        updated_by="user-admin-2",
    )
    await test_db.commit()

    assert updated["exists"] is True
    assert updated["policy"]["rule_config"]["similarity_threshold"] == 0.9
    assert updated["policy"]["prompt_config"]["interruption_template_id"] == "tpl-001"
