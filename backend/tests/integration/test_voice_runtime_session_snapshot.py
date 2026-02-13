"""
Integration tests for session voice policy snapshot persistence.
"""
from __future__ import annotations

import os
import uuid
from copy import deepcopy
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.db.models import PracticeSession, Presentation, Scenario, User

os.environ["ENVIRONMENT"] = "development"


async def _create_runtime_entities(test_db: AsyncSession) -> tuple[VoiceRuntimeProfile, Agent, Persona]:
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="测试默认实时配置",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-2",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        name="测试销售Agent",
        description="用于集成测试",
        category="sales",
        status="published",
        default_knowledge_base_ids=["kb_test_1"],
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="测试客户角色",
        description="用于集成测试",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是谨慎型采购经理。",
        knowledge_base_ids=["kb_test_2"],
    )
    agent_persona = AgentPersona(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        persona_id=persona.id,
        is_default=True,
        override_config={"challenge_frequency": 0.6, "response_length": "short"},
    )
    test_db.add_all([profile, agent, persona, agent_persona])
    await test_db.commit()
    return profile, agent, persona


def _snapshot_ref(snapshot: Any) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None

    source = snapshot.get("source")
    tool_policy = snapshot.get("tool_policy")
    ref: dict[str, Any] = {
        "voice_mode": snapshot.get("voice_mode"),
        "runtime_profile_id": snapshot.get("runtime_profile_id"),
        "resolved_at": snapshot.get("resolved_at"),
        "tool_policy": tool_policy if isinstance(tool_policy, dict) else {},
        "knowledge_base_ids": [
            str(item)
            for item in (snapshot.get("knowledge_base_ids") or [])
            if item is not None
        ],
        "source": {str(k): str(v) for k, v in source.items()} if isinstance(source, dict) else {},
    }
    association_override = snapshot.get("agent_persona_override_config")
    if isinstance(association_override, dict):
        ref["agent_persona_override_config"] = association_override
    return ref


def _headers_for_user(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_start_session_persists_voice_policy_snapshot(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Creating an enhanced sales session should persist resolved voice policy snapshot."""
    _, agent, persona = await _create_runtime_entities(test_db)

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["success"] is True
    session_id = payload["data"]["session_id"]

    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    assert session is not None
    assert session.voice_mode == "stepfun_realtime"
    assert session.voice_policy_snapshot is not None
    assert session.voice_policy_snapshot.get("voice_mode") == "stepfun_realtime"
    assert set(session.voice_policy_snapshot.get("knowledge_base_ids", [])) == {"kb_test_1", "kb_test_2"}
    assert payload["data"]["voice_policy_snapshot_ref"] == _snapshot_ref(session.voice_policy_snapshot)


@pytest.mark.asyncio
async def test_start_session_honors_explicit_scenario_id(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Enhanced session creation should persist the caller-selected scenario_id."""
    _, agent, persona = await _create_runtime_entities(test_db)
    explicit_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="explicit_sales_scenario",
        description="User-selected scenario",
        is_active=True,
    )
    test_db.add(explicit_scenario)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "scenario_id": explicit_scenario.scenario_id,
            "agent_id": agent.id,
            "persona_id": persona.id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["scenario_id"] == explicit_scenario.scenario_id

    session_id = body["data"]["session_id"]
    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    persisted_session = session_result.scalar_one()
    assert persisted_session.scenario_id == explicit_scenario.scenario_id

    auto_scenario_result = await test_db.execute(
        select(Scenario).where(Scenario.name == f"agent_{agent.id}")
    )
    assert auto_scenario_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_start_presentation_session_persists_voice_policy_snapshot(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Presentation session creation should reuse the same snapshot solidification semantics."""
    _, agent, persona = await _create_runtime_entities(test_db)

    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="presentation_default",
        description="presentation scenario for snapshot test",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="演示文稿",
        file_url="https://example.com/demo.pptx",
        status="ready",
    )
    test_db.add_all([scenario, presentation])
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "presentation",
            "presentation_id": presentation.presentation_id,
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "legacy",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["voice_mode"] == "legacy"
    assert isinstance(body["data"]["voice_policy_snapshot"], dict)
    assert body["data"]["voice_policy_snapshot"]["voice_mode"] == "legacy"
    assert body["data"]["voice_policy_snapshot_ref"]["voice_mode"] == "legacy"


@pytest.mark.asyncio
async def test_snapshot_baseline_is_immutable_and_report_replay_refer_same_baseline(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Later runtime policy changes must not overwrite existing session snapshot baselines."""
    profile, agent, persona = await _create_runtime_entities(test_db)

    create_resp = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
        },
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = session_result.scalar_one()
    baseline_snapshot = deepcopy(session.voice_policy_snapshot)
    baseline_ref = _snapshot_ref(baseline_snapshot)

    # Simulate admin mutating runtime profile + agent/persona linkage after session creation.
    profile.voice_mode = "legacy"
    profile.model_name = "step-audio-2-mini"
    agent.default_knowledge_base_ids = ["kb_changed_agent"]
    persona.knowledge_base_ids = ["kb_changed_persona"]
    await test_db.commit()

    session.status = "completed"
    await test_db.commit()

    session_detail_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}",
        headers=auth_headers,
    )
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/report",
        headers=auth_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session_id}/replay",
        headers=auth_headers,
    )

    assert session_detail_resp.status_code == 200
    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    detail_body = session_detail_resp.json()
    report_body = report_resp.json()
    replay_body = replay_resp.json()

    assert detail_body["data"]["voice_policy_snapshot"] == baseline_snapshot
    assert detail_body["data"]["voice_policy_snapshot_ref"] == baseline_ref
    assert report_body["data"]["voice_policy_snapshot_ref"] == baseline_ref
    assert replay_body["data"]["voice_policy_snapshot_ref"] == baseline_ref

    # DB should remain unchanged for baseline fields.
    refreshed = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    persisted = refreshed.scalar_one()
    assert persisted.voice_policy_snapshot == baseline_snapshot


