"""E2E Tests for WebSocket Flow."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sales_bot.websocket.simple_handler import SimpleSalesHandler


class TestWebSocketFlow:
    """E2E tests for WebSocket conversation flow."""

    @pytest.fixture
    def session_id(self):
        return str(uuid.uuid4())

    @pytest.fixture
    def handler(self):
        return SimpleSalesHandler()

    @pytest.mark.asyncio
    async def test_should_handle_text_message(self, handler, session_id):
        """Test handling of text message type."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.session_status = "in_progress"
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        with patch.object(handler, "_launch_response_task", new=AsyncMock()) as mock_launch:
            mock_launch.return_value = True
            await handler.handle_message({
                "type": "text",
                "data": {"text": "Hello"},
            })
            mock_launch.assert_awaited_once_with("Hello", source="text")

    @pytest.mark.asyncio
    async def test_should_handle_pause_message(self, handler, session_id):
        """Test handling of pause control message."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.session_status = "in_progress"
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()
        handler._stop_streaming_asr = AsyncMock()

        with patch.object(
            handler,
            "_apply_lifecycle_action",
            new=AsyncMock(return_value=MagicMock(to_status="paused")),
        ):
            await handler.handle_message({"type": "pause", "data": {}})

        handler.manager.send_json.assert_called()
        call_args = handler.manager.send_json.call_args[0]
        assert call_args[1]["type"] == "status"
        assert call_args[1]["data"]["ai_state"] == "idle"

    @pytest.mark.asyncio
    async def test_should_handle_resume_message(self, handler, session_id):
        """Test handling of resume control message."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.session_status = "paused"
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()
        with patch.object(
            handler,
            "_apply_lifecycle_action",
            new=AsyncMock(return_value=MagicMock(to_status="in_progress")),
        ):
            await handler.handle_message({"type": "resume", "data": {}})

        handler.manager.send_json.assert_called()
        call_args = handler.manager.send_json.call_args[0]
        assert call_args[1]["type"] == "status"
        assert call_args[1]["data"]["ai_state"] == "listening"

    @pytest.mark.asyncio
    async def test_should_set_persona(self, handler):
        """Test persona can be set."""
        await handler.set_persona("skeptical_buyer")
        assert handler.persona_id == "skeptical_buyer"

    @pytest.mark.asyncio
    async def test_should_send_status_message(self, handler, session_id):
        """Test status message format."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.turn_count = 5
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        await handler._send_status("thinking")

        call_args = handler.manager.send_json.call_args[0]
        msg = call_args[1]
        assert msg["type"] == "status"
        assert msg["data"]["ai_state"] == "thinking"
        assert msg["data"]["turn_count"] == 5

    @pytest.mark.asyncio
    async def test_should_send_error_message(self, handler, session_id):
        """Test error message format."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        await handler._send_error("[PROCESSING_ERROR]", "error")

        call_args = handler.manager.send_json.call_args[0]
        msg = call_args[1]
        assert msg["type"] == "error"
        assert msg["data"]["code"] == "[PROCESSING_ERROR]"

    @pytest.mark.asyncio
    async def test_should_send_heartbeat_message(self, handler, session_id):
        """Test heartbeat message format."""
        handler.websocket = AsyncMock()
        handler.session_id = session_id
        handler.manager = MagicMock()
        handler.manager.send_json = AsyncMock()

        await handler._send_heartbeat()

        call_args = handler.manager.send_json.call_args[0]
        msg = call_args[1]
        assert msg["type"] == "heartbeat"
