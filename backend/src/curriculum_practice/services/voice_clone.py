from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VoiceCloneResult:
    ok: bool
    voice_id: str | None
    retryable: bool
    fallback_voice: str | None
    reason_code: str | None


class VoiceCloneResponse(Protocol):
    status_code: int

    def json(self) -> Mapping[str, object]: ...


class VoiceCloneTransport(Protocol):
    async def post(
        self,
        url: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        timeout: float,
    ) -> VoiceCloneResponse: ...


class VoiceCloneService:
    def __init__(
        self,
        *,
        transport: VoiceCloneTransport | None,
        endpoint_url: str | None,
        fallback_voice: str | None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport
        self._endpoint_url = endpoint_url
        self._fallback_voice = fallback_voice
        self._timeout_seconds = timeout_seconds

    async def create_voice(
        self,
        *,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
    ) -> VoiceCloneResult:
        if self._transport is None or not self._endpoint_url:
            return self._failure("voice_clone_unavailable", retryable=False)
        try:
            response = await self._transport.post(
                self._endpoint_url,
                files={"audio": ("voice_sample", audio_bytes, content_type)},
                data={"voice_name": voice_name},
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return self._failure("voice_clone_timeout", retryable=True)
        except Exception:
            return self._failure("voice_clone_transport_error", retryable=True)

        if 200 <= response.status_code < 300:
            try:
                payload = response.json()
            except (TypeError, ValueError):
                return self._failure("voice_clone_bad_response", retryable=True)
            if not isinstance(payload, Mapping):
                return self._failure("voice_clone_bad_response", retryable=True)
            voice_id = payload.get("voice_id")
            if isinstance(voice_id, str) and voice_id:
                return VoiceCloneResult(
                    ok=True,
                    voice_id=voice_id,
                    retryable=False,
                    fallback_voice=None,
                    reason_code=None,
                )
            return self._failure("voice_clone_missing_voice_id", retryable=False)
        if response.status_code >= 500:
            return self._failure("voice_clone_retryable_failure", retryable=True)
        return self._failure("voice_clone_rejected", retryable=False)

    def _failure(self, reason_code: str, *, retryable: bool) -> VoiceCloneResult:
        return VoiceCloneResult(
            ok=False,
            voice_id=None,
            retryable=retryable,
            fallback_voice=self._fallback_voice,
            reason_code=reason_code,
        )
