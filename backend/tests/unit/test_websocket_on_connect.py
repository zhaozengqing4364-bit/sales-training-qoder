import asyncio
import inspect
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.error_handling.result import Result
from common.websocket.base_handler import BaseWebSocketHandler


class _NoStateService:
    async def get_state(self, _session_id: str) -> Result[None]:
        return Result.ok(None)

    async def save_state(self, _snapshot) -> Result[None]:
        return Result.ok(None)


def _websocket_that_stops_after_first_receive(events: list[str]) -> Mock:
    websocket = Mock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()

    async def stop_after_receive():
        events.append("receive")
        raise RuntimeError("stop test connection")

    websocket.receive_json = AsyncMock(side_effect=stop_after_receive)
    return websocket


@pytest.mark.asyncio
async def test_should_await_default_on_connect_after_connection_setup_before_receive_loop():
    """Base handler exposes a no-op connect hook that runs after setup, before receive."""

    assert inspect.iscoroutinefunction(BaseWebSocketHandler.on_connect)
    assert await BaseWebSocketHandler("presentation").on_connect() is None

    events: list[str] = []

    class TimingHandler(BaseWebSocketHandler):
        async def on_connect(self) -> None:
            events.append("on_connect")
            assert self.message_queue is not None
            assert self.running is True

        async def _process_messages(self) -> None:
            events.append("process_messages")
            await asyncio.sleep(0)

    websocket = _websocket_that_stops_after_first_receive(events)

    with (
        patch("common.websocket.base_handler.get_session_state_service", return_value=_NoStateService()),
        patch("common.auth.service.verify_token", return_value={}),
    ):
        handler = TimingHandler("presentation")
        await handler.handle_connection(websocket, "session-on-connect", "token")

    assert events[0] == "on_connect"
    assert "receive" in events
    assert events.index("on_connect") < events.index("receive")


@pytest.mark.asyncio
async def test_should_allow_on_connect_override_to_send_server_driven_first_message():
    """Subclasses can send a first server-driven message from the connect hook."""

    events: list[str] = []

    class ExaminerReadyHandler(BaseWebSocketHandler):
        async def on_connect(self) -> None:
            await self.send_message(
                {
                    "type": "exam.question",
                    "data": {"question_id": "q-1"},
                }
            )

    websocket = _websocket_that_stops_after_first_receive(events)

    with (
        patch("common.websocket.base_handler.get_session_state_service", return_value=_NoStateService()),
        patch("common.auth.service.verify_token", return_value={}),
    ):
        handler = ExaminerReadyHandler("presentation")
        await handler.handle_connection(websocket, "session-examiner-ready", "token")

    sent_types = [call.args[0]["type"] for call in websocket.send_json.call_args_list]
    assert sent_types[:2] == ["connected", "exam.question"]
    assert events == ["receive"]
