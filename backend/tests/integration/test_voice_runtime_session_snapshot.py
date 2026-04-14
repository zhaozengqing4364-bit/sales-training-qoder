"""
Integration tests for session voice policy snapshot persistence.
"""

from __future__ import annotations

import os
import uuid
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.db.models import PracticeSession, Presentation, Scenario, User
from common.websocket.session_manager import get_session_manager

os.environ["ENVIRONMENT"] = "development"


async def _create_runtime_entities(
    test_db: AsyncSession,
) -> tuple[VoiceRuntimeProfile, Agent, Persona]:
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
        "instruction_contract_hash": snapshot.get("instruction_contract_hash"),
        "network_access_mode": snapshot.get("network_access_mode"),
        "resolved_at": snapshot.get("resolved_at"),
        "tool_policy": tool_policy if isinstance(tool_policy, dict) else {},
        "knowledge_base_ids": [
            str(item)
            for item in (snapshot.get("knowledge_base_ids") or [])
            if item is not None
        ],
        "source": {str(k): str(v) for k, v in source.items()}
        if isinstance(source, dict)
        else {},
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
    """Creating an enhanced sales session should persist the live StepFun/session-snapshot authority instead of any prompt-governance fallback."""
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
    assert set(session.voice_policy_snapshot.get("knowledge_base_ids", [])) == {
        "kb_test_2",
    }
    assert payload["data"]["voice_policy_snapshot_ref"] == _snapshot_ref(
        session.voice_policy_snapshot
    )


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
            "recent_attempts": [
                {
                    "attempted_at": "2026-03-28T12:00:00Z",
                    "query": "报价",
                    "status": "hit",
                    "result_count": 2,
                    "retrieval_mode": "vector",
                    "knowledge_base_ids": ["kb_test_2"],
                    "result_summaries": [
                        {
                            "knowledge_base_id": "kb_test_2",
                            "knowledge_base_name": "测试客户角色知识库",
                            "score": 0.88,
                            "snippet": "标准报价说明",
                            "retrieval_mode": "vector",
                        }
                    ],
                }
            ],
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
    assert (
        detail_body["data"]["voice_policy_snapshot"]["runtime_metrics"][
            "knowledge_retrieval"
        ]["attempt_count"]
        == 3
    )
    assert (
        detail_body["data"]["voice_policy_snapshot"]["runtime_metrics"][
            "knowledge_retrieval"
        ]["recent_attempts"][0]["query"]
        == "报价"
    )


@pytest.mark.asyncio
async def test_knowledge_check_reads_latest_valid_ledger_entry_when_flat_last_fields_are_missing(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Current session routes should stay truthful when only the bounded retrieval ledger has the latest attempt details."""
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
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {
        "enable_internal_retrieval": True,
    }
    snapshot["knowledge_base_ids"] = ["kb_test_1"]
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 1,
            "hit_query_count": 0,
            "total_results": 0,
            "recent_attempts": [
                {
                    "attempted_at": "2026-03-28T12:00:00Z",
                    "query": "ROI 案例",
                    "status": "search_failed",
                    "result_count": 0,
                    "retrieval_mode": "hybrid",
                    "knowledge_base_ids": ["kb_test_1"],
                    "error_summary": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                    "result_summaries": [],
                }
            ],
        }
    }
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    detail_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}",
        headers=auth_headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert detail_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    detail_body = detail_resp.json()
    knowledge_check_body = knowledge_check_resp.json()

    assert (
        detail_body["data"]["voice_policy_snapshot"]["runtime_metrics"][
            "knowledge_retrieval"
        ]["recent_attempts"][0]["query"]
        == "ROI 案例"
    )
    assert knowledge_check_body["success"] is True
    assert knowledge_check_body["data"]["status"] == "search_failed"
    assert (
        knowledge_check_body["data"]["summary"]
        == "知识检索触发失败，请检查知识库或 Embedding 服务"
    )
    assert knowledge_check_body["data"]["last_status"] == "search_failed"
    assert knowledge_check_body["data"]["last_query"] == "ROI 案例"
    assert (
        knowledge_check_body["data"]["last_error"]
        == "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout"
    )


@pytest.mark.asyncio
async def test_knowledge_check_reports_kb_not_ready_status(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Knowledge-check diagnostics should surface kb_not_ready status from runtime metrics."""
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
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {
        "enable_internal_retrieval": True,
    }
    snapshot["knowledge_base_ids"] = ["kb_test_1"]
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 2,
            "hit_query_count": 0,
            "total_results": 0,
            "last_result_count": 0,
            "hit_rate": 0.0,
            "last_query": "石犀产品目录",
            "last_status": "kb_not_ready",
            "recent_queries": ["石犀产品目录"],
        }
    }
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "kb_not_ready"
    assert body["data"]["summary"] == "知识库文档尚未处理完成"
    assert body["data"]["last_status"] == "kb_not_ready"
    assert body["data"]["attempt_count"] == 2
    assert body["data"]["knowledge_base_ids"] == ["kb_test_1"]


