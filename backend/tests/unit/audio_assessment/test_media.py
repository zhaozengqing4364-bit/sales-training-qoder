from __future__ import annotations

import json
from pathlib import Path

import pytest

from audio_assessment.media import FFmpegAudioMediaTool
from audio_assessment.storage import AudioStorageError


@pytest.mark.asyncio
async def test_media_tool_validates_decodes_and_normalizes_without_trusting_extension(
    tmp_path: Path,
) -> None:
    source = tmp_path / "declared.webm"
    destination = tmp_path / "normalized.wav"
    source.write_bytes(b"not-used-by-fake-tool")
    tool = FFmpegAudioMediaTool(ffmpeg="fake-ffmpeg", ffprobe="fake-ffprobe")

    async def run(*command: str, allow_stderr_result: bool = False):
        del allow_stderr_result
        if command[0] == "fake-ffprobe":
            return (
                json.dumps(
                    {
                        "format": {"duration": "12.0"},
                        "streams": [
                            {
                                "codec_type": "audio",
                                "sample_rate": "48000",
                                "channels": 2,
                            }
                        ],
                    }
                ),
                "",
            )
        if "-version" in command:
            return "ffmpeg version 7.1-test\n", ""
        if "-af" in command:
            return (
                "",
                "silence_duration: 3.0\nmean_volume: -22.0 dB\nmax_volume: -0.1 dB",
            )
        destination.write_bytes(b"normalized-wave")
        return "", ""

    tool._run = run  # type: ignore[method-assign]
    result = await tool.inspect_and_normalize(
        source=source,
        destination=destination,
        declared_content_type="audio/webm",
        max_duration_seconds=30,
    )

    assert result.path == destination
    assert result.inspection.duration_seconds == 12
    assert result.inspection.sample_rate_hz == 48_000
    assert result.inspection.channels == 2
    assert result.inspection.silence_ratio == 0.25
    assert result.inspection.speech_ratio == 0.75
    assert result.inspection.clipping_ratio == 1.0
    assert result.inspection.tool_version == "ffmpeg version 7.1-test"


@pytest.mark.asyncio
async def test_media_tool_rejects_corrupt_or_overlong_audio(tmp_path: Path) -> None:
    source = tmp_path / "recording.mp3"
    source.write_bytes(b"corrupt")
    tool = FFmpegAudioMediaTool(ffmpeg="fake-ffmpeg", ffprobe="fake-ffprobe")

    async def corrupt_probe(*command: str, allow_stderr_result: bool = False):
        del command, allow_stderr_result
        return "not-json", ""

    tool._run = corrupt_probe  # type: ignore[method-assign]
    with pytest.raises(AudioStorageError) as corrupt:
        await tool.inspect_and_normalize(
            source=source,
            destination=tmp_path / "corrupt.wav",
            declared_content_type="audio/mpeg",
            max_duration_seconds=30,
        )
    assert corrupt.value.code == "audio_media_invalid"
    assert corrupt.value.retryable is False

    async def long_probe(*command: str, allow_stderr_result: bool = False):
        del command, allow_stderr_result
        return (
            json.dumps(
                {
                    "format": {"duration": "62"},
                    "streams": [
                        {
                            "codec_type": "audio",
                            "sample_rate": "16000",
                            "channels": 1,
                        }
                    ],
                }
            ),
            "",
        )

    tool._run = long_probe  # type: ignore[method-assign]
    with pytest.raises(AudioStorageError) as overlong:
        await tool.inspect_and_normalize(
            source=source,
            destination=tmp_path / "overlong.wav",
            declared_content_type="audio/mpeg",
            max_duration_seconds=60,
        )
    assert overlong.value.code == "audio_media_invalid"
    assert overlong.value.retryable is False
