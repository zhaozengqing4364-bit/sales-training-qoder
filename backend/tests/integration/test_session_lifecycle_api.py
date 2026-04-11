"""
Integration tests for session lifecycle REST controls.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import common.api.practice as practice_api
import evaluation.services.report_generation_trigger as trigger_module
from common.auth.service import create_access_token
from common.conversation.models import ConversationMessage
from common.db.models import PracticeSession, Scenario, User
from common.db.session_lifecycle import (
    SESSION_LIFECYCLE_RACE_SCENARIOS,
    SessionLifecycleService,
)
from common.error_handling.result import Result
from common.websocket.session_manager import get_session_manager
from evaluation.services.report_generation_trigger import trigger_report_generation


LIFECYCLE_API_CONCURRENCY_CONTRACT = {
    "intentional_terminal_statuses": {
        "sales": "scoring",
        "presentation": "completed",
    },
    "intentional_differences": {
        "sales": "REST end returns scoring first so background report finalization can complete the session later.",
        "presentation": "REST end settles directly on end as completed because presentation sessions do not insert a scoring handoff.",
    },
    "regression_entrypoint": (
        "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
        "backend/tests/unit/test_session_lifecycle_service.py "
        "backend/tests/integration/test_session_lifecycle_api.py -x -q"
    ),
}


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


def _session_factory(bind) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )


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


def test_race_catalog_focuses_on_terminal_regressions() -> None:
    assert [scenario.slug for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS] == [
        "sales_end_beats_stale_resume",
        "presentation_end_beats_stale_pause",
    ]
    assert all(scenario.winner_action == "end" for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS)
    assert [scenario.expected_status for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS] == [
        "scoring",
        "completed",
    ]


def test_lifecycle_api_concurrency_contract_documents_terminal_split() -> None:
    assert LIFECYCLE_API_CONCURRENCY_CONTRACT["intentional_terminal_statuses"] == {
        "sales": "scoring",
        "presentation": "completed",
    }
    assert LIFECYCLE_API_CONCURRENCY_CONTRACT["regression_entrypoint"] == (
        "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
        "backend/tests/unit/test_session_lifecycle_service.py "
        "backend/tests/integration/test_session_lifecycle_api.py -x -q"
    )
    assert "background report finalization" in LIFECYCLE_API_CONCURRENCY_CONTRACT[
        "intentional_differences"
    ]["sales"]
    assert "directly on end as completed" in LIFECYCLE_API_CONCURRENCY_CONTRACT[
        "intentional_differences"
    ]["presentation"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "race_scenario",
    SESSION_LIFECYCLE_RACE_SCENARIOS,
    ids=lambda scenario: scenario.slug,
)
async def test_lifecycle_race_proof_preserves_terminal_status_against_stale_writer(
    test_db: AsyncSession,
    test_user: User,
    race_scenario,
):
    seeded_session = await _create_session(
        test_db,
        user_id=str(test_user.user_id),
        scenario_type=race_scenario.scenario_type,
        status=race_scenario.initial_status,
    )
    session_id = str(seeded_session.session_id)
    factory = _session_factory(test_db.bind)

    async with factory() as winner_db, factory() as stale_db:
        winner_service = SessionLifecycleService(winner_db)
        stale_service = SessionLifecycleService(stale_db)

        winner_session, winner_scenario_type = await winner_service.get_session_with_scenario(session_id)
        stale_session, stale_scenario_type = await stale_service.get_session_with_scenario(session_id)

        assert winner_session is not None
        assert stale_session is not None
        assert winner_scenario_type == race_scenario.scenario_type
        assert stale_scenario_type == race_scenario.scenario_type

        winner_transition = await winner_service.transition(
            session=winner_session,
            scenario_type=winner_scenario_type,
            action=race_scenario.winner_action,
            now=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
        )
        await winner_db.commit()
        assert winner_transition.to_status == race_scenario.expected_status

        stale_transition = await stale_service.transition(
            session=stale_session,
            scenario_type=stale_scenario_type,
            action=race_scenario.stale_action,
            now=datetime(2026, 2, 11, 12, 1, tzinfo=UTC),
        )
        assert stale_transition.changed is False
        assert stale_transition.from_status == race_scenario.expected_status
        assert stale_transition.to_status == race_scenario.expected_status
        await stale_db.commit()

    async with factory() as verify_db:
        persisted_session = (
            await verify_db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
        ).scalar_one()

    assert persisted_session.status == race_scenario.expected_status


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
async def test_sales_end_response_stays_scoring_but_background_finalization_can_complete_session(
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
    session.logic_score = 84
    session.accuracy_score = 82
    session.completeness_score = 80
    session.effectiveness_snapshot = {
        "pass_flags": {
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        "main_capability_passed": False,
        "overall_result": "fail",
        "main_issue": {
            "issue_type": "evidence_gap",
            "issue_text": "客户要案例，但这一轮还没给出证据。",
            "recovery_rule": "下一轮先补案例和 ROI 数字。",
        },
        "next_goal": {
            "goal_type": "evidence_backing",
            "goal_text": "下一轮优先补一条 ROI 证据。",
            "rule": "至少补一个案例或量化收益。",
        },
        "evaluable": True,
        "not_evaluable_reason": None,
    }
    test_db.add(
        ConversationMessage(
            session_id=session.session_id,
            turn_number=1,
            role="user",
            content="我现在最关心同行案例和回收周期。",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            sales_stage="objection",
            score_snapshot={"overall_score": 82},
            is_highlight=True,
            highlight_type="bad",
            highlight_reason="客户已经追问 ROI 证据。",
        )
    )
    await test_db.commit()

    session_id = str(session.session_id)
    response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=_headers_for_user(str(test_user.user_id)),
        json={"action": "end"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "scoring"

    persisted_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
    ).scalar_one()
    assert persisted_session.status == "scoring"

    session_factory = async_sessionmaker(
        test_db.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    mock_report_service = AsyncMock()
    mock_report_service.generate_report = AsyncMock(
        return_value=Result.fail("[ENHANCED_REPORT_FAILED]")
    )

    def _init_report_service(self) -> None:
        self.report_service = mock_report_service

    monkeypatch.setattr(trigger_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        trigger_module.ReportGenerationTrigger,
        "_init_report_service",
        _init_report_service,
    )

    await trigger_report_generation(session_id, "sales", db=None)

    async with session_factory() as verify_db:
        persisted_session = (
            await verify_db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
        ).scalar_one()
    assert persisted_session.report_status == "failed"
    assert persisted_session.status == "completed"
    assert persisted_session.report_error == "[ENHANCED_REPORT_FAILED]"


@pytest.mark.asyncio
async def test_lifecycle_api_end_presentation_completes_without_scoring_handoff(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    report_trigger_mock = AsyncMock()
    monkeypatch.setattr(
        practice_api.SessionLifecycleService,
        "trigger_report_generation_if_needed",
        report_trigger_mock,
    )

    async def _stub_presentation_end(self, session_id: str, *, commit: bool = True):
        session = (
            await self.db.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
        ).scalar_one()
        session.status = "completed"
        session.end_time = datetime(2026, 2, 11, 13, 5, tzinfo=UTC)
        session.total_duration_seconds = 300
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return Result.ok(session)

    monkeypatch.setattr(
        practice_api.PresentationCoachService,
        "end_session",
        _stub_presentation_end,
    )

    session = await _create_session(
        test_db,
        user_id=str(test_user.user_id),
        scenario_type="presentation",
        status="in_progress",
    )
    session.start_time = datetime(2026, 2, 11, 13, 0, tzinfo=UTC)
    await test_db.commit()
    await test_db.refresh(session)
    session_id = str(session.session_id)

    response = await async_client.post(
        f"/api/v1/practice/sessions/{session_id}/lifecycle",
        headers=_headers_for_user(str(test_user.user_id)),
        json={"action": "end"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["previous_status"] == "in_progress"
    assert body["data"]["status"] == "completed"
    assert body["data"]["ai_state"] == "idle"
    assert body["data"]["changed"] is True

    persisted_session = (
        await test_db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
    ).scalar_one()
    assert persisted_session.status == "completed"
    assert persisted_session.end_time is not None
    assert persisted_session.total_duration_seconds == 300
    report_trigger_mock.assert_awaited_once()
    transition = report_trigger_mock.await_args.args[0]
    assert transition.action == "end"
    assert transition.to_status == "completed"
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
