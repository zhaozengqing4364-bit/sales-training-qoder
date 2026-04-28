"""
Circuit Breaker - Fault tolerance for ASR and other external services

Implements Constitution Principle IV: Fault tolerance and recovery
- Prevents cascade failures when services are unavailable
- Automatic recovery detection
- Configurable thresholds and timeouts

Requirements: P0-FIXES.md Issue #11
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import TypeVar

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes before closing from half-open
    timeout_seconds: int = 60  # Time before attempting recovery
    half_open_max_calls: int = 3  # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for service resilience

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Usage:
        cb = CircuitBreaker(failure_threshold=5, timeout_seconds=60)

        if cb.can_execute():
            try:
                result = await service.call()
                cb.record_success()
            except (RuntimeError, ConnectionError, TimeoutError, OSError):
                cb.record_failure()
        else:
            # Use fallback
            result = fallback()
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
        on_state_change: Callable[[CircuitState, CircuitState], None] | None = None,
    ):
        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
            half_open_max_calls=half_open_max_calls,
        )
        self.on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._lock = RLock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state"""
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)"""
        with self._lock:
            return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal)"""
        with self._lock:
            return self._state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)"""
        with self._lock:
            return self._state == CircuitState.HALF_OPEN

    def can_execute(self) -> bool:
        """
        Check if request should be allowed through

        Returns:
            True if request can proceed, False if should use fallback
        """
        with self._lock:
            self._total_calls += 1

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if time.time() - self._last_failure_time > self.config.timeout_seconds:
                    logger.info(
                        f"Circuit '{self.name}' timeout expired, transitioning to HALF_OPEN",
                        extra={
                            "circuit": self.name,
                            "from_state": "OPEN",
                            "to_state": "HALF_OPEN",
                        },
                    )
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._success_count = 0
                    self._half_open_calls = 1
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self._half_open_calls >= self.config.half_open_max_calls:
                    return False
                self._half_open_calls += 1
                return True

            return True

    def record_success(self):
        """Record a successful call"""
        with self._lock:
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(
                        f"Circuit '{self.name}' recovered, closing",
                        extra={
                            "circuit": self.name,
                            "from_state": "HALF_OPEN",
                            "to_state": "CLOSED",
                        },
                    )
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                if self._failure_count > 0:
                    self._failure_count = 0

    def record_failure(self):
        """Record a failed call"""
        with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"Circuit '{self.name}' failed in HALF_OPEN, reopening",
                    extra={
                        "circuit": self.name,
                        "from_state": "HALF_OPEN",
                        "to_state": "OPEN",
                    },
                )
                self._transition_to(CircuitState.OPEN)
                self._success_count = 0
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit '{self.name}' opened after {self._failure_count} failures",
                        extra={
                            "circuit": self.name,
                            "from_state": "CLOSED",
                            "to_state": "OPEN",
                            "failure_count": self._failure_count,
                        },
                    )
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to new state and trigger callback"""
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return
            self._state = new_state

            if self.on_state_change:
                try:
                    self.on_state_change(old_state, new_state)
                except (RuntimeError, ValueError, OSError) as e:
                    logger.error(f"Circuit state change callback error: {e}")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "failure_rate": (
                    self._total_failures / self._total_calls
                    if self._total_calls > 0
                    else 0
                ),
                "last_failure_time": self._last_failure_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                },
            }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = RLock()

    def get_or_create(
        self, name: str, failure_threshold: int = 5, timeout_seconds: int = 60, **kwargs
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    timeout_seconds=timeout_seconds,
                    **kwargs,
                )
            return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name"""
        with self._lock:
            return self._breakers.get(name)

    def get_all_stats(self) -> dict:
        """Get stats for all circuit breakers"""
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self._breakers.items()}


# Global registry
_circuit_registry: CircuitBreakerRegistry | None = None
_circuit_registry_lock = RLock()


def get_circuit_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry"""
    global _circuit_registry
    with _circuit_registry_lock:
        if _circuit_registry is None:
            _circuit_registry = CircuitBreakerRegistry()
        return _circuit_registry
