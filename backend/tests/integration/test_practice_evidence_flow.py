from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.conversation.session_evidence import SessionEvidenceService
from common.db.models import (
    Base,
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    SessionStatus,
    User,
)
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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


async def _create_runtime_entities(
    db_session: AsyncSession,
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
    db_session.add_all([profile, agent, persona, agent_persona])
    await db_session.commit()
    return profile, agent, persona


def _without_replay_anchor(value: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key != "replay_anchor"}


async def _create_presentation_review_session(
    db_session: AsyncSession,
    *,
    user: User,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="presentation evidence route family",
        is_active=True,
    )
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="共享回放课件",
        file_url="file:///tmp/presentation-evidence-flow.pptx",
        status="ready",
        version_number=3,
        total_pages=2,
        ocr_progress=1.0,
    )
    page_1 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="第一页业务目标与客户问题",
    )
    page_2 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=2,
        ocr_extracted_text="第二页ROI结果与客户案例",
    )
    talking_points = [
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_1.page_id,
            description="业务目标",
            created_by="admin",
            confirmed_by_admin=True,
        ),
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_2.page_id,
            description="客户案例",
            created_by="admin",
            confirmed_by_admin=True,
        ),
    ]
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(user.user_id),
        scenario_id=scenario.scenario_id,
        presentation_id=presentation.presentation_id,
        status=SessionStatus.COMPLETED.value,
        total_duration_seconds=12 * 60,
    )
    messages = [
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标。",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            transcript_metadata={"page_number": 1},
            score_snapshot={"overall_score": 86},
        ),
        ConversationMessage(
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content="第二页补 ROI 结果和客户案例。",
            timestamp=datetime.now(UTC),
            duration_ms=2200,
            transcript_metadata={"page_number": 2},
            score_snapshot={"overall_score": 90},
        ),
    ]
    db_session.add_all([
        scenario,
        presentation,
        page_1,
        page_2,
        session,
        *talking_points,
        *messages,
    ])
    await db_session.commit()
    return session


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
async def admin_user(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"flow-admin-{uuid.uuid4().hex[:8]}",
        name="Evidence Flow Admin",
        email=f"evidence_flow_admin_{uuid.uuid4().hex[:6]}@example.com",
        role="admin",
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
async def admin_headers(admin_user: User):
    token = create_access_token(data={"sub": str(admin_user.user_id)})
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
    assert _without_replay_anchor(report_data["main_issue"]) == _without_replay_anchor(
        replay_data["main_issue"]
    )
    assert _without_replay_anchor(report_data["next_goal"]) == _without_replay_anchor(
        replay_data["next_goal"]
    )


@pytest.mark.asyncio
async def test_report_history_admin_and_replay_routes_keep_session_evidence_as_canonical_read_model(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="canonical evidence route family",
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

    baseline_projection_result = await SessionEvidenceService(db_session).get_projection(
        session_id=session.session_id,
        require_completed=True,
    )
    assert baseline_projection_result.is_success
    baseline_projection = baseline_projection_result.value

    get_projection_calls: list[dict[str, object]] = []
    build_projection_calls: list[dict[str, object]] = []
    original_get_projection = SessionEvidenceService.get_projection
    original_build_projection = SessionEvidenceService.build_projection

    async def instrumented_get_projection(self, *args, **kwargs):
        session_id = kwargs.get("session_id")
        if session_id is None and args:
            session_id = args[0]
        get_projection_calls.append(
            {
                "session_id": str(session_id),
                "require_completed": bool(kwargs.get("require_completed", False)),
            }
        )
        return await original_get_projection(self, *args, **kwargs)

    def instrumented_build_projection(cls, *args, **kwargs):
        session_obj = kwargs.get("session") if kwargs else None
        messages = kwargs.get("messages") if kwargs else None
        if session_obj is None and args:
            session_obj = args[0]
        if messages is None and len(args) > 1:
            messages = args[1]
        scenario_type = kwargs.get("scenario_type") if kwargs else None
        build_projection_calls.append(
            {
                "session_id": str(session_obj.session_id),
                "message_count": len(messages),
                "scenario_type": scenario_type,
            }
        )
        return original_build_projection(
            session_obj,
            messages,
            scenario_type=scenario_type,
        )

    monkeypatch.setattr(
        SessionEvidenceService,
        "get_projection",
        instrumented_get_projection,
    )
    monkeypatch.setattr(
        SessionEvidenceService,
        "build_projection",
        classmethod(instrumented_build_projection),
    )

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )
    replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=auth_headers,
    )
    history_resp = await async_client.get(
        "/api/v1/users/me/history?page=1&page_size=10&scenario_type=sales_bot",
        headers=auth_headers,
    )
    admin_resp = await async_client.get(
        f"/api/v1/admin/users/{test_user.user_id}/sessions?page=1&page_size=10",
        headers=admin_headers,
    )

    assert report_resp.status_code == 200
    assert replay_resp.status_code == 200
    assert history_resp.status_code == 200
    assert admin_resp.status_code == 200

    report_data = report_resp.json()["data"]
    replay_data = replay_resp.json()["data"]
    history_item = next(
        item
        for item in history_resp.json()["data"]["sessions"]
        if item["session_id"] == session.session_id
    )
    admin_item = next(
        item
        for item in admin_resp.json()["data"]["items"]
        if item["session_id"] == session.session_id
    )

    assert report_data["overall_score"] == pytest.approx(baseline_projection.overall_score)
    assert replay_data["overall_score"] == pytest.approx(baseline_projection.overall_score)
    assert history_item["overall_score"] == pytest.approx(baseline_projection.overall_score)
    assert admin_item["scores"]["overall"] == pytest.approx(baseline_projection.overall_score)

    assert report_data["evaluable"] is replay_data["evaluable"] is history_item["evaluable"]
    assert history_item["evaluable"] is admin_item["evaluable"] is True
    assert report_data["not_evaluable_reason"] is None
    assert replay_data["not_evaluable_reason"] is None
    assert history_item["not_evaluable_reason"] is None
    assert admin_item["not_evaluable_reason"] is None

    assert report_data["evidence_completeness"] == baseline_projection.evidence_completeness
    assert replay_data["evidence_completeness"] == baseline_projection.evidence_completeness
    assert history_item["evidence_completeness"] == baseline_projection.evidence_completeness
    assert admin_item["evidence_completeness"] == baseline_projection.evidence_completeness

    assert _without_replay_anchor(report_data["main_issue"]) == baseline_projection.main_issue
    assert _without_replay_anchor(replay_data["main_issue"]) == baseline_projection.main_issue
    assert history_item["main_issue"] == baseline_projection.main_issue
    assert admin_item["main_issue"] == baseline_projection.main_issue

    assert _without_replay_anchor(report_data["next_goal"]) == baseline_projection.next_goal
    assert _without_replay_anchor(replay_data["next_goal"]) == baseline_projection.next_goal
    assert history_item["next_goal"] == baseline_projection.next_goal
    assert admin_item["next_goal"] == baseline_projection.next_goal

    assert {
        call["session_id"]
        for call in get_projection_calls
    } == {session.session_id}
    assert any(call["require_completed"] is False for call in get_projection_calls)
    assert any(call["require_completed"] is True for call in get_projection_calls)

    canonical_build_calls = [
        call
        for call in build_projection_calls
        if call["session_id"] == session.session_id
    ]
    assert len(canonical_build_calls) >= 4
    assert all(call["message_count"] == 2 for call in canonical_build_calls)


