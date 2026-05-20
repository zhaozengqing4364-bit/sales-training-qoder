from __future__ import annotations

from typing import Any

import pytest

from common.db.session_lifecycle import SessionLifecycleAction
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
