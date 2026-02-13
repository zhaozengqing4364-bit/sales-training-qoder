"""
Session State Service - WebSocket reconnection state persistence

Implements Constitution Principle IV: Fault tolerance and recovery
- Persists session state for reconnection scenarios
- Maintains data consistency across network interruptions
- Provides graceful degradation on reconnection failure

Requirements: Story 2.9 - WebSocket Exception Recovery
"""

import asyncio
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional
from datetime import datetime, timezone

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
    last_activity: float = field(default_factory=time.time)
    user_id: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionStateSnapshot":
        """Create from dictionary"""
        return cls(**data)


class SessionStateService:
    """
    Session state persistence service for WebSocket reconnection.

    Features:
    - Save session state snapshots in memory for fast access
    - Optional database persistence for durability
    - Automatic cleanup of expired states (30 minutes)
    - Thread-safe access with asyncio locks

    Configuration:
    - state_ttl: 1800 seconds (30 minutes)
    - cleanup_interval: 300 seconds (5 minutes)
    """

    def __init__(
        self,
        state_ttl: int = 1800,  # 30 minutes
        cleanup_interval: int = 300,  # 5 minutes
    ):
        self.states: Dict[str, SessionStateSnapshot] = {}
        self.state_ttl = state_ttl
        self.cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the background cleanup task"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session state service started")

    async def stop(self):
        """Stop the background cleanup task"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Session state service stopped")

    async def save_state(self, state: SessionStateSnapshot) -> Result[None]:
        """
        Save session state snapshot.

        Args:
            state: Session state snapshot to save

        Returns:
            Result[None]: Success or failure
        """
        try:
            async with self._lock:
                self.states[state.session_id] = state

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
        try:
            async with self._lock:
                state = self.states.get(session_id)

            if not state:
                logger.info(f"Session state not found: {session_id}")
                return Result.ok(None)

            # Check if state has expired
            now = time.time()
            age = now - state.last_activity
            if age > self.state_ttl:
                logger.info(f"Session state expired: {session_id}, age={age}s")
                await self.delete_state(session_id)
                return Result.ok(None)

            logger.info(f"Retrieved session state: {session_id}")
            return Result.ok(state)

        except Exception as e:
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
        try:
            async with self._lock:
                if session_id in self.states:
                    del self.states[session_id]

            logger.info(f"Deleted session state: {session_id}")
            return Result.ok(None)

        except Exception as e:
            logger.error(f"Failed to delete session state: {str(e)}")
            return Result.fail(f"[STATE_DELETE_FAILED] {str(e)}")

    async def get_recent_messages(
        self,
        db: AsyncSession,
        session_id: str,
        limit: int = 10
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
        """Background task to clean up expired states"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_states()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    async def _cleanup_expired_states(self):
        """Clean up states that have exceeded TTL"""
        now = time.time()
        expired_sessions = []

        async with self._lock:
            for session_id, state in list(self.states.items()):
                age = now - state.last_activity
                if age > self.state_ttl:
                    expired_sessions.append((session_id, age))

        for session_id, age in expired_sessions:
            await self.delete_state(session_id)
            logger.info(f"Cleaned up expired session state: {session_id}, age={int(age)}s")

    def get_stats(self) -> dict:
        """Get session state service statistics"""
        now = time.time()

        # Count states by age
        active_last_5min = sum(
            1 for s in self.states.values() if now - s.last_activity < 300
        )
        active_last_hour = sum(
            1 for s in self.states.values() if now - s.last_activity < 3600
        )

        return {
            "total_states": len(self.states),
            "active_last_5min": active_last_5min,
            "active_last_hour": active_last_hour,
            "state_ttl": self.state_ttl,
            "cleanup_interval": self.cleanup_interval,
        }


# Global session state service instance
_session_state_service: Optional[SessionStateService] = None


def get_session_state_service() -> SessionStateService:
    """Get or create global session state service instance"""
    global _session_state_service
    if _session_state_service is None:
        _session_state_service = SessionStateService()
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
