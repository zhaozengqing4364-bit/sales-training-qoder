"""Integration tests for knowledge activation flow in sales sessions."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.db.models import PracticeSession
from common.knowledge.models import KnowledgeBase, KnowledgeDocument


def _build_customer_pressure_policy(
    *,
    sales_focus: str,
    value_axes: list[str],
    objection_axes: list[str],
    expected_questions: list[str],
    question_strategy: str = "single_issue",
    revisit_on_evasion: bool = True,
    require_evidence: bool = True,
) -> dict[str, Any]:
    return {
        "system_prompt": "你是谨慎型采购经理。",
        "customer_pressure": {
            "source": "explicit",
            "pressure_direction": {
                "sales_focus": sales_focus,
                "value_axes": value_axes,
                "objection_axes": objection_axes,
            },
            "follow_up_behavior": {
                "question_strategy": question_strategy,
                "revisit_on_evasion": revisit_on_evasion,
                "require_evidence": require_evidence,
                "expected_customer_questions": expected_questions,
            },
        },
    }


async def _create_runtime_entities(
    test_db: AsyncSession,
    *,
    persona_kb_ids: list[str] | None = None,
    persona_name: str = "知识链路客户角色",
    persona_policy: dict[str, Any] | None = None,
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
        name=persona_name,
        description="用于知识库链路集成测试",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是谨慎型采购经理。",
        knowledge_base_ids=persona_kb_ids or [],
        persona_policy=persona_policy,
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
async def test_new_sales_session_freezes_customer_pressure_contract_per_persona(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_db: AsyncSession,
):
    """Sessions should freeze one explicit customer-pressure contract per persona on the snapshot."""
    kb, _ = await _create_knowledge_base_with_document(test_db, doc_status="ready")
    _, agent, proof_persona = await _create_runtime_entities(
        test_db,
        persona_kb_ids=[kb.id],
        persona_name="证据压测角色",
        persona_policy=_build_customer_pressure_policy(
            sales_focus="proof",
            value_axes=["ROI", "客户收益"],
            objection_axes=["价格", "实施风险"],
            expected_questions=["你拿什么证明这个 ROI 不是口号？"],
            revisit_on_evasion=True,
            require_evidence=True,
        ),
    )

    price_persona = Persona(
        id=str(uuid.uuid4()),
        name="价格压测角色",
        description="用于冻结不同 pressure contract",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是压价型采购经理。",
        knowledge_base_ids=[kb.id],
        persona_policy=_build_customer_pressure_policy(
            sales_focus="price",
            value_axes=["预算优先级"],
            objection_axes=["价格", "竞品替代"],
            expected_questions=["如果预算卡死，你怎么证明这笔钱值？"],
            revisit_on_evasion=False,
            require_evidence=True,
        ),
    )
    test_db.add(
        AgentPersona(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            persona_id=price_persona.id,
            is_default=False,
            override_config={"challenge_frequency": 0.8},
        )
    )
    test_db.add(price_persona)
    await test_db.commit()

    proof_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=proof_persona.id,
    )
    price_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=price_persona.id,
    )

    proof_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == proof_session_id)
        )
    ).scalar_one()
    price_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == price_session_id)
        )
    ).scalar_one()

    proof_snapshot = deepcopy(proof_session.voice_policy_snapshot)
    price_snapshot = deepcopy(price_session.voice_policy_snapshot)

    assert proof_snapshot["knowledge_base_ids"] == [kb.id]
    assert price_snapshot["knowledge_base_ids"] == [kb.id]
    assert proof_snapshot["customer_pressure"]["pressure_direction"]["sales_focus"] == "proof"
    assert price_snapshot["customer_pressure"]["pressure_direction"]["sales_focus"] == "price"
    assert proof_snapshot["customer_pressure"]["follow_up_behavior"]["revisit_on_evasion"] is True
    assert price_snapshot["customer_pressure"]["follow_up_behavior"]["revisit_on_evasion"] is False
    assert proof_snapshot["source"]["customer_pressure_source"] == "explicit"
    assert price_snapshot["source"]["customer_pressure_source"] == "explicit"
    assert proof_snapshot["persona_policy"]["customer_pressure"] == proof_snapshot["customer_pressure"]
    assert price_snapshot["persona_policy"]["customer_pressure"] == price_snapshot["customer_pressure"]
    assert proof_snapshot["instruction_contract_hash"] != price_snapshot["instruction_contract_hash"]

    proof_persona.persona_policy = _build_customer_pressure_policy(
        sales_focus="budget_priority",
        value_axes=["预算优先级"],
        objection_axes=["价格"],
        expected_questions=["预算有限时你凭什么优先拿这笔钱？"],
        revisit_on_evasion=False,
        require_evidence=True,
    )
    await test_db.commit()

    refreshed_proof_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == proof_session_id)
        )
    ).scalar_one()
    assert refreshed_proof_session.voice_policy_snapshot["customer_pressure"] == proof_snapshot["customer_pressure"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_sales_session_freezes_competitor_and_implementation_pressure_contracts(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    test_db: AsyncSession,
):
    """Competitor and implementation-risk personas should freeze their own objection contracts."""
    kb, _ = await _create_knowledge_base_with_document(test_db, doc_status="ready")
    _, agent, _ = await _create_runtime_entities(test_db, persona_kb_ids=[kb.id])

    competitor_persona = Persona(
        id=str(uuid.uuid4()),
        name="竞品替代压测角色",
        description="用于冻结竞品替代 pressure contract",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是保守型采购负责人。",
        knowledge_base_ids=[kb.id],
        persona_policy=_build_customer_pressure_policy(
            sales_focus="replacement_risk",
            value_axes=["替代成本", "迁移收益"],
            objection_axes=["竞品替代", "价格"],
            expected_questions=["如果不换现有方案，损失到底是什么？"],
            revisit_on_evasion=True,
            require_evidence=True,
        ),
    )
    implementation_persona = Persona(
        id=str(uuid.uuid4()),
        name="实施风险压测角色",
        description="用于冻结实施风险 pressure contract",
        category="customer",
        difficulty="medium",
        status="active",
        system_prompt="你是谨慎型项目负责人。",
        knowledge_base_ids=[kb.id],
        persona_policy=_build_customer_pressure_policy(
            sales_focus="implementation_risk",
            value_axes=["上线稳定性"],
            objection_axes=["实施风险", "服务边界"],
            expected_questions=["谁来负责上线、排期和风险兜底？"],
            revisit_on_evasion=True,
            require_evidence=True,
        ),
    )
    test_db.add_all(
        [
            AgentPersona(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                persona_id=competitor_persona.id,
                is_default=False,
                override_config={"challenge_frequency": 0.8},
            ),
            AgentPersona(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                persona_id=implementation_persona.id,
                is_default=False,
                override_config={"challenge_frequency": 0.85},
            ),
            competitor_persona,
            implementation_persona,
        ]
    )
    await test_db.commit()

    competitor_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=competitor_persona.id,
    )
    implementation_session_id = await _create_sales_session(
        async_client,
        auth_headers,
        agent_id=agent.id,
        persona_id=implementation_persona.id,
    )

    competitor_session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == competitor_session_id
            )
        )
    ).scalar_one()
    implementation_session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == implementation_session_id
            )
        )
    ).scalar_one()

    competitor_snapshot = deepcopy(competitor_session.voice_policy_snapshot)
    implementation_snapshot = deepcopy(implementation_session.voice_policy_snapshot)

    assert competitor_snapshot["knowledge_base_ids"] == [kb.id]
    assert implementation_snapshot["knowledge_base_ids"] == [kb.id]
    assert (
        competitor_snapshot["customer_pressure"]["pressure_direction"]["sales_focus"]
        == "replacement_risk"
    )
    assert (
        implementation_snapshot["customer_pressure"]["pressure_direction"]["sales_focus"]
        == "implementation_risk"
    )
    assert competitor_snapshot["customer_pressure"]["pressure_direction"]["objection_axes"] == [
        "竞品替代",
        "价格",
    ]
    assert implementation_snapshot["customer_pressure"]["pressure_direction"]["objection_axes"] == [
        "实施风险",
        "服务边界",
    ]
    assert competitor_snapshot["customer_pressure"]["follow_up_behavior"][
        "expected_customer_questions"
    ] == ["如果不换现有方案，损失到底是什么？"]
    assert implementation_snapshot["customer_pressure"]["follow_up_behavior"][
        "expected_customer_questions"
    ] == ["谁来负责上线、排期和风险兜底？"]
    assert competitor_snapshot["source"]["customer_pressure_source"] == "explicit"
    assert implementation_snapshot["source"]["customer_pressure_source"] == "explicit"
    assert (
        competitor_snapshot["persona_policy"]["customer_pressure"]
        == competitor_snapshot["customer_pressure"]
    )
    assert (
        implementation_snapshot["persona_policy"]["customer_pressure"]
        == implementation_snapshot["customer_pressure"]
    )
    assert (
        competitor_snapshot["instruction_contract_hash"]
        != implementation_snapshot["instruction_contract_hash"]
    )

    competitor_persona.persona_policy = _build_customer_pressure_policy(
        sales_focus="budget_priority",
        value_axes=["预算优先级"],
        objection_axes=["价格"],
        expected_questions=["预算冻结时这笔钱为什么要先给你？"],
        revisit_on_evasion=False,
        require_evidence=True,
    )
    await test_db.commit()

    refreshed_competitor_session = (
        await test_db.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == competitor_session_id
            )
        )
    ).scalar_one()
    assert (
        refreshed_competitor_session.voice_policy_snapshot["customer_pressure"]
        == competitor_snapshot["customer_pressure"]
    )


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
