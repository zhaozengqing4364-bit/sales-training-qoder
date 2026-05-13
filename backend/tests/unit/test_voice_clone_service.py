from __future__ import annotations

import pytest

from curriculum_practice.services.voice_clone import VoiceCloneService


class _MockResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


class _MockTransport:
    def __init__(self, response: _MockResponse | BaseException) -> None:
        self.response = response

    async def post(
        self,
        url: str,
        *,
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        timeout: float,
    ) -> _MockResponse:
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_should_return_voice_id_when_stepfun_voice_clone_succeeds() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(_MockResponse(200, {"voice_id": "custom_voice_cto"})),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is True
    assert result.voice_id == "custom_voice_cto"
    assert result.retryable is False
    assert result.fallback_voice is None
    assert result.reason_code is None


@pytest.mark.asyncio
async def test_should_return_retryable_failure_on_timeout() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(TimeoutError()),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is True
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_timeout"


@pytest.mark.asyncio
async def test_should_return_retryable_failure_on_5xx() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(_MockResponse(503, {"error": "busy"})),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is True
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_retryable_failure"


@pytest.mark.asyncio
async def test_should_return_non_retryable_failure_on_4xx() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(_MockResponse(400, {"error": "bad audio"})),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is False
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_rejected"


@pytest.mark.asyncio
async def test_should_fallback_to_default_voice_when_clone_unavailable() -> None:
    service = VoiceCloneService(
        transport=None,
        endpoint_url=None,
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is False
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_unavailable"


@pytest.mark.asyncio
async def test_should_return_retryable_failure_on_transport_error() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(ConnectionError("network down")),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is True
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_transport_error"


@pytest.mark.asyncio
async def test_should_return_retryable_failure_on_json_parse_error() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(_MockResponse(200, ValueError("bad json"))),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is True
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_bad_response"


@pytest.mark.asyncio
async def test_should_return_retryable_failure_on_non_dict_json() -> None:
    service = VoiceCloneService(
        transport=_MockTransport(_MockResponse(200, ["not", "a", "dict"])),
        endpoint_url="https://stepfun.example/voices",
        fallback_voice="default_voice",
    )

    result = await service.create_voice(
        voice_name="谨慎型 CTO",
        audio_bytes=b"voice-bytes",
        content_type="audio/wav",
    )

    assert result.ok is False
    assert result.retryable is True
    assert result.fallback_voice == "default_voice"
    assert result.reason_code == "voice_clone_bad_response"
