"""Unit tests for the ASR fallback provider-chain seam."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from common.audio.asr_base import ASRProvider
from common.audio.asr_with_fallback import (
    ASR_BROWSER_HANDOFF_CODE,
    ASRServiceWithFallback,
)
from common.error_handling.result import Result


class _SuccessfulProvider(ASRProvider):
    def __init__(self, text: str) -> None:
        self.text = text

    async def stream_transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
    ) -> AsyncIterator[Result[str]]:
        async for _ in audio_stream:
            yield Result.ok(self.text)

    async def transcribe_file(self, audio_file: str) -> Result[str]:
        return Result.ok(self.text)

    async def health_check(self) -> Result[bool]:
        return Result.ok(True)


@pytest.mark.asyncio
async def test_provider_chain_uses_explicit_fallback_provider_after_primary_failure():
    """A configured fallback provider can recover the request without browser handoff."""
    service = ASRServiceWithFallback(
        retry_count=1,
        request_timeout=0.2,
        circuit_name="asr-provider-chain-success",
        fallback_provider_factories=(
            ("local_streaming", lambda: _SuccessfulProvider("fallback transcript")),
        ),
    )
    service._transcribe_once = AsyncMock(return_value=Result.fail("[PRIMARY_DOWN]"))
    service._asr_service = SimpleNamespace(provider_name="alibaba")

    result = await service.transcribe(b"audio")

    assert result.is_success is True
    assert result.value == "fallback transcript"
    assert service.get_last_degraded_result() is None


@pytest.mark.asyncio
async def test_provider_chain_returns_structured_browser_handoff_when_no_provider_exists():
    """Without a real fallback provider, expose a degraded browser handoff payload."""
    service = ASRServiceWithFallback(
        retry_count=1,
        request_timeout=0.2,
        circuit_name="asr-provider-chain-degraded",
    )
    service._transcribe_once = AsyncMock(return_value=Result.fail("[PRIMARY_DOWN]"))
    service._asr_service = SimpleNamespace(provider_name="alibaba")

    result = await service.transcribe(b"audio")

    assert result.is_success is False
    assert result.fallback == ASR_BROWSER_HANDOFF_CODE

    degraded = service.get_last_degraded_result()
    assert degraded is not None
    assert degraded.as_payload() == {
        "status": "degraded",
        "code": ASR_BROWSER_HANDOFF_CODE,
        "reason": "[ASR_FALLBACK_PROVIDER_UNAVAILABLE]",
        "attempted_providers": [
            {
                "provider": "alibaba",
                "status": "failed",
                "code": "[PRIMARY_DOWN]",
            }
        ],
        "fallback_provider": "browser_web_speech",
        "message": "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。",
        "user_action": "请启用浏览器麦克风权限，或改用文本输入继续练习。",
        "retryable": True,
    }
