"""
Unit Tests for Voice Policy Monitor

Tests Story 4.7: 语音策略自动回滚监控告警集成
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sales_bot.services.voice_policy_monitor import (
    ServiceType,
    PolicyState,
    RollbackConfig,
    ServiceMetrics,
    RollbackEvent,
    VoicePolicyMonitor,
)


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def monitor_config():
    """Create default rollback configuration"""
    return RollbackConfig()


@pytest.fixture
def voice_policy_monitor(mock_db, monitor_config):
    """Create VoicePolicyMonitor instance"""
    return VoicePolicyMonitor(db=mock_db, config=monitor_config)


# Task 1.1 - Task 1: 监控指标收集服务

class TestServiceMetrics:
    """Test ServiceMetrics dataclass"""

    def test_initial_state(self):
        """Test that ServiceMetrics initializes correctly"""
        metrics = ServiceMetrics(service_type=ServiceType.ASR, provider="aliyun")

        assert metrics.service_type == ServiceType.ASR
        assert metrics.provider == "aliyun"
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0
        assert metrics.error_rate == 0.0
        assert metrics.consecutive_failures == 0

    def test_add_latency(self):
        """Test latency tracking"""
        metrics = ServiceMetrics(service_type=ServiceType.ASR, provider="aliyun")

        metrics.add_latency(150)
        assert len(metrics.latencies) == 1
        assert metrics.p50_latency == 150.0

        # Add more latencies
        metrics.add_latency(200)
        metrics.add_latency(250)

        # Check percentiles are calculated
        assert metrics.p50_latency == 200.0
        assert metrics.p95_latency == 250.0
        assert metrics.p99_latency == 250.0

    def test_record_success(self):
        """Test success recording"""
        metrics = ServiceMetrics(service_type=ServiceType.ASR, provider="aliyun")

        metrics.record_success()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0
        assert metrics.error_rate == 0.0
        assert metrics.consecutive_failures == 0

    def test_record_failure(self):
        """Test failure recording"""
        metrics = ServiceMetrics(service_type=ServiceType.ASR, provider="aliyun")

        metrics.record_failure()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.success_rate == 0.0
        assert metrics.error_rate == 1.0
        assert metrics.consecutive_failures == 1

        # Multiple failures should increment consecutive_failures
        metrics.record_failure()
        metrics.record_failure()
        assert metrics.consecutive_failures == 3

    def test_success_resets_consecutive_failures(self):
        """Test that success resets consecutive failures"""
        metrics = ServiceMetrics(service_type=ServiceType.ASR, provider="aliyun")

        metrics.record_failure()
        metrics.record_failure()
        assert metrics.consecutive_failures == 2

        metrics.record_success()
        assert metrics.consecutive_failures == 0


# Task 2: 实现阈值检测逻辑

class TestThresholdDetection:
    """Test threshold detection logic"""

    def test_p95_latency_threshold_triggers_rollback(self, voice_policy_monitor):
        """Test that P95 latency > 300ms triggers rollback"""
        monitor = voice_policy_monitor

        # Add latency samples - P95 > 300ms
        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")
        for i in range(15):
            metrics.add_latency(250)  # 15 samples with 250ms
        metrics.add_latency(400)  # 5 samples with 400ms (P95 = 400ms)

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert decision["should_rollback"] is True
        assert "P95 latency" in decision["reason"]
        assert "400.0" in decision["reason"]  # Contains P95 value

    def test_p95_latency_within_threshold_no_rollback(self, voice_policy_monitor):
        """Test that P95 latency <= 300ms does NOT trigger rollback"""
        monitor = voice_policy_monitor

        # Add latency samples - P95 <= 300ms
        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")
        for i in range(15):
            metrics.add_latency(200)  # 15 samples with 200ms
        metrics.add_latency(280)  # 5 samples with 280ms (P95 = 280ms)

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert decision["should_rollback"] is False
        assert "does not exceed threshold" in decision["reason"] or "within threshold" in decision["reason"]

    def test_success_rate_below_threshold_triggers_rollback(self, voice_policy_monitor):
        """Test that success rate < 90% triggers rollback"""
        monitor = voice_policy_monitor

        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")

        # 10 requests, 8 success -> 80% success rate
        for _ in range(8):
            metrics.record_success()
        for _ in range(2):
            metrics.record_failure()

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert decision["should_rollback"] is True
        assert "Success rate" in decision["reason"]
        assert "80%" in decision["reason"]

    def test_consecutive_failures_trigger_rollback(self, voice_policy_monitor):
        """Test that consecutive failures trigger rollback"""
        monitor = voice_policy_monitor

        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")

        # 5 consecutive failures
        for _ in range(5):
            metrics.record_failure()

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert decision["should_rollback"] is True
        assert "consecutive failures" in decision["reason"]

    def test_insufficient_samples_no_rollback(self, voice_policy_monitor):
        """Test that insufficient samples prevent rollback"""
        monitor = voice_policy_monitor

        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")

        # Only 5 samples (min_sample_size = 10)
        for _ in range(5):
            metrics.add_latency(500)  # High latency

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert decision["should_rollback"] is False
        assert "Insufficient samples" in decision["reason"]


# Task 3: 实现冷却期管理

class TestCooldownManagement:
    """Test cooldown period management"""

    def test_cooldown_after_rollback(self, voice_policy_monitor):
        """Test that rollback triggers cooldown period"""
        monitor = voice_policy_monitor

        # Simulate rollback
        monitor._last_rollback_time[ServiceType.ASR] = 0

        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)

        assert "In cooldown period" in decision["reason"]

    def test_recovery_cooldown_prevents_immediate_restore(self, voice_policy_monitor):
        """Test that recovery cooldown prevents immediate restore"""
        monitor = voice_policy_monitor

        # Set last rollback time
        monitor._last_rollback_time[ServiceType.ASR] = 0

        # Try to check recovery
        result = monitor.check_recovery(ServiceType.ASR)

        assert result.is_success
        assert result.value["should_restore"] is False
        assert "Still in recovery cooldown" in result.value["reason"]


# Task 4: 实现审计日志记录

class TestAuditLogging:
    """Test audit logging"""

    @pytest.mark.asyncio
    async def test_rollback_event_creation(self):
        """Test rollback event creation"""
        event = RollbackEvent(
            event_id="test-event-1",
            session_id="session-123",
            service_type=ServiceType.ASR,
            from_provider="aliyun",
            to_provider="edge",
            trigger_reason="P95 latency exceeded threshold",
            metrics_snapshot={
                "p95_latency_ms": 400.0,
                "success_rate": 0.85,
            },
        )

        assert event.event_id == "test-event-1"
        assert event.session_id == "session-123"
        assert event.service_type == ServiceType.ASR
        assert event.from_provider == "aliyun"
        assert event.to_provider == "edge"
        assert "P95 latency exceeded" in event.trigger_reason

    @pytest.mark.asyncio
    async def test_get_current_provider(self, voice_policy_monitor):
        """Test getting current provider"""
        provider = voice_policy_monitor.get_current_provider(ServiceType.ASR)

        assert provider in ["aliyun", "edge", "browser"]

    @pytest.mark.asyncio
    async def test_get_policy_state(self, voice_policy_monitor):
        """Test getting policy state"""
        state = voice_policy_monitor.get_policy_state(ServiceType.ASR)

        assert isinstance(state, PolicyState)


# Task 5: 测试 metrics 获取

class TestMetricsRetrieval:
    """Test metrics retrieval methods"""

    def test_get_metrics(self, voice_policy_monitor):
        """Test get_metrics method"""
        monitor = voice_policy_monitor

        # Record some metrics
        metrics = monitor._get_or_create_metrics(ServiceType.ASR, "aliyun")
        metrics.add_latency(200)
        metrics.record_success()

        result = monitor.get_metrics(ServiceType.ASR, "aliyun")

        assert "service_type" in result
        assert result["service_type"] == "asr"
        assert result["provider"] == "aliyun"
        assert "p50_latency_ms" in result
        assert "total_requests" in result

    def test_get_rollback_history_empty(self, voice_policy_monitor):
        """Test rollback history when empty"""
        monitor = voice_policy_monitor

        history = monitor.get_rollback_history()

        assert isinstance(history, list)
        assert len(history) == 0


# Task 6: 测试 circuit breaker 集成

class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with monitor"""

    def test_enable_circuit_breaker(self, voice_policy_monitor):
        """Test enabling circuit breaker"""
        monitor = voice_policy_monitor

        circuit = monitor.enable_circuit_breaker(ServiceType.ASR, "aliyun")

        assert circuit is not None
        assert circuit.name == "asr_aliyun"

    def test_get_circuit_breaker_state(self, voice_policy_monitor):
        """Test getting circuit breaker state"""
        monitor = voice_policy_monitor
        monitor.enable_circuit_breaker(ServiceType.ASR, "aliyun")

        state = monitor.get_circuit_breaker_state(ServiceType.ASR, "aliyun")

        assert "enabled" in state
        assert state["enabled"] is True
        assert "state" in state
