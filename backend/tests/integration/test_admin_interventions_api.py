"""Integration tests for admin intervention persistence APIs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from admin.api import interventions as interventions_api

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.auth.service import create_access_token
from common.db.models import Base, PracticeSession, Scenario, User
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create isolated in-memory DB for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Provide async DB session bound to test engine."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_{uuid.uuid4().hex[:8]}",
        name="Admin Tester",
        department="Ops",
        email="admin@example.com",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def trainee_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"trainee_{uuid.uuid4().hex[:8]}",
        name="Trainee Tester",
        department="Sales",
        email="trainee@example.com",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sales_scenario(db_session: AsyncSession) -> Scenario:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="Sales Scenario",
        description="seeded for intervention tests",
        is_active=True,
    )
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_completed_session(
    db_session: AsyncSession,
    *,
    user_id: str,
    scenario_id: str,
) -> PracticeSession:
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario_id,
        status="completed",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        total_duration_seconds=180,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.mark.asyncio
async def test_admin_can_create_and_list_manager_interventions(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    trainee_user: User,
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "evidence_gap",
            "note": "优先补 ROI 和客户案例证据。",
            "due_state": "pending",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["user_id"] == str(trainee_user.user_id)
    assert created["issue_family"] == "evidence_gap"
    assert created["note"] == "优先补 ROI 和客户案例证据。"
    assert created["due_state"] == "pending"
    assert created["reminder_status"] == "not_sent"
    assert created["resolving_session_id"] is None

    list_response = await async_client.get(
        "/api/v1/admin/interventions",
        params={"user_id": str(trainee_user.user_id)},
        headers=admin_headers,
    )

    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["intervention_id"] == created["intervention_id"]
    assert items[0]["issue_family"] == "evidence_gap"

    row = (
        await db_session.execute(
            text(
                "SELECT issue_family, note, due_state, reminder_status, resolving_session_id "
                "FROM manager_interventions WHERE intervention_id = :intervention_id"
            ),
            {"intervention_id": created["intervention_id"]},
        )
    ).mappings().one()
    assert row["issue_family"] == "evidence_gap"
    assert row["note"] == "优先补 ROI 和客户案例证据。"
    assert row["due_state"] == "pending"
    assert row["reminder_status"] == "not_sent"
    assert row["resolving_session_id"] is None


@pytest.mark.asyncio
async def test_remind_route_marks_existing_intervention_sent(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    trainee_user: User,
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "value_expression",
            "note": "先建立价值表达重点。",
        },
        headers=admin_headers,
    )
    intervention_id = create_response.json()["data"]["intervention_id"]

    remind_response = await async_client.post(
        "/api/v1/admin/interventions/remind",
        json={
            "user_id": str(trainee_user.user_id),
            "intervention_id": intervention_id,
            "note": "请本周补一次围绕价值表达的练习。",
        },
        headers=admin_headers,
    )

    assert remind_response.status_code == 200
    remind_data = remind_response.json()["data"]
    assert remind_data["sent"] is True
    assert remind_data["user_id"] == str(trainee_user.user_id)

    row = (
        await db_session.execute(
            text(
                "SELECT note, due_state, reminder_status, reminder_sent_at "
                "FROM manager_interventions WHERE intervention_id = :intervention_id"
            ),
            {"intervention_id": intervention_id},
        )
    ).mappings().one()
    assert row["note"] == "请本周补一次围绕价值表达的练习。"
    assert row["due_state"] == "due"
    assert row["reminder_status"] == "sent"
    assert row["reminder_sent_at"] is not None


@pytest.mark.asyncio
async def test_remind_route_translates_intervention_user_mismatch_business_error(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    trainee_user: User,
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "value_expression",
            "note": "先建立价值表达重点。",
        },
        headers=admin_headers,
    )
    intervention_id = create_response.json()["data"]["intervention_id"]
    other_user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"other_trainee_{uuid.uuid4().hex[:8]}",
        name="Other Trainee",
        department="Sales",
        email=f"other-trainee-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    remind_response = await async_client.post(
        "/api/v1/admin/interventions/remind",
        json={
            "user_id": str(other_user.user_id),
            "intervention_id": intervention_id,
            "note": "请本周补一次围绕价值表达的练习。",
        },
        headers=admin_headers,
    )

    assert remind_response.status_code == 400
    assert remind_response.json()["detail"] == "[INTERVENTION_USER_MISMATCH]"


@pytest.mark.asyncio
async def test_manager_lite_remind_without_intervention_id_updates_latest_open_focus(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    trainee_user: User,
    db_session: AsyncSession,
) -> None:
    older_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "evidence_gap",
            "note": "先补 ROI 和客户案例证据。",
        },
        headers=admin_headers,
    )
    older_id = older_response.json()["data"]["intervention_id"]

    latest_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "objection_response",
            "note": "下一轮继续把异议回应说完整。",
        },
        headers=admin_headers,
    )
    latest_id = latest_response.json()["data"]["intervention_id"]

    remind_response = await async_client.post(
        "/api/v1/admin/interventions/remind",
        json={
            "user_id": str(trainee_user.user_id),
            "note": "请按本周主管重点完成一次围绕异议回应的复练。",
        },
        headers=admin_headers,
    )

    assert remind_response.status_code == 200
    remind_data = remind_response.json()["data"]
    assert remind_data["sent"] is True
    assert remind_data["user_id"] == str(trainee_user.user_id)
    assert remind_data["intervention_id"] == latest_id

    latest_row = (
        await db_session.execute(
            text(
                "SELECT issue_family, note, due_state, reminder_status, reminder_sent_at "
                "FROM manager_interventions WHERE intervention_id = :intervention_id"
            ),
            {"intervention_id": latest_id},
        )
    ).mappings().one()
    assert latest_row["issue_family"] == "objection_response"
    assert latest_row["note"] == "请按本周主管重点完成一次围绕异议回应的复练。"
    assert latest_row["due_state"] == "due"
    assert latest_row["reminder_status"] == "sent"
    assert latest_row["reminder_sent_at"] is not None

    older_row = (
        await db_session.execute(
            text(
                "SELECT issue_family, note, due_state, reminder_status, reminder_sent_at "
                "FROM manager_interventions WHERE intervention_id = :intervention_id"
            ),
            {"intervention_id": older_id},
        )
    ).mappings().one()
    assert older_row["issue_family"] == "evidence_gap"
    assert older_row["note"] == "先补 ROI 和客户案例证据。"
    assert older_row["due_state"] == "pending"
    assert older_row["reminder_status"] == "not_sent"
    assert older_row["reminder_sent_at"] is None


@pytest.mark.asyncio
async def test_admin_can_link_intervention_to_resolving_session(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    trainee_user: User,
    sales_scenario: Scenario,
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/interventions",
        json={
            "user_id": str(trainee_user.user_id),
            "issue_family": "objection_response",
            "note": "围绕价格异议做一次复练。",
        },
        headers=admin_headers,
    )
    intervention_id = create_response.json()["data"]["intervention_id"]
    resolving_session = await _create_completed_session(
        db_session,
        user_id=str(trainee_user.user_id),
        scenario_id=str(sales_scenario.scenario_id),
    )

    update_response = await async_client.patch(
        f"/api/v1/admin/interventions/{intervention_id}",
        json={
            "due_state": "resolved",
            "resolving_session_id": str(resolving_session.session_id),
        },
        headers=admin_headers,
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["intervention_id"] == intervention_id
    assert updated["due_state"] == "resolved"
    assert updated["resolving_session_id"] == str(resolving_session.session_id)

    row = (
        await db_session.execute(
            text(
                "SELECT due_state, resolving_session_id FROM manager_interventions "
                "WHERE intervention_id = :intervention_id"
            ),
            {"intervention_id": intervention_id},
        )
    ).mappings().one()
    assert row["due_state"] == "resolved"
    assert row["resolving_session_id"] == str(resolving_session.session_id)


@pytest.mark.asyncio
async def test_create_route_delegates_to_manager_intervention_write_service(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    trainee_user: User,
) -> None:
    observed: dict[str, object] = {}
    timestamp = datetime.now(UTC)

    class FakeWriteService:
        def __init__(self, db: AsyncSession) -> None:
            observed["db_bound"] = db is not None

        async def create_intervention(self, *, payload, current_user):
            observed["payload_user_id"] = str(payload.user_id)
            observed["payload_issue_family"] = payload.issue_family
            observed["payload_note"] = payload.note
            observed["current_user_id"] = str(current_user.user_id)
            return SimpleNamespace(
                intervention_id=uuid.uuid4(),
                manager_user_id=uuid.UUID(str(admin_user.user_id)),
                user_id=uuid.UUID(str(trainee_user.user_id)),
                issue_family=payload.issue_family,
                note=payload.note,
                due_state="pending",
                reminder_status="not_sent",
                reminder_sent_at=None,
                resolving_session_id=None,
                created_at=timestamp,
                updated_at=timestamp,
            )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        interventions_api,
        "ManagerInterventionWriteService",
        FakeWriteService,
    )
    try:
        response = await async_client.post(
            "/api/v1/admin/interventions",
            json={
                "user_id": str(trainee_user.user_id),
                "issue_family": "evidence_gap",
                "note": "优先补 ROI 和客户案例证据。",
            },
            headers=admin_headers,
        )
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert observed == {
        "db_bound": True,
        "payload_user_id": str(trainee_user.user_id),
        "payload_issue_family": "evidence_gap",
        "payload_note": "优先补 ROI 和客户案例证据。",
        "current_user_id": str(admin_user.user_id),
    }
    payload = response.json()["data"]
    assert payload["user_id"] == str(trainee_user.user_id)
    assert payload["manager_user_id"] == str(admin_user.user_id)
    assert payload["issue_family"] == "evidence_gap"
    assert payload["due_state"] == "pending"
    assert payload["reminder_status"] == "not_sent"


@pytest.mark.asyncio
async def test_update_route_delegates_to_manager_intervention_write_service(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    trainee_user: User,
) -> None:
    intervention_id = str(uuid.uuid4())
    resolving_session_id = str(uuid.uuid4())
    observed: dict[str, object] = {}
    timestamp = datetime.now(UTC)

    class FakeWriteService:
        def __init__(self, db: AsyncSession) -> None:
            observed["db_bound"] = db is not None

        async def update_intervention(self, *, intervention_id: str, payload):
            observed["intervention_id"] = intervention_id
            observed["payload_due_state"] = (
                payload.due_state.value if payload.due_state is not None else None
            )
            observed["payload_resolving_session_id"] = str(payload.resolving_session_id)
            return SimpleNamespace(
                intervention_id=uuid.UUID(intervention_id),
                manager_user_id=uuid.UUID(str(admin_user.user_id)),
                user_id=uuid.UUID(str(trainee_user.user_id)),
                issue_family="objection_response",
                note="围绕价格异议做一次复练。",
                due_state="resolved",
                reminder_status="not_sent",
                reminder_sent_at=None,
                resolving_session_id=uuid.UUID(resolving_session_id),
                created_at=timestamp,
                updated_at=timestamp,
            )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        interventions_api,
        "ManagerInterventionWriteService",
        FakeWriteService,
    )
    try:
        response = await async_client.patch(
            f"/api/v1/admin/interventions/{intervention_id}",
            json={
                "due_state": "resolved",
                "resolving_session_id": resolving_session_id,
            },
            headers=admin_headers,
        )
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert observed == {
        "db_bound": True,
        "intervention_id": intervention_id,
        "payload_due_state": "resolved",
        "payload_resolving_session_id": resolving_session_id,
    }
    payload = response.json()["data"]
    assert payload["intervention_id"] == intervention_id
    assert payload["due_state"] == "resolved"
    assert payload["resolving_session_id"] == resolving_session_id


@pytest.mark.asyncio
async def test_remind_route_delegates_to_manager_intervention_write_service(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    trainee_user: User,
) -> None:
    intervention_id = str(uuid.uuid4())
    observed: dict[str, object] = {}

    class FakeWriteService:
        def __init__(self, db: AsyncSession) -> None:
            observed["db_bound"] = db is not None

        async def remind_user(self, *, payload, current_user):
            observed["payload_user_id"] = str(payload.user_id)
            observed["payload_intervention_id"] = str(payload.intervention_id)
            observed["payload_note"] = payload.note
            observed["current_user_id"] = str(current_user.user_id)
            return {
                "sent": True,
                "reminder_id": "delegated-reminder-id",
                "user_id": str(payload.user_id),
                "intervention_id": intervention_id,
            }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        interventions_api,
        "ManagerInterventionWriteService",
        FakeWriteService,
    )
    try:
        response = await async_client.post(
            "/api/v1/admin/interventions/remind",
            json={
                "user_id": str(trainee_user.user_id),
                "intervention_id": intervention_id,
                "note": "请本周补一次围绕价值表达的练习。",
            },
            headers=admin_headers,
        )
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert observed == {
        "db_bound": True,
        "payload_user_id": str(trainee_user.user_id),
        "payload_intervention_id": intervention_id,
        "payload_note": "请本周补一次围绕价值表达的练习。",
        "current_user_id": str(admin_user.user_id),
    }
    assert response.json()["data"] == {
        "sent": True,
        "reminder_id": "delegated-reminder-id",
        "user_id": str(trainee_user.user_id),
        "intervention_id": intervention_id,
    }
