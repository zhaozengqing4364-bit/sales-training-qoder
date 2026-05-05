"""
ASR Provider Abstract Interface
Constitution Principle II: Real-Time Priority - <200ms streaming latency
Constitution Principle I: Graceful degradation with Result types
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from common.error_handling.result import Result


class ASRProvider(ABC):
    """
    Abstract base class for ASR providers

    Enables switching between different ASR implementations:
    - Alibaba Cloud API (qwen3-asr-flash-realtime)
    - Local model (funasr)
    - Browser fallback (Web Speech API)
    """

    @abstractmethod
    def stream_transcribe(
        self, audio_stream: AsyncIterator[bytes], sample_rate: int = 16000
    ) -> AsyncIterator[Result[str]]:
        """
        Stream transcribe audio chunks

        Args:
            audio_stream: Async iterator of audio bytes (PCM16, 16kHz)
            sample_rate: Audio sample rate (8000 or 16000)

        Yields:
            Result with transcribed text or fallback instructions
        """
        pass

    @abstractmethod
    async def transcribe_file(self, audio_file: str) -> Result[str]:
        """
        Transcribe an audio file

        Args:
            audio_file: Path to audio file

        Returns:
            Result with transcribed text or fallback
        """
        pass

    @abstractmethod
    async def health_check(self) -> Result[bool]:
        """
        Check if provider is healthy

        Returns:
            Result indicating if provider is available
        """
        pass
