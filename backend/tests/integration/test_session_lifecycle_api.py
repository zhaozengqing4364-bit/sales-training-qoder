"""
Integration tests for session lifecycle REST controls.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import common.api.practice as practice_api
from common.auth.service import create_access_token
from common.db.models import PracticeSession, Scenario, User
from common.error_handling.result import Result
from common.websocket.session_manager import get_session_manager


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


def _stub_sales_end_dependencies(monkeypatch: pytest.MonkeyPatch):
    summary_mock = AsyncMock(
        return_value=Result.ok(
            SimpleNamespace(
                strengths=["Structured discovery"],
                actionable_feedback="Close with a concrete next step.",
                score_confidence=81,
                score_persuasion=79,
                score_clarity=84,
            )
        )
    )
    cleanup_mock = AsyncMock(return_value=Result.ok({"session_id": "stub-session"}))
    monkeypatch.setattr(practice_api.summary_service, "generate_summary", summary_mock)
    monkeypatch.setattr(practice_api.sales_bot_service, "end_session", cleanup_mock)
    return summary_mock, cleanup_mock


@pytest.mark.asyncio
async def test_lifecycle_api_start_pause_resume_end_sales(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    summary_mock, cleanup_mock = _stub_sales_end_dependencies(monkeypatch)
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
    summary_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))
    cleanup_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))


@pytest.mark.asyncio
async def test_lifecycle_api_end_triggers_report_on_first_terminal_transition(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    summary_mock, cleanup_mock = _stub_sales_end_dependencies(monkeypatch)
    report_trigger_mock = AsyncMock()
    monkeypatch.setattr(
        practice_api.SessionLifecycleService,
        "trigger_report_generation_if_needed",
        report_trigger_mock,
    )

    session = await _create_session(
        test_db,
        user_id=str(test_user.user_id),
        scenario_type="sales",
        status="in_progress",
    )
    session_id = str(session.session_id)

    response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=_headers_for_user(str(test_user.user_id)),
        json={"action": "end"},
    )

    assert response.status_code == 200
    summary_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))
    cleanup_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))
    report_trigger_mock.assert_awaited_once()
    transition = report_trigger_mock.await_args.args[0]
    assert transition.action == "end"
    assert transition.to_status == "scoring"
    assert transition.changed is True


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


@pytest.mark.asyncio
async def test_lifecycle_api_syncs_live_handler_after_rest_transition(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    summary_mock, cleanup_mock = _stub_sales_end_dependencies(monkeypatch)
    session = await _create_session(test_db, user_id=str(test_user.user_id), scenario_type="sales")
    session_id = str(session.session_id)
    headers = _headers_for_user(str(test_user.user_id))

    synced_transitions: list[tuple[str, str, str]] = []
    close_calls: list[tuple[int, str]] = []

    handler = SimpleNamespace(
        send_message=AsyncMock(),
        sync_lifecycle_transition=AsyncMock(
            side_effect=lambda transition: synced_transitions.append(
                (transition.action, transition.to_status, transition.ai_state)
            )
        ),
        close=AsyncMock(
            side_effect=lambda code=1000, reason="": close_calls.append((code, reason))
        ),
    )

    session_manager = get_session_manager()
    await session_manager.register_session(session_id, handler, user_id=str(test_user.user_id))
    try:
        for action in ("start", "pause", "resume", "end"):
            response = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/lifecycle",
                headers=headers,
                json={"action": action},
            )
            assert response.status_code == 200

        assert synced_transitions == [
            ("start", "in_progress", "listening"),
            ("pause", "paused", "idle"),
            ("resume", "in_progress", "listening"),
            ("end", "scoring", "idle"),
        ]
        assert close_calls == [(1000, "Session ended")]
        summary_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))
        cleanup_mock.assert_awaited_once_with(uuid.UUID(str(session_id)))
    finally:
        await session_manager.unregister_session(session_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    session = await _create_session(
        test_db,
        user_id=str(test_user.user_id),
        scenario_type="sales",
        status="scoring",
    )
    session.logic_score = 88
    session.accuracy_score = 86
    session.completeness_score = 90
    await test_db.commit()
    await test_db.refresh(session)

    summary_mock, cleanup_mock = _stub_sales_end_dependencies(monkeypatch)
    info_spy = MagicMock()
    monkeypatch.setattr(practice_api.logger, "info", info_spy)

    close_calls: list[tuple[int, str]] = []
    handler = SimpleNamespace(
        send_message=AsyncMock(),
        sync_lifecycle_transition=AsyncMock(),
        close=AsyncMock(
            side_effect=lambda code=1000, reason="": close_calls.append((code, reason))
        ),
    )

    session_manager = get_session_manager()
    session_id = str(session.session_id)
    await session_manager.register_session(session_id, handler, user_id=str(test_user.user_id))
    try:
        response = await async_client.post(
            f"/api/v1/practice/sessions/{session_id}/lifecycle",
            headers=_headers_for_user(str(test_user.user_id)),
            json={"action": "end"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["previous_status"] == "scoring"
        assert body["data"]["status"] == "scoring"
        assert body["data"]["changed"] is False
        assert close_calls == [(1000, "Session ended")]
        summary_mock.assert_not_awaited()
        cleanup_mock.assert_not_awaited()

        transition_logs = [
            call.kwargs
            for call in info_spy.call_args_list
            if call.args and call.args[0] == "practice_session_lifecycle_transition_applied"
        ]
        close_logs = [
            call.kwargs
            for call in info_spy.call_args_list
            if call.args and call.args[0] == "practice_session_terminal_connection_close"
        ]
        assert transition_logs == [
            {
                "session_id": session_id,
                "scenario_type": "sales",
                "action": "end",
                "to_status": "scoring",
                "changed": False,
            }
        ]
        assert close_logs == [
            {
                "session_id": session_id,
                "scenario_type": "sales",
                "action": "end",
                "to_status": "scoring",
                "terminal_connection_closed": True,
            }
        ]
    finally:
        await session_manager.unregister_session(session_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_lifecycle_api_refreshes_live_session_activity_after_rest_transition(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    session = await _create_session(
        test_db,
        user_id=str(test_user.user_id),
        scenario_type="sales",
    )
    session_id = str(session.session_id)
    headers = _headers_for_user(str(test_user.user_id))

    handler = SimpleNamespace(
        send_message=AsyncMock(),
        sync_lifecycle_transition=AsyncMock(),
        close=AsyncMock(),
    )

    session_manager = get_session_manager()
    await session_manager.register_session(
        session_id,
        handler,
        user_id=str(test_user.user_id),
    )
    try:
        session_manager.sessions[session_id].last_activity = 1.0

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session_id}/lifecycle",
            headers=headers,
            json={"action": "start"},
        )

        assert response.status_code == 200
        assert session_manager.sessions[session_id].last_activity > 1.0
    finally:
        await session_manager.unregister_session(session_id, reason="test_cleanup")
