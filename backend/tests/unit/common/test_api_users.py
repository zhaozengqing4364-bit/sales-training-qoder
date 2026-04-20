"""
Tests for Users API endpoints
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ManagerIntervention, PracticeSession, Scenario, User


@pytest.mark.asyncio
async def test_update_current_user_success(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test successful user profile update"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"name": "Updated Name", "department": "Engineering"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == "Updated Name"
    assert data["data"]["department"] == "Engineering"


@pytest.mark.asyncio
async def test_update_user_email_success(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test successful user email update"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"email": "newemail@example.com"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == test_user.name


@pytest.mark.asyncio
async def test_update_user_email_duplicate(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    another_user: User,
    auth_headers: dict,
):
    """Test that duplicate email is rejected"""
    response = await async_client.patch(
        "/api/v1/users/me",
        json={"email": another_user.email},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "EMAIL_ALREADY_EXISTS" in data["error"]


@pytest.mark.asyncio
async def test_update_user_partial_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test that only provided fields are updated"""
    original_department = test_user.department

    response = await async_client.patch(
        "/api/v1/users/me",
        json={"name": "New Name Only"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == "New Name Only"
    assert data["data"]["department"] == original_department


@pytest.mark.asyncio
async def test_update_user_no_fields(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    auth_headers: dict,
):
    """Test update with no fields provided"""
    response = await async_client.patch(
        "/api/v1/users/me", json={}, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["display_name"] == test_user.name


@pytest.mark.asyncio
async def test_update_user_unauthorized(
    async_client: AsyncClient,
):
    """Test that unauthorized requests are rejected"""
    response = await async_client.patch(
        "/api/v1/users/me", json={"name": "Unauthorized Update"}
    )

    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_get_open_intervention_returns_current_users_latest_focus(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    another_user: User,
    auth_headers: dict,
):
    older = datetime(2026, 4, 18, 9, 0, tzinfo=UTC)
    newer = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)
    test_db.add_all([
        ManagerIntervention(
            intervention_id=str(uuid.uuid4()),
            manager_user_id=str(another_user.user_id),
            user_id=str(test_user.user_id),
            issue_family="evidence_gap",
            note="先补一条客户案例。",
            due_state="pending",
            reminder_status="not_sent",
            created_at=older,
            updated_at=older,
        ),
        ManagerIntervention(
            intervention_id="latest-intervention",
            manager_user_id=str(another_user.user_id),
            user_id=str(test_user.user_id),
            issue_family="objection_handling",
            note="本周先处理价格异议。",
            due_state="due",
            reminder_status="sent",
            reminder_sent_at=newer,
            created_at=older,
            updated_at=newer,
        ),
    ])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/users/me/interventions/open",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["intervention_id"] == "latest-intervention"
    assert payload["issue_family"] == "objection_handling"
    assert payload["note"] == "本周先处理价格异议。"
    assert payload["due_state"] == "due"
    assert "manager_user_id" not in payload


@pytest.mark.asyncio
async def test_get_open_intervention_hides_resolved_and_other_users_focus(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    another_user: User,
    auth_headers: dict,
):
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="销售对练",
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(test_user.user_id),
        scenario_id=scenario.scenario_id,
        status="completed",
    )
    now = datetime(2026, 4, 19, 9, 0, tzinfo=UTC)
    test_db.add_all([
        scenario,
        session,
        ManagerIntervention(
            intervention_id=str(uuid.uuid4()),
            manager_user_id=str(another_user.user_id),
            user_id=str(test_user.user_id),
            issue_family="resolved_gap",
            note="已解决，不应展示。",
            due_state="resolved",
            reminder_status="sent",
            reminder_sent_at=now,
            resolving_session_id=session.session_id,
            created_at=now,
            updated_at=now,
        ),
        ManagerIntervention(
            intervention_id="other-user-intervention",
            manager_user_id=str(test_user.user_id),
            user_id=str(another_user.user_id),
            issue_family="other_user_gap",
            note="他人的提醒不能泄漏。",
            due_state="due",
            reminder_status="sent",
            reminder_sent_at=now + timedelta(minutes=1),
            created_at=now + timedelta(minutes=1),
            updated_at=now + timedelta(minutes=1),
        ),
    ])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/users/me/interventions/open",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.asyncio
async def test_get_open_intervention_requires_auth(async_client: AsyncClient):
    response = await async_client.get("/api/v1/users/me/interventions/open")

    assert response.status_code in [401, 403]
