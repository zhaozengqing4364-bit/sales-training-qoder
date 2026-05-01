"""
Voice Policy Monitor - Automatic Rollback with Monitoring and Alerting

Implements Story 4.7: Voice Policy Automatic Rollback - Monitoring & Alerting Integration

Features:
- Real-time metrics collection (ASR/TTS latency, error rate, success rate)
- Threshold detection (P95 latency > 300ms triggers alert)
- Automatic rollback to backup strategy
- Cooldown period management (prevents frequent switching)
- Comprehensive audit logging

References:
- Requirements: Story 4.7 (Voice Policy Auto-Rollback)
- Constitution Principles:
  - I. NO ERROR POPUPS - Graceful degradation
  - IV. Fault tolerance and recovery
  - VII. Observability - Structured logging with trace_id

Dependencies:
- voice_runtime_policy.py: VoiceRuntimePolicyService
- latency_tracker.py: LatencyTracker
- common/resilience/circuit_breaker.py: CircuitBreaker
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import SystemLog
from common.error_handling.result import Result
from common.monitoring.latency_tracker import get_latency_tracker
from common.monitoring.logger import get_logger
from common.resilience.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


class ServiceType(str, Enum):
    """Types of voice services to monitor"""

    ASR = "asr"
    TTS = "tts"


class PolicyState(str, Enum):
    """State of voice policy"""

    ACTIVE = "active"  # Using primary policy
    ROLLED_BACK = "rolled_back"  # Using fallback policy
    COOLING_DOWN = "cooling_down"  # In cooldown after rollback


class AlertLevel(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ServiceMetrics:
    """Metrics for a single voice service"""

    service_type: ServiceType
    provider: str  # aliyun, edge, browser

    # Latency metrics (ms)
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0

    # Success metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 1.0

    # Error rate tracking
    error_rate: float = 0.0
    consecutive_failures: int = 0
    max_consecutive_failures: int = 5

    def add_latency(self, latency_ms: float) -> None:
        """Add a latency measurement"""
        self.latencies.append(latency_ms)
        self._recalculate_percentiles()

    def record_success(self) -> None:
        """Record a successful request"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self._recalculate_rates()

    def record_failure(self) -> None:
        """Record a failed request"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self._recalculate_rates()

    def _recalculate_percentiles(self) -> None:
        """Recalculate latency percentiles"""
        if not self.latencies:
            return

        sorted_latencies = sorted(self.latencies)
        count = len(sorted_latencies)

        def percentile(p: float) -> float:
            idx = int(p / 100 * count)
            return sorted_latencies[min(idx, count - 1)]

        self.p50_latency = percentile(50)
        self.p95_latency = percentile(95)
        self.p99_latency = percentile(99)

    def _recalculate_rates(self) -> None:
        """Recalculate success and error rates"""
        if self.total_requests > 0:
            self.success_rate = self.successful_requests / self.total_requests
            self.error_rate = self.failed_requests / self.total_requests


@dataclass
class RollbackConfig:
    """Configuration for automatic rollback behavior"""

    # Latency thresholds (ms)
    p95_latency_threshold: float = 300.0  # P95 > 300ms triggers rollback
    p99_latency_threshold: float = 500.0  # P99 > 500ms triggers immediate rollback

    # Success rate thresholds
    min_success_rate: float = 0.90  # Success rate < 90% triggers rollback

    # Cooldown period (seconds)
    rollback_cooldown_seconds: int = 300  # 5 minutes cooldown after rollback
    recovery_cooldown_seconds: int = 600  # 10 minutes cooldown before recovery

    # Sampling requirements
    min_sample_size: int = 10  # Minimum samples before making decisions

    # Circuit breaker settings
    circuit_failure_threshold: int = 5
    circuit_timeout_seconds: int = 60


@dataclass
class RollbackEvent:
    """Record of a rollback event for audit"""

    event_id: str
    session_id: str | None
    service_type: ServiceType
    from_provider: str
    to_provider: str
    trigger_reason: str
    metrics_snapshot: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class VoicePolicyMonitor:
    """
    Voice Policy Monitor - Automatic rollback with monitoring and alerting

    Monitors voice service health and automatically rolls back to fallback
    when performance degrades below thresholds.

    Key Responsibilities:
    1. Collect real-time metrics (latency, success rate, error rate)
    2. Detect threshold violations (P95 latency > 300ms)
    3. Trigger automatic rollback to backup strategy
    4. Manage cooldown periods to prevent oscillation
    5. Log comprehensive audit trail

    Usage:
        monitor = VoicePolicyMonitor(db_session, config)

        # Record metrics during operation
        monitor.record_asr_result(
            session_id="...",
            provider="aliyun",
            latency_ms=150,
            success=True
        )

        # Check if rollback is needed
        decision = monitor.evaluate_rollback_decision(ServiceType.ASR)
        if decision.should_rollback:
            await monitor.execute_rollback(
                ServiceType.ASR,
                "aliyun",
                "edge",
                decision.reason
            )
    """

    def __init__(
        self,
        db: AsyncSession,
        config: RollbackConfig | None = None,
        on_rollback: Callable[[RollbackEvent], None] | None = None,
    ):
        self.db = db
        self.config = config or RollbackConfig()
        self.on_rollback = on_rollback

        # Metrics storage
        self._metrics: dict[ServiceType, dict[str, ServiceMetrics]] = defaultdict(
            lambda: defaultdict(
                lambda: ServiceMetrics(service_type=ServiceType.ASR, provider="")
            )
        )

        # Policy state
        self._policy_state: dict[ServiceType, PolicyState] = {
            ServiceType.ASR: PolicyState.ACTIVE,
            ServiceType.TTS: PolicyState.ACTIVE,
        }

        # Rollback history
        self._rollback_history: list[RollbackEvent] = []
        self._last_rollback_time: dict[ServiceType, float] = {}

        # Current provider mapping
        self._current_provider: dict[ServiceType, str] = {
            ServiceType.ASR: "aliyun",  # Default primary
            ServiceType.TTS: "aliyun",  # Default primary
        }

        # Circuit breakers for each service/provider combination
        self._circuit_breakers: dict[tuple[ServiceType, str], CircuitBreaker] = {}

        # Latency tracker integration
        self._latency_tracker = get_latency_tracker()

        # Audit logging
        self._audit_enabled = True

    def record_asr_result(
        self,
        session_id: str | None,
        provider: str,
        latency_ms: float,
        success: bool,
        error_code: str | None = None,
    ) -> None:
        """
        Record ASR operation result

        Args:
            session_id: Practice session ID
            provider: ASR provider (aliyun, browser)
            latency_ms: Operation latency in milliseconds
            success: Whether operation succeeded
            error_code: Error code if failed
        """
        metrics = self._get_or_create_metrics(ServiceType.ASR, provider)

        if success:
            metrics.record_success()
            metrics.add_latency(latency_ms)
        else:
            metrics.record_failure()
            logger.warning(
                "ASR failure recorded",
                extra={
                    "provider": provider,
                    "session_id": session_id,
                    "error_code": error_code,
                    "consecutive_failures": metrics.consecutive_failures,
                },
            )

        # Check circuit breaker state
        circuit_key = (ServiceType.ASR, provider)
        if circuit_key in self._circuit_breakers:
            circuit = self._circuit_breakers[circuit_key]
            if success:
                circuit.record_success()
            else:
                circuit.record_failure()

        # Update latency tracker if available
        if self._latency_tracker and session_id:
            self._latency_tracker.record(
                session_id,
                "asr_complete" if success else "asr_failed",
                {"provider": provider, "latency_ms": latency_ms},
            )

    def record_tts_result(
        self,
        session_id: str | None,
        provider: str,
        latency_ms: float,
        success: bool,
        error_code: str | None = None,
    ) -> None:
        """
        Record TTS operation result

        Args:
            session_id: Practice session ID
            provider: TTS provider (aliyun, edge, browser)
            latency_ms: Operation latency in milliseconds
            success: Whether operation succeeded
            error_code: Error code if failed
        """
        metrics = self._get_or_create_metrics(ServiceType.TTS, provider)

        if success:
            metrics.record_success()
            metrics.add_latency(latency_ms)
        else:
            metrics.record_failure()
            logger.warning(
                "TTS failure recorded",
                extra={
                    "provider": provider,
                    "session_id": session_id,
                    "error_code": error_code,
                    "consecutive_failures": metrics.consecutive_failures,
                },
            )

        # Check circuit breaker state
        circuit_key = (ServiceType.TTS, provider)
        if circuit_key in self._circuit_breakers:
            circuit = self._circuit_breakers[circuit_key]
            if success:
                circuit.record_success()
            else:
                circuit.record_failure()

        # Update latency tracker if available
        if self._latency_tracker and session_id:
            self._latency_tracker.record(
                session_id,
                "tts_complete" if success else "tts_failed",
                {"provider": provider, "latency_ms": latency_ms},
            )

    def evaluate_rollback_decision(self, service_type: ServiceType) -> dict[str, Any]:
        """
        Evaluate if a rollback should be triggered based on metrics

        Args:
            service_type: ASR or TTS service

        Returns:
            Dict with:
                - should_rollback: bool
                - reason: str
                - current_provider: str
                - recommended_provider: str
                - metrics_snapshot: dict
        """
        current_provider = self._current_provider[service_type]
        metrics = self._get_or_create_metrics(service_type, current_provider)

        decision: dict[str, Any] = {
            "should_rollback": False,
            "reason": "",
            "current_provider": current_provider,
            "recommended_provider": self._get_fallback_provider(current_provider),
            "metrics_snapshot": {},
        }

        # Check cooldown period
        if self._is_in_cooldown(service_type):
            decision["reason"] = "In cooldown period, skipping evaluation"
            return decision

        # Consecutive failures can trigger rollback immediately
        if metrics.consecutive_failures >= metrics.max_consecutive_failures:
            decision["should_rollback"] = True
            decision["reason"] = (
                f"consecutive failures {metrics.consecutive_failures} "
                f"exceeds threshold {metrics.max_consecutive_failures}"
            )

        sample_count = max(metrics.total_requests, len(metrics.latencies))

        # Check if we have enough samples
        if (
            not decision["should_rollback"]
            and sample_count < self.config.min_sample_size
        ):
            decision["reason"] = (
                f"Insufficient samples: {sample_count} "
                f"(min {self.config.min_sample_size})"
            )
            return decision

        # Check P95 latency threshold
        if metrics.p95_latency > self.config.p95_latency_threshold:
            decision["should_rollback"] = True
            decision["reason"] = (
                f"P95 latency {metrics.p95_latency:.1f}ms "
                f"exceeds threshold {self.config.p95_latency_threshold}ms"
            )

        # Check P99 latency threshold (critical)
        if metrics.p99_latency > self.config.p99_latency_threshold:
            decision["should_rollback"] = True
            decision["reason"] = (
                f"P99 latency {metrics.p99_latency:.1f}ms "
                f"exceeds critical threshold {self.config.p99_latency_threshold}ms"
            )

        # Check success rate threshold
        if (
            not decision["should_rollback"]
            and metrics.success_rate < self.config.min_success_rate
        ):
            decision["should_rollback"] = True
            decision["reason"] = (
                f"Success rate {metrics.success_rate:.0%} "
                f"below threshold {self.config.min_success_rate:.0%}"
            )

        decision["metrics_snapshot"] = {
            "p50_latency_ms": round(metrics.p50_latency, 2),
            "p95_latency_ms": round(metrics.p95_latency, 2),
            "p99_latency_ms": round(metrics.p99_latency, 2),
            "success_rate": round(metrics.success_rate, 4),
            "error_rate": round(metrics.error_rate, 4),
            "total_requests": metrics.total_requests,
            "consecutive_failures": metrics.consecutive_failures,
        }

        if not decision["should_rollback"] and not decision["reason"]:
            decision["reason"] = "Metrics within threshold"

        return decision

    async def execute_rollback(
        self,
        service_type: ServiceType,
        from_provider: str,
        to_provider: str,
        reason: str,
        session_id: str | None = None,
    ) -> Result[RollbackEvent]:
        """
        Execute automatic rollback from one provider to another

        Args:
            service_type: ASR or TTS service
            from_provider: Current provider being rolled back from
            to_provider: Fallback provider to roll back to
            reason: Reason for the rollback
            session_id: Related session ID if available

        Returns:
            Result with RollbackEvent or error
        """
        event_id = str(uuid.uuid4())
        current_provider = self._current_provider[service_type]

        # Get current metrics for snapshot
        metrics = self._get_or_create_metrics(service_type, current_provider)
        metrics_snapshot = {
            "p50_latency_ms": round(metrics.p50_latency, 2),
            "p95_latency_ms": round(metrics.p95_latency, 2),
            "p99_latency_ms": round(metrics.p99_latency, 2),
            "success_rate": round(metrics.success_rate, 4),
            "error_rate": round(metrics.error_rate, 4),
            "total_requests": metrics.total_requests,
            "consecutive_failures": metrics.consecutive_failures,
        }

        # Create rollback event
        rollback_event = RollbackEvent(
            event_id=event_id,
            session_id=session_id,
            service_type=service_type,
            from_provider=current_provider,
            to_provider=to_provider,
            trigger_reason=reason,
            metrics_snapshot=metrics_snapshot,
        )

        # Update provider state
        self._current_provider[service_type] = to_provider
        self._policy_state[service_type] = PolicyState.ROLLED_BACK
        self._last_rollback_time[service_type] = time.time()

        # Store event
        self._rollback_history.append(rollback_event)
        if len(self._rollback_history) > 1000:  # Keep last 1000 events
            self._rollback_history.pop(0)

        # Log critical alert
        logger.error(
            f"[VOICE_ROLLBACK] {service_type.value.upper()}: "
            f"{from_provider} -> {to_provider}",
            extra={
                "event_id": event_id,
                "service_type": service_type.value,
                "from_provider": from_provider,
                "to_provider": to_provider,
                "reason": reason,
                "session_id": session_id,
                **metrics_snapshot,
            },
        )

        # Write audit log
        if self._audit_enabled:
            await self._write_audit_log(rollback_event)

        # Trigger callback if registered
        if self.on_rollback:
            try:
                self.on_rollback(rollback_event)
            except Exception as e:
                logger.error(f"Error in rollback callback: {e}")

        return Result.ok(rollback_event)

    def check_recovery(self, service_type: ServiceType) -> Result[dict[str, Any]]:
        """
        Check if primary provider has recovered and can be restored

        Args:
            service_type: ASR or TTS service

        Returns:
            Result with recovery decision
        """
        # Check if cooldown period has passed
        if self._is_in_recovery_cooldown(service_type):
            return Result.ok(
                {"should_restore": False, "reason": "Still in recovery cooldown period"}
            )

        if self._policy_state[service_type] == PolicyState.ACTIVE:
            return Result.ok(
                {"should_restore": False, "reason": "Already using primary provider"}
            )

        current_provider = self._current_provider[service_type]
        primary_provider = self._get_primary_provider(service_type)

        # Check primary provider metrics
        metrics = self._get_or_create_metrics(service_type, primary_provider)

        if metrics.total_requests < self.config.min_sample_size:
            return Result.ok(
                {
                    "should_restore": False,
                    "reason": f"Insufficient samples for primary: {metrics.total_requests}",
                }
            )

        # Check if primary has recovered
        recovered = (
            metrics.p95_latency <= self.config.p95_latency_threshold
            and metrics.success_rate >= self.config.min_success_rate
            and metrics.consecutive_failures == 0
        )

        if recovered:
            # Check circuit breaker state
            circuit_key = (service_type, primary_provider)
            if circuit_key in self._circuit_breakers:
                circuit = self._circuit_breakers[circuit_key]
                if circuit.is_open:
                    return Result.ok(
                        {
                            "should_restore": False,
                            "reason": "Primary provider circuit is still open",
                        }
                    )

            # Restore primary
            self._current_provider[service_type] = primary_provider
            self._policy_state[service_type] = PolicyState.ACTIVE

            logger.info(
                f"[VOICE_RECOVERY] {service_type.value.upper()}: "
                f"{current_provider} -> {primary_provider}",
                extra={
                    "service_type": service_type.value,
                    "from_provider": current_provider,
                    "to_provider": primary_provider,
                    "metrics": {
                        "p95_latency_ms": round(metrics.p95_latency, 2),
                        "success_rate": round(metrics.success_rate, 4),
                    },
                },
            )

            return Result.ok(
                {
                    "should_restore": True,
                    "reason": "Primary provider metrics within thresholds",
                    "metrics_snapshot": {
                        "p95_latency_ms": round(metrics.p95_latency, 2),
                        "success_rate": round(metrics.success_rate, 4),
                    },
                }
            )

        return Result.ok(
            {
                "should_restore": False,
                "reason": "Primary provider metrics not yet recovered",
                "metrics_snapshot": {
                    "p95_latency_ms": round(metrics.p95_latency, 2),
                    "success_rate": round(metrics.success_rate, 4),
                    "p95_threshold": self.config.p95_latency_threshold,
                    "success_rate_threshold": self.config.min_success_rate,
                },
            }
        )

    def get_current_provider(self, service_type: ServiceType) -> str:
        """Get current provider for a service"""
        return self._current_provider[service_type]

    def get_policy_state(self, service_type: ServiceType) -> PolicyState:
        """Get current policy state for a service"""
        return self._policy_state[service_type]

    def get_metrics(self, service_type: ServiceType, provider: str) -> dict[str, Any]:
        """Get current metrics for a service provider"""
        metrics = self._get_or_create_metrics(service_type, provider)
        return {
            "service_type": service_type.value,
            "provider": provider,
            "p50_latency_ms": round(metrics.p50_latency, 2),
            "p95_latency_ms": round(metrics.p95_latency, 2),
            "p99_latency_ms": round(metrics.p99_latency, 2),
            "success_rate": round(metrics.success_rate, 4),
            "error_rate": round(metrics.error_rate, 4),
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "consecutive_failures": metrics.consecutive_failures,
        }

    def get_rollback_history(
        self, service_type: ServiceType | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get rollback event history"""
        events = self._rollback_history

        if service_type is not None:
            events = [e for e in events if e.service_type == service_type]

        events = events[-limit:]

        return [
            {
                "event_id": e.event_id,
                "service_type": e.service_type.value,
                "from_provider": e.from_provider,
                "to_provider": e.to_provider,
                "trigger_reason": e.trigger_reason,
                "timestamp": e.timestamp.isoformat(),
                "metrics_snapshot": e.metrics_snapshot,
            }
            for e in reversed(events)
        ]

    def enable_circuit_breaker(
        self, service_type: ServiceType, provider: str
    ) -> CircuitBreaker:
        """Enable circuit breaker for a service provider"""
        circuit_key = (service_type, provider)
        if circuit_key not in self._circuit_breakers:
            self._circuit_breakers[circuit_key] = CircuitBreaker(
                name=f"{service_type.value}_{provider}",
                failure_threshold=self.config.circuit_failure_threshold,
                timeout_seconds=self.config.circuit_timeout_seconds,
            )
        return self._circuit_breakers[circuit_key]

    def get_circuit_breaker_state(
        self, service_type: ServiceType, provider: str
    ) -> dict[str, Any]:
        """Get circuit breaker state for a service provider"""
        circuit_key = (service_type, provider)
        if circuit_key not in self._circuit_breakers:
            return {"enabled": False}

        circuit = self._circuit_breakers[circuit_key]
        return {
            "enabled": True,
            "state": circuit.state.value,
            "is_open": circuit.is_open,
            "stats": circuit.get_stats(),
        }

    def reset_metrics(self, service_type: ServiceType | None = None) -> None:
        """Reset metrics for monitoring (for testing or manual intervention)"""
        if service_type is None:
            self._metrics.clear()
        else:
            self._metrics[service_type].clear()

        logger.info(
            "Metrics reset",
            extra={"service_type": service_type.value if service_type else "all"},
        )

    def _get_or_create_metrics(
        self, service_type: ServiceType, provider: str
    ) -> ServiceMetrics:
        """Get or create metrics for a service provider"""
        if service_type not in self._metrics:
            self._metrics[service_type] = {}

        if provider not in self._metrics[service_type]:
            self._metrics[service_type][provider] = ServiceMetrics(
                service_type=service_type, provider=provider
            )

        return self._metrics[service_type][provider]

    def _get_fallback_provider(self, current_provider: str) -> str:
        """Get fallback provider for rollback"""
        fallback_map = {
            "aliyun": "edge",
            "edge": "browser",
            "browser": "edge",  # Last resort is browser, but edge preferred
        }
        return fallback_map.get(current_provider, "edge")

    def _get_primary_provider(self, service_type: ServiceType) -> str:
        """Get primary provider for a service type"""
        return "aliyun"  # Aliyun is the preferred primary

    def _is_in_cooldown(self, service_type: ServiceType) -> bool:
        """Check if service is in rollback cooldown period"""
        if service_type not in self._last_rollback_time:
            return False

        last_rollback = self._last_rollback_time[service_type]
        if last_rollback <= 0:
            return True

        elapsed = time.time() - last_rollback
        return elapsed < self.config.rollback_cooldown_seconds

    def _is_in_recovery_cooldown(self, service_type: ServiceType) -> bool:
        """Check if service is in recovery cooldown period"""
        if service_type not in self._last_rollback_time:
            return False

        last_rollback = self._last_rollback_time[service_type]
        if last_rollback <= 0:
            return True

        elapsed = time.time() - last_rollback
        return elapsed < self.config.recovery_cooldown_seconds

    async def _write_audit_log(self, event: RollbackEvent) -> None:
        """Write rollback event to audit log"""
        try:
            log_entry = SystemLog(
                action="voice_policy_rollback",
                user_id=None,  # System-initiated
                user_identifier="system",
                status="warning",  # Rollback is a warning event
                details=str(
                    {
                        "event_id": event.event_id,
                        "service_type": event.service_type.value,
                        "from_provider": event.from_provider,
                        "to_provider": event.to_provider,
                        "trigger_reason": event.trigger_reason,
                        "metrics_snapshot": event.metrics_snapshot,
                        "timestamp": event.timestamp.isoformat(),
                    }
                ),
            )
            self.db.add(log_entry)
            await self.db.flush()

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Global instances
_voice_policy_monitors: dict[int, VoicePolicyMonitor] = {}


def get_voice_policy_monitor(
    db: AsyncSession,
    config: RollbackConfig | None = None,
    on_rollback: Callable[[RollbackEvent], None] | None = None,
) -> VoicePolicyMonitor:
    """Get or create voice policy monitor for database session"""
    # Use id() as a simple hash for the session
    session_id = id(db)
    if session_id not in _voice_policy_monitors:
        _voice_policy_monitors[session_id] = VoicePolicyMonitor(
            db=db,
            config=config,
            on_rollback=on_rollback,
        )
    return _voice_policy_monitors[session_id]


def clear_voice_policy_monitor(db: AsyncSession) -> None:
    """Clear voice policy monitor for database session (cleanup)"""
    session_id = id(db)
    _voice_policy_monitors.pop(session_id, None)
