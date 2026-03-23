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


def _sales_effectiveness_snapshot() -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": False,
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
            "goal_type": "evidence_then_next_step",
            "goal_text": "补上一条案例或 ROI 证据，并确认下一步动作。",
            "rule": "至少引用一条证据，并明确约定下一步。",
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
async def test_user(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"sales-flow-user-{uuid.uuid4().hex[:8]}",
        name="Sales Value User",
        email=f"sales_value_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User):
    token = create_access_token(data={"sub": str(test_user.user_id)})
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
async def test_report_api_surfaces_sales_rollups_main_issue_and_next_goal(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="sales value training scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        total_duration_seconds=240,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        effectiveness_snapshot=_sales_effectiveness_snapshot(),
        voice_policy_snapshot={
            "voice_mode": "stepfun_realtime",
            "knowledge_base_ids": ["kb-sales-1"],
            "persona_policy": {
                "sales_focus": "把产品价值翻译成客户收益，并处理价格 / ROI / 竞品异议",
            },
            "tool_policy": {
                "network_access_mode": "controlled",
            },
            "source": {"persona": "persona-1", "agent": "agent-1"},
            "resolved_at": "2026-03-23T00:00:00Z",
        },
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="听起来功能不少，但我还是没看到对 ROI 的直接帮助。",
                timestamp=datetime.now(UTC),
                duration_ms=1600,
                sales_stage="discovery",
                score_snapshot={"overall_score": 78},
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="我们能把线索流失率降低 18%，并有同业案例可参考。",
                timestamp=datetime.now(UTC),
                duration_ms=1900,
                sales_stage="objection",
                score_snapshot={"overall_score": 83},
            ),
        ]
    )
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]

    assert payload["logic_score"] == pytest.approx(80.0)
    assert payload["accuracy_score"] == pytest.approx(69.5)
    assert payload["completeness_score"] == pytest.approx(71.5)
    assert payload["overall_score"] == pytest.approx(73.67, abs=0.05)
    assert payload["main_issue"] == {
        "issue_type": "value_translation_gap",
        "issue_text": "产品价值说得太功能化，还没有翻译成客户收益与 ROI。",
        "recovery_rule": "下一轮先把价值翻译成客户收益，再回应价格与竞品问题。",
    }
    assert payload["next_goal"] == {
        "goal_type": "evidence_then_next_step",
        "goal_text": "补上一条案例或 ROI 证据，并确认下一步动作。",
        "rule": "至少引用一条证据，并明确约定下一步。",
    }
    assert payload["pass_flags"] == {
        "pass_3min_flow": False,
        "pass_5turn_defense": True,
        "pass_4step_structure": False,
    }
    assert payload["overall_result"] == "fail"
    assert payload["evaluable"] is True
    assert payload["not_evaluable_reason"] is None
    assert payload["voice_policy_snapshot_ref"]["voice_mode"] == "stepfun_realtime"
    assert payload["voice_policy_snapshot_ref"]["knowledge_base_ids"] == ["kb-sales-1"]
    assert payload["retry_entry"] == {
        "scenario_type": "sales",
        "agent_id": None,
        "persona_id": None,
        "presentation_id": None,
    }
    assert payload["stage_summary"] == [
        {"stage": "discovery", "duration_ms": 1600, "score": 78},
        {"stage": "objection", "duration_ms": 1900, "score": 83},
    ]
