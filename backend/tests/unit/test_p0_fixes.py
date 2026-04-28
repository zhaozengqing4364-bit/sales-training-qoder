"""
Tests for P0 Fixes

Tests for:
- Circuit Breaker
- Session Manager
- Session Rate Limiter
- ASR with Fallback
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, Mock

import pytest


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

    def test_concurrent_failures_open_once(self):
        """Concurrent failure recording should produce one closed->open transition."""
        from common.resilience.circuit_breaker import CircuitBreaker, CircuitState

        transitions: list[tuple[CircuitState, CircuitState]] = []
        breaker = CircuitBreaker(
            name="concurrent_failure_circuit",
            failure_threshold=1,
            on_state_change=lambda old, new: transitions.append((old, new)),
        )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _: breaker.record_failure(), range(8)))

        stats = breaker.get_stats()
        assert breaker.is_open
        assert stats["total_failures"] == 8
        assert transitions == [(CircuitState.CLOSED, CircuitState.OPEN)]

    def test_concurrent_half_open_probe_limit_counts_transitioning_call(self):
        """The call that moves OPEN -> HALF_OPEN should consume one probe slot."""
        from common.resilience.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(
            name="half_open_probe_limit_circuit",
            failure_threshold=1,
            timeout_seconds=0,
            half_open_max_calls=2,
        )
        breaker.record_failure()

        with ThreadPoolExecutor(max_workers=8) as executor:
            allowed = list(executor.map(lambda _: breaker.can_execute(), range(8)))

        assert sum(allowed) == 2
        assert breaker.is_half_open

    def test_half_open_failure_resets_success_count_for_next_recovery_window(self):
        """A failed half-open probe should not carry stale successes into retry."""
        from common.resilience.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(
            name="half_open_success_reset_circuit",
            failure_threshold=1,
            success_threshold=2,
            timeout_seconds=0,
        )
        breaker.record_failure()
        assert breaker.can_execute()
        breaker.record_success()
        breaker.record_failure()

        assert breaker.can_execute()
        breaker.record_success()

        assert breaker.is_half_open
        assert breaker.get_stats()["success_count"] == 1


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
    async def test_reregistering_same_active_session_does_not_consume_creation_quota(
        self,
    ):
        """Should treat duplicate active-session registration as a heartbeat."""
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=10,
            max_sessions_per_hour=2,
            max_total_concurrent=10,
            session_window=3600,
            cleanup_interval=0.1,
        )

        await limiter.register_session("user_1", "session_1")
        await limiter.register_session("user_1", "session_1")

        assert limiter.current_total == 1
        assert limiter.get_user_stats("user_1")["created_in_window"] == 1
        assert (await limiter.check_limit("user_1")) == (True, "")

    @pytest.mark.asyncio
    async def test_session_creation_window_is_separate_from_active_sessions(self):
        """Should deny excessive sequential creations even after sessions end."""
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=10,
            max_sessions_per_hour=2,
            max_total_concurrent=10,
            session_window=3600,
            cleanup_interval=0.1,
        )

        assert (await limiter.check_limit("user_1")) == (True, "")
        await limiter.register_session("user_1", "session_1")
        await limiter.unregister_session("user_1", "session_1")
        assert limiter.current_total == 0

        assert (await limiter.check_limit("user_1")) == (True, "")
        await limiter.register_session("user_1", "session_2")
        await limiter.unregister_session("user_1", "session_2")
        assert limiter.get_user_stats("user_1")["active_sessions"] == 0
        assert limiter.get_user_stats("user_1")["created_in_window"] == 2

        allowed, reason = await limiter.check_limit("user_1")

        assert not allowed
        assert "每小时会话上限" in reason

    @pytest.mark.asyncio
    async def test_session_creation_window_expires_without_active_session(self):
        """Should allow a new creation after old creation timestamps expire."""
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=10,
            max_sessions_per_hour=1,
            max_total_concurrent=10,
            session_window=1,
            cleanup_interval=0.1,
        )
        limiter.user_session_creations["user_1"] = [time.time() - 2]

        allowed, reason = await limiter.check_limit("user_1")

        assert allowed
        assert reason == ""
        assert limiter.user_session_creations.get("user_1") is None

    def test_user_stats_drops_expired_creation_window_entries(self):
        """Should report creation quota from the cleaned current window."""
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=10,
            max_sessions_per_hour=1,
            max_total_concurrent=10,
            session_window=1,
            cleanup_interval=0.1,
        )
        limiter.user_session_creations["user_1"] = [time.time() - 2]

        stats = limiter.get_user_stats("user_1")

        assert stats["created_in_window"] == 0
        assert stats["remaining_creations"] == 1
        assert limiter.user_session_creations.get("user_1") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_removes_orphan_creation_windows(self):
        """Should clean stale creation counters even when no active sessions remain."""
        from common.rate_limit.session_limiter import SessionRateLimiter

        limiter = SessionRateLimiter(
            max_concurrent_per_user=10,
            max_sessions_per_hour=1,
            max_total_concurrent=10,
            session_window=1,
            cleanup_interval=0.1,
        )
        limiter.user_session_creations["user_1"] = [time.time() - 2]

        await limiter._cleanup_expired_sessions()

        assert limiter.user_session_creations.get("user_1") is None

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

    def test_jitter_backoff_helper_caps_delay(self):
        """Should keep jittered delay within max cap."""
        from common.resilience.backoff import compute_jitter_backoff_seconds

        delay = compute_jitter_backoff_seconds(
            attempt=4,
            base_delay_seconds=0.5,
            max_delay_seconds=1.0,
            jitter_ratio=0.2,
        )

        assert 0.0 <= delay <= 1.0

    @pytest.mark.asyncio
    async def test_transcribe_uses_shared_jitter_backoff_helper(self, monkeypatch):
        """ASR fallback retries should delegate delay calculation to shared helper."""
        import common.audio.asr_with_fallback as asr_module
        from common.audio.asr_with_fallback import ASRServiceWithFallback
        from common.error_handling.result import Result

        service = ASRServiceWithFallback(
            retry_count=2,
            base_retry_delay=0.1,
            request_timeout=0.2,
        )
        service._transcribe_once = AsyncMock(
            side_effect=[Result.fail("[ASR_STREAMING_ERROR]"), Result.fail("[ASR_STREAMING_ERROR]")]
        )

        helper_calls = []

        def _fake_backoff(**kwargs):
            helper_calls.append(kwargs)
            return 0.01

        sleep_mock = AsyncMock()
        monkeypatch.setattr(asr_module, "compute_jitter_backoff_seconds", _fake_backoff)
        monkeypatch.setattr(asr_module.asyncio, "sleep", sleep_mock)

        result = await service.transcribe(b"audio-bytes")

        assert result.is_success is False
        assert helper_calls == [
            {
                "attempt": 1,
                "base_delay_seconds": 0.1,
                "max_delay_seconds": 0.2,
            }
        ]
        sleep_mock.assert_awaited_once_with(0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
