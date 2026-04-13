"""
Session Manager - WebSocket session timeout and heartbeat management

Implements Constitution Principle II: Real-time priority with resource protection
- Monitors session activity and closes inactive sessions
- Prevents zombie connections from consuming resources
- Provides heartbeat mechanism for connection health monitoring

Requirements: P0-FIXES.md Issue #10
"""

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime, timezone

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionInfo:
    """Session information for timeout tracking"""

    session_id: str
    handler: "BaseWebSocketHandler"
    last_activity: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    user_id: Optional[str] = None


class SessionManager:
    """
    WebSocket session manager with timeout and heartbeat support

    Features:
    - Automatic session timeout after 30 minutes of inactivity
    - Heartbeat monitoring (30 second interval)
    - Resource cleanup for expired sessions
    - Activity tracking per session

    Configuration:
    - timeout_seconds: 1800 (30 minutes)
    - heartbeat_interval: 30 seconds
    - cleanup_interval: 60 seconds
    """

    def __init__(
        self,
        timeout_seconds: int = 1800,  # 30 minutes
        heartbeat_interval: int = 30,  # 30 seconds
        cleanup_interval: int = 60,  # 60 seconds
    ):
        self.sessions: Dict[str, SessionInfo] = {}
        self.timeout_seconds = timeout_seconds
        self.heartbeat_interval = heartbeat_interval
        self.cleanup_interval = cleanup_interval
        self.cleanup_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
        self.metrics = {
            "registered_sessions": 0,
            "unregistered_sessions": 0,
            "timeout_closures": 0,
            "heartbeat_failures": 0,
            "cleanup_loop_errors": 0,
            "heartbeat_loop_errors": 0,
        }

    async def start(self):
        """Start session monitoring (cleanup and heartbeat loops)"""
        if self._running:
            return

        self._running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Session manager started")

    async def stop(self):
        """Stop session monitoring"""
        self._running = False

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info("Session manager stopped")

    async def register_session(
        self,
        session_id: str,
        handler: "BaseWebSocketHandler",
        user_id: Optional[str] = None,
    ):
        """Register a new session for monitoring"""
        self.sessions[session_id] = SessionInfo(
            session_id=session_id,
            handler=handler,
            user_id=user_id,
            last_activity=time.time(),
            created_at=time.time(),
        )
        self.metrics["registered_sessions"] += 1
        logger.info(
            f"Session registered: {session_id}",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "total_sessions": len(self.sessions),
            },
        )

    async def update_activity(self, session_id: str):
        """Update last activity timestamp for a session"""
        if session_id in self.sessions:
            self.sessions[session_id].last_activity = time.time()

    async def unregister_session(self, session_id: str, reason: str = "manual"):
        """Unregister a session"""
        if session_id in self.sessions:
            session_info = self.sessions[session_id]
            del self.sessions[session_id]
            self.metrics["unregistered_sessions"] += 1
            logger.info(
                f"Session unregistered: {session_id}",
                extra={
                    "session_id": session_id,
                    "user_id": session_info.user_id,
                    "reason": reason,
                    "total_sessions": len(self.sessions),
                },
            )

    async def sync_lifecycle_transition(self, transition) -> bool:
        """Synchronize a DB lifecycle transition into the live handler."""
        session_id = str(transition.session.session_id)
        session_info = self.sessions.get(session_id)
        if session_info is None:
            return False

        sync_method = getattr(session_info.handler, "sync_lifecycle_transition", None)
        if callable(sync_method):
            maybe_result = sync_method(transition)
            if inspect.isawaitable(maybe_result):
                await maybe_result
            return True

        if hasattr(session_info.handler, "session_status"):
            session_info.handler.session_status = transition.to_status
        if hasattr(session_info.handler, "ai_state"):
            session_info.handler.ai_state = transition.ai_state
        return True

    async def close_session_connection(
        self,
        session_id: str,
        *,
        code: int = 1000,
        reason: str = "Session closed",
    ) -> bool:
        """Close the live websocket connection for one tracked session."""
        session_info = self.sessions.get(session_id)
        if session_info is None:
            return False

        close_method = getattr(session_info.handler, "close", None)
        if not callable(close_method):
            return False

        maybe_result = close_method(code=code, reason=reason)
        if inspect.isawaitable(maybe_result):
            await maybe_result
        return True

    async def _cleanup_loop(self):
        """Background task to clean up expired sessions"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                self.metrics["cleanup_loop_errors"] += 1
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_expired_sessions(self):
        """Clean up sessions that have exceeded timeout"""
        now = time.time()
        expired_sessions = []

        for session_id, info in self.sessions.items():
            inactive_duration = now - info.last_activity
            if inactive_duration > self.timeout_seconds:
                expired_sessions.append((session_id, inactive_duration))

        for session_id, inactive_duration in expired_sessions:
            info = self.sessions.get(session_id)
            if not info:
                continue

            try:
                # Send timeout notification
                await info.handler.send_message(
                    {
                        "type": "session_timeout",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {
                            "message": "会话超时，请重新开始",
                            "inactive_duration": int(inactive_duration),
                            "timeout_seconds": self.timeout_seconds,
                        },
                    }
                )

                # Close connection
                await info.handler.close(code=1000, reason="Session timeout")
                self.metrics["timeout_closures"] += 1

                logger.warning(
                    f"Session timeout: {session_id}, "
                    f"inactive for {int(inactive_duration)}s",
                    extra={
                        "session_id": session_id,
                        "user_id": info.user_id,
                        "inactive_duration": inactive_duration,
                    },
                )

            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Failed to cleanup session {session_id}: {e}")
            finally:
                # Always remove from tracking
                await self.unregister_session(session_id, reason="timeout")

    async def _heartbeat_loop(self):
        """Background task to send periodic heartbeats"""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeats()
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                self.metrics["heartbeat_loop_errors"] += 1
                logger.error(f"Heartbeat loop error: {e}")

    async def _send_heartbeats(self):
        """Send heartbeat to all active sessions"""
        now = time.time()
        dead_sessions = []

        for session_id, info in list(self.sessions.items()):
            try:
                await info.handler.send_message(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {
                            "timestamp": now,
                            "session_age": int(now - info.created_at),
                        },
                    }
                )
            except (RuntimeError, ValueError, OSError) as e:
                self.metrics["heartbeat_failures"] += 1
                logger.warning(
                    f"Failed to send heartbeat to {session_id}: {e}",
                    extra={"session_id": session_id},
                )
                dead_sessions.append(session_id)

        # Clean up dead connections
        for session_id in dead_sessions:
            await self.unregister_session(session_id, reason="heartbeat_failed")

    def _runtime_diagnostics_for_handler(self, handler) -> dict | None:
        getter = getattr(handler, "get_runtime_diagnostics", None)
        if not callable(getter):
            return None
        try:
            diagnostics = getter()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to read handler runtime diagnostics: {exc}")
            return None
        return diagnostics if isinstance(diagnostics, dict) else None

    def describe_authority(self) -> dict[str, dict[str, object]]:
        """Describe which websocket runtime facts this process truly owns."""
        return {
            "connection_registry": {
                "owner": "session_manager.sessions",
                "storage": "process_memory",
                "shared_across_instances": False,
                "survives_restart": False,
                "inspection_surface": "SessionManager.get_stats()",
            },
            "session_snapshot": {
                "owner": "session_state_service",
                "storage": "redis_snapshot",
                "shared_across_instances": True,
                "survives_restart": True,
            },
        }

    def get_stats(self) -> dict:
        """Get session manager statistics"""
        now = time.time()
        total = len(self.sessions)

        # Count sessions by age
        active_last_5min = sum(
            1 for s in self.sessions.values() if now - s.last_activity < 300
        )
        active_last_hour = sum(
            1 for s in self.sessions.values() if now - s.last_activity < 3600
        )

        tracked_sessions = [
            {
                "session_id": info.session_id,
                "user_id": info.user_id,
                "scenario": getattr(info.handler, "scenario", None),
                "session_status": getattr(info.handler, "session_status", None),
                "ai_state": getattr(info.handler, "ai_state", None),
                "connected_at": info.created_at,
                "last_activity_at": info.last_activity,
                "session_age_seconds": round(max(0.0, now - info.created_at), 3),
                "inactive_seconds": round(max(0.0, now - info.last_activity), 3),
                "runtime_diagnostics": self._runtime_diagnostics_for_handler(
                    info.handler
                ),
            }
            for info in sorted(self.sessions.values(), key=lambda item: item.session_id)
        ]

        return {
            "total_sessions": total,
            "active_last_5min": active_last_5min,
            "active_last_hour": active_last_hour,
            "timeout_seconds": self.timeout_seconds,
            "heartbeat_interval": self.heartbeat_interval,
            "authority": self.describe_authority(),
            "connection_visibility": {
                "scope": "process_local",
                "shared_across_instances": False,
                "survives_restart": False,
                "running": self._running,
            },
            "tracked_sessions": tracked_sessions,
            "metrics": dict(self.metrics),
        }


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def init_session_manager():
    """Initialize session manager on application startup"""
    manager = get_session_manager()
    await manager.start()
    logger.info("Session manager initialized")


async def shutdown_session_manager():
    """Shutdown session manager on application shutdown"""
    global _session_manager
    if _session_manager:
        await _session_manager.stop()
        _session_manager = None
        logger.info("Session manager shutdown")
