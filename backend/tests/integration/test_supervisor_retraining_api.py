from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import PracticeSession, Presentation, Scenario, User


async def _create_user(
    db: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=email_prefix,
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_presentation_session(
    db: AsyncSession,
    *,
    user: User,
    status: str = "completed",
    logic_score: float = 62.0,
    accuracy_score: float = 70.0,
    completeness_score: float = 66.0,
) -> PracticeSession:
    presentation = Presentation(
        presentation_id=str(uuid.uuid4()),
        title="Supervisor Phase 2 Deck",
        file_url="/tmp/supervisor-phase2.pptx",
        status="ready",
        total_pages=3,
        ocr_progress=1.0,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="presentation",
        name=f"presentation_{uuid.uuid4().hex[:8]}",
        description="Presentation review scenario",
        is_active=True,
    )
    db.add_all([presentation, scenario])
    await db.flush()
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(user.user_id),
        scenario_id=str(scenario.scenario_id),
        presentation_id=str(presentation.presentation_id),
        status=status,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) if status == "completed" else None,
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        report_status="completed",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_supervisor_review_creates_retraining_task_and_before_after(
    async_client,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRESENTATION_REQUIRE_AGENT_PERSONA", "false")
    trainee = await _create_user(test_db, role="user", email_prefix="phase2-trainee")
    supervisor = await _create_user(
        test_db, role="admin", email_prefix="phase2-supervisor"
    )
    source_session = await _create_presentation_session(test_db, user=trainee)

    review_response = await async_client.post(
        "/api/v1/supervisor/reviews",
        headers=_auth_headers(supervisor),
        json={
            "session_id": str(source_session.session_id),
            "decision": "needs_retraining",
            "readiness_status": "shadow_only",
            "comment": "补强演讲结构后再试讲。",
            "required_retraining": True,
            "skill_dimension": "逻辑结构",
        },
    )

    assert review_response.status_code == 201
    review_body = review_response.json()["data"]
    assert review_body["decision"] == "needs_retraining"
    assert review_body["required_retraining"] is True
    assert review_body["retraining_tasks"][0]["skill_dimension"] == "逻辑结构"

    task = review_body["retraining_tasks"][0]
    task_response = await async_client.get(
        "/api/v1/retraining/tasks",
        headers=_auth_headers(trainee),
    )
    assert task_response.status_code == 200
    tasks = task_response.json()["data"]
    assert [item["task_id"] for item in tasks] == [task["task_id"]]

    start_response = await async_client.post(
        f"/api/v1/retraining/tasks/{task['task_id']}/start-session",
        headers=_auth_headers(trainee),
    )
    assert start_response.status_code == 200
    started_session_id = start_response.json()["data"]["session_id"]

    started_session = await test_db.get(PracticeSession, started_session_id)
    assert started_session is not None
    setattr(started_session, "status", "completed")
    setattr(started_session, "end_time", datetime.now(UTC))
    setattr(started_session, "logic_score", 82.0)
    setattr(started_session, "accuracy_score", 78.0)
    setattr(started_session, "completeness_score", 80.0)
    await test_db.commit()

    complete_response = await async_client.post(
        f"/api/v1/retraining/tasks/{task['task_id']}/complete-with-session",
        headers=_auth_headers(trainee),
        json={"completed_session_id": started_session_id},
    )
    assert complete_response.status_code == 200
    completed_task = complete_response.json()["data"]
    assert completed_task["status"] == "completed"
    assert completed_task["before_after"]["retraining_completed"] is True
    assert completed_task["before_after"]["score_delta"] > 0

    reports_response = await async_client.get(
        "/api/v1/supervisor/team/reports",
        headers=_auth_headers(supervisor),
    )
    assert reports_response.status_code == 200
    reports = reports_response.json()["data"]
    source_report = next(
        item for item in reports if item["session_id"] == str(source_session.session_id)
    )
    assert source_report["latest_review"]["decision"] == "needs_retraining"
    assert source_report["before_after"]["completed_session_id"] == started_session_id


@pytest.mark.asyncio
async def test_supervisor_write_routes_reject_non_admin(
    async_client,
    test_db: AsyncSession,
) -> None:
    trainee = await _create_user(test_db, role="user", email_prefix="phase2-user")
    source_session = await _create_presentation_session(test_db, user=trainee)

    response = await async_client.post(
        "/api/v1/supervisor/reviews",
        headers=_auth_headers(trainee),
        json={
            "session_id": str(source_session.session_id),
            "decision": "approved",
            "readiness_status": "approved",
            "comment": "ok",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ADMIN_REQUIRED]"
