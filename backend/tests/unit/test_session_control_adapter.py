from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleAction,
)
from sales_bot.websocket.session_control_adapter import SessionControlAdapter


class FakeTransition:
    def __init__(self, *, action: SessionLifecycleAction, to_status: str) -> None:
        self.action = action
        self.to_status = to_status


class FakeLifecycleService:
    def __init__(self) -> None:
        self.transition_calls: list[dict] = []

    async def transition(
        self,
        *,
        session: Any,
        scenario_type: str | None,
        action: SessionLifecycleAction,
    ) -> FakeTransition:
        self.transition_calls.append(
            {"session": session, "scenario_type": scenario_type, "action": action}
        )
        return FakeTransition(action=action, to_status="in_progress")


class FailingLifecycleService:
    async def transition(
        self,
        *,
        session: Any,
        scenario_type: str | None,
        action: SessionLifecycleAction,
    ) -> FakeTransition:
        raise RuntimeError("transition failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name, action", [("start", "start"), ("pause", "pause"), ("resume", "resume"), ("end", "end")])
async def test_session_control_adapter_lifecycle_methods_delegate_to_service_transition(method_name: str, action: str) -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)
    session = object()

    transition = await getattr(adapter, method_name)(
        session=session,
        scenario_type="sales",
    )

    assert transition.action == action
    assert service.transition_calls == [
        {
            "session": session,
            "scenario_type": "sales",
            "action": action,
        }
    ]


@pytest.mark.asyncio
async def test_session_control_adapter_apply_action_delegates_to_service_transition() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)
    session = object()

    transition = await adapter.apply_action(
        session=session,
        scenario_type="sales",
        action="resume",
    )

    assert transition.action == "resume"
    assert service.transition_calls == [
        {
            "session": session,
            "scenario_type": "sales",
            "action": "resume",
        }
    ]


@pytest.mark.parametrize(
    "status, expected",
    [("in_progress", True), ("paused", False), ("preparing", False), ("scoring", False)],
)
def test_session_control_adapter_validate_transition_uses_lifecycle_input_rules(status: str, expected: bool) -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)

    assert adapter.validate_transition(status) is expected


def test_validate_transition_rejects_pause_when_idle() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)

    assert adapter.validate_transition("preparing", action="pause") is False


def test_validate_transition_allows_pause_when_running() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)

    assert adapter.validate_transition("in_progress", action="pause") is True


@pytest.mark.asyncio
async def test_transition_history_tracks_all_actions() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service, max_history_size=2)
    session = SimpleNamespace(session_id="session-1")

    await adapter.start(session=session, scenario_type="sales")
    await adapter.pause(session=session, scenario_type="sales")
    await adapter.resume(session=session, scenario_type="sales")

    history = adapter.transition_history()
    assert [record.action for record in history] == ["pause", "resume"]
    assert [record.success for record in history] == [True, True]
    assert [record.session_id for record in history] == ["session-1", "session-1"]


@pytest.mark.asyncio
async def test_recover_last_failed_returns_failed_transition_record() -> None:
    adapter = SessionControlAdapter(FailingLifecycleService())
    session = SimpleNamespace(session_id="session-1", status="in_progress")

    with pytest.raises(RuntimeError, match="transition failed"):
        await adapter.pause(session=session, scenario_type="sales")

    failed_record = adapter.recover_last_failed_transition()
    assert failed_record is not None
    assert failed_record.session_id == "session-1"
    assert failed_record.action == "pause"
    assert failed_record.success is False
    assert failed_record.error == "transition failed"
    assert session.status == "in_progress"


@pytest.mark.asyncio
async def test_is_idempotent_true_for_duplicate_transition() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)
    session = SimpleNamespace(session_id="session-1")
    payload = {"source": "client-control"}

    assert adapter.is_idempotent(session=session, action="pause", payload=payload) is False

    await adapter.apply_action(
        session=session,
        scenario_type="sales",
        action="pause",
        payload=payload,
    )

    assert adapter.is_idempotent(session=session, action="pause", payload=payload) is True
    assert adapter.is_idempotent(session=session, action="pause", payload={}) is False


@pytest.mark.asyncio
async def test_apply_action_prevalidates_status_action_before_delegating() -> None:
    service = FakeLifecycleService()
    adapter = SessionControlAdapter(service)
    session = SimpleNamespace(session_id="session-1", status="preparing")

    with pytest.raises(InvalidSessionTransitionError):
        await adapter.apply_action(
            session=session,
            scenario_type="sales",
            action="pause",
        )

    assert service.transition_calls == []
