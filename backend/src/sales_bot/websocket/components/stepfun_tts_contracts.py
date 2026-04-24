"""Backend contract helpers for StepFun outbound TTS payloads.

The frontend still consumes the historical ``tts_chunk`` v1 shape.  V2 is a
strict superset that keeps those fields while adding explicit protocol and
ordering metadata for newer clients and contract fixtures.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, Literal

TTSChunkProtocolVersion = Literal["v1", "v2"]
DEFAULT_TTS_CHUNK_PROTOCOL_VERSION: TTSChunkProtocolVersion = "v1"
TTS_CHUNK_CONTRACT_NAME = "tts_chunk"
TTS_CHUNK_V1_CONTRACT = "tts_chunk.v1"
TTS_CHUNK_V2_CONTRACT = "tts_chunk.v2"


def normalize_tts_chunk_protocol_version(value: object) -> TTSChunkProtocolVersion:
    """Return a supported TTS chunk protocol version with safe fallback."""
    if str(value or "").strip().lower() == "v2":
        return "v2"
    return "v1"


def build_tts_chunk_event(
    *,
    stream_id: str,
    request_id: int,
    chunk_index: int,
    audio: str,
    duration_ms: int,
    is_final: bool,
    text: str | None = None,
    total_duration_ms: int | None = None,
    audio_format: str | None = None,
    sample_rate: int | None = None,
    playback_rate: float | None = None,
    knowledge_answer_diagnostics: dict[str, Any] | None = None,
    protocol_version: object = DEFAULT_TTS_CHUNK_PROTOCOL_VERSION,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build a backward-compatible outbound ``tts_chunk`` websocket event.

    V1 data is intentionally the existing flat payload.  V2 keeps every v1 field
    and adds explicit protocol/order/audio metadata so clients can opt into a
    stricter contract without breaking existing playback queues.
    """
    normalized_protocol = normalize_tts_chunk_protocol_version(protocol_version)
    normalized_audio_format = (audio_format or "").strip().lower()

    data: dict[str, Any] = {
        "chunk_index": chunk_index,
        "audio": audio,
        "duration_ms": duration_ms,
        "is_final": is_final,
    }
    if text is not None:
        data["text"] = text
    if total_duration_ms is not None:
        data["total_duration_ms"] = total_duration_ms
    if normalized_audio_format:
        data["audio_format"] = normalized_audio_format
    if sample_rate is not None:
        data["sample_rate"] = sample_rate
    if playback_rate is not None:
        data["playback_rate"] = playback_rate
    if knowledge_answer_diagnostics is not None:
        data["knowledge_answer_diagnostics"] = copy.deepcopy(
            knowledge_answer_diagnostics
        )

    if normalized_protocol == "v2":
        data["protocol_version"] = TTS_CHUNK_V2_CONTRACT
        data["contract"] = {
            "name": TTS_CHUNK_CONTRACT_NAME,
            "version": "v2",
            "backward_compatible_with": TTS_CHUNK_V1_CONTRACT,
        }
        data["ordering"] = {
            "chunk_index": chunk_index,
            "is_final": is_final,
            "stream_id": stream_id,
            "request_id": request_id,
        }
        data["audio_meta"] = {
            "format": normalized_audio_format or None,
            "sample_rate": sample_rate,
            "duration_ms": duration_ms,
            "total_duration_ms": total_duration_ms,
            "playback_rate": playback_rate,
        }

    event: dict[str, Any] = {
        "type": "tts_chunk",
        "timestamp": datetime.now(UTC).isoformat(),
        "stream_id": stream_id,
        "request_id": request_id,
        "data": data,
    }
    if trace_id:
        event["trace_id"] = trace_id
    return event
