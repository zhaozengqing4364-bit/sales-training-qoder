"""
Integration tests for Admin Users API.

Covers create/update/deactivate flows, RBAC boundaries, audit logs, and
list/detail consistency.
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import Agent models so Base.metadata has all FK targets used by common models.
from agent.models import Agent, AgentPersona, Persona, VoiceRuntimeProfile  # noqa: F401
from common.db.models import Base, SystemLog, User
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
