"""
Base WebSocket Handler with connection lifecycle management
Constitution Principle I: No error popups, graceful degradation
"""
import asyncio
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from common.monitoring.logger import get_logger, set_trace_id, get_trace_id

logger = get_logger(__name__)


class ConnectionManager:
    """Manage WebSocket connections across all scenarios"""

    def __init__(self):
        # Scenario -> Session ID -> WebSocket
        self.active_connections: dict[str, dict[str, WebSocket]] = {
            "presentation": {},
            "sales": {}
        }

    async def connect(self, websocket: WebSocket, scenario: str, session_id: str):
        """Accept and track connection"""
        await websocket.accept()
        if scenario not in self.active_connections:
            self.active_connections[scenario] = {}

        self.active_connections[scenario][session_id] = websocket
        logger.info(f"WebSocket connected: scenario={scenario}, session={session_id}")

        # Send acknowledgment
        await self.send_json(websocket, {
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"session_id": session_id}
        })

    def disconnect(self, scenario: str, session_id: str):
        """Remove connection from tracking"""
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
        if scenario in self.active_connections:
            websocket = self.active_connections[scenario].get(session_id)
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
    Implements message queue for non-blocking handling
    """

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.manager = get_connection_manager()
        self.message_queue: asyncio.Queue = None
        self.running = False

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
        except Exception as e:
            logger.warning(f"Token verification failed: {str(e)}")
            set_trace_id("")

        # Connect
        await self.manager.connect(websocket, self.scenario, session_id)

        # Initialize message queue
        self.message_queue = asyncio.Queue()
        self.running = True

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
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {}
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally: session={session_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            # Cleanup
            self.running = False
            self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()

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
            except Exception as e:
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
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "code": error_code,
                "message": message,
                "user_action": user_action,  # What client should do
                "trace_id": get_trace_id()
            }
        })
