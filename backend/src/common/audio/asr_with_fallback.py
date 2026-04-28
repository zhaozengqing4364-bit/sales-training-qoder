"""
ASR Service with Circuit Breaker and Fallback Strategy

Implements Constitution Principle IV: Fault tolerance and recovery
- Circuit breaker prevents cascade failures
- Automatic retry with exponential backoff
- Graceful degradation to fallback options

Requirements: P0-FIXES.md Issue #11
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from common.audio.asr_base import ASRProvider
from common.audio.asr_service import ASRService, get_asr_service
from common.config import settings
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from common.resilience.backoff import compute_jitter_backoff_seconds
from common.resilience.circuit_breaker import get_circuit_registry

logger = get_logger(__name__)

ASR_BROWSER_HANDOFF_CODE = "[ASR_BROWSER_HANDOFF_REQUIRED]"
ASR_FALLBACK_PROVIDER_UNAVAILABLE_CODE = "[ASR_FALLBACK_PROVIDER_UNAVAILABLE]"

ASRProviderAttemptStatus = Literal["succeeded", "failed"]
ASRProviderFactory = Callable[[], ASRProvider]


@dataclass(frozen=True)
class ASRProviderAttempt:
    """Outcome for a single provider in the ASR provider chain."""

    provider: str
    status: ASRProviderAttemptStatus
    code: str | None = None

    def as_payload(self) -> dict[str, str]:
        payload = {"provider": self.provider, "status": self.status}
        if self.code:
            payload["code"] = self.code
        return payload


@dataclass(frozen=True)
class ASRDegradedResult:
    """Structured terminal ASR degradation for browser handoff."""

    code: str
    reason: str
    attempted_providers: tuple[ASRProviderAttempt, ...]
    fallback_provider: str = "browser_web_speech"
    user_message: str = "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。"
    user_action: str = "请启用浏览器麦克风权限，或改用文本输入继续练习。"
    retryable: bool = True

    def as_payload(self) -> dict[str, Any]:
        return {
            "status": "degraded",
            "code": self.code,
            "reason": self.reason,
            "attempted_providers": [
                attempt.as_payload() for attempt in self.attempted_providers
            ],
            "fallback_provider": self.fallback_provider,
            "message": self.user_message,
            "user_action": self.user_action,
            "retryable": self.retryable,
        }


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
    - [ASR_BROWSER_HANDOFF_REQUIRED]: No server-side fallback provider completed
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
        fallback_provider_factories: Sequence[
            tuple[str, ASRProviderFactory]
        ] | None = None,
        browser_fallback_provider: str | None = None,
        browser_handoff_message: str | None = None,
        browser_handoff_action: str | None = None,
    ):
        self._asr_service: ASRService | None = None
        self.retry_count = retry_count
        self.base_retry_delay = base_retry_delay
        self.request_timeout = request_timeout
        self.circuit_name = circuit_name
        self._fallback_provider_factories = tuple(fallback_provider_factories or ())
        self._browser_fallback_provider = (
            browser_fallback_provider or settings.ASR_BROWSER_FALLBACK_PROVIDER
        )
        self._browser_handoff_message = (
            browser_handoff_message or settings.ASR_BROWSER_HANDOFF_MESSAGE
        )
        self._browser_handoff_action = (
            browser_handoff_action or settings.ASR_BROWSER_HANDOFF_ACTION
        )
        self._provider_attempts: list[ASRProviderAttempt] = []
        self._last_degraded_result: ASRDegradedResult | None = None

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
            - [ASR_BROWSER_HANDOFF_REQUIRED]: Client/browser ASR handoff required
            - [ASR_TIMEOUT]: Request timeout
        """
        self._provider_attempts = []
        self._last_degraded_result = None

        # Check circuit breaker
        if not self._circuit.can_execute():
            logger.warning(
                "ASR circuit breaker is open, rejecting request",
                extra={"circuit": self.circuit_name},
            )
            self._last_degraded_result = self._build_degraded_result(
                reason="[ASR_CIRCUIT_OPEN]",
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

            except TimeoutError:
                last_error = TimeoutError("ASR request timeout")
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

        primary_code = (
            str(last_error) if last_error is not None else "[ASR_TEMPORARILY_UNAVAILABLE]"
        )
        self._provider_attempts.append(
            ASRProviderAttempt(
                provider=self._get_primary_provider_name(),
                status="failed",
                code=primary_code,
            )
        )

        fallback_result = await self._try_fallback_provider_chain(audio, sample_rate)
        if fallback_result.is_success:
            self._circuit.record_success()
            return fallback_result

        reason = fallback_result.fallback or ASR_FALLBACK_PROVIDER_UNAVAILABLE_CODE
        self._last_degraded_result = self._build_degraded_result(reason=reason)
        logger.warning(
            "ASR provider chain degraded to browser handoff",
            extra=self._last_degraded_result.as_payload(),
        )
        return Result.fail(ASR_BROWSER_HANDOFF_CODE)

    def _get_primary_provider_name(self) -> str:
        """Return the selected primary provider name without leaking config details."""
        try:
            return self._get_asr_service().provider_name
        except (ConnectionError, OSError, RuntimeError, ValueError):
            return "primary"

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

        except (TimeoutError, ConnectionError, OSError, RuntimeError) as e:
            logger.error(f"ASR streaming error: {e}")
            return Result.fail("[ASR_STREAMING_ERROR]")

    async def _try_fallback_provider_chain(
        self,
        audio: bytes,
        sample_rate: int,
    ) -> Result[str]:
        """Try explicitly configured server-side fallback providers in order."""
        if not self._fallback_provider_factories:
            return Result.fail(ASR_FALLBACK_PROVIDER_UNAVAILABLE_CODE)

        for provider_name, provider_factory in self._fallback_provider_factories:
            try:
                provider = provider_factory()
                result = await asyncio.wait_for(
                    self._transcribe_with_provider(provider, audio, sample_rate),
                    timeout=self.request_timeout,
                )
            except TimeoutError:
                self._provider_attempts.append(
                    ASRProviderAttempt(
                        provider=provider_name,
                        status="failed",
                        code="[ASR_TIMEOUT]",
                    )
                )
                continue
            except (ConnectionError, OSError, RuntimeError, ValueError) as e:
                self._provider_attempts.append(
                    ASRProviderAttempt(
                        provider=provider_name,
                        status="failed",
                        code=str(e),
                    )
                )
                continue

            if result.is_success:
                self._provider_attempts.append(
                    ASRProviderAttempt(provider=provider_name, status="succeeded")
                )
                return result

            self._provider_attempts.append(
                ASRProviderAttempt(
                    provider=provider_name,
                    status="failed",
                    code=result.fallback or "[ASR_FALLBACK_FAILED]",
                )
            )

        return Result.fail(ASR_FALLBACK_PROVIDER_UNAVAILABLE_CODE)

    async def _transcribe_with_provider(
        self,
        provider: ASRProvider,
        audio: bytes,
        sample_rate: int,
    ) -> Result[str]:
        """Transcribe one audio buffer through a concrete ASR provider."""

        async def audio_stream():
            yield audio

        results = []
        async for result in provider.stream_transcribe(audio_stream(), sample_rate):
            if result.is_success:
                results.append(result.value)

        if results:
            return Result.ok(" ".join(results))
        return Result.fail("[ASR_NO_RESULT]")

    def _build_degraded_result(self, *, reason: str) -> ASRDegradedResult:
        """Build the explicit terminal degradation payload for clients/support."""
        return ASRDegradedResult(
            code=ASR_BROWSER_HANDOFF_CODE,
            reason=reason,
            attempted_providers=tuple(self._provider_attempts),
            fallback_provider=self._browser_fallback_provider,
            user_message=self._browser_handoff_message,
            user_action=self._browser_handoff_action,
        )

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

    def get_last_degraded_result(self) -> ASRDegradedResult | None:
        """Return the most recent structured ASR degradation, if any."""
        return self._last_degraded_result


# Singleton instance
_asr_with_fallback: ASRServiceWithFallback | None = None


def get_asr_with_fallback() -> ASRServiceWithFallback:
    """Get singleton ASR service with fallback"""
    global _asr_with_fallback
    if _asr_with_fallback is None:
        _asr_with_fallback = ASRServiceWithFallback()
    return _asr_with_fallback
