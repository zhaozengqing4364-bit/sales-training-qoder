"""Structural performance guards for /team Journey list and Workbench."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.db.models import (
    Base,
    ComprehensiveReport,
    PracticeSession,
    Scenario,
    SupervisorReview,
    Team,
    TeamMembership,
    TrainingTask,
    User,
)
from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)
from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.revision_service import (
    PATH_LOGICAL_ID,
    PATH_RESOURCE_TYPE,
)
from supervisor.service import SupervisorReviewService

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
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@contextmanager
def _capture_sql_statements(engine: AsyncEngine) -> Iterator[list[str]]:
    statements: list[str] = []

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        del conn, cursor, parameters, context, executemany
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


def _admin() -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin-{uuid.uuid4().hex}",
        name="管理员",
        email=f"{uuid.uuid4().hex}@example.com",
        role="admin",
        is_active=True,
    )


def _learner(index: int) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"learner-{index}-{uuid.uuid4().hex}",
        name=f"学员{index:03d}",
        email=f"learner{index}@example.com",
        role="user",
        is_active=True,
    )


def _path_payload() -> dict:
    return TrainingPathPayload.model_validate(
        {
            "title": "新人训练",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "阶段一",
                    "order_index": 1,
                    "required": True,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "模块一",
                            "order_index": 1,
                            "required": True,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "assignment-1",
                                    "title": "作业一",
                                    "type": "assignment",
                                    "order_index": 1,
                                    "required": True,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                },
                                {
                                    "activity_id": "quiz-1",
                                    "title": "知识测验",
                                    "type": "quiz",
                                    "order_index": 2,
                                    "required": True,
                                    "config": {
                                        "exam_paper_id": str(uuid.uuid4()),
                                        "pass_score": 60,
                                    },
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ).model_dump(mode="json")


async def _seed_team_dataset(db: AsyncSession, *, learner_count: int) -> User:
    admin = _admin()
    db.add(admin)
    await db.flush()
    team = Team(
        team_id=str(uuid.uuid4()),
        code=f"team-{uuid.uuid4().hex[:8]}",
        name="性能测试团队",
        is_active=True,
        created_by=str(admin.user_id),
    )
    payload = _path_payload()
    revision_id = str(uuid.uuid4())
    revision = SalesTrainerAssetRevision(
        revision_id=revision_id,
        resource_type=PATH_RESOURCE_TYPE,
        logical_id=PATH_LOGICAL_ID,
        revision_no=1,
        status="published",
        payload_json=payload,
        payload_hash=hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        created_by=str(admin.user_id),
    )
    active = SalesTrainerAssetActiveRevision(
        resource_type=PATH_RESOURCE_TYPE,
        logical_id=PATH_LOGICAL_ID,
        active_revision_id=revision_id,
        activated_by=str(admin.user_id),
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        name="scenario",
        scenario_type="sales",
        description="d",
    )
    db.add_all([team, revision, active, scenario])
    await db.flush()

    now = datetime.now(UTC)
    for index in range(learner_count):
        learner = _learner(index)
        db.add(learner)
        await db.flush()
        db.add(
            TeamMembership(
                membership_id=str(uuid.uuid4()),
                team_id=str(team.team_id),
                user_id=str(learner.user_id),
                membership_role="primary",
                effective_from=now - timedelta(days=30),
                created_by=str(admin.user_id),
            )
        )
        enrollment = NewcomerTrainingEnrollment(
            enrollment_id=str(uuid.uuid4()),
            learner_id=str(learner.user_id),
            path_id=PATH_LOGICAL_ID,
            path_revision_id=revision_id,
            status="active",
        )
        db.add(enrollment)
        await db.flush()
        db.add(
            NewcomerTrainingActivityAttempt(
                attempt_id=str(uuid.uuid4()),
                enrollment_id=str(enrollment.enrollment_id),
                path_revision_id=revision_id,
                activity_id="quiz-1",
                activity_type="quiz",
                attempt_no=1,
                client_token=f"token-{learner.user_id}",
                status="failed",
                passed=False,
                score=40,
                max_score=100,
                activity_snapshot={"activity_id": "quiz-1"},
            )
        )
        db.add(
            TrainingTask(
                task_id=str(uuid.uuid4()),
                title="额外任务",
                assignee_id=str(learner.user_id),
                scenario_type="sales",
                goal="练习",
                status="completed",
                created_at=now - timedelta(days=1),
            )
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=str(learner.user_id),
            scenario_id=str(scenario.scenario_id),
            status="completed",
            start_time=now - timedelta(days=1),
        )
        db.add(session)
        await db.flush()
        db.add(
            ComprehensiveReport(
                session_id=str(session.session_id),
                overall_score=65,
                dimension_scores=[{"name": "产品准确性", "score": 55}],
                key_improvements=["表达不够具体"],
            )
        )
        db.add(
            SupervisorReview(
                review_id=str(uuid.uuid4()),
                session_id=str(session.session_id),
                trainee_user_id=str(learner.user_id),
                supervisor_user_id=str(admin.user_id),
                decision="pending",
                readiness_status="not_ready",
                required_retraining=False,
                comment="需关注产品准确性",
            )
        )
    await db.commit()
    return admin


@pytest.mark.asyncio
@pytest.mark.performance
async def test_should_push_workbench_date_predicates_into_sql(test_engine, db_session):
    admin = await _seed_team_dataset(db_session, learner_count=20)
    service = SupervisorReviewService(db_session)
    date_from = datetime(2020, 1, 1, tzinfo=UTC)
    date_to = datetime(2030, 1, 1, tzinfo=UTC)
    with _capture_sql_statements(test_engine) as statements:
        payload = await service.get_team_workbench(
            current_user=admin,
            date_from=date_from,
            date_to=date_to,
        )
    joined = "\n".join(statements).lower()
    assert "training_tasks" in joined
    assert "created_at" in joined
    assert "practice_sessions" in joined
    assert "start_time" in joined
    assert ">=" in joined
    assert "<=" in joined
    assert "readiness" not in payload
    assert "retraining_candidates" not in payload
    assert payload["extra_task_progress"]["total_tasks"] == 20
    assert len(payload["learners"]) == 20
    # No per-learner score refresh loops (avoid SELECT ... FROM practice_sessions WHERE session_id = ? style score probes).
    score_lookups = [
        sql
        for sql in statements
        if "practice_sessions" in sql.lower()
        and "session_id" in sql.lower()
        and " = ?" in sql.lower()
        and "in (" not in sql.lower()
    ]
    assert len(score_lookups) == 0


@pytest.mark.asyncio
@pytest.mark.performance
async def test_should_keep_workbench_sql_bounded_for_large_team(
    test_engine, db_session
):
    admin = await _seed_team_dataset(db_session, learner_count=100)
    service = SupervisorReviewService(db_session)
    with _capture_sql_statements(test_engine) as statements:
        payload = await service.get_team_workbench(current_user=admin)
    # Bounded read model: constant-ish query count, never one score query per learner.
    assert len(statements) < 40
    assert len(payload["learners"]) == 100
