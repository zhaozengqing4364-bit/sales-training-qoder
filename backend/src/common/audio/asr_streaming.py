"""
Local Streaming ASR Provider using Paraformer-zh-streaming
Constitution Principle II: Real-Time Priority - <200ms streaming latency
Constitution Principle I: Graceful degradation with fallback support

Features:
- True streaming ASR (not pseudo-streaming)
- Native incremental output (~600ms display granularity)
- Model size: ~220MB (符合 <500MB 要求)
- Optimized for Chinese speech recognition

Use for:
- Real-time voice practice sessions
- Low-latency interactive scenarios
- Production environments requiring streaming
"""
import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import numpy as np
from funasr import AutoModel

from common.audio.asr_base import ASRProvider
from common.error_handling.result import Result
from common.monitoring.latency_tracker import get_latency_tracker
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class LocalStreamingASRProvider(ASRProvider):
    """
    Local streaming ASR provider using Paraformer-zh-streaming model.

    This provider supports true streaming ASR with incremental output,
    unlike pseudo-streaming which requires complete audio chunks.

    Performance characteristics:
    - First token latency: ~200ms
    - Display granularity: ~600ms
    - Lookahead: 300ms
    - Model size: ~220MB

    References:
    - FunASR: https://github.com/modelscope/FunASR
    - Paraformer-zh-streaming: https://huggingface.co/funasr/paraformer-zh-streaming
    """

    def __init__(
        self,
        device: str = "cuda",
        chunk_size_ms: int = 600,
        encoder_chunk_look_back: int = 4,
        decoder_chunk_look_back: int = 1,
    ):
        """
        Initialize streaming ASR provider.

        Args:
            device: Device to run model on ('cuda' or 'cpu')
            chunk_size_ms: Chunk size in milliseconds for streaming (default: 600ms)
            encoder_chunk_look_back: Encoder look-back chunks for context
            decoder_chunk_look_back: Decoder look-back chunks for context
        """
        self.device = device
        self.chunk_size_ms = chunk_size_ms
        self.encoder_chunk_look_back = encoder_chunk_look_back
        self.decoder_chunk_look_back = decoder_chunk_look_back

        self._model = None
        self._loaded = False

        # Streaming state
        self._cache: dict[str, Any] = {}

    def _ensure_loaded(self) -> None:
        """Lazy load model only when needed."""
        if self._loaded:
            return

        try:
            logger.info(
                f"Loading Paraformer-zh-streaming model on {self.device}",
                extra={"device": self.device, "chunk_size_ms": self.chunk_size_ms},
            )

            # Load streaming model with online configuration
            self._model = AutoModel(
                model="paraformer-zh-streaming",
                device=self.device,
                disable_pbar=True,
                # Streaming specific settings
                chunk_size=[0, 10, 5],  # [0, 10, 5] for 600ms chunks
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back,
            )

            self._loaded = True
            logger.info("Paraformer-zh-streaming model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load streaming ASR model: {str(e)}")
            # Fall back to CPU if CUDA fails
            if self.device == "cuda":
                logger.warning("Falling back to CPU for streaming ASR")
                self.device = "cpu"
                self._ensure_loaded()

    def _reset_cache(self) -> None:
        """Reset streaming cache for new session."""
        self._cache = {}

    async def stream_transcribe(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 16000,
    ) -> AsyncIterator[Result[str]]:
        """
        Stream transcribe audio chunks with true streaming output.

        This method processes audio incrementally and yields partial
        transcription results as they become available, enabling
        real-time display of recognized text.

        Args:
            audio_stream: Async iterator of audio bytes (PCM16, 16kHz mono)
            sample_rate: Audio sample rate (default: 16000)

        Yields:
            Result with transcribed text (partial or final)

        Performance:
        - First token: ~200ms after first chunk
        - Update interval: ~600ms
        - Target latency: <200ms (Constitution Principle II)
        """
        self._ensure_loaded()
        self._reset_cache()

        # Generate trace ID for latency tracking
        trace_id = f"asr_stream_{uuid.uuid4().hex[:8]}"
        tracker = get_latency_tracker()
        tracker.start_trace(trace_id)
        tracker.record(trace_id, "ASR_STREAM_START")

        # Calculate chunk size in bytes
        # PCM16: 2 bytes per sample, 16kHz
        bytes_per_ms = (sample_rate * 2) // 1000
        chunk_size_bytes = self.chunk_size_ms * bytes_per_ms

        audio_buffer = bytearray()
        chunk_count = 0
        first_result = True
        
        # 关键修复：手动累积所有识别结果
        # FunASR 流式模型每次返回的是当前 chunk 的局部识别，不是累积文本
        accumulated_texts: list[str] = []

        try:
            async for chunk in audio_stream:
                audio_buffer.extend(chunk)

                # Process when buffer has enough data
                while len(audio_buffer) >= chunk_size_bytes:
                    # Extract chunk
                    chunk_data = bytes(audio_buffer[:chunk_size_bytes])
                    audio_buffer = audio_buffer[chunk_size_bytes:]
                    chunk_count += 1

                    # Process chunk
                    result = await self._process_streaming_chunk(
                        chunk_data, sample_rate, is_final=False
                    )

                    if result:
                        if first_result:
                            tracker.record(
                                trace_id,
                                "ASR_FIRST_RESULT",
                                {"chunk_count": chunk_count},
                            )
                            first_result = False

                        # 累积当前 chunk 的识别结果
                        accumulated_texts.append(result)
                        total_text = "".join(accumulated_texts)
                        logger.debug(
                            f"ASR chunk result: '{result}' -> accumulated: '{total_text}' "
                            f"(chunk {chunk_count})"
                        )
                        yield Result.ok(total_text)

            # Process remaining audio as final chunk
            if audio_buffer:
                final_result = await self._process_streaming_chunk(
                    bytes(audio_buffer), sample_rate, is_final=True
                )
                if final_result:
                    accumulated_texts.append(final_result)
                    total_text = "".join(accumulated_texts)
                    logger.debug(f"ASR final chunk result: '{final_result}' -> total: '{total_text}'")
                    yield Result.ok(total_text)
            else:
                # Send final signal to get any remaining text
                final_result = await self._finalize_stream()
                if final_result:
                    accumulated_texts.append(final_result)
                    total_text = "".join(accumulated_texts)
                    logger.debug(f"ASR finalize result: '{final_result}' -> total: '{total_text}'")
                    yield Result.ok(total_text)

            total_text = "".join(accumulated_texts)
            tracker.record(
                trace_id,
                "ASR_STREAM_COMPLETE",
                {"total_chunks": chunk_count, "total_text_length": len(total_text)},
            )
            tracker.complete_trace(trace_id)

        except asyncio.CancelledError:
            logger.info(f"ASR stream cancelled: {trace_id}")
            tracker.record(trace_id, "ASR_STREAM_CANCELLED")
            raise

        except Exception as e:
            logger.error(f"Streaming ASR error: {str(e)}", extra={"trace_id": trace_id})
            tracker.record(trace_id, "ASR_STREAM_ERROR", {"error": str(e)})
            yield Result.fail("[USE_BROWSER_ASR]")

    async def _process_streaming_chunk(
        self,
        audio_data: bytes,
        sample_rate: int,
        is_final: bool = False,
    ) -> str | None:
        """
        Process a single audio chunk with streaming model.

        Args:
            audio_data: PCM16 audio bytes
            sample_rate: Audio sample rate
            is_final: Whether this is the final chunk

        Returns:
            Transcribed text or None if no output yet
        """
        try:
            # Convert bytes to numpy array (PCM16 -> float32)
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_np = audio_np / 32768.0  # Normalize to [-1, 1]

            # Run streaming inference in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._model.generate(
                    input=audio_np,
                    cache=self._cache,
                    is_final=is_final,
                    chunk_size=[0, 10, 5],
                    encoder_chunk_look_back=self.encoder_chunk_look_back,
                    decoder_chunk_look_back=self.decoder_chunk_look_back,
                ),
            )

            # Debug: Log raw FunASR result
            logger.info(f"FunASR raw result (is_final={is_final}): {result}")

            # Extract text from result
            if result and isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and "text" in result[0]:
                    text = result[0]["text"]
                    if text:  # Only return non-empty text
                        return text
                elif isinstance(result[0], str):
                    if result[0]:  # Only return non-empty text
                        return result[0]

            return None

        except Exception as e:
            logger.warning(f"Chunk processing error: {str(e)}")
            return None

    async def _finalize_stream(self) -> str | None:
        """
        Finalize streaming and get any remaining text.

        Returns:
            Final transcribed text or None
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._model.generate(
                    input=np.array([], dtype=np.float32),
                    cache=self._cache,
                    is_final=True,
                ),
            )

            if result and isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and "text" in result[0]:
                    return result[0]["text"]

            return None

        except Exception as e:
            logger.warning(f"Stream finalization error: {str(e)}")
            return None

    async def transcribe_file(self, audio_file: str) -> Result[str]:
        """
        Transcribe an audio file (non-streaming mode).

        For file transcription, uses batch processing for better accuracy.

        Args:
            audio_file: Path to audio file

        Returns:
            Result with transcribed text or fallback
        """
        self._ensure_loaded()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._model.generate(
                    input=audio_file,
                    batch_size_s=300,  # Process up to 300s at once
                ),
            )

            if result and isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict) and "text" in result[0]:
                    return Result.ok(result[0]["text"])
                elif isinstance(result[0], str):
                    return Result.ok(result[0])

            return Result.fail("[USE_BROWSER_ASR]")

        except Exception as e:
            logger.error(f"File transcription error: {str(e)}")
            return Result.fail("[USE_BROWSER_ASR]")

    async def health_check(self) -> Result[bool]:
        """
        Check if streaming model is loaded and healthy.

        Returns:
            Result indicating if model is available
        """
        try:
            self._ensure_loaded()
            return Result.ok(self._loaded and self._model is not None)
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return Result.fail(False)

    @property
    def is_streaming(self) -> bool:
        """Indicate this provider supports true streaming."""
        return True

    @property
    def model_name(self) -> str:
        """Return model name for logging."""
        return "paraformer-zh-streaming"
