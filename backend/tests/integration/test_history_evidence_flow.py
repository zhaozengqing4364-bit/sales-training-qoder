from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import Base, PracticeSession, Scenario, SessionStatus, User
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_effectiveness_snapshot(
    *, evaluable: bool, reason: str | None
) -> dict[str, object]:
    return {
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "main_capability_passed": evaluable,
        "overall_result": "pass" if evaluable else "fail",
        "metrics": {
            "continuous_speech_seconds": 0.0,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0.0,
            "offtopic_max_streak": 0.0,
            "structure_coverage": 0.0,
        },
        "main_issue": {
            "issue_type": "main_capability_not_passed",
            "issue_text": "证据不足，当前无法评估。" if not evaluable else "继续保持。",
            "recovery_rule": "补齐有效互动后再结束。"
            if not evaluable
            else "保持当前节奏。",
        },
        "next_goal": {
            "goal_type": "main_capability_focus",
            "goal_text": "先完成一轮有效互动再评估。"
            if not evaluable
            else "维持当前表现。",
            "rule": "补齐用户表达和AI回应后再结束。"
            if not evaluable
            else "继续按当前节奏推进。",
        },
        "version": "rule_v1",
        "evaluable": evaluable,
        "not_evaluable_reason": reason,
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
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"history-user-{uuid.uuid4().hex[:8]}",
        name="History Evidence User",
        email=f"history_evidence_{uuid.uuid4().hex[:6]}@example.com",
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
async def test_history_statistics_and_trends_share_same_session_evidence_projection(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    sales_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="销售训练",
        is_active=True,
    )
    presentation_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="演讲训练",
        is_active=True,
    )

    legacy_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=sales_scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC) - timedelta(days=3),
        total_duration_seconds=96,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=None,
    )
    no_evidence_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=sales_scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC) - timedelta(days=2),
        total_duration_seconds=0,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=False,
            reason="INSUFFICIENT_TURN_DATA",
        ),
    )
    presentation_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=presentation_scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC) - timedelta(days=1),
        total_duration_seconds=180,
        logic_score=90.0,
        accuracy_score=84.0,
        completeness_score=87.0,
        effectiveness_snapshot=_make_effectiveness_snapshot(
            evaluable=True,
            reason=None,
        ),
    )

    db_session.add_all(
        [
            sales_scenario,
            presentation_scenario,
            legacy_session,
            no_evidence_session,
            presentation_session,
        ]
    )
    db_session.add_all(
        [
            ConversationMessage(
                session_id=legacy_session.session_id,
                turn_number=1,
                role="user",
                content="我们最近线索转化掉得很厉害。",
                timestamp=legacy_session.start_time,
                duration_ms=2100,
                sales_stage="opening",
                score_snapshot={"overall": 74},
                ai_feedback="先确认当前漏斗现状",
            ),
            ConversationMessage(
                session_id=legacy_session.session_id,
                turn_number=2,
                role="assistant",
                content="主要卡在需求确认和预算环节。",
                timestamp=legacy_session.start_time + timedelta(seconds=2),
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

    evidence_service = SessionEvidenceService(db_session)
    legacy_projection_result = await evidence_service.get_projection(
        session_id=legacy_session.session_id,
        require_completed=True,
    )
    no_evidence_projection_result = await evidence_service.get_projection(
        session_id=no_evidence_session.session_id,
        require_completed=True,
    )
    presentation_projection_result = await evidence_service.get_projection(
        session_id=presentation_session.session_id,
        require_completed=True,
    )

    assert legacy_projection_result.is_success
    assert no_evidence_projection_result.is_success
    assert presentation_projection_result.is_success

    legacy_projection = legacy_projection_result.value
    no_evidence_projection = no_evidence_projection_result.value
    presentation_projection = presentation_projection_result.value

    history_resp = await async_client.get(
        "/api/v1/users/me/history?page=1&page_size=10&scenario_type=sales_bot",
        headers=auth_headers,
    )
    analytics_history_resp = await async_client.get(
        "/api/v1/analytics/practice/history?scenario_type=sales_bot&limit=10&offset=0",
        headers=auth_headers,
    )
    stats_resp = await async_client.get(
        "/api/v1/practice/history/statistics",
        headers=auth_headers,
    )
    trends_resp = await async_client.get(
        "/api/v1/practice/history/trends?days=30",
        headers=auth_headers,
    )
    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{legacy_session.session_id}/report",
        headers=auth_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{legacy_session.session_id}/replay",
        headers=auth_headers,
    )

    assert history_resp.status_code == 200
    assert analytics_history_resp.status_code == 200
    assert stats_resp.status_code == 200
    assert trends_resp.status_code == 200
    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200

    history_data = history_resp.json()["data"]
    analytics_history_data = analytics_history_resp.json()
    stats_data = stats_resp.json()
    trends_data = trends_resp.json()["trends"]
    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]

    history_by_id = {item["session_id"]: item for item in history_data["sessions"]}
    analytics_history_by_id = {
        item["session_id"]: item for item in analytics_history_data["items"]
    }

    assert set(history_by_id) == {
        legacy_session.session_id,
        no_evidence_session.session_id,
    }
    assert set(analytics_history_by_id) == {
        legacy_session.session_id,
        no_evidence_session.session_id,
    }

    legacy_history_item = history_by_id[legacy_session.session_id]
    assert legacy_history_item["overall_score"] == pytest.approx(
        legacy_projection.overall_score
    )
    assert legacy_history_item["evaluable"] is True
    assert legacy_history_item["not_evaluable_reason"] is None
    assert (
        legacy_history_item["evidence_completeness"]
        == legacy_projection.evidence_completeness
    )
    assert legacy_history_item["evidence_completeness"]["legacy_score_key_used"] is True

    no_evidence_history_item = history_by_id[no_evidence_session.session_id]
    assert no_evidence_history_item["overall_score"] == pytest.approx(
        no_evidence_projection.overall_score
    )
    assert no_evidence_history_item["evaluable"] is False
    assert (
        no_evidence_history_item["not_evaluable_reason"]
        == no_evidence_projection.not_evaluable_reason
        == "INSUFFICIENT_TURN_DATA"
    )

    assert analytics_history_by_id[legacy_session.session_id][
        "overall_score"
    ] == pytest.approx(legacy_projection.overall_score)
    assert analytics_history_by_id[legacy_session.session_id]["evaluable"] is True
    assert analytics_history_by_id[no_evidence_session.session_id]["evaluable"] is False

    assert (
        report_data["overall_score"]
        == replay_data["overall_score"]
        == pytest.approx(legacy_projection.overall_score)
    )
    assert legacy_history_item["overall_score"] == pytest.approx(
        report_data["overall_score"]
    )
    assert legacy_history_item["overall_score"] == pytest.approx(
        replay_data["overall_score"]
    )

    assert stats_data == {
        "total_sessions": 3,
        "evaluable_sessions": 2,
        "not_evaluable_sessions": 1,
        "average_score": 84.5,
        "best_score": 87.0,
        "score_basis": "session_evidence_projection_evaluable_only",
        "total_practice_time_seconds": 276,
        "total_practice_time_minutes": 4.6,
    }

    assert [point["session_id"] for point in trends_data] == [
        legacy_session.session_id,
        presentation_session.session_id,
    ]
    assert [point["overall_score"] for point in trends_data] == [
        legacy_projection.overall_score,
        presentation_projection.overall_score,
    ]
    assert all(point["evaluable"] is True for point in trends_data)
