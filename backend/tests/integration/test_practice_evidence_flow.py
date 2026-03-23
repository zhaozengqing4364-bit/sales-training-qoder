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
        wechat_user_id=f"flow-user-{uuid.uuid4().hex[:8]}",
        name="Evidence Flow User",
        email=f"evidence_flow_{uuid.uuid4().hex[:6]}@example.com",
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
async def test_completed_session_report_and_replay_share_legacy_projection_fallback(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="evidence fallback scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        total_duration_seconds=96,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=None,
    )
    db_session.add_all([scenario, session])
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.session_id,
                turn_number=1,
                role="user",
                content="我们最近线索转化掉得很厉害。",
                timestamp=datetime.now(UTC),
                duration_ms=2100,
                sales_stage="opening",
                score_snapshot={"overall": 74},
                ai_feedback="先确认当前漏斗现状",
            ),
            ConversationMessage(
                session_id=session.session_id,
                turn_number=2,
                role="assistant",
                content="主要卡在需求确认和预算环节。",
                timestamp=datetime.now(UTC),
                duration_ms=2600,
                sales_stage="discovery",
                score_snapshot={
                    "overall_score": 89,
                    "dimension_scores": {
                        "professional": 88,
                        "communication": 82,
                        "discovery": 76,
                    },
                },
                ai_feedback="继续追问预算和决策链",
            ),
        ]
    )
    await db_session.commit()

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=auth_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    assert report_data["logic_score"] == pytest.approx(88.0)
    assert report_data["accuracy_score"] == pytest.approx(82.0)
    assert report_data["completeness_score"] == pytest.approx(76.0)
    assert report_data["overall_score"] == pytest.approx(82.0)
    assert replay_data["overall_score"] == pytest.approx(82.0)

    assert report_data["stage_summary"] == replay_data["stage_summary"] == [
        {"stage": "opening", "duration_ms": 2100, "score": 74},
        {"stage": "discovery", "duration_ms": 2600, "score": 89},
    ]
    assert replay_data["messages"][0]["score_snapshot"]["overall_score"] == 74.0
    assert replay_data["messages"][0]["score_snapshot"].get("overall") is None
    assert replay_data["messages"][1]["score_snapshot"]["overall_score"] == 89.0
    assert report_data["evaluable"] is True
    assert replay_data["evaluable"] is True
    assert report_data["not_evaluable_reason"] is None
    assert replay_data["not_evaluable_reason"] is None
    assert report_data["evidence_completeness"] == replay_data["evidence_completeness"]
    assert report_data["main_issue"] == replay_data["main_issue"]
    assert report_data["next_goal"] == replay_data["next_goal"]
