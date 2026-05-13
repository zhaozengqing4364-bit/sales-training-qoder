from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.db.models import (
    Base,
    EvaluationRun,
    PracticeSession,
    Scenario,
    TrainingReportSnapshot,
    User,
)
from curriculum_analytics.service import curriculum_analytics_service
from curriculum_practice.models import PracticeTemplate

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
@pytest.mark.performance
async def test_curriculum_analytics_dashboard_uses_bounded_queries(
    db_session: AsyncSession,
    test_engine: AsyncEngine,
) -> None:
    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"perf_{uuid.uuid4().hex[:8]}",
        name="perf learner",
        email=f"perf_{uuid.uuid4().hex[:8]}@example.com",
        role="user",
        is_active=True,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="课程分析性能场景",
        is_active=True,
    )
    db_session.add_all([learner, scenario])
    await db_session.flush()
    now = datetime.now(UTC)
    for index in range(12):
        template = PracticeTemplate(
            template_id=str(uuid.uuid4()),
            name=f"课程模板 {index}",
            description="performance template",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id="agent-perf",
            persona_id="persona-perf",
            runtime_profile_id="runtime-perf",
            scoring_ruleset_id="ruleset-perf",
            knowledge_base_refs=[],
            status="published",
            version=1,
            content_hash=f"hash-perf-{index}",
        )
        session_id = str(uuid.uuid4())
        started_at = now - timedelta(days=index % 7)
        session = PracticeSession(
            session_id=session_id,
            user_id=str(learner.user_id),
            scenario_id=str(scenario.scenario_id),
            practice_template_id=str(template.template_id),
            curriculum_snapshot={
                "practice_template": {"template_id": template.template_id, "name": template.name}
            },
            status="completed",
            report_status="completed",
            logic_score=70 + index,
            accuracy_score=70 + index,
            completeness_score=70 + index,
            start_time=started_at,
            end_time=started_at + timedelta(minutes=5),
        )
        run_id = str(uuid.uuid4())
        evaluation_run = EvaluationRun(
            run_id=run_id,
            session_id=session_id,
            status="succeeded",
            input_evidence_reference={"source": "performance-test"},
            result_payload={"overall_score": 70 + index},
        )
        snapshot = TrainingReportSnapshot(
            snapshot_id=str(uuid.uuid4()),
            session_id=session_id,
            evaluation_run_id=run_id,
            report_payload={
                "overall_score": 70 + index,
                "dimension_scores": [{"name": "异议处理", "score": 70 + index}],
            },
            evidence_completeness={"conversation": True},
            generated_at=started_at + timedelta(minutes=6),
        )
        db_session.add_all([template, session, evaluation_run, snapshot])
    await db_session.commit()

    with _capture_sql_statements(test_engine) as statements:
        result = await curriculum_analytics_service.get_dashboard(
            db=db_session,
            time_range="30d",
        )

    assert result.is_success, result.fallback
    assert len(statements) <= 5
    bounded_selects = [
        statement
        for statement in statements
        if statement.lower().startswith("select")
        and (
            "practice_sessions" in statement
            or "training_tasks" in statement
            or "training_report_snapshots" in statement
            or "supervisor_reviews" in statement
            or "retraining_tasks" in statement
        )
    ]
    assert bounded_selects
    assert all("LIMIT" in statement.upper() for statement in bounded_selects)
