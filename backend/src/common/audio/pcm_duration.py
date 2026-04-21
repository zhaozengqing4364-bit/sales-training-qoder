"""PCM audio duration helpers.

The formula is a stable technical invariant. The format values are adjustable
runtime configuration with validated defaults in ``common.config.Settings``.
"""

from __future__ import annotations

from typing import Any

from common.config import settings


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def resolve_pcm_audio_format(config: dict[str, Any] | None = None) -> tuple[int, int, int]:
    """Resolve sample rate, bytes per sample, and channels from config/defaults."""
    raw = config if isinstance(config, dict) else {}
    sample_rate_hz = _bounded_int(
        raw.get("sample_rate_hz", raw.get("sample_rate")),
        settings.TTS_DEFAULT_SAMPLE_RATE_HZ,
        minimum=8000,
        maximum=48000,
    )
    bytes_per_sample = _bounded_int(
        raw.get("bytes_per_sample"),
        settings.TTS_BYTES_PER_SAMPLE,
        minimum=1,
        maximum=4,
    )
    channels = _bounded_int(
        raw.get("channels"),
        settings.TTS_CHANNELS,
        minimum=1,
        maximum=2,
    )
    return sample_rate_hz, bytes_per_sample, channels


def calculate_pcm_duration_ms(
    audio_data: bytes,
    *,
    sample_rate_hz: int,
    bytes_per_sample: int,
    channels: int,
) -> int:
    """Calculate PCM duration in milliseconds."""
    if not audio_data:
        return 0

    bytes_per_second = sample_rate_hz * bytes_per_sample * channels
    if bytes_per_second <= 0:
        return 0
    return int(len(audio_data) * 1000 / bytes_per_second)
