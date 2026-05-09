from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import (
    Page,
    PracticeSession,
    Presentation,
    RequiredTalkingPoint,
    Scenario,
    User,
)


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
    page_1 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=1,
        ocr_extracted_text="第一页业务目标与客户痛点",
    )
    page_2 = Page(
        page_id=str(uuid.uuid4()),
        presentation_id=presentation.presentation_id,
        page_number=2,
        ocr_extracted_text="第二页 ROI 结果与客户案例",
    )
    talking_points = [
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_1.page_id,
            description="业务目标",
            created_by="admin",
            confirmed_by_admin=True,
        ),
        RequiredTalkingPoint(
            point_id=str(uuid.uuid4()),
            page_id=page_2.page_id,
            description="客户案例",
            created_by="admin",
            confirmed_by_admin=True,
        ),
    ]
    db.add_all([presentation, scenario, page_1, page_2, *talking_points])
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
        total_duration_seconds=12 * 60,
    )
    messages = [
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="第一页先讲业务目标与客户痛点。",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            transcript_metadata={"page_number": 1},
            score_snapshot={"overall_score": logic_score},
        ),
        ConversationMessage(
            session_id=session.session_id,
            turn_number=2,
            role="user",
            content="第二页补充 ROI 结果和客户案例。",
            timestamp=datetime.now(UTC),
            duration_ms=2200,
            transcript_metadata={"page_number": 2},
            score_snapshot={"overall_score": accuracy_score},
        ),
    ]
    if status == "completed":
        db.add_all(messages)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_phase2_acceptance_smoke_supervisor_retraining_loop(
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

    report_response = await async_client.get(
        f"/api/v1/practice/sessions/{source_session.session_id}/report",
        headers=_auth_headers(supervisor),
    )
    assert report_response.status_code == 200
    report_body = report_response.json()["data"]
    assert report_body["session_id"] == str(source_session.session_id)
    assert report_body["overall_score"] > 0

    review_response = await async_client.post(
        "/api/v1/supervisor/reviews",
        headers=_auth_headers(supervisor),
        json={
            "session_id": str(source_session.session_id),
            "decision": "pending",
            "readiness_status": "not_ready",
            "comment": "主管已查看报告，等待复训决策。",
            "required_retraining": False,
        },
    )

    assert review_response.status_code == 201
    review_body = review_response.json()["data"]
    assert review_body["decision"] == "pending"
    assert review_body["required_retraining"] is False
    assert review_body["retraining_tasks"] == []

    decision_response = await async_client.patch(
        f"/api/v1/supervisor/reviews/{review_body['review_id']}/decision",
        headers=_auth_headers(supervisor),
        json={
            "decision": "needs_retraining",
            "readiness_status": "shadow_only",
            "comment": "补强演讲结构后再试讲。",
            "required_retraining": True,
            "skill_dimension": "逻辑结构",
        },
    )

    assert decision_response.status_code == 200
    review_body = decision_response.json()["data"]
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

    reviews_response = await async_client.get(
        f"/api/v1/supervisor/reviews?session_id={source_session.session_id}",
        headers=_auth_headers(supervisor),
    )
    assert reviews_response.status_code == 200
    readable_review = reviews_response.json()["data"][0]
    assert readable_review["before_after"]["retraining_completed"] is True
    assert readable_review["before_after"]["score_delta"] > 0


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
