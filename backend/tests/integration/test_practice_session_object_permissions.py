from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from common.analytics.report_trends import ReportTrendService
from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import PracticeSession, Scenario, SessionStatus, User

SENSITIVE_SENTINELS = (
    "SENSITIVE_POLICY_FACT",
    "SENSITIVE_CUSTOMER_QUOTE",
    "SENSITIVE_SCORE_PROJECTION",
)


def _user(role: str = "user", *, prefix: str = "practice-acl") -> User:
    unique = uuid.uuid4().hex[:8]
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{prefix}-{role}-{unique}",
        name=f"{role} user",
        email=f"{prefix}-{role}-{unique}@example.com",
        role=role,
    )


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_sensitive_completed_session(test_db) -> tuple[User, User, User, PracticeSession]:
    owner = _user("user", prefix="practice-owner")
    outsider = _user("user", prefix="practice-outsider")
    super_admin = _user("super_admin", prefix="practice-super-admin")
    scenario = Scenario(
        scenario_type="sales",
        name="Object permission sales practice",
        is_active=True,
    )
    test_db.add_all([owner, outsider, super_admin, scenario])
    await test_db.flush()

    started_at = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    session = PracticeSession(
        user_id=str(owner.user_id),
        scenario_id=str(scenario.scenario_id),
        status=SessionStatus.COMPLETED.value,
        start_time=started_at,
        end_time=started_at + timedelta(minutes=12),
        logic_score=80,
        accuracy_score=75,
        completeness_score=70,
        voice_policy_snapshot={
            "internal_policy_fact": SENSITIVE_SENTINELS[0],
        },
        effectiveness_snapshot={
            "evaluable": True,
            "not_evaluable_reason": None,
            "main_issue": {
                "issue_text": SENSITIVE_SENTINELS[2],
            },
        },
    )
    test_db.add(session)
    await test_db.flush()

    test_db.add(
        ConversationMessage(
            session_id=str(session.session_id),
            turn_number=1,
            role="user",
            content=SENSITIVE_SENTINELS[1],
            timestamp=started_at + timedelta(minutes=1),
            is_highlight=True,
            highlight_type="bad",
            highlight_reason="contains sensitive customer quote",
        )
    )
    await test_db.commit()
    await test_db.refresh(session)
    return owner, outsider, super_admin, session


@pytest.mark.asyncio
async def test_sensitive_practice_projection_routes_reject_non_owner_without_leaking(
    async_client,
    test_db,
) -> None:
    _, outsider, _, session = await _create_sensitive_completed_session(test_db)

    endpoints = (
        f"/api/v1/practice/sessions/{session.session_id}/report",
        f"/api/v1/practice/sessions/{session.session_id}/knowledge-check",
        f"/api/v1/sessions/{session.session_id}/enhanced-report",
        f"/api/v1/practice/sessions/{session.session_id}/report-trends",
    )

    for endpoint in endpoints:
        response = await async_client.get(endpoint, headers=_headers(outsider))

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[ACCESS_DENIED]"
        assert body.get("trace_id")
        for sentinel in SENSITIVE_SENTINELS:
            assert sentinel not in response.text


@pytest.mark.asyncio
async def test_report_trends_service_rejects_non_owner_before_projection(
    test_db,
) -> None:
    _, outsider, _, session = await _create_sensitive_completed_session(test_db)

    result = await ReportTrendService().get_session_report_trends(
        db=test_db,
        requester=outsider,
        session_id=str(session.session_id),
        limit=5,
    )

    assert not result.is_success
    assert result.fallback is not None
    assert "[ACCESS_DENIED]" in result.fallback
    for sentinel in SENSITIVE_SENTINELS:
        assert sentinel not in result.fallback


@pytest.mark.asyncio
async def test_report_trends_allows_super_admin_role_alias(
    async_client,
    test_db,
) -> None:
    _, _, super_admin, session = await _create_sensitive_completed_session(test_db)

    response = await async_client.get(
        f"/api/v1/practice/sessions/{session.session_id}/report-trends",
        headers=_headers(super_admin),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["session_id"] == str(session.session_id)
    assert body["data"]["points"][0]["session_id"] == str(session.session_id)
