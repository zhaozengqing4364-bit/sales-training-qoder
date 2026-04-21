"""
v1-8: TTS Component — Extracted from EnhancedSalesHandler.

Handles all TTS response generation:
- Single-shot TTS (edge_tts)
- Streaming TTS (via tts_service with fallback)
- Browser TTS fallback
"""

import asyncio
import base64
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from common.audio.pcm_duration import (
    calculate_pcm_duration_ms,
    resolve_pcm_audio_format,
)
from common.monitoring.latency_tracker import LatencyTracker, get_latency_tracker
from common.monitoring.logger import get_logger
from common.websocket.base_handler import ConnectionManager

logger = get_logger(__name__)


def calculate_pcm_duration_ms(
    audio_data: bytes,
    *,
    sample_rate_hz: int | None = None,
    bytes_per_sample: int | None = None,
    channels: int | None = None,
) -> int:
    """Calculate PCM duration in milliseconds from audio byte metadata."""
    if not audio_data:
        return 0

    effective_sample_rate = sample_rate_hz or settings.TTS_DEFAULT_SAMPLE_RATE_HZ
    effective_bytes_per_sample = bytes_per_sample or settings.TTS_BYTES_PER_SAMPLE
    effective_channels = channels or settings.TTS_CHANNELS
    bytes_per_second = (
        effective_sample_rate * effective_bytes_per_sample * effective_channels
    )
    if bytes_per_second <= 0:
        logger.warning(
            "Invalid TTS PCM duration metadata; using zero duration",
            sample_rate_hz=effective_sample_rate,
            bytes_per_sample=effective_bytes_per_sample,
            channels=effective_channels,
        )
        return 0

    return round(len(audio_data) * 1000 / bytes_per_second)


