from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.analytics.admin_analytics_service import admin_analytics_service
from common.db.models import Base, PracticeSession, Scenario, User

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
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


def _make_effectiveness_snapshot(
    *,
    evaluable: bool,
    overall_result: str,
    issue_type: str,
    issue_text: str,
    goal_type: str,
    goal_text: str,
    not_evaluable_reason: str | None = None,
) -> dict[str, object]:
    return {
        "metrics": {
            "continuous_speech_seconds": 240,
            "filler_rate_per_100_words": 8.0,
            "offtopic_turn_count": 1,
            "offtopic_max_streak": 0,
            "structure_coverage": 0.6,
        },
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "main_capability_passed": evaluable,
        "overall_result": overall_result,
        "main_issue": {
            "issue_type": issue_type,
            "issue_text": issue_text,
            "recovery_rule": "下一轮先补齐证据。",
        },
        "next_goal": {
            "goal_type": goal_type,
            "goal_text": goal_text,
            "rule": "下一轮先完成一个完整动作。",
        },
        "evaluable": evaluable,
        "not_evaluable_reason": not_evaluable_reason,
    }


async def _create_user(
    db_session: AsyncSession,
    *,
    name: str,
    department: str,
    email: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"wechat_{uuid.uuid4().hex[:8]}",
        name=name,
        department=department,
        email=email,
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_sales_scenario(db_session: AsyncSession, *, name: str = "销售对练") -> Scenario:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=name,
        description="Admin analytics projection test",
        is_active=True,
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.mark.asyncio
async def test_overview_and_trends_use_projection_evaluability_not_legacy_weighting(
    db_session: AsyncSession,
) -> None:
    scenario = await _create_sales_scenario(db_session)
    evaluable_user = await _create_user(
        db_session,
        name="Projection User",
        department="Sales",
        email="projection-user@example.com",
    )
    not_evaluable_user = await _create_user(
        db_session,
        name="Need More Evidence",
        department="Sales",
        email="need-more-evidence@example.com",
    )

    now = datetime.now(timezone.utc)
    evaluable_start = now - timedelta(days=2)
    not_evaluable_start = now - timedelta(days=1)
    in_progress_start = now - timedelta(hours=2)

    db_session.add_all(
        [
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(evaluable_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=evaluable_start,
                end_time=evaluable_start + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=40,
                accuracy_score=50,
                completeness_score=60,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="objection_response",
                    issue_text="异议回应不够具体。",
                    goal_type="objection_response_drill",
                    goal_text="下一轮继续把异议回应说完整。",
                ),
            ),
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(not_evaluable_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=not_evaluable_start,
                end_time=not_evaluable_start + timedelta(minutes=1),
                total_duration_seconds=60,
                logic_score=95,
                accuracy_score=95,
                completeness_score=95,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=False,
                    overall_result="fail",
                    issue_type="insufficient_turn_data",
                    issue_text="当前互动不足，暂时无法判断真实问题。",
                    goal_type="collect_more_evidence",
                    goal_text="先补齐有效互动，再继续诊断。",
                    not_evaluable_reason="INSUFFICIENT_TURN_DATA",
                ),
            ),
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(evaluable_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="in_progress",
                start_time=in_progress_start,
                total_duration_seconds=120,
                logic_score=None,
                accuracy_score=None,
                completeness_score=None,
            ),
        ]
    )
    await db_session.commit()

    overview_result = await admin_analytics_service.get_overview_stats(
        db=db_session,
        time_range="30d",
        scenario_type="sales",
    )
    assert overview_result.is_success, overview_result.fallback
    overview = overview_result.value
    assert overview.total_sessions == 3
    assert overview.completed_sessions == 2
    assert overview.average_score == 50.0
    assert overview.evaluable_sessions == 1
    assert overview.not_evaluable_sessions == 1
    assert overview.score_basis == "session_evidence_projection_evaluable_only"
    assert overview.top_issue_families == [
        {
            "issue_type": "objection_response",
            "issue_text": "异议回应不够具体。",
            "count": 1,
        }
    ]
    assert overview.not_evaluable_reasons == [
        {
            "reason": "INSUFFICIENT_TURN_DATA",
            "count": 1,
        }
    ]

    trends_result = await admin_analytics_service.get_trends_data(
        db=db_session,
        time_range="30d",
        granularity="day",
    )
    assert trends_result.is_success, trends_result.fallback
    trends = trends_result.value
    assert trends["trend_data"] == [
        {
            "date": evaluable_start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "sessions_count": 1,
            "evaluable_session_count": 1,
            "not_evaluable_session_count": 0,
            "average_score": 50.0,
            "logic_score": 40.0,
            "accuracy_score": 50.0,
            "completeness_score": 60.0,
            "overall_result": "fail",
            "evaluable": True,
            "not_evaluable_reason": None,
            "main_issue": {
                "issue_type": "objection_response",
                "issue_text": "异议回应不够具体。",
                "recovery_rule": "下一轮先补齐证据。",
            },
            "next_goal": {
                "goal_type": "objection_response_drill",
                "goal_text": "下一轮继续把异议回应说完整。",
                "rule": "下一轮先完成一个完整动作。",
            },
            "stage_summary": [],
            "evidence_completeness": {
                "complete": True,
                "session_scores": True,
                "effectiveness_snapshot": True,
                "message_count": 0,
                "message_analysis": 0,
                "message_scores": 0,
                "stage_evidence": 0,
                "legacy_score_key_used": False,
                "missing_fields": [],
            },
            "active_users": 1,
        }
    ]
    assert trends["score_distribution"] == {
        "excellent": 0,
        "good": 0,
        "fair": 1,
        "poor": 0,
    }
    assert trends["projection_summary"] == {
        "completed_sessions": 2,
        "evaluable_sessions": 1,
        "not_evaluable_sessions": 1,
        "average_score": 50.0,
        "best_score": 50.0,
        "worst_score": 50.0,
        "repeated_main_issues": [],
        "repeated_next_goals": [],
        "issue_family_distribution": [
            {
                "issue_type": "objection_response",
                "issue_text": "异议回应不够具体。",
                "count": 1,
            }
        ],
        "not_evaluable_reasons": [
            {
                "reason": "INSUFFICIENT_TURN_DATA",
                "count": 1,
            }
        ],
        "score_basis": "session_evidence_projection_evaluable_only",
    }


