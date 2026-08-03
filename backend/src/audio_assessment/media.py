"""Bounded ffprobe/ffmpeg adapter used outside database transactions."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from audio_assessment.ports import (
    AudioMediaInspection,
    AudioMediaToolPort,
    NormalizedAudio,
)
from audio_assessment.storage import AudioStorageError

_SILENCE_DURATION = re.compile(r"silence_duration:\s*([0-9.]+)")
_MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?[0-9.]+)\s*dB")
_MAX_VOLUME = re.compile(r"max_volume:\s*(-?[0-9.]+)\s*dB")


class FFmpegAudioMediaTool(AudioMediaToolPort):
    def __init__(
        self, *, ffmpeg: str | None = None, ffprobe: str | None = None
    ) -> None:
        self._ffmpeg = ffmpeg or os.getenv("AUDIO_FFMPEG_BINARY") or "ffmpeg"
        self._ffprobe = ffprobe or os.getenv("AUDIO_FFPROBE_BINARY") or "ffprobe"

    async def inspect_and_normalize(
        self,
        *,
        source: Path,
        destination: Path,
        declared_content_type: str,
        max_duration_seconds: int,
    ) -> NormalizedAudio:
        if not source.is_file() or source.stat().st_size == 0:
            self._invalid("录音文件为空或已损坏。")
        probe = await self._run(
            self._ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        )
        try:
            payload = json.loads(probe[0])
            streams = [
                item
                for item in payload.get("streams", [])
                if item.get("codec_type") == "audio"
            ]
            stream = streams[0]
            duration = float(
                payload.get("format", {}).get("duration") or stream.get("duration") or 0
            )
            sample_rate = int(stream.get("sample_rate") or 0)
            channels = int(stream.get("channels") or 0)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise AudioStorageError(
                "audio_media_invalid",
                "无法识别录音格式，请重新录制或上传受支持的音频。",
                retryable=False,
            ) from exc
        if duration <= 0:
            self._invalid("录音中没有可识别的音频内容。")
        if duration > max_duration_seconds + 1:
            self._invalid("录音超过当前任务允许的最长时长。")
        if sample_rate <= 0 or channels <= 0:
            self._invalid("录音采样信息无效，请重新录制。")

        analysis = await self._run(
            self._ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-i",
            str(source),
            "-af",
            "silencedetect=noise=-45dB:d=0.5,volumedetect",
            "-f",
            "null",
            "-",
            allow_stderr_result=True,
        )
        diagnostics = analysis[1]
        silence_seconds = sum(
            float(match.group(1)) for match in _SILENCE_DURATION.finditer(diagnostics)
        )
        silence_ratio = min(1.0, max(0.0, silence_seconds / duration))
        mean_match = _MEAN_VOLUME.search(diagnostics)
        max_match = _MAX_VOLUME.search(diagnostics)
        mean_volume = float(mean_match.group(1)) if mean_match else -90.0
        max_volume = float(max_match.group(1)) if max_match else -90.0
        clipping_ratio = 1.0 if max_volume >= -0.1 else 0.0

        destination.parent.mkdir(parents=True, exist_ok=True)
        await self._run(
            self._ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise AudioStorageError(
                "audio_normalization_failed",
                "录音标准化未完成，原始录音已经保留。",
                retryable=True,
            )
        return NormalizedAudio(
            path=destination,
            inspection=AudioMediaInspection(
                content_type=declared_content_type,
                duration_seconds=duration,
                sample_rate_hz=sample_rate,
                channels=channels,
                speech_ratio=max(0.0, 1.0 - silence_ratio),
                silence_ratio=silence_ratio,
                clipping_ratio=clipping_ratio,
                mean_volume_db=mean_volume,
                tool_version=await self._version(),
            ),
        )

    async def _version(self) -> str:
        output, _ = await self._run(self._ffmpeg, "-version")
        return output.splitlines()[0][:160] if output else "ffmpeg"

    async def _run(
        self,
        *command: str,
        allow_stderr_result: bool = False,
    ) -> tuple[str, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise AudioStorageError(
                "audio_media_tool_unavailable",
                "录音处理工具暂不可用，原始录音已经保留。",
                retryable=True,
            ) from exc
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0 and not allow_stderr_result:
            raise AudioStorageError(
                "audio_media_invalid",
                "录音格式无效或已损坏，请重新录制。",
                retryable=False,
            )
        return stdout_text, stderr_text

    @staticmethod
    def _invalid(message: str) -> None:
        raise AudioStorageError(
            "audio_media_invalid",
            message,
            retryable=False,
        )


__all__ = ["FFmpegAudioMediaTool"]
