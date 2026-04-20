"""
Unit tests for leaderboard service filters and rank calculation.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.analytics.leaderboard_service import LeaderboardService
from common.db.models import Base, PracticeSession, Scenario, User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _effectiveness_snapshot(
    *, evaluable: bool, issue_type: str | None = None
) -> dict[str, object]:
    if issue_type is None:
        issue_type = "ok" if evaluable else "insufficient"
    return {
        "pass_flags": {
            "pass_3min_flow": evaluable,
            "pass_5turn_defense": evaluable,
            "pass_4step_structure": evaluable,
        },
        "overall_result": "pass" if evaluable else "fail",
        "main_issue": {
            "issue_type": issue_type,
            "issue_text": "fixture",
            "recovery_rule": "fixture",
        },
        "next_goal": {
            "goal_type": "continue",
            "goal_text": "fixture",
            "rule": "fixture",
        },
        "evaluable": evaluable,
        "not_evaluable_reason": None if evaluable else "INSUFFICIENT_TURN_DATA",
    }


def _completed_session(
    *,
    user_id: str,
    scenario_id: str,
    start_time: datetime,
    score: float,
    evaluable: bool = True,
    issue_type: str = "evidence_gap",
) -> PracticeSession:
    return PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario_id,
        status="completed",
        start_time=start_time,
        logic_score=score,
        accuracy_score=score,
        completeness_score=score,
        effectiveness_snapshot=_effectiveness_snapshot(
            evaluable=evaluable,
            issue_type=issue_type,
        ),
    )


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
        event.remove(
            engine.sync_engine, "before_cursor_execute", _before_cursor_execute
        )


@pytest_asyncio.fixture()
async def leaderboard_db() -> AsyncSession:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_leaderboard_data(leaderboard_db: AsyncSession) -> dict[str, str]:
    now = datetime.now(UTC)

    user_a = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="lb_user_a",
        name="Alice",
        email="alice@example.com",
    )
    user_b = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id="lb_user_b",
        name="Bob",
        email="bob@example.com",
    )

    sales_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="销售对练",
    )
    presentation_scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name="PPT 演练",
    )

    leaderboard_db.add_all([user_a, user_b, sales_scenario, presentation_scenario])
    await leaderboard_db.flush()

    leaderboard_db.add_all(
        [
            # Alice: sales recent
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=user_a.user_id,
                scenario_id=sales_scenario.scenario_id,
                status="completed",
                start_time=now - timedelta(days=2),
                logic_score=100,
                accuracy_score=0,
                completeness_score=0,
                effectiveness_snapshot=_effectiveness_snapshot(evaluable=True),
            ),
            # Bob: sales recent; projection-compatible unweighted score should outrank Alice.
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=user_b.user_id,
                scenario_id=sales_scenario.scenario_id,
                status="completed",
                start_time=now - timedelta(days=2),
                logic_score=0,
                accuracy_score=60,
                completeness_score=60,
                effectiveness_snapshot=_effectiveness_snapshot(evaluable=True),
            ),
            # Bob: sales old (outside "month"/"week", still in all_time)
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=user_b.user_id,
                scenario_id=sales_scenario.scenario_id,
                status="completed",
                start_time=now - timedelta(days=45),
                logic_score=95,
                accuracy_score=95,
                completeness_score=95,
                effectiveness_snapshot=_effectiveness_snapshot(evaluable=True),
            ),
            # Bob: presentation recent
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=user_b.user_id,
                scenario_id=presentation_scenario.scenario_id,
                status="completed",
                start_time=now - timedelta(days=3),
                logic_score=85,
                accuracy_score=86,
                completeness_score=87,
                effectiveness_snapshot=_effectiveness_snapshot(evaluable=True),
            ),
            # Bob: sales recent but not evaluable, should never outrank Alice.
            PracticeSession(
                session_id=str(uuid.uuid4()),
                user_id=user_b.user_id,
                scenario_id=sales_scenario.scenario_id,
                status="completed",
                start_time=now - timedelta(days=1),
                logic_score=100,
                accuracy_score=100,
                completeness_score=100,
                effectiveness_snapshot=_effectiveness_snapshot(evaluable=False),
            ),
        ]
    )
    await leaderboard_db.commit()

    return {
        "alice_id": user_a.user_id,
        "bob_id": user_b.user_id,
    }


@pytest.mark.asyncio
async def test_get_user_rank_respects_time_period_and_scenario(
    leaderboard_db: AsyncSession,
    seeded_leaderboard_data: dict[str, str],
):
    service = LeaderboardService()
    alice_id = seeded_leaderboard_data["alice_id"]

    weekly_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=alice_id,
        scenario_type="sales",
        time_period="week",
    )
    assert weekly_rank.is_success
    assert weekly_rank.value["rank"] == 2
    assert weekly_rank.value["total_users"] == 2
    assert weekly_rank.value["time_period"] == "weekly"

    all_time_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=alice_id,
        scenario_type="sales_bot",  # alias
        time_period="all_time",
    )
    assert all_time_rank.is_success
    assert all_time_rank.value["rank"] == 2
    assert all_time_rank.value["total_users"] == 2
    assert all_time_rank.value["scenario_type"] == "sales"


@pytest.mark.asyncio
async def test_calculate_leaderboard_accepts_alias_filters(
    leaderboard_db: AsyncSession,
    seeded_leaderboard_data: dict[str, str],
):
    service = LeaderboardService()

    sales_monthly = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="sales_bot",  # alias
        time_period="month",  # alias
        limit=10,
    )
    assert sales_monthly.is_success
    assert sales_monthly.value.time_period == "monthly"
    assert (
        sales_monthly.value.score_basis == "session_evidence_projection_evaluable_only"
    )
    assert sales_monthly.value.evaluable_sessions == 2
    assert sales_monthly.value.not_evaluable_sessions == 1
    assert len(sales_monthly.value.entries) == 2
    assert sales_monthly.value.entries[0].username == "Bob"
    assert sales_monthly.value.entries[0].average_score == 40.0
    assert sales_monthly.value.entries[1].username == "Alice"
    assert sales_monthly.value.entries[1].average_score == 33.33

    presentation_weekly = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="presentation",
        time_period="weekly",
        limit=10,
    )
    assert presentation_weekly.is_success
    assert len(presentation_weekly.value.entries) == 1
    assert presentation_weekly.value.entries[0].username == "Bob"


@pytest.mark.asyncio
async def test_calculate_leaderboard_pushes_ranking_aggregation_into_sql(
    leaderboard_db: AsyncSession,
    seeded_leaderboard_data: dict[str, str],
):
    service = LeaderboardService()

    with _capture_sql_statements(leaderboard_db.bind) as statements:
        sales_monthly = await service.calculate_leaderboard(
            db=leaderboard_db,
            scenario_type="sales_bot",
            time_period="month",
            limit=10,
        )

    assert sales_monthly.is_success
    assert len(sales_monthly.value.entries) == 2

    aggregate_queries = [
        statement
        for statement in statements
        if "GROUP BY users.user_id, users.name" in statement
    ]
    count_queries = [
        statement
        for statement in statements
        if "count(distinct(users.user_id))" in statement.lower()
    ]

    assert len(statements) == 4
    assert len(aggregate_queries) == 1
    assert len(count_queries) == 1
    assert (
        "practice_sessions.logic_score + practice_sessions.accuracy_score + practice_sessions.completeness_score"
        in aggregate_queries[0]
    )
    assert "ORDER BY average_score DESC" in aggregate_queries[0]
    assert "JOIN scenarios" in aggregate_queries[0]


@pytest.mark.asyncio
async def test_calculate_improvement_leaderboard_requires_two_evaluable_sessions(
    leaderboard_db: AsyncSession,
):
    now = datetime.now(UTC)
    users = [
        User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=f"improvement_user_{index}",
            name=name,
            email=f"improvement_{index}@example.com",
        )
        for index, name in enumerate(["Alice", "Bob", "Carol", "Dora"], start=1)
    ]
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="销售对练",
    )
    leaderboard_db.add_all([*users, scenario])
    await leaderboard_db.flush()

    leaderboard_db.add_all(
        [
            _completed_session(
                user_id=users[0].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=5),
                score=70,
            ),
            _completed_session(
                user_id=users[0].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=3),
                score=80,
            ),
            _completed_session(
                user_id=users[0].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=85,
            ),
            _completed_session(
                user_id=users[1].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=4),
                score=90,
            ),
            _completed_session(
                user_id=users[1].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=92,
            ),
            _completed_session(
                user_id=users[2].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=95,
            ),
            _completed_session(
                user_id=users[3].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=2),
                score=60,
            ),
            _completed_session(
                user_id=users[3].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=100,
                evaluable=False,
            ),
        ]
    )
    await leaderboard_db.commit()

    service = LeaderboardService()
    result = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="sales",
        time_period="all_time",
        leaderboard_mode="improvement",
        limit=10,
    )

    assert result.is_success
    assert result.value.leaderboard_mode == "improvement"
    assert result.value.total_users == 2
    assert result.value.evaluable_sessions == 5
    assert result.value.not_evaluable_sessions == 1
    assert [entry.username for entry in result.value.entries] == ["Alice", "Bob"]
    assert result.value.entries[0].improvement_score == 15
    assert result.value.entries[0].first_score == 70
    assert result.value.entries[0].latest_score == 85
    assert result.value.entries[0].sample_size == 3
    assert result.value.entries[1].improvement_score == 2

    bob_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=users[1].user_id,
        scenario_type="sales",
        leaderboard_mode="improvement",
    )
    assert bob_rank.is_success
    assert bob_rank.value["rank"] == 2
    assert bob_rank.value["improvement_score"] == 2
    assert bob_rank.value["sample_size"] == 2

    carol_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=users[2].user_id,
        scenario_type="sales",
        leaderboard_mode="improvement",
    )
    assert carol_rank.is_success
    assert carol_rank.value["rank"] is None
    assert carol_rank.value["sample_size"] == 1
    assert carol_rank.value["message"] == "At least 2 evaluable sessions required"


@pytest.mark.asyncio
async def test_calculate_issue_type_leaderboard_filters_and_returns_buckets(
    leaderboard_db: AsyncSession,
):
    now = datetime.now(UTC)
    users = [
        User(
            user_id=str(uuid.uuid4()),
            wechat_user_id=f"issue_user_{index}",
            name=name,
            email=f"issue_{index}@example.com",
        )
        for index, name in enumerate(["Alice", "Bob", "Carol", "Dora"], start=1)
    ]
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="销售对练",
    )
    leaderboard_db.add_all([*users, scenario])
    await leaderboard_db.flush()

    leaderboard_db.add_all(
        [
            _completed_session(
                user_id=users[0].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=3),
                score=80,
                issue_type="evidence_gap",
            ),
            _completed_session(
                user_id=users[0].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=90,
                issue_type="evidence_gap",
            ),
            _completed_session(
                user_id=users[1].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=70,
                issue_type="evidence_gap",
            ),
            _completed_session(
                user_id=users[2].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=95,
                issue_type="objection_handling",
            ),
            _completed_session(
                user_id=users[3].user_id,
                scenario_id=scenario.scenario_id,
                start_time=now - timedelta(days=1),
                score=100,
                evaluable=False,
                issue_type="evidence_gap",
            ),
        ]
    )
    await leaderboard_db.commit()

    service = LeaderboardService()
    evidence_result = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="sales",
        leaderboard_mode="issue_type",
        issue_type="evidence_gap",
        limit=10,
    )

    assert evidence_result.is_success
    assert evidence_result.value.leaderboard_mode == "issue_type"
    assert evidence_result.value.issue_type == "evidence_gap"
    assert evidence_result.value.evaluable_sessions == 3
    assert evidence_result.value.not_evaluable_sessions == 1
    assert [entry.username for entry in evidence_result.value.entries] == [
        "Alice",
        "Bob",
    ]
    assert evidence_result.value.entries[0].average_score == 85
    assert all(
        entry.issue_type == "evidence_gap" for entry in evidence_result.value.entries
    )
    assert evidence_result.value.issue_type_buckets == [
        {"issue_type": "evidence_gap", "count": 2, "evaluable_sessions": 3},
        {"issue_type": "objection_handling", "count": 1, "evaluable_sessions": 1},
    ]

    objection_result = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="sales",
        leaderboard_mode="issue_type",
        issue_type="objection_handling",
        limit=10,
    )
    assert objection_result.is_success
    assert [entry.username for entry in objection_result.value.entries] == ["Carol"]

    buckets_result = await service.calculate_leaderboard(
        db=leaderboard_db,
        scenario_type="sales",
        leaderboard_mode="issue_type",
        limit=10,
    )
    assert buckets_result.is_success
    assert buckets_result.value.entries == []
    assert buckets_result.value.issue_type_buckets == [
        {"issue_type": "evidence_gap", "count": 2, "evaluable_sessions": 3},
        {"issue_type": "objection_handling", "count": 1, "evaluable_sessions": 1},
    ]
    assert buckets_result.value.eligibility["explanation"] == (
        "请选择一个目标问题后查看同目标榜"
    )

    bob_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=users[1].user_id,
        scenario_type="sales",
        leaderboard_mode="issue_type",
        issue_type="evidence_gap",
    )
    assert bob_rank.is_success
    assert bob_rank.value["rank"] == 2
    assert bob_rank.value["issue_type"] == "evidence_gap"

    unselected_rank = await service.get_user_rank(
        db=leaderboard_db,
        user_id=users[1].user_id,
        scenario_type="sales",
        leaderboard_mode="issue_type",
    )
    assert unselected_rank.is_success
    assert unselected_rank.value["rank"] is None
    assert (
        unselected_rank.value["issue_type_buckets"]
        == buckets_result.value.issue_type_buckets
    )
