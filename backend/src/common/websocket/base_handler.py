"""
Base WebSocket Handler with connection lifecycle management
Constitution Principle I: No error popups, graceful degradation
"""

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from common.auth.service import JWTError, resolve_websocket_token
from common.config import settings
from common.monitoring.logger import get_logger, get_trace_id, set_trace_id
from common.monitoring.metrics import (
    track_websocket_connection,
    track_websocket_connection_event,
    track_websocket_error,
    track_websocket_message,
    track_websocket_send_failure,
)
from common.monitoring.trace_context import normalize_trace_id
from common.websocket.session_state_service import (
    SessionStateSnapshot,
    get_session_state_service,
)

if TYPE_CHECKING:
    from common.db.session_lifecycle import SessionLifecycleTransition

logger = get_logger(__name__)

DEFAULT_MESSAGE_QUEUE_SIZE = 300
WEBSOCKET_QUEUE_OVERFLOW_CODE = "[WS_QUEUE_OVERFLOW]"


@dataclass(frozen=True)
class WebSocketSendResult:
    """Structured send outcome for callers that must react to failures."""

    success: bool
    skipped: bool = False
    message_type: str = "unknown"
    error_type: str | None = None
    error: str | None = None

    @classmethod
    def sent(cls, message_type: str) -> "WebSocketSendResult":
        return cls(success=True, message_type=message_type)

    @classmethod
    def skipped_send(
        cls,
        message_type: str,
        *,
        error_type: str,
        error: str,
    ) -> "WebSocketSendResult":
        return cls(
            success=False,
            skipped=True,
            message_type=message_type,
            error_type=error_type,
            error=error,
        )

    @classmethod
    def failed(
        cls,
        message_type: str,
        *,
        error_type: str,
        error: str,
    ) -> "WebSocketSendResult":
        return cls(
            success=False,
            message_type=message_type,
            error_type=error_type,
            error=error,
        )


def _get_websocket_header_value(websocket: WebSocket, header_name: str) -> str:
    """Return a string header value, tolerating simplified test doubles."""
    headers = getattr(websocket, "headers", None)

    if isinstance(headers, Mapping):
        value = headers.get(header_name, "")
        return value if isinstance(value, str) else ""

    getter = getattr(headers, "get", None)
    if callable(getter):
        try:
            value = getter(header_name, "")
        except TypeError:
            return ""
        return value if isinstance(value, str) else ""

    return ""


