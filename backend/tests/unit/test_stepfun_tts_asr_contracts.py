"""Contract tests for StepFun realtime TTS chunks and ASR fallback status."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sales_bot.websocket.components.stepfun_asr_fallback import (
    ASR_FALLBACK_REQUIRED_ERROR_CODE,
    build_asr_fallback_status_event,
    extract_asr_error_reason,
)
from sales_bot.websocket.components.stepfun_tts_contracts import (
    TTS_CHUNK_V2_CONTRACT,
    build_tts_chunk_event,
)
from sales_bot.websocket.stepfun_realtime_handler import (
    RealtimeResponseState,
    StepFunRealtimeHandler,
)


def test_tts_chunk_v1_contract_keeps_legacy_flat_payload_shape():
    event = build_tts_chunk_event(
        stream_id="stream-1",
        request_id=7,
        chunk_index=0,
        audio="AAE=",
        duration_ms=120,
        is_final=False,
        audio_format="PCM16",
        sample_rate=24000,
        playback_rate=1.25,
        protocol_version="v1",
    )

    assert event["type"] == "tts_chunk"
    assert event["stream_id"] == "stream-1"
    assert event["request_id"] == 7
    assert event["data"] == {
        "chunk_index": 0,
        "audio": "AAE=",
        "duration_ms": 120,
        "is_final": False,
        "audio_format": "pcm16",
        "sample_rate": 24000,
        "playback_rate": 1.25,
    }


def test_tts_chunk_v2_contract_is_v1_compatible_superset():
    event = build_tts_chunk_event(
        stream_id="stream-2",
        request_id=8,
        chunk_index=3,
        audio="",
        duration_ms=0,
        is_final=True,
        text="最终回复",
        total_duration_ms=960,
        audio_format="pcm16",
        sample_rate=24000,
        playback_rate=1.0,
        protocol_version="v2",
    )

    data = event["data"]
    assert data["chunk_index"] == 3
    assert data["is_final"] is True
    assert data["text"] == "最终回复"
    assert data["protocol_version"] == TTS_CHUNK_V2_CONTRACT
    assert data["contract"] == {
        "name": "tts_chunk",
        "version": "v2",
        "backward_compatible_with": "tts_chunk.v1",
    }
    assert data["ordering"] == {
        "chunk_index": 3,
        "is_final": True,
        "stream_id": "stream-2",
        "request_id": 8,
    }
    assert data["audio_meta"] == {
        "format": "pcm16",
        "sample_rate": 24000,
        "duration_ms": 0,
        "total_duration_ms": 960,
        "playback_rate": 1.0,
    }


@pytest.mark.asyncio
async def test_stepfun_audio_delta_can_emit_v2_chunk_contract():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_status = AsyncMock()
    handler._active_response = RealtimeResponseState(
        request_id=9,
        stream_id="stream-v2",
    )
    handler._stepfun_output_audio_format = "pcm16"
    handler._stepfun_output_sample_rate = 24000
    handler._stepfun_playback_rate = 1.1
    handler._tts_chunk_protocol_version = "v2"

    await handler._forward_audio_delta_chunk("AAECAw==")

    payload = handler.manager.send_json.await_args.args[1]
    data = payload["data"]
    assert payload["type"] == "tts_chunk"
    assert data["chunk_index"] == 0
    assert data["protocol_version"] == TTS_CHUNK_V2_CONTRACT
    assert data["ordering"]["stream_id"] == "stream-v2"
    assert data["audio_meta"]["sample_rate"] == 24000


def test_asr_fallback_reason_only_matches_transcription_errors():
    assert (
        extract_asr_error_reason(
            {
                "type": "error",
                "error": {
                    "code": "input_audio_transcription_unavailable",
                    "message": "ASR provider unavailable",
                },
            }
        )
        == "input_audio_transcription_unavailable"
    )
    assert extract_asr_error_reason({"type": "error", "message": "rate limit"}) is None


def test_asr_fallback_status_event_uses_stable_status_envelope():
    event = build_asr_fallback_status_event(
        reason="input_audio_transcription_unavailable",
        session_status="in_progress",
        ai_state="listening",
        turn_count=2,
        trace_id="trace-asr",
    )

    assert event["type"] == "status"
    assert event["trace_id"] == "trace-asr"
    assert event["data"]["session_status"] == "in_progress"
    assert event["data"]["asr_status"] == {
        "state": "fallback_required",
        "reason": "input_audio_transcription_unavailable",
        "primary_provider": "stepfun_realtime",
        "fallback_provider": "browser_web_speech",
        "fallback_code": "[ASR_BROWSER_HANDOFF_REQUIRED]",
        "message": "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。",
        "user_action": "请启用浏览器麦克风权限，或改用文本输入继续练习。",
        "retryable": True,
    }


@pytest.mark.asyncio
async def test_stepfun_upstream_asr_error_emits_status_then_fallback_error():
    handler = StepFunRealtimeHandler()
    handler.websocket = MagicMock()
    handler.manager = MagicMock()
    handler.manager.send_json = AsyncMock()
    handler._send_error = AsyncMock()
    handler.session_status = "in_progress"
    handler.ai_state = "listening"
    handler.turn_count = 4

    await handler._handle_upstream_error(
        {
            "type": "error",
            "error": {
                "code": "input_audio_transcription_unavailable",
                "message": "ASR provider unavailable",
            },
        }
    )

    status_payload = handler.manager.send_json.await_args.args[1]
    assert status_payload["type"] == "status"
    assert status_payload["data"]["asr_status"]["fallback_provider"] == (
        "browser_web_speech"
    )
    handler._send_error.assert_awaited_once_with(
        ASR_FALLBACK_REQUIRED_ERROR_CODE,
        "语音识别服务暂时不可用，请切换到浏览器语音识别或文本输入。",
    )
