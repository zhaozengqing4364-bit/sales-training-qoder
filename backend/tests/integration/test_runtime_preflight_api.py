"""Integration tests for runtime preflight API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from curriculum_practice.models import ExaminerAgent


@pytest.mark.asyncio
async def test_runtime_preflight_returns_examiner_blockers(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="考核",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    agent = ExaminerAgent(
        name="考官",
        question_source_ids=[],
        learner_level_strategy={},
        scoring_policy_id="policy-1",
        timeout_config={"max_seconds": 600},
        safety_config={},
        prompt_config={},
        simulation_config={},
        status="published",
        version=1,
        content_hash="agent-hash",
    )
    test_db.add(agent)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        curriculum_snapshot={
            "kind": "curriculum_examiner_session",
            "content_assets": [
                {
                    "asset_type": "examiner_agent",
                    "asset_id": str(agent.examiner_agent_id),
                    "version": 1,
                    "hash": "agent-hash",
                    "snapshot_label": "考官",
                }
            ],
        },
    )
    test_db.add(session)
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/runtime-preflight",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["runnable"] is False
    assert payload["runtime_type"] == "examiner"
    assert payload["code"] == "EXAMINER_RUNTIME_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_runtime_preflight_requires_auth(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="销售",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()
    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        agent_id="agent-1",
        persona_id="persona-1",
        voice_mode="stepfun_realtime",
    )
    test_db.add(session)
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/runtime-preflight",
    )

    assert response.status_code == 401
