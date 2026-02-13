"""
Integration tests for session lifecycle REST controls.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PracticeSession, Scenario, User


def _headers_for_user(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_session(
    db_session: AsyncSession,
    *,
    user_id: str,
    scenario_type: str = "sales",
    status: str = "preparing",
) -> PracticeSession:
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type=scenario_type,
        name=f"lifecycle_{scenario_type}_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        scenario_id=scenario.scenario_id,
        status=status,
        voice_mode="legacy",
    )
    db_session.add_all([scenario, session])
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.mark.asyncio
async def test_lifecycle_api_start_pause_resume_end_sales(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    session = await _create_session(test_db, user_id=str(test_user.user_id), scenario_type="sales")
    session_id = str(session.session_id)
    headers = _headers_for_user(str(test_user.user_id))

    start_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=headers,
        json={"action": "start"},
    )
    assert start_response.status_code == 200
    start_body = start_response.json()
    assert start_body.get("trace_id")
    assert start_body["success"] is True
    assert start_body["data"]["previous_status"] == "preparing"
    assert start_body["data"]["status"] == "in_progress"
    assert start_body["data"]["ai_state"] == "listening"
    assert start_body["data"]["changed"] is True
    assert start_body["data"]["scenario_type"] == "sales"

    pause_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=headers,
        json={"action": "pause"},
    )
    assert pause_response.status_code == 200
    pause_body = pause_response.json()
    assert pause_body["data"]["previous_status"] == "in_progress"
    assert pause_body["data"]["status"] == "paused"
    assert pause_body["data"]["ai_state"] == "idle"

    resume_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=headers,
        json={"action": "resume"},
    )
    assert resume_response.status_code == 200
    resume_body = resume_response.json()
    assert resume_body["data"]["previous_status"] == "paused"
    assert resume_body["data"]["status"] == "in_progress"
    assert resume_body["data"]["ai_state"] == "listening"

    end_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=headers,
        json={"action": "end"},
    )
    assert end_response.status_code == 200
    end_body = end_response.json()
    assert end_body["data"]["previous_status"] == "in_progress"
    assert end_body["data"]["status"] == "scoring"
    assert end_body["data"]["ai_state"] == "idle"
    assert end_body["data"]["end_time"] is not None

    persisted_session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    persisted_session = persisted_session_result.scalar_one()
    assert persisted_session.status == "scoring"
    assert persisted_session.end_time is not None
    assert persisted_session.total_duration_seconds is not None
    assert persisted_session.total_duration_seconds >= 0


@pytest.mark.asyncio
async def test_lifecycle_api_rejects_invalid_transition_without_state_mutation(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    session = await _create_session(test_db, user_id=str(test_user.user_id), scenario_type="sales")
    session_id = str(session.session_id)
    headers = _headers_for_user(str(test_user.user_id))

    response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=headers,
        json={"action": "resume"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body.get("trace_id")
    assert body["success"] is False
    assert body["error"] == "[INVALID_SESSION_TRANSITION]"
    assert body["details"]["current_status"] == "preparing"
    assert body["details"]["requested_action"] == "resume"

    session_result = await test_db.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    persisted_session = session_result.scalar_one()
    assert persisted_session.status == "preparing"
    assert persisted_session.end_time is None


@pytest.mark.asyncio
async def test_lifecycle_api_enforces_owner_and_admin_access(
    async_client: AsyncClient,
    test_db: AsyncSession,
):
    owner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"owner_{uuid.uuid4().hex[:8]}",
        name="Lifecycle Owner",
        role="user",
    )
    outsider = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"outsider_{uuid.uuid4().hex[:8]}",
        name="Lifecycle Outsider",
        role="user",
    )
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_{uuid.uuid4().hex[:8]}",
        name="Lifecycle Admin",
        role="admin",
    )
    test_db.add_all([owner, outsider, admin])
    await test_db.commit()

    session = await _create_session(test_db, user_id=str(owner.user_id), scenario_type="presentation")
    session_id = str(session.session_id)

    outsider_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=_headers_for_user(str(outsider.user_id)),
        json={"action": "start"},
    )
    assert outsider_response.status_code == 403
    outsider_body = outsider_response.json()
    assert outsider_body["success"] is False
    assert outsider_body["error"] == "[ACCESS_DENIED]"
    assert outsider_body.get("trace_id")

    admin_response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=_headers_for_user(str(admin.user_id)),
        json={"action": "start"},
    )
    assert admin_response.status_code == 200
    admin_body = admin_response.json()
    assert admin_body["success"] is True
    assert admin_body["data"]["status"] == "in_progress"
    assert admin_body["data"]["scenario_type"] == "presentation"
