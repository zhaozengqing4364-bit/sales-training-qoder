"""
Session State Service - WebSocket reconnection state persistence

Implements Constitution Principle IV: Fault tolerance and recovery
- Persists session state for reconnection scenarios
- Maintains data consistency across network interruptions
- Provides graceful degradation on reconnection failure

Requirements: Story 2.9 - WebSocket Exception Recovery
"""

import asyncio
import importlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.conversation.models import ConversationMessage
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)

SESSION_STATE_STARTUP_POLICY_ENV = "SESSION_STATE_STARTUP_POLICY"
SESSION_STATE_SNAPSHOT_ENABLED_ENV = "SESSION_STATE_SNAPSHOT_ENABLED"
SESSION_STATE_STARTUP_POLICIES = {"required", "optional", "disabled"}
SESSION_STATE_DEFAULT_STARTUP_POLICY = "required"


def _env_bool_disabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


def _resolve_startup_policy(startup_policy: str | None = None) -> str:
    if startup_policy is not None:
        configured = startup_policy
    elif _env_bool_disabled(os.getenv(SESSION_STATE_SNAPSHOT_ENABLED_ENV)):
        configured = "disabled"
    else:
        configured = os.getenv(
            SESSION_STATE_STARTUP_POLICY_ENV,
            SESSION_STATE_DEFAULT_STARTUP_POLICY,
        )

    normalized = (configured or SESSION_STATE_DEFAULT_STARTUP_POLICY).strip().lower()
    if normalized in SESSION_STATE_STARTUP_POLICIES:
        return normalized

    logger.warning(
        "Invalid session state startup policy; using required",
        configured_policy=configured,
        default_policy=SESSION_STATE_DEFAULT_STARTUP_POLICY,
    )
    return SESSION_STATE_DEFAULT_STARTUP_POLICY


def _load_redis_module() -> Any:
    return importlib.import_module("redis.asyncio")