@pytest.mark.asyncio
async def test_leaderboard_and_agent_stats_use_projection_scores_and_counts(
    db_session: AsyncSession,
) -> None:
    scenario = await _create_sales_scenario(db_session, name="重点客户推进")
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Enterprise Coach",
        category="sales",
        status="published",
    )
    persona = Persona(
        id=str(uuid.uuid4()),
        name="Skeptical CFO",
        category="customer",
        difficulty="hard",
        system_prompt="Stay skeptical.",
        status="active",
    )
    db_session.add_all([agent, persona])
    await db_session.flush()

    top_user = await _create_user(
        db_session,
        name="Top Projection",
        department="Enterprise",
        email="top-projection@example.com",
    )
    second_user = await _create_user(
        db_session,
        name="Legacy Weighted Winner",
        department="Enterprise",
        email="legacy-weighted@example.com",
    )

    now = datetime.now(timezone.utc)
    top_start = now - timedelta(days=3)
    second_start = now - timedelta(days=2)

    db_session.add_all(
        [
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(top_user.user_id),
                scenario_id=str(scenario.scenario_id),
                agent_id=str(agent.id),
                persona_id=str(persona.id),
                status="completed",
                start_time=top_start,
                end_time=top_start + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=40,
                accuracy_score=50,
                completeness_score=60,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="objection_response",
                    issue_text="异议回应不够具体。",
                    goal_type="objection_response_drill",
                    goal_text="下一轮继续把异议回应说完整。",
                ),
            ),
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(second_user.user_id),
                scenario_id=str(scenario.scenario_id),
                agent_id=str(agent.id),
                persona_id=str(persona.id),
                status="completed",
                start_time=second_start,
                end_time=second_start + timedelta(minutes=5),
                total_duration_seconds=300,
                logic_score=70,
                accuracy_score=40,
                completeness_score=38,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="value_translation_gap",
                    issue_text="价值表达还没连到客户收益。",
                    goal_type="benefit_translation_drill",
                    goal_text="下一轮先把价值翻译成客户收益。",
                ),
            ),
        ]
    )
    await db_session.commit()

    leaderboard_result = await admin_analytics_service.get_leaderboard(
        db=db_session,
        time_range="30d",
        limit=10,
    )
    assert leaderboard_result.is_success, leaderboard_result.fallback
    leaderboard = leaderboard_result.value
    assert [entry["user_name"] for entry in leaderboard] == [
        "Top Projection",
        "Legacy Weighted Winner",
    ]
    assert leaderboard[0]["average_score"] == 50.0
    assert leaderboard[0]["best_score"] == 50.0
    assert leaderboard[0]["evaluable_sessions"] == 1
    assert leaderboard[0]["not_evaluable_sessions"] == 0
    assert leaderboard[0]["score_basis"] == "session_evidence_projection_evaluable_only"
    assert leaderboard[1]["average_score"] == 49.3
    assert leaderboard[1]["primary_issue_type"] == "value_translation_gap"
    assert leaderboard[1]["primary_next_goal_type"] == "benefit_translation_drill"

    agent_result = await admin_analytics_service.get_agent_stats(
        db=db_session,
        time_range="30d",
        limit=10,
    )
    assert agent_result.is_success, agent_result.fallback
    agent_payload = agent_result.value
    assert agent_payload["agent_stats"] == [
        {
            "agent_id": str(agent.id),
            "agent_name": "Enterprise Coach",
            "category": "sales",
            "usage_count": 2,
            "average_score": 49.7,
            "completion_rate": 100.0,
            "evaluable_sessions": 2,
            "not_evaluable_sessions": 0,
            "score_basis": "session_evidence_projection_evaluable_only",
        }
    ]
    assert agent_payload["persona_stats"] == [
        {
            "persona_id": str(persona.id),
            "persona_name": "Skeptical CFO",
            "difficulty": "hard",
            "usage_count": 2,
            "average_score": 49.7,
            "evaluable_sessions": 2,
            "not_evaluable_sessions": 0,
            "score_basis": "session_evidence_projection_evaluable_only",
        }
    ]
    assert agent_payload["scenario_distribution"] == {"sales": 2}
