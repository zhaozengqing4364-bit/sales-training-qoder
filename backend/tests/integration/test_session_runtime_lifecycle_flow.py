"""Integration tests for session runtime lifecycle transitions."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.services.session_runtime_state_service import (
    SessionRuntimeStateService,
    read_lifecycle_snapshot,
)


@pytest.mark.asyncio
async def test_should_transition_create_preflight_started_completed(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="lifecycle-sales",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="preparing",
        agent_id="123e4567-e89b-12d3-a456-426614174001",
        persona_id="223e4567-e89b-12d3-a456-426614174002",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"voice_mode": "stepfun_realtime"},
    )
    test_db.add(session)
    await test_db.commit()

    lifecycle = SessionRuntimeStateService(test_db)
    await lifecycle.initialize_on_create(
        str(session.session_id),
        has_runtime_snapshot=True,
        source="test",
    )

    preflight_response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/runtime-preflight",
        headers=auth_headers,
    )
    assert preflight_response.status_code == 200, preflight_response.text
    preflight_payload = preflight_response.json()["data"]
    assert preflight_payload["runtime_lifecycle_state"] in {"runnable", "failed"}

    await lifecycle.mark_started(str(session.session_id), source="test_ws")
    await test_db.refresh(session)
    started = read_lifecycle_snapshot(session.runtime_state)
    assert started.state == "started"

    await lifecycle.mark_completed(str(session.session_id), source="test_end")
    await test_db.refresh(session)
    completed = read_lifecycle_snapshot(session.runtime_state)
    assert completed.state == "completed"

    detail_response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    assert detail["runtime_lifecycle_state"] == "completed"
    assert detail["failure_code"] is None


@pytest.mark.asyncio
async def test_should_mark_failed_on_preflight_block(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="lifecycle-blocked",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="preparing",
        voice_mode="legacy",
    )
    test_db.add(session)
    await test_db.commit()

    lifecycle = SessionRuntimeStateService(test_db)
    await lifecycle.initialize_on_create(
        str(session.session_id),
        has_runtime_snapshot=False,
        source="test",
    )
    await lifecycle.apply_preflight_result(
        str(session.session_id),
        runnable=False,
        code="LEGACY_SALES_RUNTIME_DISABLED",
        hint="旧版语音模式已停用",
    )
    await test_db.refresh(session)
    snapshot = read_lifecycle_snapshot(session.runtime_state)
    assert snapshot.state == "failed"
    assert snapshot.failure_code == "LEGACY_SALES_RUNTIME_DISABLED"
    assert snapshot.failure_hint == "旧版语音模式已停用"


@pytest.mark.asyncio
async def test_should_lazy_backfill_lifecycle_on_get_session(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="lazy-backfill-get",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        agent_id="123e4567-e89b-12d3-a456-426614174001",
        persona_id="223e4567-e89b-12d3-a456-426614174002",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"voice_mode": "stepfun_realtime"},
    )
    test_db.add(session)
    await test_db.commit()

    detail_response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()["data"]
    assert detail["runtime_lifecycle_state"] == "completed"

    await test_db.refresh(session)
    persisted = read_lifecycle_snapshot(session.runtime_state)
    assert persisted.state == "completed"
