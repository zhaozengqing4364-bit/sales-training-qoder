from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Register agent/voice-runtime tables referenced by shared metadata.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.auth.service import create_access_token
from common.db.models import (
    Base,
    ConversationMessage,
    PracticeSession,
    Scenario,
    ScoringRuleset,
    SessionStatus,
    SystemLog,
    User,
)
from common.effectiveness.scoring_rulesets import (
    SCORING_RULESET_SCORE_BASIS,
    ScoringDimensionRule,
    ScoringRulesetDefinition,
    ScoringRulesetService,
)

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


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    import common.auth.service as auth_service
    import main as main_module
    from common.db.session import get_db as current_get_db

    app = main_module.app

    async def override_get_db():
        yield db_session

    for target in {
        current_get_db,
        getattr(main_module, "get_db", current_get_db),
        getattr(auth_service, "get_db", current_get_db),
    }:
        app.dependency_overrides[target] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _seed_user(db: AsyncSession, *, role: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{role}_{uuid.uuid4().hex[:8]}",
        name=f"{role.title()} Tester",
        department="QA",
        email=f"{role}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _seed_user(db_session, role="admin")


@pytest_asyncio.fixture
async def normal_user(db_session: AsyncSession) -> User:
    return await _seed_user(db_session, role="user")


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(normal_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(normal_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _candidate_definition() -> dict:
    default_definition = ScoringRulesetService.build_default_definition("sales")
    dimensions = []
    for dimension in default_definition.dimensions:
        dimensions.append(
            ScoringDimensionRule(
                dimension_id=dimension.dimension_id,
                label=dimension.label,
                weight=10.0 if dimension.dimension_id == "next_step_commitment" else 0.1,
                rollup_contributions=dimension.rollup_contributions,
            )
        )
    return ScoringRulesetDefinition(
        scenario_type="sales",
        score_basis=SCORING_RULESET_SCORE_BASIS,
        dimensions=dimensions,
    ).model_dump(mode="json")


async def _seed_completed_sales_session(
    db: AsyncSession,
    *,
    user: User,
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="scoring ruleset scenario",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(user.user_id),
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        total_duration_seconds=120,
        logic_score=58.0,
        accuracy_score=72.0,
        completeness_score=88.0,
        effectiveness_snapshot={
            "pass_flags": {
                "pass_3min_flow": True,
                "pass_5turn_defense": True,
                "pass_4step_structure": True,
            },
            "main_capability_passed": True,
            "overall_result": "pass",
            "main_issue": {
                "issue_type": "evidence_gap",
                "issue_text": "补充量化证据。",
                "recovery_rule": "下一轮补 ROI 证据。",
            },
            "next_goal": {
                "goal_type": "next_step",
                "goal_text": "推进下一步。",
                "rule": "提出明确行动。",
            },
            "version": "rule_v1",
            "evaluable": True,
            "not_evaluable_reason": None,
        },
    )
    db.add_all([scenario, session])
    db.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="我们想提升线索转化。",
            timestamp=datetime.now(UTC),
            duration_ms=2000,
            sales_stage="closing",
            score_snapshot={
                "overall_score": 78,
                "dimension_scores": {
                    "value_expression": 50,
                    "customer_benefit_connection": 60,
                    "evidence_usage": 70,
                    "objection_handling": 90,
                    "next_step_commitment": 100,
                },
            },
            ai_feedback="继续推进下一步承诺",
        )
    )
    await db.commit()
    await db.refresh(session)
    return session


@pytest.mark.asyncio
async def test_admin_scoring_ruleset_dry_run_publish_report_and_rollback_flow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    normal_user: User,
) -> None:
    session = await _seed_completed_sales_session(db_session, user=normal_user)
    definition = _candidate_definition()

    denied = await async_client.get(
        "/api/v1/evaluation/admin/scoring-rulesets/active",
        params={"scenario_type": "sales"},
        headers=user_headers,
    )
    assert denied.status_code == 403

    create_v1 = await async_client.post(
        "/api/v1/evaluation/admin/scoring-rulesets",
        json={
            "scenario_type": "sales",
            "version": "sales-v1",
            "display_name": "Sales scoring v1",
            "definition": ScoringRulesetService.build_default_definition(
                "sales"
            ).model_dump(mode="json"),
        },
        headers=admin_headers,
    )
    assert create_v1.status_code == 200
    v1_id = create_v1.json()["data"]["ruleset_id"]
    publish_v1 = await async_client.post(
        f"/api/v1/evaluation/admin/scoring-rulesets/{v1_id}/publish",
        json={"reason": "baseline publish"},
        headers=admin_headers,
    )
    assert publish_v1.status_code == 200

    create_v2 = await async_client.post(
        "/api/v1/evaluation/admin/scoring-rulesets",
        json={
            "scenario_type": "sales",
            "version": "sales-v2",
            "display_name": "Sales scoring v2",
            "description": "Emphasize next-step commitment for dry-run comparison.",
            "definition": definition,
        },
        headers=admin_headers,
    )
    assert create_v2.status_code == 200
    v2_id = create_v2.json()["data"]["ruleset_id"]

    dry_run = await async_client.post(
        "/api/v1/evaluation/admin/scoring-rulesets/dry-run",
        json={"session_id": session.session_id, "candidate_ruleset_id": v2_id},
        headers=admin_headers,
    )
    assert dry_run.status_code == 200
    dry_run_data = dry_run.json()["data"]
    assert dry_run_data["mode"] == "dry_run"
    assert dry_run_data["mutates_history"] is False
    assert dry_run_data["baseline"]["ruleset_version"] == "sales-v1"
    assert dry_run_data["candidate"]["ruleset_version"] == "sales-v2"
    assert dry_run_data["delta"]["overall_score"] > 0

    publish_v2 = await async_client.post(
        f"/api/v1/evaluation/admin/scoring-rulesets/{v2_id}/publish",
        json={"reason": "publish dry-run candidate"},
        headers=admin_headers,
    )
    assert publish_v2.status_code == 200
    assert publish_v2.json()["data"]["is_active"] is True

    report = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report",
        headers=user_headers,
    )
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["ruleset_version"] == "sales-v2"
    assert report_data["score_basis"] == SCORING_RULESET_SCORE_BASIS
    assert report_data["evidence_completeness"]["scoring_ruleset"]["version"] == "sales-v2"

    rollback = await async_client.post(
        f"/api/v1/evaluation/admin/scoring-rulesets/{v1_id}/rollback",
        json={"reason": "rollback after comparison"},
        headers=admin_headers,
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["version"] == "sales-v1"
    assert rollback.json()["data"]["is_active"] is True

    active_rows = (
        await db_session.execute(
            select(ScoringRuleset).where(
                ScoringRuleset.scenario_type == "sales",
                ScoringRuleset.is_active.is_(True),
            )
        )
    ).scalars().all()
    assert [row.version for row in active_rows] == ["sales-v1"]

    audit_actions = (
        await db_session.execute(
            select(SystemLog.action).where(
                SystemLog.action.in_(
                    ["scoring_ruleset.publish", "scoring_ruleset.rollback"]
                )
            )
        )
    ).scalars().all()
    assert audit_actions.count("scoring_ruleset.publish") == 2
    assert audit_actions.count("scoring_ruleset.rollback") == 1
