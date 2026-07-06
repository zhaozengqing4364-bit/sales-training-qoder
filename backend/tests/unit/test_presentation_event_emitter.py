from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from common.websocket.base_handler import WebSocketSendResult
from presentation_coach.websocket.components.presentation_event_emitter import (
    PresentationEventEmitter,
)


@pytest.mark.asyncio
async def test_event_emitter_returns_false_when_structured_send_fails() -> None:
    websocket = Mock()
    send_json = AsyncMock(
        return_value=WebSocketSendResult.failed(
            "status",
            error_type="RuntimeError",
            error="socket closed",
        )
    )
    emitter = PresentationEventEmitter(
        send_json=send_json,
        websocket_provider=lambda: websocket,
    )

    sent = await emitter.send_status(
        ai_state="idle",
        session_status="in_progress",
        turn_count=1,
        current_page=2,
    )

    assert sent is False
    send_json.assert_awaited_once()