class ConnectionManager:
    """Manage WebSocket connections across all scenarios"""

    def __init__(self) -> None:
        # Scenario -> Session ID -> WebSocket
        self.active_connections: dict[str, dict[str, WebSocket]] = {
            "presentation": {},
            "sales": {},
        }
        self._lock = asyncio.Lock()

    @staticmethod
    def _message_type(message: dict[str, Any]) -> str:
        message_type = message.get("type")
        return str(message_type) if message_type else "unknown"

    async def connect(
        self, websocket: WebSocket, scenario: str, session_id: str
    ) -> None:
        """Accept and track connection"""
        await websocket.accept()
        previous_websocket: WebSocket | None = None
        async with self._lock:
            if scenario not in self.active_connections:
                self.active_connections[scenario] = {}
            previous_websocket = self.active_connections[scenario].get(session_id)
            self.active_connections[scenario][session_id] = websocket
        logger.info(f"WebSocket connected: scenario={scenario}, session={session_id}")
        track_websocket_connection_event(scenario, "connect")
        if previous_websocket is None:
            track_websocket_connection(scenario, 1)
        if previous_websocket is not None and previous_websocket is not websocket:
            await self._close_replaced_websocket(previous_websocket)

        # Send acknowledgment
        await self.send_json(
            websocket,
            {
                "type": "connected",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {"session_id": session_id},
            },
            scenario=scenario,
            session_id=session_id,
        )

    async def _close_replaced_websocket(self, websocket: WebSocket) -> None:
        """Close stale duplicate sockets for the same scenario/session pair."""
        if websocket.client_state == WebSocketState.DISCONNECTED:
            return
        try:
            await websocket.close(code=1012)
        except RuntimeError:
            pass

    async def disconnect(self, scenario: str, session_id: str) -> None:
        """Remove connection from tracking"""
        removed = False
        async with self._lock:
            if scenario in self.active_connections:
                removed = (
                    self.active_connections[scenario].pop(session_id, None) is not None
                )
        logger.info(
            f"WebSocket disconnected: scenario={scenario}, session={session_id}"
        )
        track_websocket_connection_event(scenario, "disconnect")
        if removed:
            track_websocket_connection(scenario, -1)

    async def send_json(
        self,
        websocket: WebSocket | None,
        message: dict[str, Any],
        *,
        scenario: str | None = None,
        session_id: str | None = None,
    ) -> WebSocketSendResult:
        """Send JSON message safely"""
        message_type = self._message_type(message)
        if websocket is None:
            return WebSocketSendResult.skipped_send(
                message_type,
                error_type="MissingWebSocket",
                error="WebSocket is not available",
            )

        metric_scenario = scenario or "unknown"
        started_at = perf_counter()
        try:
            await websocket.send_json(message)
            track_websocket_message(
                metric_scenario,
                "outbound",
                perf_counter() - started_at,
                message_type,
            )
            return WebSocketSendResult.sent(message_type)
        except Exception as e:
            error_type = type(e).__name__
            error = str(e)
            logger.error(
                "websocket_send_failed",
                scenario=scenario,
                session_id=session_id,
                message_type=message_type,
                error_type=error_type,
                error=error,
            )
            track_websocket_send_failure(metric_scenario, message_type, error_type)
            track_websocket_error(metric_scenario, error_type)
            return WebSocketSendResult.failed(
                message_type,
                error_type=error_type,
                error=error,
            )

    async def broadcast_to_session(
        self, scenario: str, session_id: str, message: dict[str, Any]
    ) -> WebSocketSendResult:
        """Send message to specific session"""
        websocket = None
        async with self._lock:
            websocket = self.active_connections.get(scenario, {}).get(session_id)
        if websocket:
            return await self.send_json(
                websocket,
                message,
                scenario=scenario,
                session_id=session_id,
            )
        return WebSocketSendResult.skipped_send(
            self._message_type(message),
            error_type="MissingWebSocket",
            error="Session has no active WebSocket",
        )

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

    MAX_MESSAGE_QUEUE_SIZE = settings.WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE
    BACKPRESSURE_POLICY = settings.WEBSOCKET_BACKPRESSURE_POLICY

    def __init__(self, scenario: str):
        self.scenario = scenario
        self.manager = get_connection_manager()
        self.message_queue: asyncio.Queue[dict[str, Any]] | None = None
        self.running = False
        self.websocket: WebSocket | None = None
        self.session_id: str | None = None
        self.state_service = get_session_state_service()
        self.user_id: str | None = None
        self.max_message_queue_size = self._get_configured_queue_size()

    @staticmethod
    def _get_configured_queue_size() -> int:
        """Return the validated inbound message queue size."""
        configured = getattr(
            settings,
            "WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE",
            DEFAULT_MESSAGE_QUEUE_SIZE,
        )
        if isinstance(configured, int) and 1 <= configured <= 5000:
            return configured
        logger.warning(
            "Invalid WEBSOCKET_MAX_MESSAGE_QUEUE_SIZE; using default",
            configured_value=configured,
            default_value=DEFAULT_MESSAGE_QUEUE_SIZE,
        )
        return DEFAULT_MESSAGE_QUEUE_SIZE

    async def on_connect(self) -> None:
        """Hook for subclasses that need to send server-driven messages on connect."""
        pass

    async def _enqueue_received_message(
        self, websocket: WebSocket, data: dict[str, Any]
    ) -> None:
        """Enqueue a received message without allowing unbounded memory growth."""
        if self.message_queue is None:
            logger.warning("Dropping websocket message before queue initialization")
            return

        try:
            self.message_queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning(
                "WebSocket message queue overflow; dropping newest message",
                scenario=self.scenario,
                session_id=self.session_id,
                queue_size=self.message_queue.qsize(),
            )
            await self.manager.send_json(
                websocket,
                {
                    "type": "backpressure",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": {
                        "code": WEBSOCKET_QUEUE_OVERFLOW_CODE,
                        "policy": getattr(
                            settings,
                            "WEBSOCKET_BACKPRESSURE_POLICY",
                            "drop_newest",
                        ),
                        "queue_size": self.message_queue.qsize(),
                        "user_action": "retry_later",
                    },
                },
                scenario=self.scenario,
                session_id=self.session_id,
            )

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        """
        Main connection handler
        Override in subclasses for scenario-specific logic
        """
        # Set trace_id from token or generate new
        resolved_token = resolve_websocket_token(
            query_token=token,
            authorization_header=_get_websocket_header_value(
                websocket,
                "authorization",
            ),
            cookie_header=_get_websocket_header_value(
                websocket,
                "cookie",
            ),
        )
        try:
            # Verify token and extract trace_id
            from common.auth.service import verify_token

            payload = verify_token(resolved_token)
            set_trace_id(
                normalize_trace_id(trace_id)
                or normalize_trace_id(payload.get("trace_id", ""))
                or ""
            )
            self.user_id = payload.get("user_id")
        except (JWTError, RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Token verification failed: {str(e)}")
            set_trace_id(normalize_trace_id(trace_id) or "")

        # Check for existing session state (reconnection scenario)
        existing_state = await self.state_service.get_state(session_id)
        is_reconnection = existing_state.is_success and existing_state.value is not None

        # Connect
        self.websocket = websocket
        self.session_id = session_id
        await self.manager.connect(websocket, self.scenario, session_id)

        # Initialize message queue
        self.message_queue = asyncio.Queue(maxsize=self.MAX_MESSAGE_QUEUE_SIZE)
        self.running = True

        # Restore state if reconnection
        if existing_state.value is not None and is_reconnection:
            logger.info(f"Reconnection detected for session: {session_id}")
            await self._restore_session_state(existing_state.value)

        await self.on_connect()

        # Start message processing task
        processing_task = asyncio.create_task(self._process_messages())

        try:
            # Receive messages loop
            while self.running:
                try:
                    # Set timeout for receiving
                    data = await asyncio.wait_for(
                        websocket.receive_json(),
                        timeout=30.0,  # 30s timeout
                    )
                    await self._enqueue_message(data, websocket)

                except TimeoutError:
                    # Send heartbeat
                    await self.manager.send_json(
                        websocket,
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.now(UTC).isoformat(),
                            "data": {},
                        },
                        scenario=self.scenario,
                        session_id=session_id,
                    )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally: session={session_id}")
        except (RuntimeError, ValueError, OSError) as e:
            track_websocket_error(self.scenario, type(e).__name__)
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            # Save session state before cleanup
            await self._save_session_state()
            # Cleanup
            self.running = False
            await self.manager.disconnect(self.scenario, session_id)
            processing_task.cancel()

    async def _enqueue_message(
        self, data: dict[str, Any], websocket: WebSocket
    ) -> bool:
        """Enqueue a message without allowing unbounded memory growth."""
        if self.message_queue is None:
            return False

        try:
            self.message_queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            policy = self.BACKPRESSURE_POLICY
            dropped = "newest"
            if policy == "drop_oldest":
                with suppress(asyncio.QueueEmpty):
                    self.message_queue.get_nowait()
                try:
                    self.message_queue.put_nowait(data)
                    dropped = "oldest"
                except asyncio.QueueFull:
                    dropped = "newest"

            logger.warning(
                "WebSocket message queue full",
                scenario=self.scenario,
                session_id=self.session_id,
                max_size=self.MAX_MESSAGE_QUEUE_SIZE,
                policy=policy,
                dropped=dropped,
            )
            await self.manager.send_json(
                websocket,
                {
                    "type": "backpressure",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "data": {
                        "reason": "message_queue_full",
                        "policy": policy,
                        "dropped": dropped,
                        "max_size": self.MAX_MESSAGE_QUEUE_SIZE,
                    },
                },
                scenario=self.scenario,
                session_id=self.session_id,
            )
            return False

    async def send_message(self, message: dict[str, Any]) -> WebSocketSendResult:
        """Send message to current websocket connection (SessionManager hook)."""
        if not self.websocket:
            return WebSocketSendResult.skipped_send(
                self.manager._message_type(message),
                error_type="MissingWebSocket",
                error="Handler has no active WebSocket",
            )
        return await self.manager.send_json(
            self.websocket,
            message,
            scenario=self.scenario,
            session_id=self.session_id,
        )

    async def close(self, code: int = 1000, reason: str = "Session closed") -> None:
        """Close current websocket connection safely (SessionManager hook)."""
        if not self.websocket:
            return

        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.close(code=code, reason=reason)
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Failed to close websocket: {e}")

    async def sync_lifecycle_transition(
        self, transition: "SessionLifecycleTransition"
    ) -> None:
        """Apply persisted lifecycle state pushed from REST controls."""
        if hasattr(self, "session_status"):
            self.session_status = transition.to_status
        if hasattr(self, "ai_state"):
            self.ai_state = transition.ai_state

    async def _process_messages(self) -> None:
        """
        Process messages from queue
        Override in subclasses for scenario-specific message handling
        """
        while self.running:
            try:
                if self.message_queue is None:
                    logger.warning(
                        "Stopping message processor without initialized queue"
                    )
                    break
                message = await self.message_queue.get()
                await self.handle_message(message)
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Message processing error: {str(e)}")

    async def handle_message(self, message: dict[str, Any]) -> None:
        """
        Handle individual message
        Override in subclasses
        """
        msg_type = message.get("type")
        logger.info(f"Received message type: {msg_type}")

        # Base handler does nothing - subclasses implement specific logic
        pass

    async def send_error(
        self,
        websocket: WebSocket,
        error_code: str,
        message: str,
        user_action: str | None = None,
    ) -> WebSocketSendResult:
        """
        Send error message (not shown as popup to user)
        Constitution: All errors converted to graceful degradation
        """
        return await self.manager.send_json(
            websocket,
            {
                "type": "error",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "code": error_code,
                    "message": message,
                    "user_action": user_action,  # What client should do
                    "trace_id": get_trace_id(),
                },
            },
            scenario=self.scenario,
            session_id=self.session_id,
        )

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

    async def _save_session_state(self) -> None:
        """Save current session state snapshot."""
        if not self.session_id:
            return

        snapshot = self._create_state_snapshot()
        result = await self.state_service.save_state(snapshot)

        if result.is_success:
            logger.info(f"Saved session state: {self.session_id}")
        elif result.fallback == "[SESSION_STATE_SNAPSHOT_DISABLED]":
            logger.info(
                "Skipped session state snapshot because snapshot storage is disabled",
                session_id=self.session_id,
                scenario=self.scenario,
            )
        else:
            logger.warning(f"Failed to save session state: {result.fallback}")

    async def _restore_session_state(self, state: SessionStateSnapshot) -> None:
        """
        Restore session state from snapshot.
        Override in subclasses to handle scenario-specific state restoration.
        """
        logger.info(
            f"Restoring session state: session_id={state.session_id}, "
            f"scenario={state.scenario}"
        )
        # Base implementation - subclasses can override to restore specific state

    async def _send_reconnection_success(self, state: SessionStateSnapshot) -> None:
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
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "session_id": state.session_id,
                    "scenario": state.scenario,
                    "restored_state": state.to_dict(),
                },
            },
            scenario=self.scenario,
            session_id=self.session_id,
        )

    def _get_active_websocket(self) -> WebSocket | None:
        """Get current active websocket for the session."""
        return self.websocket
