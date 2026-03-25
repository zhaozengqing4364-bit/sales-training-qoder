from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import Base, PracticeSession, Scenario, SessionStatus, User
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_effectiveness_snapshot(*, evaluable: bool, reason: str | None) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 78.0,
            "customer_benefit_score": 72.0,
            "evidence_usage_score": 54.0,
            "objection_handling_score": 76.0,
            "next_step_score": 68.0,
            "value_articulation_rollup": 75.6,
            "evidence_benefit_rollup": 62.1,
            "objection_progress_rollup": 72.8,
        },
        "main_issue": {
            "issue_type": "evidence_gap",
            "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
            "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
        },
        "next_goal": {
            "goal_type": "evidence_backing",
            "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
            "rule": "至少补上一条证据和一个明确的下一步动作。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
    }


def _make_stale_sales_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "metrics": {
            "value_expression_score": 82.0,
            "customer_benefit_score": 78.0,
            "evidence_usage_score": 61.0,
            "objection_handling_score": 74.0,
            "next_step_score": 69.0,
            "value_articulation_rollup": 80.0,
            "evidence_benefit_rollup": 69.5,
            "objection_progress_rollup": 71.5,
        },
        "main_issue": {
            "issue_type": "value_translation_gap",
            "issue_text": "产品价值说得太功能化，还没有翻译成客户收益与 ROI。",
            "recovery_rule": "下一轮先把价值翻译成客户收益，再回应价格与竞品问题。",
        },
        "next_goal": {
            "goal_type": "value_to_benefit_translation",
            "goal_text": "先把产品价值翻译成客户收益，再进入方案说明。",
            "rule": "至少说清一个客户场景、一个收益指标、一个量化变化。",
        },
        "version": "rule_v1",
        "evaluable": True,
        "not_evaluable_reason": None,
    }


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"contract-owner-{uuid.uuid4().hex[:8]}",
        name="Contract Owner",
        email=f"contract_owner_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def outsider(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"contract-outsider-{uuid.uuid4().hex[:8]}",
        name="Contract Outsider",
        email=f"contract_outsider_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner: User):
    token = create_access_token(data={"sub": str(owner.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def outsider_headers(outsider: User):
    token = create_access_token(data={"sub": str(outsider.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_report_and_replay_contract_share_same_session_evidence_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract evidence scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=75.6,
        accuracy_score=62.1,
        completeness_score=72.8,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        ),
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我先介绍一下我们现在的跟进流程。",
                timestamp=datetime.now(UTC),
                duration_ms=1200,
                sales_stage="opening",
                score_snapshot={"overall": 76},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="目前主要痛点是线索流失。",
                timestamp=datetime.now(UTC),
                duration_ms=1800,
                sales_stage="discovery",
                score_snapshot={"overall_score": 84},
            ),
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert report_data["overall_score"] == replay_data["overall_score"] == pytest.approx(70.2, abs=0.05)
    assert report_data["logic_score"] == pytest.approx(75.6)
    assert report_data["accuracy_score"] == pytest.approx(62.1)
    assert report_data["completeness_score"] == pytest.approx(72.8)
    assert report_data["main_issue"] == replay_data["main_issue"]
    assert report_data["next_goal"] == replay_data["next_goal"]
    assert report_data["main_issue"]["issue_type"] == "evidence_gap"
    assert report_data["next_goal"]["goal_type"] == "evidence_backing"
    assert report_data["not_evaluable_reason"] == replay_data["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"
    assert report_data["evaluable"] is False
    assert replay_data["evaluable"] is False
    assert report_data["stage_summary"] == replay_data["stage_summary"] == [
        {"stage": "opening", "duration_ms": 1200, "score": 76},
        {"stage": "discovery", "duration_ms": 1800, "score": 84},
    ]
    assert report_data["evidence_completeness"]["legacy_score_key_used"] is True
    assert replay_data["evidence_completeness"]["legacy_score_key_used"] is True


@pytest.mark.asyncio
async def test_report_and_replay_contract_override_stale_sales_snapshot_with_aligned_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract stale alignment scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="ROI 这一块你们有真实案例吗？",
                timestamp=datetime.now(UTC),
                duration_ms=1600,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 82.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 80.0,
                        "证据使用": 58.0,
                        "异议处理": 76.0,
                        "推进下一步": 72.0,
                    },
                },
            )
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert report_data["main_issue"] == replay_data["main_issue"] == {
        "issue_type": "evidence_gap",
        "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
        "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
    }
    assert report_data["next_goal"] == replay_data["next_goal"] == {
        "goal_type": "evidence_backing",
        "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
        "rule": "至少补上一条证据和一个明确的下一步动作。",
    }


@pytest.mark.asyncio
async def test_knowledge_check_keeps_claim_truth_distinct_from_kb_lock_chain_failures(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract runtime truth scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        total_duration_seconds=180,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
        voice_policy_snapshot={
            "knowledge_base_ids": ["kb-truth-1"],
            "tool_policy": {
                "enable_internal_retrieval": True,
                "require_kb_grounding": True,
            },
            "runtime_metrics": {
                "knowledge_retrieval": {
                    "attempt_count": 1,
                    "hit_query_count": 0,
                    "total_results": 0,
                    "last_status": "search_failed",
                    "last_error": "[KNOWLEDGE_SEARCH_UNAVAILABLE] embedding timeout",
                    "kb_lock_required": True,
                    "kb_lock_last_status": "blocked_search_failed",
                    "kb_lock_block_count": 1,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "kb_lock_updated_at": datetime.now(UTC).isoformat(),
                }
            },
        },
    )
    db_session.add_all([scenario, session])
    db_session.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="ROI 这一块你们有真实案例吗？",
            timestamp=datetime.now(UTC),
            duration_ms=1600,
            sales_stage="discovery",
            score_snapshot={
                "overall_score": 82.0,
                "dimension_scores": {
                    "价值表达": 84.0,
                    "客户收益连接": 80.0,
                    "证据使用": 58.0,
                    "异议处理": 76.0,
                    "推进下一步": 72.0,
                },
            },
        )
    )
    await db_session.commit()

    knowledge_check_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        headers=owner_headers,
    )

    assert knowledge_check_resp.status_code == 200
    knowledge_check_data = knowledge_check_resp.json()["data"]
    assert knowledge_check_data["kb_lock_status"] == "blocked_search_failed"
    assert knowledge_check_data["kb_lock_chain_failure"] is True
    assert knowledge_check_data["claim_truth"] == {
        "status": "weak_evidence",
        "label": "证据偏弱",
        "source": "score_snapshot",
        "reason": "low_evidence_score",
        "evidence_score": 58.0,
    }
    assert knowledge_check_data["claim_truth_status"] == "weak_evidence"
    assert knowledge_check_data["claim_truth_source"] == "score_snapshot"


@pytest.mark.asyncio
async def test_replay_completion_gate_and_report_access_control_remain_unchanged(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
    outsider_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="contract gate scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(owner.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS.value,
    )
    db_session.add_all([scenario, session])
    await db_session.commit()

    owner_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=owner_headers,
    )
    owner_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=owner_headers,
    )
    outsider_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=outsider_headers,
    )
    outsider_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=outsider_headers,
    )

    assert owner_report_resp.status_code == 200
    assert owner_replay_resp.status_code == 400
    assert owner_replay_resp.json()["error"] == "[SESSION_NOT_COMPLETED]"
    assert outsider_report_resp.status_code == 403
    assert outsider_report_resp.json()["error"] == "[ACCESS_DENIED]"
    assert outsider_replay_resp.status_code == 403
    assert outsider_replay_resp.json()["error"] == "[ACCESS_DENIED]"