@pytest.mark.asyncio
async def test_completed_session_report_and_replay_override_stale_sales_snapshot(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="evidence alignment scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        total_duration_seconds=180,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
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
            ai_feedback="补充案例和 ROI 数据",
        )
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

    assert _without_replay_anchor(report_data["main_issue"]) == _without_replay_anchor(
        replay_data["main_issue"]
    ) == {
        "issue_type": "evidence_gap",
        "issue_text": "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
        "recovery_rule": "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
    }
    assert _without_replay_anchor(report_data["next_goal"]) == _without_replay_anchor(
        replay_data["next_goal"]
    ) == {
        "goal_type": "evidence_backing",
        "goal_text": "先用案例、数据或ROI证据支撑主张，再推进下一步。",
        "rule": "至少补上一条证据和一个明确的下一步动作。",
    }
    assert report_data["effectiveness_snapshot"]["main_issue"]["issue_type"] == "evidence_gap"
    assert replay_data["effectiveness_snapshot"]["main_issue"]["issue_type"] == "evidence_gap"


@pytest.mark.asyncio
async def test_create_session_persists_retry_focus_intent_from_report_retry_entry(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    _, agent, persona = await _create_runtime_entities(db_session)
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="retry focus source scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        total_duration_seconds=180,
        logic_score=80.0,
        accuracy_score=69.5,
        completeness_score=71.5,
        effectiveness_snapshot=_make_stale_sales_snapshot(),
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

    report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )
    assert report_resp.status_code == 200
    focus_intent = report_resp.json()["data"]["retry_entry"]["focus_intent"]

    create_resp = await async_client.post(
        "/api/v1/practice/sessions",
        headers=auth_headers,
        json={
            "scenario_type": "sales",
            "agent_id": agent.id,
            "persona_id": persona.id,
            "focus_intent": focus_intent,
        },
    )

    assert create_resp.status_code == 201
    create_data = create_resp.json()["data"]
    assert create_data["voice_policy_snapshot"]["focus_intent"] == focus_intent

    persisted = (
        await db_session.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == create_data["session_id"]
            )
        )
    ).scalar_one()
    assert persisted.voice_policy_snapshot["focus_intent"] == focus_intent


