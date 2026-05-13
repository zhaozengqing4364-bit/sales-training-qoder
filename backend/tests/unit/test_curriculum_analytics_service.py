from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.db.models import (
    Base,
    EvaluationRun,
    PracticeSession,
    RetrainingTask,
    Scenario,
    SupervisorReview,
    SupervisorScoreCalibration,
    TrainingReportSnapshot,
    TrainingTask,
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


async def _create_user(db_session: AsyncSession, *, name: str, role: str = "user") -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"wechat_{uuid.uuid4().hex[:8]}",
        name=name,
        email=f"{name}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_sales_scenario(db_session: AsyncSession) -> Scenario:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="课程分析场景",
        description="Curriculum analytics test scenario",
        is_active=True,
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


async def _create_template(
    db_session: AsyncSession,
    *,
    template_id: str,
    name: str,
) -> PracticeTemplate:
    template = PracticeTemplate(
        template_id=template_id,
        name=name,
        description=f"{name} description",
        scenario_type="sales",
        mode="customer_roleplay",
        agent_id="agent-analytics",
        persona_id="persona-analytics",
        runtime_profile_id="runtime-analytics",
        scoring_ruleset_id="ruleset-analytics",
        knowledge_base_refs=[],
        status="published",
        version=1,
        content_hash=f"hash-{template_id}",
    )
    db_session.add(template)
    await db_session.flush()
    return template


async def _create_completed_session_with_snapshot(
    db_session: AsyncSession,
    *,
    user: User,
    scenario: Scenario,
    template: PracticeTemplate,
    session_id: str,
    started_at: datetime,
    logic_score: float,
    accuracy_score: float,
    completeness_score: float,
    dimension_scores: list[dict[str, object]],
    report_lineage: dict[str, object] | None = None,
) -> PracticeSession:
    session = PracticeSession(
        session_id=session_id,
        user_id=str(user.user_id),
        scenario_id=str(scenario.scenario_id),
        practice_template_id=str(template.template_id),
        curriculum_snapshot={
            "practice_template": {
                "template_id": str(template.template_id),
                "name": template.name,
                "version": template.version,
                "content_hash": template.content_hash,
            },
            "stage_snapshots": {
                "stage_discovery": {
                    "template_ref": {
                        "asset_id": str(template.template_id),
                        "version": template.version,
                    }
                }
            },
        },
        status="completed",
        report_status="completed",
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        start_time=started_at,
        end_time=started_at + timedelta(minutes=8),
        effectiveness_snapshot={"evaluable": True},
    )
    evaluation_run = EvaluationRun(
        run_id=str(uuid.uuid4()),
        session_id=session_id,
        status="succeeded",
        input_evidence_reference={"source": "unit-test"},
        result_payload={"overall_score": (logic_score + accuracy_score + completeness_score) / 3},
    )
    snapshot = TrainingReportSnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session_id,
        evaluation_run_id=str(evaluation_run.run_id),
        report_payload={
            "overall_score": (logic_score + accuracy_score + completeness_score) / 3,
            "dimension_scores": dimension_scores,
            "lineage": report_lineage or {},
        },
        evidence_completeness={"conversation": True},
        generated_at=started_at + timedelta(minutes=9),
    )
    db_session.add_all([session, evaluation_run, snapshot])
    await db_session.flush()
    return session


