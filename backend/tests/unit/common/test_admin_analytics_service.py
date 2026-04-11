from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.analytics.admin_analytics_service import admin_analytics_service
from common.db.models import Base, ConversationMessage, PracticeSession, Scenario, User

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


@contextmanager
def _capture_sql_statements(engine: AsyncEngine) -> Iterator[list[str]]:
    statements: list[str] = []

    def _before_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ) -> None:
        normalized = " ".join(str(statement).split())
        if normalized.startswith(("PRAGMA ", "SAVEPOINT ", "RELEASE SAVEPOINT ")):
            return
        statements.append(normalized)

    event.listen(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before_cursor_execute)


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
                "degraded_reasons": [
                    "no_retrieval_facts",
                    "no_scored_turns",
                    "no_audio_segments",
                ],
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


@pytest.mark.asyncio
async def test_operating_pack_groups_cohort_department_buckets_and_manager_lists(
    db_session: AsyncSession,
) -> None:
    scenario = await _create_sales_scenario(db_session, name="团队周节奏")

    north_risk = await _create_user(
        db_session,
        name="North Risk",
        department="North",
        email="north-risk@example.com",
    )
    south_risk = await _create_user(
        db_session,
        name="South Risk",
        department="South",
        email="south-risk@example.com",
    )
    not_evaluable_user = await _create_user(
        db_session,
        name="Need More Turns",
        department="North",
        email="need-more-turns@example.com",
    )
    degraded_user = await _create_user(
        db_session,
        name="Degraded Evidence",
        department="North",
        email="degraded-evidence@example.com",
    )
    improving_user = await _create_user(
        db_session,
        name="Improving User",
        department="North",
        email="improving-user@example.com",
    )
    inactive_user = await _create_user(
        db_session,
        name="Inactive User",
        department="East",
        email="inactive-user@example.com",
    )

    now = datetime.now(timezone.utc)

    north_risk_session_id = str(uuid.uuid4())
    south_risk_session_id = str(uuid.uuid4())
    degraded_session_id = str(uuid.uuid4())
    improving_fail_one_id = str(uuid.uuid4())
    improving_fail_two_id = str(uuid.uuid4())
    improving_pass_one_id = str(uuid.uuid4())
    improving_pass_two_id = str(uuid.uuid4())

    db_session.add_all(
        [
            PracticeSession(
                session_id=north_risk_session_id,
                user_id=str(north_risk.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=6),
                end_time=now - timedelta(days=6) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=55,
                accuracy_score=50,
                completeness_score=45,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="value_translation_gap",
                    issue_text="ROI 证据没接到客户收益。",
                    goal_type="benefit_translation_drill",
                    goal_text="下一轮先把 ROI 翻译成客户收益。",
                ),
            ),
            PracticeSession(
                session_id=south_risk_session_id,
                user_id=str(south_risk.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=2),
                end_time=now - timedelta(days=2) + timedelta(minutes=5),
                total_duration_seconds=300,
                logic_score=60,
                accuracy_score=52,
                completeness_score=38,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="value_expression",
                    issue_text="价值表达还停留在产品功能。",
                    goal_type="benefit_translation_drill",
                    goal_text="下一轮先把功能翻译成客户收益。",
                ),
            ),
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(not_evaluable_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=4),
                end_time=now - timedelta(days=4) + timedelta(minutes=1),
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
                session_id=degraded_session_id,
                user_id=str(degraded_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=3),
                end_time=now - timedelta(days=3) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=80,
                accuracy_score=70,
                completeness_score=60,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="structure_gap",
                    issue_text="结构还不完整，客户难以跟上。",
                    goal_type="structure_drill",
                    goal_text="下一轮先讲完整四段结构。",
                ),
            ),
            PracticeSession(
                session_id=improving_fail_one_id,
                user_id=str(improving_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=6, hours=12),
                end_time=now - timedelta(days=6, hours=12) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=52,
                accuracy_score=48,
                completeness_score=46,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="evidence_gap",
                    issue_text="案例证据还不够扎实。",
                    goal_type="evidence_backing",
                    goal_text="下一轮先补一个完整客户案例。",
                ),
            ),
            PracticeSession(
                session_id=improving_fail_two_id,
                user_id=str(improving_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=5, hours=12),
                end_time=now - timedelta(days=5, hours=12) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=50,
                accuracy_score=46,
                completeness_score=44,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="fail",
                    issue_type="evidence_gap",
                    issue_text="案例证据还不够扎实。",
                    goal_type="evidence_backing",
                    goal_text="下一轮先补一个完整客户案例。",
                ),
            ),
            PracticeSession(
                session_id=improving_pass_one_id,
                user_id=str(improving_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=1, hours=12),
                end_time=now - timedelta(days=1, hours=12) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=82,
                accuracy_score=84,
                completeness_score=86,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="pass",
                    issue_type="evidence_gap",
                    issue_text="案例证据还不够扎实。",
                    goal_type="evidence_backing",
                    goal_text="下一轮先补一个完整客户案例。",
                ),
            ),
            PracticeSession(
                session_id=improving_pass_two_id,
                user_id=str(improving_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(hours=18),
                end_time=now - timedelta(hours=18) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=84,
                accuracy_score=86,
                completeness_score=88,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="strong_pass",
                    issue_type="evidence_gap",
                    issue_text="案例证据还不够扎实。",
                    goal_type="evidence_backing",
                    goal_text="下一轮先补一个完整客户案例。",
                ),
            ),
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=str(inactive_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=10),
                end_time=now - timedelta(days=10) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=75,
                accuracy_score=76,
                completeness_score=77,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="pass",
                    issue_type="structure_gap",
                    issue_text="历史结构练习。",
                    goal_type="structure_drill",
                    goal_text="历史结构练习。",
                ),
            ),
            ConversationMessage(
                session_id=degraded_session_id,
                turn_number=1,
                role="user",
                content="我先介绍一下方案。",
                timestamp=now - timedelta(days=3) + timedelta(seconds=30),
            ),
            ConversationMessage(
                session_id=degraded_session_id,
                turn_number=2,
                role="assistant",
                content="继续。",
                timestamp=now - timedelta(days=3) + timedelta(seconds=60),
            ),
        ]
    )
    await db_session.commit()

    operating_result = await admin_analytics_service.get_operating_pack(
        db=db_session,
        time_range="7d",
        scenario_type="sales",
        limit=10,
        inactive_days=7,
    )

    assert operating_result.is_success, operating_result.fallback
    operating_pack = operating_result.value
    assert operating_pack["score_basis"] == "session_evidence_projection_evaluable_only"

    weekly_summary = operating_pack["weekly_summary"]
    assert weekly_summary["window_days"] == 7
    assert weekly_summary["completed_sessions"] == 8
    assert weekly_summary["evaluable_sessions"] == 7
    assert weekly_summary["not_evaluable_sessions"] == 1
    assert weekly_summary["degraded_sessions"] == 8
    assert weekly_summary["at_risk_users"] == 4
    assert weekly_summary["improving_users"] == 1
    assert weekly_summary["top_issue_family"]["issue_family"] == "value_expression"
    assert weekly_summary["top_issue_family"]["count"] == 2
    assert weekly_summary["top_not_evaluable_reason"] == {
        "reason": "INSUFFICIENT_TURN_DATA",
        "count": 1,
    }

    assert operating_pack["cohort_issue_buckets"] == [
        {
            "issue_family": "value_expression",
            "issue_type": "value_expression",
            "issue_text": "价值表达还停留在产品功能。",
            "count": 2,
            "user_count": 2,
            "department_count": 2,
        },
        {
            "issue_family": "evidence_gap",
            "issue_type": "evidence_gap",
            "issue_text": "案例证据还不够扎实。",
            "count": 2,
            "user_count": 1,
            "department_count": 1,
        },
        {
            "issue_family": "structure_gap",
            "issue_type": "structure_gap",
            "issue_text": "结构还不完整，客户难以跟上。",
            "count": 1,
            "user_count": 1,
            "department_count": 1,
        },
    ]

    department_buckets = {
        bucket["department"]: bucket for bucket in operating_pack["department_issue_buckets"]
    }
    assert department_buckets["North"]["session_count"] == 7
    assert department_buckets["North"]["evaluable_sessions"] == 6
    assert department_buckets["North"]["not_evaluable_sessions"] == 1
    assert department_buckets["North"]["issue_buckets"] == [
        {
            "issue_family": "evidence_gap",
            "issue_type": "evidence_gap",
            "issue_text": "案例证据还不够扎实。",
            "count": 2,
            "user_count": 1,
        },
        {
            "issue_family": "structure_gap",
            "issue_type": "structure_gap",
            "issue_text": "结构还不完整，客户难以跟上。",
            "count": 1,
            "user_count": 1,
        },
        {
            "issue_family": "value_expression",
            "issue_type": "value_translation_gap",
            "issue_text": "ROI 证据没接到客户收益。",
            "count": 1,
            "user_count": 1,
        },
    ]
    assert department_buckets["North"]["degradation_breakdown"] == {
        "not_evaluable_reasons": [
            {
                "reason": "INSUFFICIENT_TURN_DATA",
                "count": 1,
            }
        ],
        "degraded_reasons": [
            {
                "reason": "no_audio_segments",
                "count": 7,
            },
            {
                "reason": "no_retrieval_facts",
                "count": 7,
            },
            {
                "reason": "no_scored_turns",
                "count": 7,
            },
        ],
    }
    assert department_buckets["South"]["issue_buckets"] == [
        {
            "issue_family": "value_expression",
            "issue_type": "value_expression",
            "issue_text": "价值表达还停留在产品功能。",
            "count": 1,
            "user_count": 1,
        }
    ]

    assert operating_pack["repeated_blocker_families"] == [
        {
            "issue_family": "value_expression",
            "issue_type": "value_expression",
            "issue_text": "价值表达还停留在产品功能。",
            "count": 2,
            "user_count": 2,
            "department_count": 2,
        },
        {
            "issue_family": "evidence_gap",
            "issue_type": "evidence_gap",
            "issue_text": "案例证据还不够扎实。",
            "count": 2,
            "user_count": 1,
            "department_count": 1,
        },
    ]

    assert operating_pack["degradation_breakdown"] == {
        "not_evaluable_reasons": [
            {
                "reason": "INSUFFICIENT_TURN_DATA",
                "count": 1,
            }
        ],
        "degraded_reasons": [
            {
                "reason": "no_audio_segments",
                "count": 8,
            },
            {
                "reason": "no_retrieval_facts",
                "count": 8,
            },
            {
                "reason": "no_scored_turns",
                "count": 8,
            },
        ],
    }

    manager_lists = operating_pack["manager_lists"]
    assert [item["user_name"] for item in manager_lists["not_passed"]] == [
        "South Risk",
        "Degraded Evidence",
        "North Risk",
    ]
    assert manager_lists["not_passed"][0]["issue_family"] == "value_expression"
    assert manager_lists["not_passed"][1]["issue_family"] == "structure_gap"
    assert manager_lists["not_passed"][2]["issue_family"] == "value_expression"
    assert manager_lists["inactive_streak"][0]["user_name"] == "Inactive User"
    assert manager_lists["inactive_streak"][0]["inactive_days"] >= 7
    assert manager_lists["improving"] == [
        {
            "user_id": str(improving_user.user_id),
            "user_name": "Improving User",
            "department": "North",
            "pass_gain": 100.0,
            "baseline_pass_rate": 0.0,
            "current_pass_rate": 100.0,
        }
    ]


