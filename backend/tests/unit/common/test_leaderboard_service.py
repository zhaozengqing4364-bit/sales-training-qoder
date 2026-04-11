"""
Unit tests for leaderboard service filters and rank calculation.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid
from typing import Iterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.analytics.leaderboard_service import LeaderboardService
from common.db.models import Base, PracticeSession, Scenario, User


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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
    now = datetime.now(timezone.utc)

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
                logic_score=90,
                accuracy_score=88,
                completeness_score=92,
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
    assert weekly_rank.value["rank"] == 1
    assert weekly_rank.value["total_users"] == 1
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
    assert len(sales_monthly.value.entries) == 1
    assert sales_monthly.value.entries[0].username == "Alice"

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
    assert len(sales_monthly.value.entries) == 1

    aggregate_queries = [
        statement
        for statement in statements
        if "avg(practice_sessions.logic_score" in statement.lower()
    ]
    count_queries = [
        statement
        for statement in statements
        if "count(distinct(users.user_id))" in statement.lower()
    ]

    assert len(statements) == 2
    assert len(aggregate_queries) == 1
    assert len(count_queries) == 1
    assert "GROUP BY users.user_id, users.name" in aggregate_queries[0]
    assert "ORDER BY average_score DESC" in aggregate_queries[0]
    assert "JOIN scenarios" in aggregate_queries[0]
