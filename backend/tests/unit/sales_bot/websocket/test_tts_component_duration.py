"""Tests for TTS duration calculation in sales websocket components."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sales_bot.websocket.components.tts_component import TTSComponent


class _FakeManager:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, websocket, message: dict) -> None:
        self.messages.append(message)


class _FakeTTSService:
    async def synthesize(self, text: str):
        async def audio_stream():
            yield b"\0" * 48_000

        return SimpleNamespace(is_success=True, value=audio_stream())


@pytest.mark.asyncio
async def test_tts_component_uses_configured_pcm_sample_rate_for_duration():
    """24kHz 16-bit mono PCM with 48k bytes should be one second."""
    manager = _FakeManager()
    component = TTSComponent(
        _FakeTTSService(),
        persona_config={
            "tts_config": {
                "sample_rate_hz": 24_000,
                "bytes_per_sample": 2,
                "channels": 1,
            }
        },
    )

    await component.send_response(
        text="hello",
        websocket=object(),
        manager=manager,
        trace_id="trace-1",
        stream_id="stream-1",
        request_id=1,
    )

    assert manager.messages[0]["type"] == "tts_audio"
    assert manager.messages[0]["data"]["duration_ms"] == 1000
