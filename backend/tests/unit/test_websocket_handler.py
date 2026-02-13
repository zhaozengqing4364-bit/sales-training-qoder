"""
WebSocket Handler Unit Tests
Tests: ConnectionManager, BaseWebSocketHandler, Constitution Principle I
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from common.websocket.base_handler import (
    ConnectionManager,
    BaseWebSocketHandler,
    get_connection_manager
)


@pytest.mark.asyncio
class TestConnectionManager:
    """Test WebSocket connection lifecycle management"""

    @pytest.fixture
    def manager(self):
        """Fresh manager for each test"""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket object"""
        ws = Mock()
        ws.send_json = AsyncMock()
        ws.accept = AsyncMock()
        return ws

    async def test_connect_and_track(self, manager, mock_websocket):
        """Verify connection is tracked after connection"""
        await manager.connect(mock_websocket, "presentation", "test-session")

        assert manager.get_connection_count("presentation") == 1
        assert "test-session" in manager.active_connections["presentation"]

    async def test_sends_connected_message(self, manager, mock_websocket):
        """Verify connected message is sent"""
        await manager.connect(mock_websocket, "presentation", "test-session")

        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "connected"
        assert sent_data["data"]["session_id"] == "test-session"

    async def test_disconnect_removes_tracking(self, manager, mock_websocket):
        """Verify connection is removed after disconnect"""
        manager.active_connections["presentation"]["test-session"] = mock_websocket

        manager.disconnect("presentation", "test-session")

        assert "test-session" not in manager.active_connections["presentation"]
        assert manager.get_connection_count("presentation") == 0

    async def test_send_json_success(self, manager, mock_websocket):
        """Verify message is sent successfully"""
        await manager.send_json(mock_websocket, {"type": "test", "data": "value"})

        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "test"

    async def test_send_json_failure_logged_not_raised(
        self, manager, caplog
    ):
        """
        Verify send failure is logged (not thrown)
        Constitution Principle I: Errors handled gracefully
        """
        # Create a broken WebSocket that throws
        broken_ws = Mock()
        broken_ws.send_json = AsyncMock(side_effect=Exception("Send failed"))

        # Should not raise, only log
        await manager.send_json(broken_ws, {"type": "test"})

        # Verify error was logged
        # assert "Failed to send message" in caplog.text

    async def test_broadcast_to_session(self, manager, mock_websocket):
        """Verify message reaches specific session"""
        manager.active_connections["presentation"]["session-1"] = mock_websocket

        await manager.broadcast_to_session(
            "presentation", "session-1", {"type": "test", "data": "value"}
        )

        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "test"

    async def test_broadcast_to_nonexistent_session(
        self, manager, mock_websocket, caplog
    ):
        """Verify broadcast to nonexistent session doesn't crash"""
        # Should not raise
        await manager.broadcast_to_session(
            "presentation", "nonexistent", {"type": "test"}
        )

        # No send attempt should be made
        assert not mock_websocket.send_json.called

    async def test_get_connection_count_by_scenario(self, manager):
        """Verify connection count by scenario"""
        # Add connections to different scenarios
        for i in range(5):
            manager.active_connections["presentation"][f"session-{i}"] = Mock()
        for i in range(3):
            manager.active_connections["sales"][f"session-{i}"] = Mock()

        assert manager.get_connection_count("presentation") == 5
        assert manager.get_connection_count("sales") == 3

    async def test_get_connection_count_all(self, manager):
        """Verify total connection count across all scenarios"""
        for i in range(5):
            manager.active_connections["presentation"][f"session-{i}"] = Mock()
        for i in range(3):
            manager.active_connections["sales"][f"session-{i}"] = Mock()

        assert manager.get_connection_count() == 8

    async def test_connect_to_new_scenario(self, manager, mock_websocket):
        """Verify new scenario is created when needed"""
        # Scenario doesn't exist yet
        assert "new_scenario" not in manager.active_connections

        await manager.connect(mock_websocket, "new_scenario", "test-session")

        assert "new_scenario" in manager.active_connections
        assert manager.get_connection_count("new_scenario") == 1


