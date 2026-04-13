"""
Session State Service - WebSocket reconnection state persistence

Implements Constitution Principle IV: Fault tolerance and recovery
- Persists session state for reconnection scenarios
- Maintains data consistency across network interruptions
- Provides graceful degradation on reconnection failure

Requirements: Story 2.9 - WebSocket Exception Recovery
"""

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.models import ConversationMessage
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionStateSnapshot:
    """Session state snapshot for reconnection recovery"""

    session_id: str
    scenario: str  # 'presentation' or 'sales'
    turn_count: int = 0
    current_page: Optional[int] = None
    session_status: str = "in_progress"
    ai_state: str = "idle"
    runtime_state: dict[str, Any] | None = None
    last_activity: float = field(default_factory=time.time)
    user_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionStateSnapshot":
        """Create from dictionary"""
        return cls(**data)


class SessionStateService:
    """
    Session state persistence service for WebSocket reconnection.

    Features:
    - Save session state snapshots in Redis for distributed deployments
    - Automatic expiration by Redis TTL
    - Thread-safe access with asyncio locks

    Configuration:
    - state_ttl: 1800 seconds (30 minutes)
    - cleanup_interval: 300 seconds (5 minutes, Redis health check)
    """

    def __init__(
        self,
        state_ttl: int = 1800,  # 30 minutes
        cleanup_interval: int = 300,  # 5 minutes
        redis_url: str | None = None,
        key_prefix: str | None = None,
    ):
        self.state_ttl = state_ttl
        self.cleanup_interval = cleanup_interval
        self.redis_url = (
            redis_url
            or os.getenv("SESSION_STATE_REDIS_URL")
            or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        )
        self.key_prefix = key_prefix or os.getenv(
            "SESSION_STATE_KEY_PREFIX", "ws:session_state:"
        )

        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        self._redis: Any | None = None
        self.metrics = {
            "save_calls": 0,
            "get_calls": 0,
            "get_misses": 0,
            "delete_calls": 0,
            "save_failures": 0,
            "get_failures": 0,
            "delete_failures": 0,
            "healthcheck_failures": 0,
        }
        self.last_saved_session_id: str | None = None
        self.last_loaded_session_id: str | None = None
        self.last_deleted_session_id: str | None = None
        self.last_saved_snapshot: dict[str, Any] | None = None
        self.last_loaded_snapshot: dict[str, Any] | None = None
        self.last_error: dict[str, Any] | None = None

    @staticmethod
    def _summarize_snapshot(state: SessionStateSnapshot) -> dict[str, Any]:
        runtime_state = state.runtime_state if isinstance(state.runtime_state, dict) else {}
        reconnect_state = runtime_state.get("reconnect_state")
        normalized_reconnect_state = (
            dict(reconnect_state) if isinstance(reconnect_state, dict) else None
        )
        last_error = None
        connection_epoch = 0
        last_disconnect_reason = None
        if normalized_reconnect_state is not None:
            connection_epoch = int(normalized_reconnect_state.get("connection_epoch") or 0)
            last_disconnect_reason = normalized_reconnect_state.get(
                "last_disconnect_reason"
            )
            candidate_last_error = normalized_reconnect_state.get("last_error")
            if isinstance(candidate_last_error, dict):
                last_error = dict(candidate_last_error)
        return {
            "session_id": state.session_id,
            "scenario": state.scenario,
            "turn_count": state.turn_count,
            "current_page": state.current_page,
            "session_status": state.session_status,
            "ai_state": state.ai_state,
            "user_id": state.user_id,
            "last_activity": state.last_activity,
            "runtime_keys": sorted(runtime_state.keys()),
            "request_epoch": int(runtime_state.get("current_request_id") or 0),
            "connection_epoch": connection_epoch,
            "last_disconnect_reason": last_disconnect_reason,
            "last_error": last_error,
            "reconnect_state": normalized_reconnect_state,
        }

    def _state_key(self, session_id: str) -> str:
        return f"{self.key_prefix}{session_id}"

    def _require_redis(self):
        if self._redis is None:
            raise RuntimeError("Session state Redis client is not initialized")
        return self._redis

    def describe_authority(self) -> dict[str, dict[str, Any]]:
        """Describe which runtime state belongs in Redis versus process memory."""
        return {
            "session_snapshot": {
                "owner": "session_state_service",
                "storage": "redis_snapshot",
                "shared_across_instances": True,
                "survives_restart": True,
                "ttl_seconds": self.state_ttl,
                "inspection_surface": "SessionStateService.get_stats()",
            },
            "runtime_connections": {
                "owner": "session_manager.sessions",
                "storage": "process_memory",
                "shared_across_instances": False,
                "survives_restart": False,
            },
        }

    async def start(self):
        """Start Redis-backed session state service"""
        if self._running:
            return

        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError(
                "redis package is required for SessionStateService"
            ) from exc

        async with self._lock:
            if self._running:
                return

            client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            try:
                await client.ping()
            except Exception as exc:
                try:
                    await client.aclose()
                except Exception:
                    pass
                raise RuntimeError(
                    f"Failed to connect Redis for session state: {exc}"
                ) from exc

            self._redis = client
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(
            "Session state service started",
            redis_url=self.redis_url,
            key_prefix=self.key_prefix,
            state_ttl=self.state_ttl,
        )

    async def stop(self):
        """Stop background task and close Redis connection"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        redis_client = self._redis
        self._redis = None
        if redis_client is not None:
            try:
                await redis_client.aclose()
            except Exception as exc:
                logger.warning(f"Failed to close Redis client cleanly: {exc}")

        logger.info("Session state service stopped")

    async def save_state(self, state: SessionStateSnapshot) -> Result[None]:
        """
        Save session state snapshot.

        Args:
            state: Session state snapshot to save

        Returns:
            Result[None]: Success or failure
        """
        self.metrics["save_calls"] += 1
        try:
            state.last_activity = time.time()
            payload = json.dumps(state.to_dict(), ensure_ascii=False)
            redis_client = self._require_redis()
            await redis_client.set(
                self._state_key(state.session_id),
                payload,
                ex=self.state_ttl,
            )
            self.last_saved_session_id = state.session_id
            self.last_saved_snapshot = self._summarize_snapshot(state)
            self.last_error = None

            logger.info(
                f"Saved session state: {state.session_id}",
                extra={
                    "session_id": state.session_id,
                    "scenario": state.scenario,
                    "turn_count": state.turn_count,
                    "current_page": state.current_page,
                    "ai_state": state.ai_state,
                },
            )
            return Result.ok(None)

        except Exception as e:
            self.metrics["save_failures"] += 1
            self.last_error = {
                "operation": "save_state",
                "session_id": state.session_id,
                "error": str(e),
            }
            logger.error(f"Failed to save session state: {str(e)}")
            return Result.fail(f"[STATE_SAVE_FAILED] {str(e)}")

    async def get_state(self, session_id: str) -> Result[Optional[SessionStateSnapshot]]:
        """
        Get session state snapshot.

        Args:
            session_id: Session UUID

        Returns:
            Result[Optional[SessionStateSnapshot]]: State or None if not found
        """
        self.metrics["get_calls"] += 1
        try:
            redis_client = self._require_redis()
            raw_state = await redis_client.get(self._state_key(session_id))
            if not raw_state:
                self.metrics["get_misses"] += 1
                self.last_error = None
                logger.info(f"Session state not found: {session_id}")
                return Result.ok(None)

            data = json.loads(raw_state)
            state = SessionStateSnapshot.from_dict(data)
            self.last_loaded_session_id = session_id
            self.last_loaded_snapshot = self._summarize_snapshot(state)
            self.last_error = None
            logger.info(f"Retrieved session state: {session_id}")
            return Result.ok(state)

        except Exception as e:
            self.metrics["get_failures"] += 1
            self.last_error = {
                "operation": "get_state",
                "session_id": session_id,
                "error": str(e),
            }
            logger.error(f"Failed to get session state: {str(e)}")
            return Result.fail(f"[STATE_GET_FAILED] {str(e)}")

    async def delete_state(self, session_id: str) -> Result[None]:
        """
        Delete session state snapshot.

        Args:
            session_id: Session UUID

        Returns:
            Result[None]: Success or failure
        """
        self.metrics["delete_calls"] += 1
        try:
            redis_client = self._require_redis()
            await redis_client.delete(self._state_key(session_id))
            self.last_deleted_session_id = session_id
            self.last_error = None
            logger.info(f"Deleted session state: {session_id}")
            return Result.ok(None)

        except Exception as e:
            self.metrics["delete_failures"] += 1
            self.last_error = {
                "operation": "delete_state",
                "session_id": session_id,
                "error": str(e),
            }
            logger.error(f"Failed to delete session state: {str(e)}")
            return Result.fail(f"[STATE_DELETE_FAILED] {str(e)}")

    async def get_recent_messages(
        self,
        db: AsyncSession,
        session_id: str,
        limit: int = 10,
    ) -> Result[list[ConversationMessage]]:
        """
        Get recent conversation messages for reconnection.

        Args:
            db: Database session
            session_id: Session UUID
            limit: Maximum number of messages to retrieve

        Returns:
            Result[list[ConversationMessage]]: Recent messages or failure
        """
        try:
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.timestamp.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            messages = list(result.scalars().all())

            # Reverse to get chronological order
            messages.reverse()

            logger.info(
                f"Retrieved {len(messages)} recent messages for session: {session_id}"
            )

            return Result.ok(messages)

        except Exception as e:
            logger.error(f"Failed to get recent messages: {str(e)}")
            return Result.fail(f"[MESSAGES_GET_FAILED] {str(e)}")

    async def _cleanup_loop(self):
        """Background task used as Redis health checker."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                redis_client = self._require_redis()
                await redis_client.ping()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.metrics["healthcheck_failures"] += 1
                self.last_error = {
                    "operation": "healthcheck",
                    "error": str(e),
                }
                logger.error(f"Session state Redis health check failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get session state service statistics."""
        return {
            "state_ttl": self.state_ttl,
            "cleanup_interval": self.cleanup_interval,
            "redis_connected": self._redis is not None,
            "running": self._running,
            "key_prefix": self.key_prefix,
            "authority": self.describe_authority(),
            "snapshot_visibility": {
                "scope": "redis_snapshot",
                "shared_across_instances": True,
                "survives_restart": True,
                "redis_connected": self._redis is not None,
                "running": self._running,
            },
            "metrics": dict(self.metrics),
            "last_saved_session_id": self.last_saved_session_id,
            "last_loaded_session_id": self.last_loaded_session_id,
            "last_deleted_session_id": self.last_deleted_session_id,
            "last_saved_snapshot": dict(self.last_saved_snapshot)
            if isinstance(self.last_saved_snapshot, dict)
            else None,
            "last_loaded_snapshot": dict(self.last_loaded_snapshot)
            if isinstance(self.last_loaded_snapshot, dict)
            else None,
            "last_error": dict(self.last_error) if isinstance(self.last_error, dict) else None,
        }


# Global session state service instance
_session_state_service: Optional[SessionStateService] = None


def get_session_state_service() -> SessionStateService:
    """Get or create global session state service instance"""
    global _session_state_service
    if _session_state_service is None:
        ttl = int(os.getenv("SESSION_STATE_TTL_SECONDS", "1800"))
        cleanup_interval = int(os.getenv("SESSION_STATE_CLEANUP_INTERVAL_SECONDS", "300"))
        _session_state_service = SessionStateService(
            state_ttl=ttl,
            cleanup_interval=cleanup_interval,
        )
    return _session_state_service


async def init_session_state_service():
    """Initialize session state service on application startup"""
    service = get_session_state_service()
    await service.start()
    logger.info("Session state service initialized")


async def shutdown_session_state_service():
    """Shutdown session state service on application shutdown"""
    global _session_state_service
    if _session_state_service:
        await _session_state_service.stop()
        _session_state_service = None
        logger.info("Session state service shutdown")
