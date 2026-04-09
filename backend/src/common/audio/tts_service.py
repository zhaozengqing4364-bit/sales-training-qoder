"""
TTS Service - Edge-TTS wrapper with ConfigManager integration

Refactored to load configuration from ConfigManager with environment variable fallback.
Supports Edge-TTS (free) and potentially other providers.

References:
- Requirements: R6.4 (TTS Service loads from ConfigManager)
- Design: model-config-management/design.md
- Constitution Principle I: Fallback to browser TTS on failure
- Voice Practice Optimization: Streaming TTS (Requirements 2.1, 2.6)
"""
from collections.abc import AsyncIterator, Callable, Awaitable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

try:
    import edge_tts as _edge_tts
    _EDGE_TTS_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - depends on optional runtime deps
    _edge_tts = SimpleNamespace(Communicate=None)
    _EDGE_TTS_IMPORT_ERROR = exc

edge_tts = _edge_tts

from common.ai.config_manager import get_config_manager
from common.ai.models import ModelConfig, ModelType
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _get_edge_tts_module() -> Any:
    """Return the edge_tts module or raise the captured import error lazily."""
    if getattr(edge_tts, "Communicate", None) is None and _EDGE_TTS_IMPORT_ERROR is not None:
        raise RuntimeError("edge_tts is unavailable") from _EDGE_TTS_IMPORT_ERROR
    return edge_tts


@dataclass
class TTSChunk:
    """
    Represents a single TTS audio chunk for streaming.
    
    Attributes:
        chunk_index: Sequential index of this chunk (0-based)
        audio: Raw audio bytes (MP3 format)
        duration_ms: Estimated duration of this chunk in milliseconds
        is_final: Whether this is the last chunk
        text: Full text (only included in final chunk)
        total_duration_ms: Total duration (only included in final chunk)
    """
    chunk_index: int
    audio: bytes
    duration_ms: int
    is_final: bool = False
    text: str | None = None
    total_duration_ms: int | None = None


