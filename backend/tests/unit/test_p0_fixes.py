"""
Tests for P0 Fixes

Tests for:
- Circuit Breaker
- Session Manager
- Session Rate Limiter
- ASR with Fallback
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock


class TestCircuitBreaker:
    """Test Circuit Breaker functionality"""

    @pytest.fixture
    def circuit_breaker(self):
        from common.resilience.circuit_breaker import CircuitBreaker

        return CircuitBreaker(
            name="test_circuit",
            failure_threshold=3,
            timeout_seconds=1,
            success_threshold=2,
        )

    def test_initial_state_closed(self, circuit_breaker):
        """Circuit should start in CLOSED state"""
        assert circuit_breaker.is_closed
        assert not circuit_breaker.is_open
        assert not circuit_breaker.is_half_open

    def test_can_execute_when_closed(self, circuit_breaker):
        """Should allow execution when closed"""
        assert circuit_breaker.can_execute()

    def test_opens_after_failures(self, circuit_breaker):
        """Circuit should open after threshold failures"""
        for _ in range(3):
            circuit_breaker.record_failure()

        assert circuit_breaker.is_open
        assert not circuit_breaker.can_execute()

    def test_records_success(self, circuit_breaker):
        """Should record success and reset failure count"""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()

        assert circuit_breaker.is_closed

    def test_get_stats(self, circuit_breaker):
        """Should return circuit statistics"""
        stats = circuit_breaker.get_stats()

        assert "name" in stats
        assert "state" in stats
        assert stats["name"] == "test_circuit"


class TestSessionManager:
    """Test Session Manager functionality"""

    @pytest.fixture
    async def session_manager(self):
        from common.websocket.session_manager import SessionManager

        manager = SessionManager(
            timeout_seconds=1, heartbeat_interval=0.1, cleanup_interval=0.1
        )
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_register_session(self, session_manager):
        """Should register a session"""
        mock_handler = Mock()
        mock_handler.send_message = AsyncMock()

        await session_manager.register_session(
            "test_session", mock_handler, user_id="test_user"
        )

        assert "test_session" in session_manager.sessions
        assert session_manager.sessions["test_session"].user_id == "test_user"

    @pytest.mark.asyncio
    async def test_update_activity(self, session_manager):
        """Should update session activity"""
        mock_handler = Mock()
        mock_handler.send_message = AsyncMock()

        await session_manager.register_session("test_session", mock_handler)
        old_time = session_manager.sessions["test_session"].last_activity

        await asyncio.sleep(0.01)
        await session_manager.update_activity("test_session")

        new_time = session_manager.sessions["test_session"].last_activity
        assert new_time > old_time

    @pytest.mark.asyncio
    async def test_unregister_session(self, session_manager):
        """Should unregister a session"""
        mock_handler = Mock()
        mock_handler.send_message = AsyncMock()

        await session_manager.register_session("test_session", mock_handler)
        await session_manager.unregister_session("test_session")

        assert "test_session" not in session_manager.sessions

    @pytest.mark.asyncio
    async def test_get_stats_contains_metrics(self, session_manager):
        """Should expose manager metrics for observability"""
        mock_handler = Mock()
        mock_handler.send_message = AsyncMock()
        mock_handler.close = AsyncMock()

        await session_manager.register_session("stats_session", mock_handler)
        stats = session_manager.get_stats()

        assert "metrics" in stats
        assert stats["metrics"]["registered_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_timeout_updates_metrics(self, session_manager):
        """Should track timeout closures and unregister counts"""
        mock_handler = Mock()
        mock_handler.send_message = AsyncMock()
        mock_handler.close = AsyncMock()

        await session_manager.register_session("timeout_session", mock_handler)
        session_manager.sessions["timeout_session"].last_activity -= 5

        await session_manager._cleanup_expired_sessions()
        stats = session_manager.get_stats()

        assert "timeout_session" not in session_manager.sessions
        assert stats["metrics"]["timeout_closures"] >= 1
        assert stats["metrics"]["unregistered_sessions"] >= 1


class TestSessionRateLimiter:
    """Test Session Rate Limiter functionality"""

    @pytest.fixture
    async def rate_limiter(self):
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=2,
            max_sessions_per_hour=5,
            max_total_concurrent=10,
            cleanup_interval=0.1,
        )
        await limiter.start()
        yield limiter
        await limiter.stop()

    @pytest.mark.asyncio
    async def test_check_limit_allowed(self, rate_limiter):
        """Should allow session creation when under limit"""
        allowed, reason = await rate_limiter.check_limit("user_1")

        assert allowed
        assert reason == ""

    @pytest.mark.asyncio
    async def test_check_limit_denied_concurrent(self, rate_limiter):
        """Should deny when user has too many concurrent sessions"""
        # Register max sessions
        await rate_limiter.register_session("user_1", "session_1")
        await rate_limiter.register_session("user_1", "session_2")

        allowed, reason = await rate_limiter.check_limit("user_1")

        assert not allowed
        assert "已有" in reason

    @pytest.mark.asyncio
    async def test_register_and_unregister(self, rate_limiter):
        """Should register and unregister sessions"""
        await rate_limiter.register_session("user_1", "session_1")
        assert rate_limiter.current_total == 1

        await rate_limiter.unregister_session("user_1", "session_1")
        assert rate_limiter.current_total == 0

    @pytest.mark.asyncio
    async def test_global_limit(self, rate_limiter):
        """Should enforce global concurrent limit"""
        # Fill up global limit
        for i in range(10):
            await rate_limiter.register_session(f"user_{i}", f"session_{i}")

        allowed, reason = await rate_limiter.check_limit("new_user")

        assert not allowed
        assert "系统繁忙" in reason

    def test_get_stats(self, rate_limiter):
        """Should return rate limiter statistics"""
        stats = rate_limiter.get_stats()

        assert "total_sessions" in stats
        assert "max_total_concurrent" in stats
        assert stats["max_concurrent_per_user"] == 2


class TestASRWithFallback:
    """Test ASR Service with Fallback"""

    @pytest.fixture
    def asr_service(self):
        from common.audio.asr_with_fallback import ASRServiceWithFallback

        return ASRServiceWithFallback(
            retry_count=2, base_retry_delay=0.1, request_timeout=0.5
        )

    def test_initialization(self, asr_service):
        """Should initialize with correct config"""
        assert asr_service.retry_count == 2
        assert asr_service.base_retry_delay == 0.1
        assert asr_service.request_timeout == 0.5

    def test_circuit_breaker_attached(self, asr_service):
        """Should have circuit breaker attached"""
        assert asr_service._circuit is not None
        assert asr_service._circuit.name == "asr_service"

    def test_get_circuit_stats(self, asr_service):
        """Should return circuit stats"""
        stats = asr_service.get_circuit_stats()

        assert "name" in stats
        assert "state" in stats
        assert stats["name"] == "asr_service"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