@dataclass
class SessionStateSnapshot:
    """Session state snapshot for reconnection recovery"""

    session_id: str
    scenario: str  # 'presentation' or 'sales'
    turn_count: int = 0
    current_page: int | None = None
    session_status: str = "in_progress"
    ai_state: str = "idle"
    runtime_state: dict[str, Any] | None = None
    last_activity: float = field(default_factory=time.time)
    user_id: str | None = None

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
        startup_policy: str | None = None,
    ):
        self.state_ttl = state_ttl
        self.cleanup_interval = cleanup_interval
        env_redis_url = os.getenv("SESSION_STATE_REDIS_URL") or os.getenv("REDIS_URL")
        self.redis_url: str = redis_url or env_redis_url or "redis://localhost:6379/0"
        env_key_prefix = os.getenv("SESSION_STATE_KEY_PREFIX")
        self.key_prefix: str = key_prefix or env_key_prefix or "ws:session_state:"
        self.startup_policy = _resolve_startup_policy(startup_policy)

        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._running = False
        self._redis: Any | None = None
        self._health_status = "stopped"
        self._startup_error: dict[str, Any] | None = None
        self._snapshot_disabled_reason: str | None = None
        self.metrics = {
            "save_calls": 0,
            "get_calls": 0,
            "get_misses": 0,
            "delete_calls": 0,
            "save_failures": 0,
            "get_failures": 0,
            "delete_failures": 0,
            "healthcheck_failures": 0,
            "disabled_operations": 0,
        }
        self.last_saved_session_id: str | None = None
        self.last_loaded_session_id: str | None = None
        self.last_deleted_session_id: str | None = None
        self.last_saved_snapshot: dict[str, Any] | None = None
        self.last_loaded_snapshot: dict[str, Any] | None = None
        self.last_error: dict[str, Any] | None = None

    @staticmethod
    def _summarize_snapshot(state: SessionStateSnapshot) -> dict[str, Any]:
        runtime_state = (
            state.runtime_state if isinstance(state.runtime_state, dict) else {}
        )
        reconnect_state = runtime_state.get("reconnect_state")
        normalized_reconnect_state = (
            dict(reconnect_state) if isinstance(reconnect_state, dict) else None
        )
        last_error = None
        connection_epoch = 0
        last_disconnect_reason = None
        if normalized_reconnect_state is not None:
            connection_epoch = int(
                normalized_reconnect_state.get("connection_epoch") or 0
            )
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

    def _require_redis(self) -> Any:
        if self._redis is None:
            raise RuntimeError(
                "Session state Redis client is not initialized "
                f"(health_status={self._health_status}, "
                f"startup_policy={self.startup_policy})"
            )
        return self._redis

    @property
    def snapshot_enabled(self) -> bool:
        return self._running and self._redis is not None

    def get_health(self) -> dict[str, Any]:
        ready = self._health_status == "ok" or (
            self.startup_policy in {"optional", "disabled"}
            and self._health_status in {"degraded", "disabled"}
        )
        return {
            "status": self._health_status,
            "ready": ready,
            "startup_policy": self.startup_policy,
            "snapshot_enabled": self.snapshot_enabled,
            "redis_connected": self._redis is not None,
            "disabled_reason": self._snapshot_disabled_reason,
            "startup_error": dict(self._startup_error)
            if isinstance(self._startup_error, dict)
            else None,
        }

    def _snapshot_disabled_result(
        self,
        operation: str,
        session_id: str,
    ) -> Result[Any]:
        self.metrics["disabled_operations"] += 1
        self.last_error = {
            "operation": operation,
            "session_id": session_id,
            "error": "[SESSION_STATE_SNAPSHOT_DISABLED]",
            "health_status": self._health_status,
            "startup_policy": self.startup_policy,
            "disabled_reason": self._snapshot_disabled_reason,
        }
        logger.warning(
            "Session state snapshot operation skipped",
            operation=operation,
            session_id=session_id,
            health_status=self._health_status,
            startup_policy=self.startup_policy,
            disabled_reason=self._snapshot_disabled_reason,
        )
        return Result.fail("[SESSION_STATE_SNAPSHOT_DISABLED]")

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

    async def start(self) -> None:
        """Start Redis-backed session state service"""
        if self._running:
            return

        if self.startup_policy == "disabled":
            self._health_status = "disabled"
            self._startup_error = None
            self._snapshot_disabled_reason = "startup_policy_disabled"
            logger.warning(
                "Session state snapshots disabled by configuration",
                startup_policy=self.startup_policy,
            )
            return

        try:
            redis = _load_redis_module()
        except ImportError as exc:
            self._handle_startup_failure(exc, reason="redis_package_missing")
            if self.startup_policy == "optional":
                return
            raise RuntimeError(
                "redis package is required for SessionStateService"
            ) from exc

        async with self._lock:
            if self._running:
                return

            client: Any = redis.from_url(
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
                self._handle_startup_failure(exc, reason="redis_unavailable")
                if self.startup_policy == "optional":
                    return
                raise RuntimeError(
                    f"Failed to connect Redis for session state: {exc}"
                ) from exc

            self._redis = client
            self._running = True
            self._health_status = "ok"
            self._startup_error = None
            self._snapshot_disabled_reason = None
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(
            "Session state service started",
            redis_url=self.redis_url,
            key_prefix=self.key_prefix,
            state_ttl=self.state_ttl,
        )

    def _handle_startup_failure(self, exc: Exception, *, reason: str) -> None:
        self._redis = None
        self._running = False
        self._startup_error = {
            "operation": "start",
            "reason": reason,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        self.last_error = dict(self._startup_error)
        self._snapshot_disabled_reason = reason
        self._health_status = (
            "degraded" if self.startup_policy == "optional" else "error"
        )
        log_method = (
            logger.warning if self.startup_policy == "optional" else logger.error
        )
        log_method(
            "Session state Redis startup failed",
            startup_policy=self.startup_policy,
            reason=reason,
            error_type=type(exc).__name__,
            error=str(exc),
        )

    async def stop(self) -> None:
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

        self._health_status = "stopped"
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
        if not self.snapshot_enabled:
            return self._snapshot_disabled_result("save_state", state.session_id)

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

    async def get_state(self, session_id: str) -> Result[SessionStateSnapshot | None]:
        """
        Get session state snapshot.

        Args:
            session_id: Session UUID

        Returns:
            Result[Optional[SessionStateSnapshot]]: State or None if not found
        """
        self.metrics["get_calls"] += 1
        if not self.snapshot_enabled:
            return self._snapshot_disabled_result("get_state", session_id)

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
        if not self.snapshot_enabled:
            return self._snapshot_disabled_result("delete_state", session_id)

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

    async def _cleanup_loop(self) -> None:
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
                self._health_status = "degraded"
                logger.error(f"Session state Redis health check failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get session state service statistics."""
        return {
            "state_ttl": self.state_ttl,
            "cleanup_interval": self.cleanup_interval,
            "redis_connected": self._redis is not None,
            "running": self._running,
            "startup_policy": self.startup_policy,
            "snapshot_enabled": self.snapshot_enabled,
            "health": self.get_health(),
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
            "last_error": dict(self.last_error)
            if isinstance(self.last_error, dict)
            else None,
        }


# Global session state service instance
_session_state_service: SessionStateService | None = None


def get_session_state_service() -> SessionStateService:
    """Get or create global session state service instance"""
    global _session_state_service
    if _session_state_service is None:
        ttl = int(os.getenv("SESSION_STATE_TTL_SECONDS", "1800"))
        cleanup_interval = int(
            os.getenv("SESSION_STATE_CLEANUP_INTERVAL_SECONDS", "300")
        )
        _session_state_service = SessionStateService(
            state_ttl=ttl,
            cleanup_interval=cleanup_interval,
        )
    return _session_state_service


async def init_session_state_service() -> SessionStateService:
    """Initialize session state service on application startup"""
    service = get_session_state_service()
    await service.start()
    logger.info(
        "Session state service initialized",
        health=service.get_health(),
    )
    return service


async def shutdown_session_state_service() -> None:
    """Shutdown session state service on application shutdown"""
    global _session_state_service
    if _session_state_service:
        await _session_state_service.stop()
        _session_state_service = None
        logger.info("Session state service shutdown")