class TTSService:
    """
    Text-to-speech service with ConfigManager integration.

    Features:
    - Loads configuration from ConfigManager (database)
    - Falls back to environment variables if no database config
    - Uses Edge-TTS (free Microsoft Edge browser API)
    - Falls back to browser TTS on failure

    Requirements: R6.4 (TTS Service loads from ConfigManager)
    """

    def __init__(self, config: ModelConfig | None = None):
        """
        Initialize TTS service.

        Args:
            config: Optional ModelConfig. If not provided, uses default from ConfigManager.
        """
        self._config_manager = get_config_manager()
        self._config = config
        self._effective_config: dict[str, Any] | None = None

        # Default voice parameters
        self.voice = "zh-CN-XiaoxiaoNeural"
        self.rate = "+0%"
        self.volume = "+0%"
        self.pitch = "+0Hz"

        # Initialize configuration
        self._init_config()

    def _init_config(self) -> None:
        """
        Initialize configuration from ConfigManager or environment.

        Priority:
        1. Explicit config passed to constructor
        2. Default config from ConfigManager (database)
        3. Environment variable fallback
        """
        if self._config:
            # Use explicit config
            self._effective_config = {
                "provider": self._config.provider,
                "model_name": self._config.model_name,
                "extra_config": self._config.extra_config or {},
            }
        else:
            # Get from ConfigManager (database or env fallback)
            self._effective_config = self._config_manager.get_effective_config(ModelType.TTS)

        if self._effective_config:
            # Apply configuration
            self.voice = self._effective_config.get("model_name", "zh-CN-XiaoxiaoNeural")
            extra_config = self._effective_config.get("extra_config", {})
            self.rate = extra_config.get("rate", "+0%")
            self.volume = extra_config.get("volume", "+0%")
            self.pitch = extra_config.get("pitch", "+0Hz")

            logger.info(f"TTS service initialized with voice: {self.voice}")
        else:
            logger.info("TTS service using default configuration")

    @property
    def is_configured(self) -> bool:
        """Check if TTS service is properly configured"""
        return True  # Edge-TTS doesn't require API key

    @property
    def provider(self) -> str:
        """Get current provider name"""
        if self._effective_config:
            return self._effective_config.get("provider", "local")
        return "local"

    def reload_config(self, config: ModelConfig | None = None) -> None:
        """
        Reload configuration and reinitialize.

        Args:
            config: Optional new config. If not provided, reloads from ConfigManager.
        """
        self._config = config
        self._init_config()

    async def synthesize(
        self,
        text: str,
        voice: str | None = None
    ) -> Result[AsyncIterator[bytes]]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Voice to use (overrides default)

        Returns:
            Result with audio stream iterator or fallback message
        """
        try:
            voice = voice or self.voice
            communicate = _get_edge_tts_module().Communicate(
                text,
                voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )

            async def audio_stream():
                """Async generator for audio chunks"""
                try:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            yield chunk["data"]
                except (ConnectionError, OSError, RuntimeError) as e:
                    logger.error(f"Audio streaming error: {str(e)}")
                    raise

            return Result.ok(audio_stream())

        except Exception as e:
            logger.error(f"TTS synthesis error: {str(e)}")
            # Fallback: signal frontend to use browser TTS
            return Result.fail("[USE_BROWSER_TTS]")

    async def synthesize_streaming(
        self,
        text: str,
        on_chunk: Callable[[TTSChunk], Awaitable[None]],
        voice: str | None = None,
    ) -> Result[int]:
        """
        Synthesize text to speech with streaming output.
        
        Yields audio chunks immediately as they are generated by edge-tts,
        enabling low-latency playback on the frontend.
        
        Args:
            text: Text to synthesize
            on_chunk: Async callback for each audio chunk (TTSChunk)
            voice: Voice to use (overrides default)
            
        Returns:
            Result containing total duration in ms, or fallback message
            
        Requirements: 2.1, 2.6 (Streaming TTS Playback)
        """
        try:
            voice = voice or self.voice
            communicate = _get_edge_tts_module().Communicate(
                text,
                voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )

            chunk_index = 0
            total_duration_ms = 0
            
            # Estimate duration per byte (MP3 at ~128kbps = ~16 bytes/ms)
            # This is approximate; actual duration depends on bitrate
            BYTES_PER_MS = 16

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data = chunk["data"]
                    # Estimate duration based on audio size
                    chunk_duration_ms = max(1, len(audio_data) // BYTES_PER_MS)
                    total_duration_ms += chunk_duration_ms
                    
                    tts_chunk = TTSChunk(
                        chunk_index=chunk_index,
                        audio=audio_data,
                        duration_ms=chunk_duration_ms,
                        is_final=False,
                    )
                    
                    await on_chunk(tts_chunk)
                    chunk_index += 1
                    
                    logger.debug(
                        f"TTS chunk {chunk_index}: {len(audio_data)} bytes, "
                        f"~{chunk_duration_ms}ms"
                    )

            # Send final chunk marker with metadata
            if chunk_index > 0:
                final_chunk = TTSChunk(
                    chunk_index=chunk_index,
                    audio=b"",  # Empty audio for final marker
                    duration_ms=0,
                    is_final=True,
                    text=text,
                    total_duration_ms=total_duration_ms,
                )
                await on_chunk(final_chunk)
                
            logger.info(
                f"TTS streaming complete: {chunk_index} chunks, "
                f"total ~{total_duration_ms}ms"
            )
            
            return Result.ok(total_duration_ms)

        except Exception as e:
            logger.error(f"TTS streaming error: {str(e)}")
            # Fallback: signal frontend to use browser TTS
            return Result.fail("[USE_BROWSER_TTS]")

    async def synthesize_to_file(
        self,
        text: str,
        output_file: str,
        voice: str | None = None
    ) -> Result[bool]:
        """
        Synthesize speech to file.

        Args:
            text: Text to synthesize
            output_file: Output audio file path
            voice: Voice to use

        Returns:
            Result indicating success or failure
        """
        try:
            voice = voice or self.voice
            communicate = _get_edge_tts_module().Communicate(
                text,
                voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )

            await communicate.save(output_file)
            logger.info(f"TTS saved to {output_file}")
            return Result.ok(True)

        except Exception as e:
            logger.error(f"TTS file save error: {str(e)}")
            return Result.fail("[USE_BROWSER_TTS]")

    def set_voice_parameters(
        self,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None
    ) -> None:
        """Set voice synthesis parameters"""
        if rate:
            self.rate = rate
        if volume:
            self.volume = volume
        if pitch:
            self.pitch = pitch


# Singleton instance
_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    """
    Get singleton TTS service instance.

    Returns:
        TTSService instance
    """
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service


def create_tts_service(config: ModelConfig) -> TTSService:
    """
    Create a new TTS service with specific configuration.

    Use this when you need a non-default configuration.

    Args:
        config: ModelConfig to use

    Returns:
        New TTSService instance
    """
    return TTSService(config=config)


async def reload_tts_service() -> None:
    """
    Reload the singleton TTS service with fresh configuration.

    Call this after ConfigManager cache is refreshed.
    """
    global _tts_service
    if _tts_service is not None:
        _tts_service.reload_config()
        logger.info("TTS service reloaded with fresh configuration")