@pytest.mark.asyncio
async def test_completed_presentation_report_and_replay_share_ppt_route_family(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    session = await _create_presentation_review_session(
        db_session,
        user=test_user,
    )

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

    assert report_data["scenario_type"] == replay_data["scenario_type"] == "presentation"
    assert replay_data["presentation_id"] == session.presentation_id
    assert report_data["retry_entry"] == {
        "scenario_type": "presentation",
        "agent_id": None,
        "persona_id": None,
        "presentation_id": session.presentation_id,
    }
    assert report_data["presentation_review"] == replay_data["presentation_review"]
    assert report_data["evidence_completeness"] == replay_data["evidence_completeness"]
    assert report_data["main_issue"] is None
    assert report_data["next_goal"] is None
    assert replay_data["main_issue"] is None
    assert replay_data["next_goal"] is None
    assert replay_data["evaluable"] is None
    assert replay_data["not_evaluable_reason"] is None


@pytest.mark.asyncio
async def test_same_session_sales_report_survives_scoring_and_completed_replay_reuses_same_projection_family(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="same session scoring parity scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.SCORING.value,
        total_duration_seconds=180,
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

    scoring_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )
    scoring_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=auth_headers,
    )

    assert scoring_report_resp.status_code == 200
    assert scoring_replay_resp.status_code == 400
    assert scoring_replay_resp.json()["error"] == "[SESSION_NOT_COMPLETED]"

    session.status = SessionStatus.COMPLETED.value
    await db_session.commit()
    await db_session.refresh(session)

    completed_report_resp = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=auth_headers,
    )
    completed_replay_resp = await async_client.get(
        f"/api/v1/sessions/{session.session_id}/replay",
        headers=auth_headers,
    )

    assert completed_report_resp.status_code == 200
    assert completed_replay_resp.status_code == 200

    scoring_report_data = scoring_report_resp.json()["data"]
    completed_report_data = completed_report_resp.json()["data"]
    completed_replay_data = completed_replay_resp.json()["data"]

    assert scoring_report_data["overall_score"] == pytest.approx(82.0)
    assert completed_report_data["overall_score"] == completed_replay_data["overall_score"] == pytest.approx(82.0)
    assert completed_report_data["stage_summary"] == completed_replay_data["stage_summary"] == [
        {"stage": "opening", "duration_ms": 2100, "score": 74},
        {"stage": "discovery", "duration_ms": 2600, "score": 89},
    ]
    assert completed_report_data["evidence_completeness"] == completed_replay_data["evidence_completeness"]
    assert _without_replay_anchor(completed_report_data["main_issue"]) == _without_replay_anchor(
        completed_replay_data["main_issue"]
    )
    assert _without_replay_anchor(completed_report_data["next_goal"]) == _without_replay_anchor(
        completed_replay_data["next_goal"]
    )
