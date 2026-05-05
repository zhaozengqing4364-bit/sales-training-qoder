"""
Local qwen3-asr-flash ASR Provider
Constitution Principle I: Graceful degradation with fallback support

Use for:
- Development environments
- Offline scenarios
- API outages (automatic fallback)
"""

import asyncio
from collections.abc import AsyncIterator

import numpy as np
from funasr import AutoModel

from common.audio.asr_base import ASRProvider
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


class LocalASRProvider(ASRProvider):
    """
    Local ASR provider using funasr with qwen3-asr-flash model

    Startup time: 3-5 seconds (lazy load)
    Use for: Development, offline scenarios, API fallback
    """

    def __init__(self, device: str = "cuda"):
        self.device = device
        self.model = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load model only when needed"""
        if self._loaded:
            return

        try:
            logger.info(f"Loading local ASR model on {self.device}")
            self.model = AutoModel(
                model="qwen3-asr-flash",
                device=self.device,
                disable_pbar=True,
            )
            self._loaded = True
            logger.info("Local ASR model loaded successfully")
        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Failed to load local ASR: {str(e)}")
            # Fall back to CPU if CUDA fails
            if self.device == "cuda":
                logger.warning("Falling back to CPU for ASR")
                self.device = "cpu"
                self._ensure_loaded()

    async def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], sample_rate: int = 16000
    ) -> AsyncIterator[Result[str]]:
        """
        Stream transcribe using local model

        Args:
            audio_stream: Async iterator of audio bytes (PCM16, 16kHz)
            sample_rate: Audio sample rate

        Yields:
            Result with transcribed text or fallback instruction
        """
        self._ensure_loaded()

        try:
            audio_buffer = bytearray()

            async for chunk in audio_stream:
                audio_buffer.extend(chunk)

                # Process when buffer has enough data (200ms chunks)
                if len(audio_buffer) >= 6400:  # ~200ms at 16kHz
                    text = await self._process_chunk(bytes(audio_buffer), sample_rate)
                    if text:
                        yield Result.ok(text)
                    audio_buffer.clear()

            # Process remaining audio
            if audio_buffer:
                text = await self._process_chunk(bytes(audio_buffer), sample_rate)
                if text:
                    yield Result.ok(text)

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Local ASR streaming error: {str(e)}")
            yield Result.fail("[USE_BROWSER_ASR]")

    async def _process_chunk(self, audio_data: bytes, sample_rate: int) -> str | None:
        """Process a single audio chunk with local model"""
        try:
            # Convert bytes to numpy array
            audio_np = (
                np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            )

            # Run ASR (blocking, so run in thread pool)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.generate(
                    input=audio_np,
                    cache={},
                    language="auto",
                    use_itn=True,
                ),
            )

            if result and "text" in result:
                return result["text"]

            return None

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.warning(f"Chunk processing error: {str(e)}")
            return None

    async def transcribe_file(self, audio_file: str) -> Result[str]:
        """
        Transcribe audio file with local model

        Args:
            audio_file: Path to audio file

        Returns:
            Result with transcribed text or fallback
        """
        self._ensure_loaded()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: self.model.generate(input=audio_file)
            )

            if result and "text" in result:
                return Result.ok(result["text"])
            else:
                return Result.fail("[USE_BROWSER_ASR]")

        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Local file transcription error: {str(e)}")
            return Result.fail("[USE_BROWSER_ASR]")

    async def health_check(self) -> Result[bool]:
        """
        Check if local model is loaded

        Returns:
            Result indicating if model is available
        """
        try:
            self._ensure_loaded()
            return Result.ok(self._loaded)
        except (ConnectionError, OSError, RuntimeError, ValueError) as e:
            logger.error(f"Local ASR health check failed: {str(e)}")
            return Result.fail(False)