class TTSComponent:
    """
    Manages TTS audio response generation and delivery.

    Supports two modes:
    - Single-shot: Generates full audio, sends as one message (tts_audio)
    - Streaming: Sends audio in chunks for lower latency (tts_chunk)
    """

    def __init__(self, tts_service: Any, persona_config: dict[str, Any]):
        self.tts_service = tts_service
        self.persona_config = persona_config

    def _get_tts_params(self) -> dict[str, str]:
        """Extract TTS parameters from persona config."""
        tts_config = self.persona_config.get("tts_config", {})
        return {
            "voice": tts_config.get("voice", "zh-CN-XiaoxiaoNeural"),
            "rate": tts_config.get("rate", "+0%"),
            "volume": tts_config.get("volume", "+0%"),
            "pitch": tts_config.get("pitch", "+0Hz"),
        }

    async def send_response(
        self,
        text: str,
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
        stream_id: str | None,
        request_id: int,
        is_interrupted_fn: Callable[[], bool] | None = None,
        current_stream_id_fn: Callable[[], str | None] | None = None,
    ) -> None:
        """
        Send TTS response.

        Priority:
        1) Stream via service (`tts_chunk`) for lower latency
        2) Fallback to aggregated single-shot (`tts_audio`)
        3) Browser TTS fallback
        """
        effective_stream_id = stream_id or f"tts-{request_id}"

        # Prefer service-level streaming path
        if hasattr(self.tts_service, "synthesize_streaming"):
            effective_is_interrupted_fn = is_interrupted_fn or (lambda: False)
            effective_current_stream_id_fn = (
                current_stream_id_fn or (lambda: effective_stream_id)
            )
            await self.send_response_streaming(
                text=text,
                request_id=request_id,
                stream_id=effective_stream_id,
                websocket=websocket,
                manager=manager,
                trace_id=trace_id,
                is_interrupted_fn=effective_is_interrupted_fn,
                current_stream_id_fn=effective_current_stream_id_fn,
            )
            return

        try:
            synthesize = getattr(self.tts_service, "synthesize", None)
            if not callable(synthesize):
                raise RuntimeError("TTS service does not support synthesize")

            result = await synthesize(text)
            if not result.is_success:
                logger.warning(f"TTS synthesize failed: {result.fallback}")
                await self.send_fallback(
                    text,
                    websocket,
                    manager,
                    trace_id,
                    effective_stream_id,
                    request_id,
                )
                return

            audio_stream = result.value
            binary_chunks: list[bytes] = []
            string_chunks: list[str] = []
            async for chunk in audio_stream:
                if isinstance(chunk, bytes):
                    binary_chunks.append(chunk)
                elif isinstance(chunk, str):
                    string_chunks.append(chunk)

            if binary_chunks:
                audio_data = b"".join(binary_chunks)
                audio_base64 = base64.b64encode(audio_data).decode("utf-8")
                sample_rate_hz, bytes_per_sample, channels = resolve_pcm_audio_format(
                    self.persona_config.get("tts_config")
                )
                duration_ms = (
                    calculate_pcm_duration_ms(
                        audio_data,
                        sample_rate_hz=sample_rate_hz,
                        bytes_per_sample=bytes_per_sample,
                        channels=channels,
                    )
                    if audio_data
                    else len(text) * 100
                )
            elif string_chunks:
                audio_base64 = "".join(string_chunks)
                duration_ms = len(text) * 100
            else:
                audio_base64 = ""
                duration_ms = len(text) * 100

            if audio_base64:
                await manager.send_json(
                    websocket,
                    {
                        "type": "tts_audio",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "trace_id": trace_id,
                        "stream_id": effective_stream_id,
                        "request_id": request_id,
                        "data": {
                            "text": text,
                            "audio": audio_base64,
                            "duration_ms": duration_ms,
                        },
                    },
                )
            else:
                logger.warning("TTS produced no audio chunks")
                await self.send_fallback(
                    text,
                    websocket,
                    manager,
                    trace_id,
                    effective_stream_id,
                    request_id,
                )

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"TTS error: {str(e)}", exc_info=True)
            await self.send_fallback(
                text,
                websocket,
                manager,
                trace_id,
                effective_stream_id,
                request_id,
            )

    async def send_response_streaming(
        self,
        text: str,
        request_id: int,
        stream_id: str,
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
        is_interrupted_fn: Callable[[], bool],
        current_stream_id_fn: Callable[[], str | None],
    ) -> None:
        """
        Send TTS audio response in streaming chunks.

        Requirements: 2.1, 2.4, 2.6 (Streaming TTS Playback)
        Critical Fix #2: Includes stream_id to prevent TTS message ordering issues.
        """
        logger.info(
            f"[TTS] Starting streaming for request {request_id}, stream {stream_id}, text: {text[:30]}..."
        )

        latency_tracker = get_latency_tracker()
        first_chunk_sent = False

        if trace_id:
            latency_tracker.record(trace_id, LatencyTracker.STAGE_TTS_START)

        async def on_chunk(audio_data: bytes, chunk_index: int, is_final: bool):
            """Callback to send each TTS chunk to the client."""
            nonlocal first_chunk_sent

            if is_interrupted_fn():
                logger.info(f"[TTS] Interrupted - canceling stream {stream_id}")
                raise asyncio.CancelledError("TTS interrupted by user")

            if stream_id != current_stream_id_fn():
                logger.warning(
                    f"[TTS] Stream ID mismatch: expected {current_stream_id_fn()}, got {stream_id}. Stopping."
                )
                raise asyncio.CancelledError("TTS stream expired")

            duration_ms = calculate_pcm_duration_ms(audio_data)
            audio_base64 = (
                base64.b64encode(audio_data).decode("utf-8") if audio_data else ""
            )

            message_data: dict[str, Any] = {
                "chunk_index": chunk_index,
                "audio": audio_base64,
                "duration_ms": duration_ms,
                "is_final": is_final,
            }

            if is_final:
                message_data["text"] = text

            await manager.send_json(
                websocket,
                {
                    "type": "tts_chunk",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "trace_id": trace_id,
                    "stream_id": stream_id,
                    "request_id": request_id,
                    "data": message_data,
                },
            )

            if not first_chunk_sent and audio_data:
                first_chunk_sent = True
                if trace_id:
                    latency_tracker.record(
                        trace_id,
                        LatencyTracker.STAGE_TTS_FIRST_CHUNK,
                        {"chunk_size": len(audio_data)},
                    )
                logger.debug(f"[TTS] Sent first chunk for stream {stream_id}")

        try:
            result = await self.tts_service.synthesize_streaming(text, on_chunk)

            if result.is_success:
                logger.info(f"[TTS] Streaming complete for stream {stream_id}")
            else:
                logger.warning(f"[TTS] Streaming failed: {result.fallback}")
                await self.send_fallback(
                    text, websocket, manager, trace_id, stream_id, request_id
                )

        except asyncio.CancelledError:
            logger.info(f"[TTS] Stream {stream_id} task was cancelled")
            raise
        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"[TTS] Streaming error: {str(e)}", exc_info=True)
            await self.send_fallback(
                text, websocket, manager, trace_id, stream_id, request_id
            )

    async def send_fallback(
        self,
        text: str,
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
        stream_id: str | None,
        request_id: int,
    ) -> None:
        """Send text-only TTS fallback for browser TTS."""
        await manager.send_json(
            websocket,
            {
                "type": "tts_audio",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "stream_id": stream_id,
                "request_id": request_id,
                "data": {
                    "text": text,
                    "audio": "",
                    "duration_ms": len(text) * 100,
                    "fallback": "browser_tts",
                },
            },
        )