@pytest.mark.asyncio
async def test_runtime_metrics_append_keeps_snapshot_reference_baseline(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Appending runtime_metrics should not change immutable snapshot reference fields."""
    _, agent, persona = await _create_runtime_entities(test_db)

    create_resp = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "stepfun_realtime",
        },
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = session_result.scalar_one()
    baseline_snapshot = deepcopy(session.voice_policy_snapshot)
    baseline_ref = _snapshot_ref(baseline_snapshot)

    mutated_snapshot = deepcopy(session.voice_policy_snapshot)
    mutated_snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 3,
            "hit_query_count": 2,
            "hit_rate": 0.6667,
            "recent_queries": ["报价", "竞品对比"],
        }
    }
    session.voice_policy_snapshot = mutated_snapshot
    session.status = "completed"
    await test_db.commit()

    detail_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}",
        headers=auth_headers,
    )
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/report",
        headers=auth_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session_id}/replay",
        headers=auth_headers,
    )

    assert detail_resp.status_code == 200
    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    detail_body = detail_resp.json()
    report_body = report_resp.json()
    replay_body = replay_resp.json()

    assert detail_body["data"]["voice_policy_snapshot_ref"] == baseline_ref
    assert report_body["data"]["voice_policy_snapshot_ref"] == baseline_ref
    assert replay_body["data"]["voice_policy_snapshot_ref"] == baseline_ref
    assert detail_body["data"]["voice_policy_snapshot"]["runtime_metrics"]["knowledge_retrieval"]["attempt_count"] == 3


@pytest.mark.asyncio
async def test_session_snapshot_access_control_owner_admin_only(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Session snapshot endpoints should be accessible only to owner or admin."""
    _, agent, persona = await _create_runtime_entities(test_db)

    create_resp = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
        },
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = session_result.scalar_one()
    session.status = "completed"

    outsider = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"snapshot-outsider-{uuid.uuid4().hex[:8]}",
        name="Snapshot Outsider",
        email=f"snapshot_outsider_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    admin_user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"snapshot-admin-{uuid.uuid4().hex[:8]}",
        name="Snapshot Admin",
        email=f"snapshot_admin_{uuid.uuid4().hex[:6]}@example.com",
        role="admin",
    )
    test_db.add_all([outsider, admin_user])
    await test_db.commit()

    outsider_headers = _headers_for_user(outsider.user_id)
    admin_headers = _headers_for_user(admin_user.user_id)

    for endpoint in (
        f"/api/v1/practice/sessions/{session_id}",
        f"/api/v1/practice/sessions/{session_id}/report",
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        f"/api/v1/sessions/{session_id}/enhanced-report",
        f"/api/v1/sessions/{session_id}/replay",
    ):
        outsider_resp = await async_client.get(endpoint, headers=outsider_headers)
        admin_resp = await async_client.get(endpoint, headers=admin_headers)
        assert outsider_resp.status_code == 403
        outsider_body = outsider_resp.json()
        assert outsider_body["success"] is False
        assert outsider_body["error"] == "[ACCESS_DENIED]"
        assert outsider_body.get("trace_id")
        assert admin_resp.status_code == 200
