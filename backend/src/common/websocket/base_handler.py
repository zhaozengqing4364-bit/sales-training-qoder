"""
Base WebSocket Handler with connection lifecycle management
Constitution Principle I: No error popups, graceful degradation
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError
from starlette.websockets import WebSocketState

from common.monitoring.logger import get_logger, set_trace_id, get_trace_id
from common.websocket.session_state_service import (
    SessionStateSnapshot,
    get_session_state_service,
)

logger = get_logger(__name__)


class ConnectionManager:
    """Manage WebSocket connections across all scenarios"""

    def __init__(self):
        # Scenario -> Session ID -> WebSocket
        self.active_connections: dict[str, dict[str, WebSocket]] = {
            "presentation": {},
            "sales": {}
        }
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, scenario: str, session_id: str):
        """Accept and track connection"""
        await websocket.accept()
        async with self._lock:
            if scenario not in self.active_connections:
                self.active_connections[scenario] = {}
            self.active_connections[scenario][session_id] = websocket
        logger.info(f"WebSocket connected: scenario={scenario}, session={session_id}")

        # Send acknowledgment
        await self.send_json(websocket, {
            "type": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"session_id": session_id}
        })

    async def disconnect(self, scenario: str, session_id: str):
        """Remove connection from tracking"""
        async with self._lock:
            if scenario in self.active_connections:
                self.active_connections[scenario].pop(session_id, None)
        logger.info(f"WebSocket disconnected: scenario={scenario}, session={session_id}")

    async def send_json(self, websocket: WebSocket, message: dict):
        """Send JSON message safely"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")

    async def broadcast_to_session(self, scenario: str, session_id: str, message: dict):
        """Send message to specific session"""
        websocket = None
        async with self._lock:
            websocket = self.active_connections.get(scenario, {}).get(session_id)
        if websocket:
            await self.send_json(websocket, message)

    def get_connection_count(self, scenario: str | None = None) -> int:
        """Get count of active connections"""
        if scenario:
            return len(self.active_connections.get(scenario, {}))
        return sum(len(conns) for conns in self.active_connections.values())


# Singleton instance
_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get singleton connection manager"""
    return _manager


class BaseWebSocketHandler:
    """
    Base class for scenario-specific WebSocket handlers
    Implements message queue for non-blocking handling and session state recovery
    """

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.manager = get_connection_manager()
        self.message_queue: asyncio.Queue = None
        self.running = False
        self.websocket: WebSocket | None = None
        self.session_id: str | None = None
        self.state_service = get_session_state_service()
        self.user_id: str | None = None

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str
    ):
        """
        Main connection handler
        Override in subclasses for scenario-specific logic
        """
        # Set trace_id from token or generate new
        try:
            # Verify token and extract trace_id
            from common.auth.service import verify_token
            payload = verify_token(token)
            set_trace_id(payload.get("trace_id", ""))
            self.user_id = payload.get("user_id")
        except (JWTError, RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Token verification failed: {str(e)}")
            set_trace_id("")

        # Check for existing session state (reconnection scenario)
        existing_state = await self.state_service.get_state(session_id)
        is_reconnection = existing_state.is_success and existing_state.value is not None

        # Connect
        self.websocket = websocket
        self.session_id = session_id
        await self.manager.connect(websocket, self.scenario, session_id)

        # Initialize message queue
        self.message_queue = asyncio.Queue()
        self.running = True

        # Restore state if reconnection
        if is_reconnection:
            logger.info(f"Reconnection detected for session: {session_id}")
            await self._restore_session_state(existing_state.value)

        # Start message processing task
        processing_task = asyncio.create_task(self._process_messages())

        try:
            # Receive messages loop
            while self.running:
                try:
                    # Set timeout for receiving
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=30.0  # 30s timeout
                    )
                    await self.message_queue.put(data)

                except TimeoutError:
                    # Send heartbeat
                    await self.manager.send_json(websocket, {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {}
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally: session={session_id}")
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            # Save session state before cleanup
            await self._save_session_state()
            # Cleanup
            self.running = False
            await self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()

    async def send_message(self, message: dict):
        """Send message to current websocket connection (SessionManager hook)."""
        if not self.websocket:
            return
        await self.manager.send_json(self.websocket, message)

    async def close(self, code: int = 1000, reason: str = "Session closed"):
        """Close current websocket connection safely (SessionManager hook)."""
        if not self.websocket:
            return

        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.close(code=code, reason=reason)
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Failed to close websocket: {e}")

    async def _process_messages(self):
        """
        Process messages from queue
        Override in subclasses for scenario-specific message handling
        """
        while self.running:
            try:
                message = await self.message_queue.get()
                await self.handle_message(message)
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Message processing error: {str(e)}")

    async def handle_message(self, message: dict):
        """
        Handle individual message
        Override in subclasses
        """
        msg_type = message.get("type")
        logger.info(f"Received message type: {msg_type}")

        # Base handler does nothing - subclasses implement specific logic
        pass

    async def send_error(self, websocket: WebSocket, error_code: str, message: str, user_action: str | None = None):
        """
        Send error message (not shown as popup to user)
        Constitution: All errors converted to graceful degradation
        """
        await self.manager.send_json(websocket, {
            "type": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "code": error_code,
                "message": message,
                "user_action": user_action,  # What client should do
                "trace_id": get_trace_id()
            }
        })

    def _create_state_snapshot(self) -> SessionStateSnapshot:
        """
        Create a session state snapshot.
        Override in subclasses to include scenario-specific state.
        """
        return SessionStateSnapshot(
            session_id=self.session_id or "",
            scenario=self.scenario,
            user_id=self.user_id,
        )

    async def _save_session_state(self):
        """Save current session state snapshot."""
        if not self.session_id:
            return

        snapshot = self._create_state_snapshot()
        result = await self.state_service.save_state(snapshot)

        if result.is_success:
            logger.info(f"Saved session state: {self.session_id}")
        else:
            logger.warning(f"Failed to save session state: {result.fallback}")

    async def _restore_session_state(self, state: SessionStateSnapshot):
        """
        Restore session state from snapshot.
        Override in subclasses to handle scenario-specific state restoration.
        """
        logger.info(
            f"Restoring session state: session_id={state.session_id}, "
            f"scenario={state.scenario}"
        )
        # Base implementation - subclasses can override to restore specific state

    async def _send_reconnection_success(self, state: SessionStateSnapshot):
        """
        Send reconnection success message to client.
        """
        websocket = self._get_active_websocket()
        if not websocket:
            return

        await self.manager.send_json(
            websocket,
            {
                "type": "reconnected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "session_id": state.session_id,
                    "scenario": state.scenario,
                    "restored_state": state.to_dict(),
                },
            },
        )

    def _get_active_websocket(self) -> WebSocket | None:
        """Get current active websocket for the session."""
        return self.websocket