@pytest.mark.asyncio
async def test_knowledge_check_reports_live_coach_health_from_registered_session_handler(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Knowledge-check should surface live coach degraded/resumed state on the current runtime route."""
    _, agent, persona = await _create_runtime_entities(test_db)

    create_resp = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "voice_mode": "legacy",
        },
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["data"]["session_id"]

    handler = SimpleNamespace(
        get_runtime_diagnostics=lambda: {
            "claim_truth": None,
            "coach_health": {
                "status": "degraded",
                "reason": "capability_pipeline_failed",
                "message": "实时辅导暂不可用，训练仍可继续。",
            },
        },
        _latest_claim_truth=None,
    )
    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler)
    try:
        resp = await async_client.get(
            f"/api/v1/practice/sessions/{session_id}/knowledge-check",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["coach_health"] == {
            "status": "degraded",
            "reason": "capability_pipeline_failed",
            "message": "实时辅导暂不可用，训练仍可继续。",
        }
        assert body["data"]["coach_health_status"] == "degraded"
        assert body["data"]["coach_health_reason"] == "capability_pipeline_failed"
        assert body["data"]["coach_health_summary"] == "实时辅导暂不可用，训练仍可继续。"
    finally:
        await session_manager.unregister_session(session_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_knowledge_check_reports_kb_lock_unbound_status(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """Knowledge-check should surface kb lock diagnostics when lock is enabled but KB unbound."""
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
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {
        "enable_internal_retrieval": True,
        "require_kb_grounding": True,
    }
    snapshot["knowledge_base_ids"] = []
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["kb_lock_required"] is True
    assert body["data"]["kb_lock_status"] == "blocked_no_kb"
    assert body["data"]["require_kb_grounding"] is True


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


# ---------------------------------------------------------------------------
# S02: retrieval_facts parity integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_sales_session_returns_identical_retrieval_facts_through_report_and_knowledge_check(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """S02 parity: same completed session yields identical retrieval_facts via both routes."""
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
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {"enable_internal_retrieval": True}
    snapshot["knowledge_base_ids"] = ["kb_test_1", "kb_test_2"]
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 3,
            "hit_query_count": 2,
            "hit_rate": 0.6667,
            "recent_attempts": [
                {
                    "attempted_at": "2026-03-28T12:10:00Z",
                    "query": "ROI 回本案例",
                    "status": "hit",
                    "result_count": 2,
                    "retrieval_mode": "hybrid",
                    "knowledge_base_ids": ["kb_test_1"],
                    "result_summaries": [
                        {
                            "knowledge_base_id": "kb_test_1",
                            "knowledge_base_name": "Agent知识库",
                            "snippet": "客户A在6个月内实现ROI回本",
                            "score": 0.92,
                            "retrieval_mode": "vector",
                        },
                    ],
                },
                {
                    "attempted_at": "2026-03-28T12:05:00Z",
                    "query": "竞品对比",
                    "status": "miss",
                    "result_count": 0,
                    "retrieval_mode": "vector",
                    "knowledge_base_ids": ["kb_test_1"],
                    "result_summaries": [],
                },
                {
                    "attempted_at": "2026-03-28T12:00:00Z",
                    "query": "报价方案",
                    "status": "hit",
                    "result_count": 1,
                    "retrieval_mode": "keyword",
                    "knowledge_base_ids": ["kb_test_2"],
                    "result_summaries": [
                        {
                            "knowledge_base_id": "kb_test_2",
                            "knowledge_base_name": "Persona知识库",
                            "snippet": "标准报价方案：¥12,000/年",
                            "score": 0.88,
                            "retrieval_mode": "keyword",
                        },
                    ],
                },
            ],
        }
    }
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/report",
        headers=auth_headers,
    )
    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert report_resp.status_code == 200
    assert knowledge_check_resp.status_code == 200

    report_rf = report_resp.json()["data"]["effectiveness_snapshot"]["retrieval_facts"]
    kc_rf = knowledge_check_resp.json()["data"]["retrieval_facts"]

    assert report_rf is not None
    assert kc_rf is not None

    # Canonical fields must match exactly
    for key in (
        "kb_bound", "knowledge_base_ids", "knowledge_base_count",
        "retrieval_enabled", "status", "summary",
        "attempt_count", "hit_count", "hit_rate",
    ):
        assert report_rf[key] == kc_rf[key], f"retrieval_facts.{key} mismatch"

    # latest_attempt parity (preserves knowledge_base_ids and result_summaries)
    assert report_rf["latest_attempt"]["status"] == kc_rf["latest_attempt"]["status"]
    assert report_rf["latest_attempt"]["query"] == kc_rf["latest_attempt"]["query"]
    assert report_rf["latest_attempt"]["result_count"] == kc_rf["latest_attempt"]["result_count"]
    assert report_rf["latest_attempt"]["knowledge_base_ids"] == kc_rf["latest_attempt"]["knowledge_base_ids"]
    assert report_rf["latest_attempt"]["result_summaries"] == kc_rf["latest_attempt"]["result_summaries"]

    # recent_attempts count and structural parity
    assert len(report_rf["recent_attempts"]) == len(kc_rf["recent_attempts"]) == 3
    for i in range(3):
        assert report_rf["recent_attempts"][i] == kc_rf["recent_attempts"][i]


@pytest.mark.asyncio
async def test_retrieval_facts_hit_with_weak_evidence_claim_truth_proves_independence(
    async_client: AsyncClient,
    auth_headers: dict,
    test_db: AsyncSession,
):
    """retrieval_facts and claim_truth are orthogonal: retrieval hit + weak_evidence coexist on both surfaces."""
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
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {"enable_internal_retrieval": True}
    snapshot["knowledge_base_ids"] = ["kb_test_2"]
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": 1,
            "hit_query_count": 1,
            "hit_rate": 1.0,
            "recent_attempts": [
                {
                    "attempted_at": "2026-03-28T12:00:00Z",
                    "query": "产品报价",
                    "status": "hit",
                    "result_count": 2,
                    "retrieval_mode": "vector",
                    "knowledge_base_ids": ["kb_test_2"],
                    "result_summaries": [
                        {
                            "knowledge_base_id": "kb_test_2",
                            "knowledge_base_name": "Persona知识库",
                            "snippet": "标准报价方案：¥12,000/年",
                            "score": 0.91,
                            "retrieval_mode": "vector",
                        },
                    ],
                },
            ],
        }
    }
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/report",
        headers=auth_headers,
    )
    kc_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert report_resp.status_code == 200
    assert kc_resp.status_code == 200

    report_rf = report_resp.json()["data"]["effectiveness_snapshot"]["retrieval_facts"]
    kc_rf = kc_resp.json()["data"]["retrieval_facts"]

    # retrieval_facts shows "hit"
    assert report_rf["status"] == "hit"
    assert kc_rf["status"] == "hit"
    assert report_rf["latest_attempt"]["result_count"] > 0
    assert kc_rf["latest_attempt"]["result_count"] > 0

    # claim_truth is present and independent from retrieval_facts
    report_ct = report_resp.json()["data"]["effectiveness_snapshot"]["claim_truth"]
    kc_ct = kc_resp.json()["data"]["claim_truth"]
    assert isinstance(report_ct, dict), "report claim_truth should be present"
    assert isinstance(kc_ct, dict), "knowledge-check claim_truth should be present"
    assert "status" in report_ct
    assert "source" in kc_ct

    # Orthogonality proof: retrieval hit coexists with a distinct claim_truth status
    assert report_rf["status"] != report_ct["status"]
    assert kc_rf["status"] != kc_ct["status"]
