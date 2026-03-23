"""Integration tests for knowledge activation flow in sales sessions."""

from __future__ import annotations

import uuid
from copy import deepcopy

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession
from common.knowledge.models import KnowledgeBase, KnowledgeDocument


async def _create_runtime_entities(
    test_db: AsyncSession,
    *,
    persona_kb_ids: list[str] | None = None,
) -> tuple[VoiceRuntimeProfile, Agent, Persona]:
    profile = VoiceRuntimeProfile(
        id=str(uuid.uuid4()),
        name="知识链路测试实时配置",
        is_default=True,
        is_active=True,
        voice_mode="stepfun_realtime",
        model_name="step-audio-r1.1",
        voice_name="qingchunshaonv",
        temperature=0.7,
    )
    agent = Agent(
        id=str(uuid.uuid4()),
        name="知识链路销售Agent",
        description="用于知识库链路集成测试",
        category="sales",
        status="published",
        default_knowledge_base_ids=[],
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="知识链路客户角色",
        description="用于知识库链路集成测试",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是谨慎型采购经理。",
        knowledge_base_ids=persona_kb_ids or [],
    )
    agent_persona = AgentPersona(
        id=str(uuid.uuid4()),
        agent_id=agent.id,
        persona_id=persona.id,
        is_default=True,
        override_config={"challenge_frequency": 0.5},
    )
    test_db.add_all([profile, agent, persona, agent_persona])
    await test_db.commit()
    return profile, agent, persona


async def _create_knowledge_base_with_document(
    test_db: AsyncSession,
    *,
    doc_status: str = "ready",
) -> tuple[KnowledgeBase, KnowledgeDocument]:
    kb_id = str(uuid.uuid4())
    kb = KnowledgeBase(
        id=kb_id,
        name="石犀产品资料库",
        description="用于验证会话快照冻结的产品资料库",
        category="product",
        vector_collection=f"kb_{kb_id.replace('-', '_')}",
        embedding_model="text-embedding-v4",
        document_count=1,
        total_chunks=4 if doc_status == "ready" else 0,
        status="active",
    )
    document = KnowledgeDocument(
        id=str(uuid.uuid4()),
        knowledge_base_id=kb_id,
        title="石犀产品手册.xlsx",
        file_type="xlsx",
        file_url=f"/tmp/{kb_id}.xlsx",
        file_size=4096,
        status=doc_status,
        chunk_count=4 if doc_status == "ready" else 0,
        error_message=None if doc_status == "ready" else "Embedding failed",
    )
    test_db.add_all([kb, document])
    await test_db.commit()
    return kb, document


async def _create_sales_session(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    *,
    agent_id: str,
    persona_id: str,
) -> str:
    response = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent_id,
            "persona_id": persona_id,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    return body["data"]["session_id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_sales_session_freezes_kb_binding_for_next_session_only(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_db: AsyncSession,
):
    """Persona KB binding changes should affect only newly created sales sessions."""
    _, agent, persona = await _create_runtime_entities(test_db, persona_kb_ids=[])

    first_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=persona.id,
    )

    kb, _ = await _create_knowledge_base_with_document(test_db, doc_status="ready")
    persona.knowledge_base_ids = [kb.id]
    await test_db.commit()

    second_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=persona.id,
    )

    first_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == first_session_id)
        )
    ).scalar_one()
    second_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == second_session_id)
        )
    ).scalar_one()

    assert first_session.voice_policy_snapshot["knowledge_base_ids"] == []
    assert second_session.voice_policy_snapshot["knowledge_base_ids"] == [kb.id]

    first_check = await async_client.get(
        f"/api/v1/practice/sessions/{first_session_id}/knowledge-check",
        headers=auth_headers,
    )
    second_check = await async_client.get(
        f"/api/v1/practice/sessions/{second_session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert first_check.status_code == 200
    assert second_check.status_code == 200
    assert first_check.json()["data"]["status"] == "no_knowledge_base"
    assert second_check.json()["data"]["status"] == "not_triggered"
    assert second_check.json()["data"]["knowledge_base_ids"] == [kb.id]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("last_status", "last_error", "attempt_count", "hit_query_count", "expected_status", "expected_summary"),
    [
        (
            "hit",
            "",
            2,
            1,
            "hit",
            "知识检索已触发并命中知识库",
        ),
        (
            "miss",
            "",
            2,
            0,
            "miss",
            "知识检索已触发，但本次未命中有效内容",
        ),
        (
            "kb_not_ready",
            "",
            1,
            0,
            "kb_not_ready",
            "知识库文档尚未处理完成",
        ),
        (
            "search_failed",
            "[KNOWLEDGE_SEARCH_UNAVAILABLE] [EMBEDDING_API_ERROR]",
            1,
            0,
            "search_failed",
            "知识检索触发失败，请检查知识库或 Embedding 服务",
        ),
    ],
)
async def test_knowledge_check_distinguishes_runtime_statuses(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_db: AsyncSession,
    last_status: str,
    last_error: str,
    attempt_count: int,
    hit_query_count: int,
    expected_status: str,
    expected_summary: str,
):
    """Knowledge diagnostics should preserve hit/miss/not-ready/search-failed evidence."""
    kb, _ = await _create_knowledge_base_with_document(test_db, doc_status="ready")
    _, agent, persona = await _create_runtime_entities(test_db, persona_kb_ids=[kb.id])
    session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=persona.id,
    )

    session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
    ).scalar_one()
    snapshot = deepcopy(session.voice_policy_snapshot)
    snapshot["tool_policy"] = {
        "enable_internal_retrieval": True,
        "require_kb_grounding": True,
    }
    snapshot["knowledge_base_ids"] = [kb.id]
    snapshot["runtime_metrics"] = {
        "knowledge_retrieval": {
            "attempt_count": attempt_count,
            "hit_query_count": hit_query_count,
            "total_results": 2 if hit_query_count else 0,
            "last_result_count": 2 if hit_query_count else 0,
            "hit_rate": 0.5 if hit_query_count else 0.0,
            "last_query": "石犀产品资料",
            "last_status": last_status,
            "last_error": last_error,
            "recent_queries": ["石犀产品资料"],
        }
    }
    session.voice_policy_snapshot = snapshot
    session.status = "completed"
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session_id}/knowledge-check",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == expected_status
    assert body["data"]["summary"] == expected_summary
    assert body["data"]["last_status"] == last_status
    assert body["data"]["recent_queries"] == ["石犀产品资料"]