@pytest.mark.asyncio
async def test_curriculum_dashboard_uses_frozen_reports_and_supervisor_outcomes(
    db_session: AsyncSession,
) -> None:
    learner = await _create_user(db_session, name="learner")
    supervisor = await _create_user(db_session, name="supervisor", role="admin")
    scenario = await _create_sales_scenario(db_session)
    objection_template = await _create_template(
        db_session,
        template_id="11111111-1111-1111-1111-111111111111",
        name="异议处理训练",
    )
    value_template = await _create_template(
        db_session,
        template_id="22222222-2222-2222-2222-222222222222",
        name="价值表达训练",
    )
    now = datetime.now(UTC)

    first_session = await _create_completed_session_with_snapshot(
        db_session,
        user=learner,
        scenario=scenario,
        template=objection_template,
        session_id="33333333-3333-3333-3333-333333333333",
        started_at=now - timedelta(days=3),
        logic_score=70,
        accuracy_score=60,
        completeness_score=80,
        dimension_scores=[
            {"name": "异议处理", "score": 55},
            {"name": "价值表达", "score": 88},
        ],
    )
    second_session = await _create_completed_session_with_snapshot(
        db_session,
        user=learner,
        scenario=scenario,
        template=value_template,
        session_id="44444444-4444-4444-4444-444444444444",
        started_at=now - timedelta(days=1),
        logic_score=82,
        accuracy_score=78,
        completeness_score=80,
        dimension_scores=[
            {"name": "异议处理", "score": 65},
            {"name": "价值表达", "score": 91},
        ],
    )
    assigned_task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="异议处理训练任务",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="完成异议处理训练",
        practice_template_id=str(objection_template.template_id),
        status="assigned",
    )
    completed_task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="价值表达训练任务",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="完成价值表达训练",
        practice_template_id=str(value_template.template_id),
        status="completed",
        resulting_session_id=str(second_session.session_id),
    )
    approved_review = SupervisorReview(
        review_id=str(uuid.uuid4()),
        session_id=str(first_session.session_id),
        trainee_user_id=str(learner.user_id),
        supervisor_user_id=str(supervisor.user_id),
        decision="approved",
        readiness_status="approved",
    )
    retraining_review = SupervisorReview(
        review_id=str(uuid.uuid4()),
        session_id=str(second_session.session_id),
        trainee_user_id=str(learner.user_id),
        supervisor_user_id=str(supervisor.user_id),
        decision="needs_retraining",
        readiness_status="shadow_only",
        required_retraining=True,
    )
    retraining_task = RetrainingTask(
        task_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        source_session_id=str(second_session.session_id),
        source_review_id=str(retraining_review.review_id),
        training_task_id=str(completed_task.task_id),
        skill_dimension="异议处理",
        title="复训：异议处理",
        status="completed",
        completed_session_id=str(first_session.session_id),
    )
    calibration = SupervisorScoreCalibration(
        calibration_id=str(uuid.uuid4()),
        review_id=str(retraining_review.review_id),
        session_id=str(second_session.session_id),
        dimension="异议处理",
        ai_score=65,
        supervisor_score=72,
        calibration_label="too_low",
        calibrated_by_user_id=str(supervisor.user_id),
    )
    db_session.add_all(
        [
            assigned_task,
            completed_task,
            approved_review,
            retraining_review,
            retraining_task,
            calibration,
        ]
    )
    await db_session.commit()

    result = await curriculum_analytics_service.get_dashboard(
        db=db_session,
        time_range="30d",
    )

    assert result.is_success, result.fallback
    dashboard = result.unwrap()
    assert dashboard.summary.assigned_count == 2
    assert dashboard.summary.completed_count == 2
    assert dashboard.summary.completion_rate == 1.0
    assert dashboard.summary.top_weak_dimension == "异议处理"
    assert dashboard.summary.average_score_delta == 10.0
    assert dashboard.review_outcomes.approved == 1
    assert dashboard.review_outcomes.calibrated == 1
    assert dashboard.review_outcomes.retraining_required == 1
    assert dashboard.retraining_conversion.created == 1
    assert dashboard.retraining_conversion.completed == 1
    assert dashboard.heatmap[0].template_name == "异议处理训练"
    assert dashboard.heatmap[0].dimension == "异议处理"
    assert dashboard.heatmap[0].average_score == 55.0
    assert [point.sample_count for point in dashboard.score_trend] == [1, 1]
    assert dashboard.cache.enabled is False


@pytest.mark.asyncio
async def test_curriculum_dashboard_excludes_assigned_tasks_outside_time_range(
    db_session: AsyncSession,
) -> None:
    learner = await _create_user(db_session, name="range learner")
    scenario = await _create_sales_scenario(db_session)
    template = await _create_template(
        db_session,
        template_id="55555555-5555-5555-5555-555555555555",
        name="范围口径训练",
    )
    now = datetime.now(UTC)
    await _create_completed_session_with_snapshot(
        db_session,
        user=learner,
        scenario=scenario,
        template=template,
        session_id="66666666-6666-6666-6666-666666666666",
        started_at=now - timedelta(days=2),
        logic_score=80,
        accuracy_score=80,
        completeness_score=80,
        dimension_scores=[{"name": "开场", "score": 80}],
    )
    recent_task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="近期任务",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="近期课程训练",
        practice_template_id=str(template.template_id),
        status="completed",
        created_at=now - timedelta(days=2),
    )
    old_task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="历史任务",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="历史课程训练",
        practice_template_id=str(template.template_id),
        status="assigned",
        created_at=now - timedelta(days=45),
    )
    db_session.add_all([recent_task, old_task])
    await db_session.commit()

    result = await curriculum_analytics_service.get_dashboard(
        db=db_session,
        time_range="30d",
    )

    assert result.is_success, result.fallback
    dashboard = result.unwrap()
    assert dashboard.summary.assigned_count == 1
    assert dashboard.summary.completed_count == 1
    assert dashboard.summary.completion_rate == 1.0


@pytest.mark.asyncio
async def test_curriculum_dashboard_uses_report_lineage_stage_snapshots_for_dimension_scores(
    db_session: AsyncSession,
) -> None:
    learner = await _create_user(db_session, name="lineage learner")
    scenario = await _create_sales_scenario(db_session)
    template = await _create_template(
        db_session,
        template_id="77777777-7777-7777-7777-777777777777",
        name="冻结血统训练",
    )
    await _create_completed_session_with_snapshot(
        db_session,
        user=learner,
        scenario=scenario,
        template=template,
        session_id="88888888-8888-8888-8888-888888888888",
        started_at=datetime.now(UTC) - timedelta(days=1),
        logic_score=70,
        accuracy_score=70,
        completeness_score=70,
        dimension_scores=[],
        report_lineage={
            "stage_snapshots": {
                "stage_objection": {
                    "name": "异议处理阶段",
                    "dimension_scores": [
                        {"name": "异议处理", "score": 42},
                        {"name": "价值表达", "score": 76},
                    ],
                }
            }
        },
    )
    task = TrainingTask(
        task_id=str(uuid.uuid4()),
        title="冻结血统任务",
        assignee_id=str(learner.user_id),
        scenario_type="sales",
        goal="验证报告血统",
        practice_template_id=str(template.template_id),
        status="completed",
    )
    db_session.add(task)
    await db_session.commit()

    result = await curriculum_analytics_service.get_dashboard(
        db=db_session,
        time_range="30d",
    )

    assert result.is_success, result.fallback
    dashboard = result.unwrap()
    assert dashboard.summary.top_weak_dimension == "异议处理"
    assert dashboard.heatmap[0].average_score == 42.0
