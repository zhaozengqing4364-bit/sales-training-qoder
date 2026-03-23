"""
Integration tests for Admin Users API.

Covers create/update/deactivate flows, RBAC boundaries, audit logs, and
list/detail consistency.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.db.models import (
    Base,
    ConversationMessage,
    PracticeSession,
    Scenario,
    SystemLog,
    User,
)
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
    """Seed an admin user for RBAC-protected routes."""
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
async def non_admin_user(db_session: AsyncSession) -> User:
    """Seed a normal user for negative RBAC checks."""
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"user_{uuid.uuid4().hex[:8]}",
        name="Normal Tester",
        department="Sales",
        email="user@example.com",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """Provide HTTP client with DB dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    """Build JWT auth header for admin user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(non_admin_user: User) -> dict[str, str]:
    """Build JWT auth header for normal user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(non_admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_user_lifecycle_and_audit_log_fields(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    db_session: AsyncSession,
) -> None:
    """Admin create/update/deactivate should persist audit fields."""
    create_response = await async_client.post(
        "/api/v1/admin/users",
        json={
            "username": "story-user",
            "email": "story-user@example.com",
            "password": "Password123",
            "name": "Story User",
            "department": "Enablement",
            "role": "user",
            "audit_reason": "initial onboarding",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    created_data = create_response.json()["data"]
    user_id = created_data["id"]

    update_response = await async_client.put(
        f"/api/v1/admin/users/{user_id}",
        json={
            "name": "Story User Updated",
            "department": "Sales Ops",
            "audit_reason": "department restructure",
        },
        headers=admin_headers,
    )
    assert update_response.status_code == 200

    delete_response = await async_client.request(
        "DELETE",
        f"/api/v1/admin/users/{user_id}",
        json={"audit_reason": "account disabled for offboarding"},
        headers=admin_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True

    detail_response = await async_client.get(
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["status"] == "inactive"

    list_response = await async_client.get(
        "/api/v1/admin/users",
        params={"search": "story-user@example.com"},
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    listed_user = next(item for item in items if item["id"] == user_id)
    assert listed_user["display_name"] == "Story User Updated"
    assert listed_user["status"] == "inactive"

    logs_result = await db_session.execute(
        select(SystemLog).order_by(SystemLog.created_at.asc())
    )
    logs = logs_result.scalars().all()
    target_logs = []
    for log in logs:
        details = json.loads(log.details or "{}")
        if details.get("target_user_id") == user_id:
            target_logs.append((log, details))

    logged_actions = {log.action for log, _ in target_logs}
    assert "admin.user.created" in logged_actions
    assert "admin.user.updated" in logged_actions
    assert "admin.user.deactivated" in logged_actions

    for log, details in target_logs:
        assert details["operator_id"] == str(admin_user.user_id)
        assert "timestamp" in details
        assert "reason" in details
        assert details["operator_email_masked"].endswith("@example.com")
        assert "***" in details["operator_email_masked"]
        assert details["target_user_id"] == user_id
        if log.action == "admin.user.updated":
            assert details["before"]["name"] == "Story User"
            assert details["after"]["name"] == "Story User Updated"


@pytest.mark.asyncio
async def test_deactivated_user_blocked_from_authenticated_access(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    non_admin_user: User,
) -> None:
    """Deactivated accounts should be blocked with explainable error."""
    suspend_response = await async_client.post(
        f"/api/v1/admin/users/{non_admin_user.user_id}/suspend",
        json={"audit_reason": "policy violation"},
        headers=admin_headers,
    )
    assert suspend_response.status_code == 200

    me_response = await async_client.get("/api/v1/users/me", headers=user_headers)
    assert me_response.status_code == 403
    assert "disabled" in me_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_users_api(
    async_client: AsyncClient,
    user_headers: dict[str, str],
) -> None:
    """RBAC should reject non-admin requests to admin users endpoints."""
    response = await async_client.get("/api/v1/admin/users", headers=user_headers)

    assert response.status_code == 403
    assert "[ADMIN_REQUIRED]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_user_duplicate_email_returns_error_code(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    non_admin_user: User,
) -> None:
    """Duplicate email creation should return explicit error code."""
    response = await async_client.post(
        "/api/v1/admin/users",
        json={
            "username": "duplicate-user",
            "email": non_admin_user.email,
            "password": "Password123",
            "name": "Duplicate User",
            "department": "QA",
            "role": "user",
            "audit_reason": "duplicate check",
        },
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "[EMAIL_ALREADY_EXISTS]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_multiple_updates_keep_list_and_detail_consistent(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Repeated updates should keep list and detail views consistent."""
    create_response = await async_client.post(
        "/api/v1/admin/users",
        json={
            "username": "concurrency-user",
            "email": "concurrency-user@example.com",
            "password": "Password123",
            "name": "Concurrency User",
            "department": "Dept-0",
            "role": "user",
            "audit_reason": "create for concurrency test",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["data"]["id"]

    response_a = await async_client.put(
        f"/api/v1/admin/users/{user_id}",
        json={
            "name": "Concurrency A",
            "department": "Dept-A",
            "audit_reason": "update A",
        },
        headers=admin_headers,
    )
    response_b = await async_client.put(
        f"/api/v1/admin/users/{user_id}",
        json={
            "name": "Concurrency B",
            "department": "Dept-B",
            "audit_reason": "update B",
        },
        headers=admin_headers,
    )
    assert response_a.status_code == 200
    assert response_b.status_code == 200

    detail_response = await async_client.get(
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    detail_user = detail_response.json()["data"]

    list_response = await async_client.get(
        "/api/v1/admin/users",
        params={"search": "concurrency-user@example.com"},
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    list_user = next(
        item
        for item in list_response.json()["data"]["items"]
        if item["id"] == user_id
    )

    assert detail_user["display_name"] == "Concurrency B"
    assert detail_user["department"] == "Dept-B"
    assert list_user["display_name"] == detail_user["display_name"]
    assert list_user["department"] == detail_user["department"]


@pytest.mark.asyncio
async def test_admin_can_update_user_role_and_persist_audit_fields(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    db_session: AsyncSession,
) -> None:
    """Admin role assignment should be effective immediately and audited."""
    create_response = await async_client.post(
        "/api/v1/admin/users",
        json={
            "username": "role-user",
            "email": "role-user@example.com",
            "password": "Password123",
            "name": "Role User",
            "department": "Enablement",
            "role": "user",
            "audit_reason": "seed role update test",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["data"]["id"]

    role_response = await async_client.put(
        f"/api/v1/admin/users/{user_id}/role",
        json={"role": "admin", "audit_reason": "promote for incident handling"},
        headers=admin_headers,
    )
    assert role_response.status_code == 200
    assert role_response.json()["data"]["role"] == "admin"

    detail_response = await async_client.get(
        f"/api/v1/admin/users/{user_id}",
        headers=admin_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["role"] == "admin"

    list_response = await async_client.get(
        "/api/v1/admin/users",
        params={"search": "role-user@example.com"},
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    list_user = next(
        item
        for item in list_response.json()["data"]["items"]
        if item["id"] == user_id
    )
    assert list_user["role"] == "admin"

    logs_result = await db_session.execute(
        select(SystemLog).order_by(SystemLog.created_at.asc())
    )
    logs = logs_result.scalars().all()
    role_update_logs = []
    for log in logs:
        details = json.loads(log.details or "{}")
        if (
            details.get("target_user_id") == user_id
            and log.action == "admin.user.role.updated"
        ):
            role_update_logs.append((log, details))

    assert role_update_logs, "expected role update audit log"
    _, details = role_update_logs[-1]
    assert details["operator_id"] == str(admin_user.user_id)
    assert details["reason"] == "promote for incident handling"
    assert details["before"]["role"] == "user"
    assert details["after"]["role"] == "admin"


@pytest.mark.asyncio
async def test_non_admin_cannot_update_user_role(
    async_client: AsyncClient,
    user_headers: dict[str, str],
    non_admin_user: User,
) -> None:
    """Role update endpoint should enforce admin permission boundary."""
    response = await async_client.put(
        f"/api/v1/admin/users/{non_admin_user.user_id}/role",
        json={"role": "admin", "audit_reason": "forbidden"},
        headers=user_headers,
    )

    assert response.status_code == 403
    assert "[ADMIN_REQUIRED]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_update_rejects_self_downgrade(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
) -> None:
    """Admin should not be able to downgrade own role."""
    response = await async_client.put(
        f"/api/v1/admin/users/{admin_user.user_id}/role",
        json={"role": "user", "audit_reason": "should fail"},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "[CANNOT_DOWNGRADE_SELF]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_user_endpoint_rejects_role_changes(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Generic update endpoint should enforce dedicated role route."""
    create_response = await async_client.post(
        "/api/v1/admin/users",
        json={
            "username": "update-user-role-blocked",
            "email": "update-user-role-blocked@example.com",
            "password": "Password123",
            "name": "Role Blocked",
            "department": "QA",
            "role": "user",
            "audit_reason": "seed role-block test",
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["data"]["id"]

    response = await async_client.put(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "admin", "audit_reason": "should use dedicated endpoint"},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "[ROLE_UPDATE_REQUIRES_DEDICATED_ENDPOINT]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_update_rejects_invalid_role_error_code(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    non_admin_user: User,
) -> None:
    """Dedicated role endpoint should return explicit invalid-role error code."""
    response = await async_client.put(
        f"/api/v1/admin/users/{non_admin_user.user_id}/role",
        json={"role": "super-admin", "audit_reason": "invalid role"},
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "[INVALID_ROLE]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_update_returns_user_not_found_error_code(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    """Dedicated role endpoint should return not-found error code for unknown user."""
    response = await async_client.put(
        f"/api/v1/admin/users/{uuid.uuid4()}/role",
        json={"role": "admin", "audit_reason": "unknown user"},
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert "[USER_NOT_FOUND]" in response.json()["detail"]


@pytest.mark.asyncio
async def test_promoted_user_can_access_admin_api_immediately_with_same_token(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    non_admin_user: User,
) -> None:
    """Role promotion should be immediately effective in RBAC checks."""
    before_response = await async_client.get("/api/v1/admin/users", headers=user_headers)
    assert before_response.status_code == 403
    assert "[ADMIN_REQUIRED]" in before_response.json()["detail"]

    promote_response = await async_client.put(
        f"/api/v1/admin/users/{non_admin_user.user_id}/role",
        json={"role": "admin", "audit_reason": "promote for immediate access test"},
        headers=admin_headers,
    )
    assert promote_response.status_code == 200
    assert promote_response.json()["data"]["role"] == "admin"

    after_response = await async_client.get("/api/v1/admin/users", headers=user_headers)
    assert after_response.status_code == 200
    assert after_response.json()["success"] is True


@pytest.mark.asyncio
async def test_user_sessions_completed_rows_expose_projection_backed_preview_fields(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    non_admin_user: User,
) -> None:
    """Completed session rows should expose unified evidence preview instead of legacy weighting."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="大客户销售演练",
        description="Projection-backed preview test",
        is_active=True,
    )
    db_session.add(scenario)
    await db_session.flush()

    completed_start = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
    completed_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        start_time=completed_start,
        end_time=completed_start + timedelta(minutes=4),
        total_duration_seconds=240,
        logic_score=40,
        accuracy_score=50,
        completeness_score=60,
        interruption_count=1,
        effectiveness_snapshot={
            "metrics": {
                "continuous_speech_seconds": 240,
                "filler_rate_per_100_words": 8.0,
                "offtopic_turn_count": 1,
                "offtopic_max_streak": 0,
                "structure_coverage": 0.6,
            },
            "pass_flags": {
                "pass_3min_flow": False,
                "pass_5turn_defense": False,
                "pass_4step_structure": False,
            },
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {
                "issue_type": "main_capability_not_passed",
                "issue_text": "关键异议回应不够具体。",
                "recovery_rule": "先回应风险，再补证据。",
            },
            "next_goal": {
                "goal_type": "single_next_goal",
                "goal_text": "下一轮先把异议处理说完整。",
                "rule": "至少完成 1 次完整异议回应。",
            },
            "evaluable": True,
            "not_evaluable_reason": None,
        },
    )
    in_progress_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        start_time=completed_start + timedelta(days=1),
        total_duration_seconds=90,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=0,
    )
    db_session.add_all([completed_session, in_progress_session])
    await db_session.flush()

    db_session.add_all(
        [
            ConversationMessage(
                session_id=str(completed_session.session_id),
                turn_number=1,
                role="user",
                content="先介绍产品价值。",
                timestamp=completed_start,
                duration_ms=45000,
                sales_stage="opening",
            ),
            ConversationMessage(
                session_id=str(completed_session.session_id),
                turn_number=2,
                role="assistant",
                content="客户追问交付风险。",
                timestamp=completed_start + timedelta(seconds=45),
                duration_ms=55000,
                sales_stage="objection",
                score_snapshot={
                    "overall": 55,
                    "dimensions": [
                        {"name": "逻辑性", "score": 40},
                        {"name": "准确性", "score": 50},
                        {"name": "完整性", "score": 60},
                    ],
                },
            ),
        ]
    )
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/admin/users/{non_admin_user.user_id}/sessions",
        params={"page": 1, "page_size": 10},
        headers=admin_headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["has_more"] is False

    completed_row = next(
        item for item in payload["items"] if item["session_id"] == str(completed_session.session_id)
    )
    in_progress_row = next(
        item for item in payload["items"] if item["session_id"] == str(in_progress_session.session_id)
    )

    assert completed_row["scores"]["overall"] == 50.0
    assert completed_row["scores"]["logic"] == 40.0
    assert completed_row["scores"]["accuracy"] == 50.0
    assert completed_row["scores"]["completeness"] == 60.0
    assert completed_row["overall_result"] == "fail"
    assert completed_row["evaluable"] is True
    assert completed_row["not_evaluable_reason"] is None
    assert completed_row["main_issue"]["issue_text"] == "关键异议回应不够具体。"
    assert completed_row["next_goal"]["goal_text"] == "下一轮先把异议处理说完整。"
    assert completed_row["feedback_summary"] == "关键异议回应不够具体。"
    assert completed_row["evidence_completeness"]["message_count"] == 2

    assert in_progress_row["scores"]["overall"] is None
    assert in_progress_row.get("overall_result") is None
    assert in_progress_row.get("evaluable") is None
    assert in_progress_row.get("main_issue") is None
    assert in_progress_row.get("next_goal") is None


@pytest.mark.asyncio
async def test_admin_progress_and_stats_follow_projection_backed_supervisor_snapshot(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
    non_admin_user: User,
) -> None:
    """Admin progress/stats should align with projection-backed preview scores and supervisor buckets."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="重点客户推进",
        description="Supervisor progress snapshot test",
        is_active=True,
    )
    db_session.add(scenario)
    await db_session.flush()

    repeated_effectiveness_snapshot = {
        "metrics": {
            "continuous_speech_seconds": 240,
            "filler_rate_per_100_words": 8.0,
            "offtopic_turn_count": 1,
            "offtopic_max_streak": 0,
            "structure_coverage": 0.6,
        },
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "main_issue": {
            "issue_type": "objection_response",
            "issue_text": "异议回应不够具体。",
            "recovery_rule": "先回应风险，再补证据。",
        },
        "next_goal": {
            "goal_type": "objection_response_drill",
            "goal_text": "下一轮继续把异议回应说完整。",
            "rule": "至少完成 1 次完整异议回应。",
        },
        "evaluable": True,
        "not_evaluable_reason": None,
    }
    not_evaluable_snapshot = {
        "metrics": {
            "continuous_speech_seconds": 20,
            "filler_rate_per_100_words": 0.0,
            "offtopic_turn_count": 0,
            "offtopic_max_streak": 0,
            "structure_coverage": 0.0,
        },
        "pass_flags": {
            "pass_3min_flow": False,
            "pass_5turn_defense": False,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "main_issue": {
            "issue_type": "insufficient_turn_data",
            "issue_text": "当前互动不足，暂时无法判断真实问题。",
            "recovery_rule": "至少完成一轮用户表达和 AI 回应。",
        },
        "next_goal": {
            "goal_type": "collect_more_evidence",
            "goal_text": "先补齐有效互动，再继续诊断。",
            "rule": "至少完成 1 次往返对话。",
        },
        "evaluable": False,
        "not_evaluable_reason": "INSUFFICIENT_TURN_DATA",
    }

    session_a_start = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)
    session_b_start = datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc)
    session_c_start = datetime(2026, 3, 10, 11, 0, tzinfo=timezone.utc)

    session_a = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        start_time=session_a_start,
        end_time=session_a_start + timedelta(minutes=4),
        total_duration_seconds=240,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=1,
        effectiveness_snapshot=repeated_effectiveness_snapshot,
    )
    session_b = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        start_time=session_b_start,
        end_time=session_b_start + timedelta(minutes=5),
        total_duration_seconds=300,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=1,
        effectiveness_snapshot=repeated_effectiveness_snapshot,
    )
    session_c = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        start_time=session_c_start,
        end_time=session_c_start + timedelta(minutes=4),
        total_duration_seconds=240,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=2,
        effectiveness_snapshot=repeated_effectiveness_snapshot,
    )
    not_evaluable_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        start_time=session_b_start + timedelta(hours=2),
        end_time=session_b_start + timedelta(hours=2, minutes=1),
        total_duration_seconds=60,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=0,
        effectiveness_snapshot=not_evaluable_snapshot,
    )
    in_progress_session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(non_admin_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="in_progress",
        start_time=session_c_start + timedelta(days=1),
        total_duration_seconds=120,
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        interruption_count=0,
    )
    db_session.add_all(
        [
            session_a,
            session_b,
            session_c,
            not_evaluable_session,
            in_progress_session,
        ]
    )
    await db_session.flush()

    db_session.add_all(
        [
            ConversationMessage(
                session_id=str(session_a.session_id),
                turn_number=1,
                role="user",
                content="先说明业务背景。",
                timestamp=session_a_start,
                duration_ms=45000,
                sales_stage="opening",
            ),
            ConversationMessage(
                session_id=str(session_a.session_id),
                turn_number=2,
                role="assistant",
                content="客户追问交付风险。",
                timestamp=session_a_start + timedelta(seconds=45),
                duration_ms=55000,
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 50,
                    "dimension_scores": {
                        "professional": 40,
                        "communication": 50,
                        "discovery": 60,
                    },
                },
            ),
            ConversationMessage(
                session_id=str(session_b.session_id),
                turn_number=1,
                role="user",
                content="先确认客户现状。",
                timestamp=session_b_start,
                duration_ms=50000,
                sales_stage="discovery",
            ),
            ConversationMessage(
                session_id=str(session_b.session_id),
                turn_number=2,
                role="assistant",
                content="客户继续追问风险控制。",
                timestamp=session_b_start + timedelta(seconds=50),
                duration_ms=60000,
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 70,
                    "dimension_scores": {
                        "professional": 60,
                        "communication": 70,
                        "discovery": 80,
                    },
                },
            ),
            ConversationMessage(
                session_id=str(session_c.session_id),
                turn_number=1,
                role="user",
                content="先介绍方案。",
                timestamp=session_c_start,
                duration_ms=42000,
                sales_stage="opening",
            ),
            ConversationMessage(
                session_id=str(session_c.session_id),
                turn_number=2,
                role="assistant",
                content="客户继续担心落地风险。",
                timestamp=session_c_start + timedelta(seconds=42),
                duration_ms=58000,
                sales_stage="objection",
                score_snapshot={
                    "overall_score": 40,
                    "dimension_scores": {
                        "professional": 30,
                        "communication": 40,
                        "discovery": 50,
                    },
                },
            ),
        ]
    )
    await db_session.commit()

    sessions_response = await async_client.get(
        f"/api/v1/admin/users/{non_admin_user.user_id}/sessions",
        params={"page": 1, "page_size": 10},
        headers=admin_headers,
    )
    stats_response = await async_client.get(
        f"/api/v1/admin/users/{non_admin_user.user_id}/stats",
        params={"time_range": "all_time"},
        headers=admin_headers,
    )
    progress_day_response = await async_client.get(
        f"/api/v1/admin/users/{non_admin_user.user_id}/progress",
        params={"time_range": "all_time", "granularity": "day"},
        headers=admin_headers,
    )
    progress_week_response = await async_client.get(
        f"/api/v1/admin/users/{non_admin_user.user_id}/progress",
        params={"time_range": "all_time", "granularity": "week"},
        headers=admin_headers,
    )

    assert sessions_response.status_code == 200
    assert stats_response.status_code == 200
    assert progress_day_response.status_code == 200
    assert progress_week_response.status_code == 200

    sessions_payload = sessions_response.json()["data"]
    session_score_map = {
        item["session_id"]: item["scores"]["overall"]
        for item in sessions_payload["items"]
        if item["status"] == "completed" and item.get("evaluable") is True
    }
    assert session_score_map == {
        str(session_c.session_id): 40.0,
        str(session_b.session_id): 70.0,
        str(session_a.session_id): 50.0,
    }

    stats_payload = stats_response.json()["data"]
    score_values = list(session_score_map.values())
    assert stats_payload["statistics"]["average_score"] == pytest.approx(
        round(sum(score_values) / len(score_values), 1)
    )
    assert stats_payload["statistics"]["best_score"] == max(score_values)
    assert stats_payload["statistics"]["worst_score"] == min(score_values)
    assert stats_payload["statistics"]["total_sessions"] == 5
    assert stats_payload["statistics"]["completed_sessions"] == 4

    progress_day = progress_day_response.json()["data"]
    assert progress_day["granularity"] == "day"
    assert [point["date"][:10] for point in progress_day["trend_data"]] == [
        "2026-03-02",
        "2026-03-05",
        "2026-03-10",
    ]

    progress_week = progress_week_response.json()["data"]
    assert progress_week["granularity"] == "week"
    assert [point["date"][:10] for point in progress_week["trend_data"]] == [
        "2026-03-02",
        "2026-03-09",
    ]
    assert [point["average_score"] for point in progress_week["trend_data"]] == [60.0, 40.0]
    assert progress_week["trend_data"][0]["sessions_count"] == 3
    assert progress_week["trend_data"][0]["evaluable_session_count"] == 2
    assert progress_week["trend_data"][0]["not_evaluable_session_count"] == 1
    assert progress_week["trend_data"][0]["overall_result"] == "fail"
    assert progress_week["trend_data"][0]["main_issue"]["issue_type"] == "objection_response"
    assert progress_week["trend_data"][0]["next_goal"]["goal_type"] == "objection_response_drill"
    assert progress_week["not_evaluable_session_count"] == 1
    assert progress_week["non_completed_session_count"] == 1
    assert progress_week["repeated_main_issues"] == [
        {
            "issue_type": "objection_response",
            "issue_text": "异议回应不够具体。",
            "count": 3,
        }
    ]
    assert progress_week["repeated_next_goals"] == [
        {
            "goal_type": "objection_response_drill",
            "goal_text": "下一轮继续把异议回应说完整。",
            "count": 3,
        }
    ]
    assert progress_week["should_switch_focus"] is True
    assert progress_week["recommendation"] == {
        "reason": "stalled_repeated_focus",
        "summary": "最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。",
    }