@pytest.mark.asyncio
async def test_get_leaderboard_batches_projection_window_and_messages_once(
    db_session: AsyncSession,
) -> None:
    scenario = await _create_sales_scenario(db_session, name="批量排行榜窗口")
    first_user = await _create_user(
        db_session,
        name="Window One",
        department="Sales",
        email="window-one@example.com",
    )
    second_user = await _create_user(
        db_session,
        name="Window Two",
        department="Sales",
        email="window-two@example.com",
    )

    now = datetime.now(timezone.utc)
    first_session_id = str(uuid.uuid4())
    second_session_id = str(uuid.uuid4())
    db_session.add_all(
        [
            PracticeSession(
                session_id=first_session_id,
                user_id=str(first_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=2),
                end_time=now - timedelta(days=2) + timedelta(minutes=4),
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
                session_id=second_session_id,
                user_id=str(second_user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=1),
                end_time=now - timedelta(days=1) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=55,
                accuracy_score=60,
                completeness_score=65,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="pass",
                    issue_type="value_translation_gap",
                    issue_text="价值表达还没连到客户收益。",
                    goal_type="benefit_translation_drill",
                    goal_text="下一轮先把价值翻译成客户收益。",
                ),
            ),
            ConversationMessage(
                session_id=first_session_id,
                turn_number=1,
                role="user",
                content="第一个会话",
                timestamp=now - timedelta(days=2) + timedelta(seconds=30),
            ),
            ConversationMessage(
                session_id=second_session_id,
                turn_number=1,
                role="user",
                content="第二个会话",
                timestamp=now - timedelta(days=1) + timedelta(seconds=45),
            ),
        ]
    )
    await db_session.commit()

    with _capture_sql_statements(db_session.bind) as statements:
        leaderboard_result = await admin_analytics_service.get_leaderboard(
            db=db_session,
            time_range="30d",
            limit=10,
        )

    assert leaderboard_result.is_success, leaderboard_result.fallback
    practice_window_queries = [
        statement for statement in statements if "FROM practice_sessions" in statement
    ]
    message_batch_queries = [
        statement for statement in statements if "FROM conversation_messages" in statement
    ]

    assert len(practice_window_queries) == 1
    assert len(message_batch_queries) == 1
    assert "conversation_messages.session_id IN" in message_batch_queries[0]
    assert "ORDER BY conversation_messages.session_id" in message_batch_queries[0]
    assert all(
        "conversation_messages.session_id =" not in statement
        for statement in message_batch_queries
    )


