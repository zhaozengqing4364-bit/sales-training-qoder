"""
Session Rate Limiter - Prevent resource exhaustion from excessive sessions

Implements Constitution Principle V: Cost control and resource protection
- Limits concurrent sessions per user
- Prevents DDoS attacks on session endpoints
- Tracks session creation rates

Requirements: P0-FIXES.md Issue #13
"""

import asyncio
import time
from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import dataclass, field

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UserSessionInfo:
    """Session information for a user"""

    session_ids: set = field(default_factory=set)
    created_at: float = field(default_factory=time.time)


class SessionRateLimiter:
    """
    Rate limiter for session creation

    Limits:
    - 3 concurrent sessions per user
    - 10 sessions per hour per user
    - 500 total concurrent sessions globally

    Usage:
        limiter = SessionRateLimiter()

        allowed, reason = await limiter.check_limit(user_id)
        if allowed:
            session_id = await create_session()
            await limiter.register_session(user_id, session_id)
        else:
            raise HTTPException(429, detail=reason)
    """

    def __init__(
        self,
        max_concurrent_per_user: int = 3,
        max_sessions_per_hour: int = 10,
        max_total_concurrent: int = 500,
        session_window: int = 3600,  # 1 hour
        cleanup_interval: int = 300,  # 5 minutes
    ):
        self.max_concurrent_per_user = max_concurrent_per_user
        self.max_sessions_per_hour = max_sessions_per_hour
        self.max_total_concurrent = max_total_concurrent
        self.session_window = session_window
        self.cleanup_interval = cleanup_interval

        # user_id -> {session_id: timestamp}
        self.user_sessions: dict[str, dict[str, float]] = defaultdict(dict)
        # user_id -> session creation timestamps within the rate-limit window.
        # Keep this separate from active sessions so users cannot bypass the
        # hourly creation limit by ending sessions immediately after creation.
        self.user_session_creations: dict[str, list[float]] = defaultdict(list)
        self.current_total = 0

        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start cleanup background task"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session rate limiter started")

    async def stop(self) -> None:
        """Stop cleanup background task"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Session rate limiter stopped")

    async def check_limit(self, user_id: str) -> tuple[bool, str]:
        """
        Check if user can create a new session

        Returns:
            (allowed: bool, reason: str)
        """
        now = time.time()
        self._cleanup_user_window(user_id, now=now)

        # 1. Check global concurrent limit
        if self.current_total >= self.max_total_concurrent:
            logger.warning(
                "Global session limit reached",
                extra={
                    "current_total": self.current_total,
                    "max_total": self.max_total_concurrent,
                },
            )
            return False, "系统繁忙，请稍后再试"

        # 2. Clean up expired sessions for this user
        if user_id in self.user_sessions:
            expired_sessions = self._expire_user_sessions(
                self.user_sessions[user_id],
                now=now,
            )
            self.current_total = max(0, self.current_total - expired_sessions)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

        # 3. Check user concurrent limit
        active_sessions = len(self.user_sessions.get(user_id, {}))
        if active_sessions >= self.max_concurrent_per_user:
            logger.warning(
                f"User {user_id} concurrent session limit reached",
                extra={
                    "user_id": user_id,
                    "active_sessions": active_sessions,
                    "max_concurrent": self.max_concurrent_per_user,
                },
            )
            return False, f"您已有{active_sessions}个活跃会话，请先结束其他会话"

        # 4. Check hourly limit
        created_in_window = len(self.user_session_creations.get(user_id, []))
        if created_in_window >= self.max_sessions_per_hour:
            logger.warning(
                f"User {user_id} hourly session limit reached",
                extra={
                    "user_id": user_id,
                    "created_in_window": created_in_window,
                    "max_per_hour": self.max_sessions_per_hour,
                },
            )
            return False, "您已达到每小时会话上限，请稍后再试"

        return True, ""

    async def register_session(self, user_id: str, session_id: str) -> None:
        """Register a new session"""
        now = time.time()
        self._cleanup_user_window(user_id, now=now)

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}

        expired_sessions = self._expire_user_sessions(
            self.user_sessions[user_id],
            now=now,
        )
        self.current_total = max(0, self.current_total - expired_sessions)

        is_new_active_session = session_id not in self.user_sessions[user_id]
        self.user_sessions[user_id][session_id] = now
        if is_new_active_session:
            self.user_session_creations[user_id].append(now)
            self.current_total += 1

        logger.info(
            f"Session registered for user {user_id}",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "user_sessions": len(self.user_sessions[user_id]),
                "total_sessions": self.current_total,
            },
        )

    async def unregister_session(self, user_id: str, session_id: str) -> None:
        """Unregister a session"""
        if user_id in self.user_sessions:
            if session_id in self.user_sessions[user_id]:
                del self.user_sessions[user_id][session_id]
                self.current_total = max(0, self.current_total - 1)

                logger.info(
                    f"Session unregistered for user {user_id}",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "user_sessions": len(self.user_sessions[user_id]),
                        "total_sessions": self.current_total,
                    },
                )

            # Clean up empty user entries
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, OSError) as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired session records"""
        now = time.time()
        total_removed = 0

        for user_id in list(self.user_sessions.keys()):
            expired_sessions = self._expire_user_sessions(
                self.user_sessions[user_id],
                now=now,
            )
            total_removed += expired_sessions
            self.current_total = max(0, self.current_total - expired_sessions)

            # Remove empty user entries
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

        for user_id in list(self.user_session_creations.keys()):
            self._cleanup_user_window(user_id, now=now)

        if total_removed > 0:
            logger.info(
                f"Cleaned up {total_removed} expired sessions",
                extra={"removed": total_removed, "remaining": self.current_total},
            )

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        now = time.time()

        # Count active users (with sessions in last hour)
        active_users = sum(
            1
            for sessions in self.user_sessions.values()
            if any(now - ts < self.session_window for ts in sessions.values())
        )

        return {
            "total_sessions": self.current_total,
            "max_total_concurrent": self.max_total_concurrent,
            "utilization": self.current_total / self.max_total_concurrent
            if self.max_total_concurrent > 0
            else 0,
            "active_users": active_users,
            "max_concurrent_per_user": self.max_concurrent_per_user,
            "max_sessions_per_hour": self.max_sessions_per_hour,
        }

    def get_user_stats(self, user_id: str) -> dict:
        """Get stats for a specific user"""
        now = time.time()
        self._cleanup_user_window(user_id, now=now)
        sessions = self.user_sessions.get(user_id, {})

        active_sessions = sum(
            1 for ts in sessions.values() if now - ts < self.session_window
        )

        return {
            "user_id": user_id,
            "active_sessions": active_sessions,
            "max_concurrent": self.max_concurrent_per_user,
            "remaining": max(0, self.max_concurrent_per_user - active_sessions),
            "created_in_window": len(self.user_session_creations.get(user_id, [])),
            "remaining_creations": max(
                0,
                self.max_sessions_per_hour
                - len(self.user_session_creations.get(user_id, [])),
            ),
        }

    def _cleanup_user_window(self, user_id: str, *, now: float) -> None:
        """Drop stale creation timestamps outside the configured window."""
        creations = self.user_session_creations.get(user_id)
        if not creations:
            self.user_session_creations.pop(user_id, None)
            return

        self.user_session_creations[user_id] = [
            created_at
            for created_at in creations
            if now - created_at < self.session_window
        ]
        if not self.user_session_creations[user_id]:
            del self.user_session_creations[user_id]

    def _expire_user_sessions(
        self,
        sessions: MutableMapping[str, float],
        *,
        now: float,
    ) -> int:
        """Remove expired active sessions and return the number removed."""
        expired = [
            session_id
            for session_id, created_at in sessions.items()
            if now - created_at >= self.session_window
        ]
        for session_id in expired:
            del sessions[session_id]
        return len(expired)


# Global rate limiter instance
_rate_limiter: SessionRateLimiter | None = None


def get_session_rate_limiter() -> SessionRateLimiter:
    """Get global session rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SessionRateLimiter()
    return _rate_limiter


async def init_session_rate_limiter() -> None:
    """Initialize rate limiter on application startup"""
    limiter = get_session_rate_limiter()
    await limiter.start()
    logger.info("Session rate limiter initialized")


async def shutdown_session_rate_limiter() -> None:
    """Shutdown rate limiter on application shutdown"""
    global _rate_limiter
    if _rate_limiter:
        await _rate_limiter.stop()
        _rate_limiter = None
        logger.info("Session rate limiter shutdown")
