"""
ASR Service with Circuit Breaker and Fallback Strategy

Implements Constitution Principle IV: Fault tolerance and recovery
- Circuit breaker prevents cascade failures
- Automatic retry with exponential backoff
- Graceful degradation to fallback options

Requirements: P0-FIXES.md Issue #11
"""

import asyncio
from typing import Optional

from common.audio.asr_service import ASRService, get_asr_service
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from common.resilience.backoff import compute_jitter_backoff_seconds
from common.resilience.circuit_breaker import get_circuit_registry, CircuitBreaker

logger = get_logger(__name__)


class ASRServiceWithFallback:
    """
    ASR Service wrapper with circuit breaker and retry logic

    Features:
    - Circuit breaker protection (5 failures => 60s cooldown)
    - Exponential backoff retry (2s, 4s, 8s)
    - Graceful error codes for frontend handling

    Error Codes:
    - [ASR_CIRCUIT_OPEN]: Circuit breaker is open, service temporarily unavailable
    - [ASR_TEMPORARILY_UNAVAILABLE]: All retries failed, service unavailable
    - [ASR_TIMEOUT]: Request timed out

    Usage:
        service = ASRServiceWithFallback()
        result = await service.transcribe(audio_bytes)

        if result.is_success:
            text = result.value
        else:
            error_code = result.fallback  # Handle error code
    """

    def __init__(
        self,
        retry_count: int = 3,
        base_retry_delay: float = 2.0,
        request_timeout: float = 5.0,
        circuit_name: str = "asr_service",
    ):
        self._asr_service: Optional[ASRService] = None
        self.retry_count = retry_count
        self.base_retry_delay = base_retry_delay
        self.request_timeout = request_timeout
        self.circuit_name = circuit_name

        # Get or create circuit breaker
        self._circuit = get_circuit_registry().get_or_create(
            name=circuit_name,
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=3,
        )

    def _get_asr_service(self) -> ASRService:
        """Lazy initialization of ASR service"""
        if self._asr_service is None:
            self._asr_service = get_asr_service()
        return self._asr_service

    async def transcribe(self, audio: bytes, sample_rate: int = 16000) -> Result[str]:
        """
        Transcribe audio with circuit breaker and retry logic

        Args:
            audio: Audio bytes to transcribe
            sample_rate: Audio sample rate (default 16000)

        Returns:
            Result with transcribed text or error code

        Error Codes:
            - [ASR_CIRCUIT_OPEN]: Circuit breaker open
            - [ASR_TEMPORARILY_UNAVAILABLE]: All retries exhausted
            - [ASR_TIMEOUT]: Request timeout
        """
        # Check circuit breaker
        if not self._circuit.can_execute():
            logger.warning(
                "ASR circuit breaker is open, rejecting request",
                extra={"circuit": self.circuit_name},
            )
            return Result.fail("[ASR_CIRCUIT_OPEN]")

        # Attempt with retries
        last_error = None

        for attempt in range(self.retry_count):
            try:
                result = await asyncio.wait_for(
                    self._transcribe_once(audio, sample_rate),
                    timeout=self.request_timeout,
                )

                if result.is_success:
                    # Record success and return
                    self._circuit.record_success()
                    return result
                else:
                    # Transcription failed but no exception
                    last_error = Exception(result.fallback or "Transcription failed")

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError("ASR request timeout")
                logger.warning(
                    f"ASR timeout on attempt {attempt + 1}/{self.retry_count}",
                    extra={"attempt": attempt + 1, "max_attempts": self.retry_count},
                )

            except (ConnectionError, OSError, RuntimeError) as e:
                last_error = e
                logger.error(
                    f"ASR error on attempt {attempt + 1}/{self.retry_count}: {e}",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self.retry_count,
                        "error": str(e),
                    },
                )

            # Record failure
            self._circuit.record_failure()

            # Check if circuit is now open
            if self._circuit.is_open:
                logger.warning(
                    "ASR circuit breaker opened after failure",
                    extra={"circuit": self.circuit_name, "attempt": attempt + 1},
                )
                break

            # Wait before retry (exponential backoff)
            if attempt < self.retry_count - 1:
                delay = compute_jitter_backoff_seconds(
                    attempt=attempt + 1,
                    base_delay_seconds=self.base_retry_delay,
                    max_delay_seconds=(
                        self.base_retry_delay * (2 ** max(self.retry_count - 1, 0))
                    ),
                )
                logger.info(
                    f"Retrying ASR in {delay}s",
                    extra={"delay": delay, "attempt": attempt + 1},
                )
                await asyncio.sleep(delay)

        # All retries failed
        logger.error(
            f"ASR failed after {self.retry_count} attempts",
            extra={
                "circuit": self.circuit_name,
                "circuit_state": self._circuit.state.value,
                "last_error": str(last_error),
            },
        )

        return Result.fail("[ASR_TEMPORARILY_UNAVAILABLE]")

    async def _transcribe_once(self, audio: bytes, sample_rate: int) -> Result[str]:
        """Single transcription attempt"""
        service = self._get_asr_service()

        # Create async generator for stream_transcribe
        async def audio_stream():
            yield audio

        # Try streaming transcribe first
        try:
            results = []
            async for result in service.stream_transcribe(audio_stream(), sample_rate):
                if result.is_success:
                    results.append(result.value)

            if results:
                return Result.ok(" ".join(results))
            else:
                return Result.fail("[ASR_NO_RESULT]")

        except (ConnectionError, OSError, RuntimeError, asyncio.TimeoutError) as e:
            logger.error(f"ASR streaming error: {e}")
            return Result.fail(f"[ASR_STREAMING_ERROR]")

    async def health_check(self) -> Result[bool]:
        """Check ASR service health"""
        try:
            service = self._get_asr_service()
            return await service.health_check()
        except (ConnectionError, OSError, RuntimeError) as e:
            logger.error(f"ASR health check failed: {e}")
            return Result.fail("[ASR_HEALTH_CHECK_FAILED]")

    def get_circuit_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return self._circuit.get_stats()


# Singleton instance
_asr_with_fallback: Optional[ASRServiceWithFallback] = None


def get_asr_with_fallback() -> ASRServiceWithFallback:
    """Get singleton ASR service with fallback"""
    global _asr_with_fallback
    if _asr_with_fallback is None:
        _asr_with_fallback = ASRServiceWithFallback()
    return _asr_with_fallback