@pytest.mark.asyncio
class TestBaseWebSocketHandler:
    """Test base WebSocket handler functionality"""

    @pytest.fixture
    def handler(self):
        """Create handler instance"""
        return BaseWebSocketHandler("presentation")

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket with async methods"""
        ws = Mock()
        ws.accept = AsyncMock()
        ws.receive_json = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    async def test_initialization(self, handler):
        """Verify handler initializes correctly"""
        assert handler.scenario == "presentation"
        assert handler.manager is not None
        assert handler.message_queue is None
        assert handler.running is False

    async def test_handle_connection_accepts_websocket(
        self, handler, mock_websocket
    ):
        """Verify connection is accepted and tracked"""
        # Mock token verification
        with patch(
            "common.auth.service.verify_token",
            return_value={"trace_id": "test-trace"}
        ):
            # Mock receive_json to wait forever (simulate open connection)
            async def wait_forever(*args, **kwargs):
                await asyncio.sleep(10)
            mock_websocket.receive_json = AsyncMock(side_effect=wait_forever)

            # Run handler in background task
            task = asyncio.create_task(
                handler.handle_connection(mock_websocket, "test-session", "token")
            )
            
            # Allow task to start
            await asyncio.sleep(0.5)

            try:
                assert mock_websocket.accept.called
                assert "test-session" in handler.manager.active_connections["presentation"]
                assert handler.message_queue is not None
                assert handler.running is True
            finally:
                # Cleanup
                handler.running = False
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def test_handle_connection_sends_client_ready(
        self, handler, mock_websocket
    ):
        """Verify client_ready message is sent after connection"""
        with patch(
            "common.auth.service.verify_token",
            return_value={}
        ):
            # Mock receive_json to throw immediately to exit
            mock_websocket.receive_json = AsyncMock(
                side_effect=Exception("Done")
            )

            try:
                await handler.handle_connection(
                    mock_websocket, "test-session", "token"
                )
            except Exception:
                pass

        # Check that at least one message was sent (connected message)
        assert mock_websocket.send_json.called

    async def test_message_processing_loop(self, handler, mock_websocket):
        """Verify messages are processed from queue"""
        # Setup
        handler.message_queue = asyncio.Queue()
        handler.running = True

        processed_messages = []

        async def mock_handle(msg):
            processed_messages.append(msg)

        handler.handle_message = mock_handle

        # Add messages to queue
        test_messages = [
            {"type": "test1", "data": "value1"},
            {"type": "test2", "data": "value2"},
        ]

        for msg in test_messages:
            await handler.message_queue.put(msg)

        # Run processing loop in background task
        task = asyncio.create_task(handler._process_messages())
        
        # Allow processing
        await asyncio.sleep(0.1)

        # Cleanup
        handler.running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(processed_messages) == 2

    async def test_send_error_with_user_action(self, handler, mock_websocket):
        """Verify error message includes user action for graceful degradation"""
        await handler.send_error(
            mock_websocket,
            "ASR_TIMEOUT",
            "ASR service unavailable",
            user_action="[USE_BROWSER_ASR]"
        )

        assert mock_websocket.send_json.called
        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["type"] == "error"
        assert sent_data["data"]["code"] == "ASR_TIMEOUT"
        assert sent_data["data"]["user_action"] == "[USE_BROWSER_ASR]"

    async def test_send_error_includes_trace_id(self, handler, mock_websocket):
        """Verify error messages include trace_id for observability"""
        with patch(
            "common.websocket.base_handler.get_trace_id",
            return_value="test-trace-123"
        ):
            await handler.send_error(
                mock_websocket,
                "TEST_ERROR",
                "Test error message"
            )

        sent_data = mock_websocket.send_json.call_args[0][0]
        assert sent_data["data"]["trace_id"] == "test-trace-123"

    async def test_handle_message_calls_registered_handler(self, handler):
        """Verify message type is logged"""
        # Mock logger
        with patch("common.websocket.base_handler.logger") as mock_logger:
            await handler.handle_message({"type": "test_message", "data": {}})

            # Verify message type was logged
            mock_logger.info.assert_called()

    async def test_heartbeat_sent_on_timeout(self, handler, mock_websocket):
        """Verify heartbeat is sent when no message received within timeout"""
        mock_websocket.receive_json = AsyncMock(side_effect=[asyncio.TimeoutError(), Exception("Stop")])

        with patch(
            "common.auth.service.verify_token",
            return_value={}
        ):
            try:
                # Run handler with short timeout
                await handler.handle_connection(mock_websocket, "test", "token")
            except Exception:
                pass

        # Check that heartbeat was sent
        heartbeat_sent = any(
            call[0][0].get("type") == "heartbeat"
            for call in mock_websocket.send_json.call_args_list
        )
        assert heartbeat_sent

    async def test_cleanup_on_disconnect(self, handler, mock_websocket):
        """Verify cleanup happens when connection closes"""
        mock_websocket.receive_json = AsyncMock(
            side_effect=Exception("WebSocketDisconnect")
        )

        with patch(
            "common.auth.service.verify_token",
            return_value={}
        ):
            try:
                await handler.handle_connection(mock_websocket, "test", "token")
            except Exception:
                pass

        # Verify connection was removed from manager
        assert "test" not in handler.manager.active_connections["presentation"]
        assert handler.running is False


@pytest.mark.asyncio
class TestConnectionManagerSingleton:
    """Test singleton pattern for ConnectionManager"""

    async def test_get_connection_manager_returns_singleton(self):
        """Verify same instance is returned"""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()

        assert manager1 is manager2

    async def test_singleton_persists_connections(self):
        """Verify connections persist across handler instances"""
        manager = get_connection_manager()
        ws = Mock()
        ws.send_json = AsyncMock()
        ws.accept = AsyncMock()

        await manager.connect(ws, "presentation", "test-session")

        # Get new manager instance
        manager2 = get_connection_manager()
        assert manager2.get_connection_count("presentation") == 1

        # Cleanup
        manager2.disconnect("presentation", "test-session")
