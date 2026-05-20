"""Unit tests for session runtime lifecycle state machine."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import PracticeSession, Scenario, User
from common.services.session_runtime_state_service import (
    SessionRuntimeStateService,
    is_transition_allowed,
    read_lifecycle_snapshot,
    suggested_action_for_lifecycle,
)


@pytest.mark.parametrize(
    ("from_state", "to_state", "allowed"),
    [
        (None, "validated", True),
        (None, "runnable", True),
        (None, "completed", True),
        (None, "failed", True),
        (None, "started", False),
        ("validated", "runnable", True),
        ("validated", "failed", True),
        ("runnable", "started", True),
        ("runnable", "failed", True),
        ("started", "completed", True),
        ("started", "failed", True),
        ("completed", "failed", False),
        ("failed", "runnable", True),
        ("failed", "validated", True),
        ("started", "validated", False),
    ],
)
def test_should_enforce_runtime_lifecycle_transition_table(
    from_state: str | None,
    to_state: str,
    allowed: bool,
) -> None:
    assert is_transition_allowed(from_state, to_state) is allowed


def test_should_read_lifecycle_snapshot_from_runtime_state_json() -> None:
    snapshot = read_lifecycle_snapshot(
        {
            "_lifecycle": {
                "state": "runnable",
                "failure_code": None,
                "failure_hint": None,
                "updated_at": "2026-05-20T00:00:00+00:00",
            },
            "reconnect_state": {"epoch": 1},
        }
    )

    assert snapshot.state == "runnable"
    assert snapshot.failure_code is None
    assert snapshot.updated_at == "2026-05-20T00:00:00+00:00"


def test_should_suggest_connect_ws_when_runnable() -> None:
    assert (
        suggested_action_for_lifecycle(lifecycle_state="runnable", runnable=True)
        == "connect_ws"
    )


def test_should_suggest_show_failure_when_failed() -> None:
    assert (
        suggested_action_for_lifecycle(lifecycle_state="failed", runnable=False)
        == "show_failure"
    )


def test_should_suggest_connect_ws_when_failed_but_preflight_runnable() -> None:
    assert (
        suggested_action_for_lifecycle(lifecycle_state="failed", runnable=True)
        == "connect_ws"
    )


@pytest.mark.asyncio
async def test_should_backfill_completed_when_business_status_terminal(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="backfill-completed",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        agent_id="123e4567-e89b-12d3-a456-426614174001",
        persona_id="223e4567-e89b-12d3-a456-426614174002",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"voice_mode": "stepfun_realtime"},
    )
    test_db.add(session)
    await test_db.commit()

    service = SessionRuntimeStateService(test_db)
    snapshot = await service.ensure_lifecycle_initialized(
        str(session.session_id),
        source="test",
    )

    assert snapshot.state == "completed"
    await test_db.refresh(session)
    persisted = read_lifecycle_snapshot(session.runtime_state)
    assert persisted.state == "completed"


@pytest.mark.asyncio
async def test_should_backfill_runnable_from_preflight_when_preparing(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="backfill-runnable",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="preparing",
        agent_id="123e4567-e89b-12d3-a456-426614174001",
        persona_id="223e4567-e89b-12d3-a456-426614174002",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"voice_mode": "stepfun_realtime"},
    )
    test_db.add(session)
    await test_db.commit()

    service = SessionRuntimeStateService(test_db)
    snapshot = await service.ensure_lifecycle_initialized(
        str(session.session_id),
        source="test",
    )

    assert snapshot.state == "runnable"


@pytest.mark.asyncio
async def test_should_backfill_failed_from_preflight_when_blocked(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="backfill-failed",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="preparing",
        voice_mode="legacy",
    )
    test_db.add(session)
    await test_db.commit()

    service = SessionRuntimeStateService(test_db)
    snapshot = await service.ensure_lifecycle_initialized(
        str(session.session_id),
        source="test",
    )

    assert snapshot.state == "validated"


@pytest.mark.asyncio
async def test_should_recover_failed_to_runnable_when_preflight_passes(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="recover-failed",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="preparing",
        agent_id="123e4567-e89b-12d3-a456-426614174001",
        persona_id="223e4567-e89b-12d3-a456-426614174002",
        voice_mode="stepfun_realtime",
        voice_policy_snapshot={"voice_mode": "stepfun_realtime"},
        runtime_state={
            "_lifecycle": {
                "state": "failed",
                "failure_code": "KB_LOCK_UNBOUND",
                "failure_hint": "blocked",
                "updated_at": "2026-05-20T00:00:00+00:00",
            }
        },
    )
    test_db.add(session)
    await test_db.commit()

    service = SessionRuntimeStateService(test_db)
    result = await service.apply_preflight_result(
        str(session.session_id),
        runnable=True,
        code=None,
        hint=None,
    )

    assert result.changed is True
    assert result.to_state == "runnable"
    snapshot = await service.get_snapshot(str(session.session_id))
    assert snapshot.state == "runnable"
    assert snapshot.failure_code is None


@pytest.mark.asyncio
async def test_should_skip_backfill_when_lifecycle_already_present(
    test_db: AsyncSession,
    test_user: User,
) -> None:
    scenario = Scenario(
        scenario_type="sales",
        name="backfill-noop",
        persona_prompt="test",
        is_active=True,
    )
    test_db.add(scenario)
    await test_db.flush()

    session = PracticeSession(
        user_id=str(test_user.user_id),
        scenario_id=str(scenario.scenario_id),
        status="completed",
        runtime_state={
            "_lifecycle": {
                "state": "failed",
                "failure_code": "PREFLIGHT_BLOCKED",
                "failure_hint": "blocked",
                "updated_at": "2026-05-20T00:00:00+00:00",
            }
        },
    )
    test_db.add(session)
    await test_db.commit()

    service = SessionRuntimeStateService(test_db)
    snapshot = await service.ensure_lifecycle_initialized(
        str(session.session_id),
        source="test",
    )

    assert snapshot.state == "failed"
    assert snapshot.failure_code == "PREFLIGHT_BLOCKED"