@pytest.mark.asyncio
async def test_get_overview_stats_replays_projection_window_for_growth_comparison(
    db_session: AsyncSession,
) -> None:
    scenario = await _create_sales_scenario(db_session, name="增长对比窗口")
    user = await _create_user(
        db_session,
        name="Growth Window",
        department="Sales",
        email="growth-window@example.com",
    )

    now = datetime.now(timezone.utc)
    current_session_id = str(uuid.uuid4())
    previous_session_id = str(uuid.uuid4())
    db_session.add_all(
        [
            PracticeSession(
                session_id=current_session_id,
                user_id=str(user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=5),
                end_time=now - timedelta(days=5) + timedelta(minutes=4),
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
                session_id=previous_session_id,
                user_id=str(user.user_id),
                scenario_id=str(scenario.scenario_id),
                status="completed",
                start_time=now - timedelta(days=40),
                end_time=now - timedelta(days=40) + timedelta(minutes=4),
                total_duration_seconds=240,
                logic_score=55,
                accuracy_score=60,
                completeness_score=65,
                effectiveness_snapshot=_make_effectiveness_snapshot(
                    evaluable=True,
                    overall_result="pass",
                    issue_type="value_translation_gap",
                    issue_text="价值表达还没连到客户收益。",
                    goal_type="benefit_translation_drill",
                    goal_text="下一轮先把价值翻译成客户收益。",
                ),
            ),
            ConversationMessage(
                session_id=current_session_id,
                turn_number=1,
                role="user",
                content="当前窗口",
                timestamp=now - timedelta(days=5) + timedelta(seconds=30),
            ),
            ConversationMessage(
                session_id=previous_session_id,
                turn_number=1,
                role="user",
                content="上一窗口",
                timestamp=now - timedelta(days=40) + timedelta(seconds=30),
            ),
        ]
    )
    await db_session.commit()

    with _capture_sql_statements(db_session.bind) as statements:
        overview_result = await admin_analytics_service.get_overview_stats(
            db=db_session,
            time_range="30d",
            scenario_type="sales",
        )

    assert overview_result.is_success, overview_result.fallback
    practice_window_queries = [
        statement for statement in statements if "FROM practice_sessions" in statement
    ]
    message_batch_queries = [
        statement for statement in statements if "FROM conversation_messages" in statement
    ]
    user_count_queries = [
        statement
        for statement in statements
        if statement.startswith("SELECT count(users.user_id)")
    ]

    assert len(practice_window_queries) == 2
    assert len(message_batch_queries) == 2
    assert len(user_count_queries) == 2
    assert all(
        "practice_sessions.start_time >=" in statement
        for statement in practice_window_queries
    )
