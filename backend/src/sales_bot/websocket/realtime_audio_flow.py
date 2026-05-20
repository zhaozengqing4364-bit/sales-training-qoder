"""Realtime audio buffering and backpressure seam for StepFun sessions."""

from __future__ import annotations

from threading import RLock


class RealtimeAudioFlowModule:
    """Owns small input/output audio buffers behind a narrow interface."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._input_audio: list[str] = []
        self._output_audio: list[str] = []

    def append_input_audio(self, audio: str) -> None:
        with self._lock:
            self._input_audio.append(audio)

    def get_input_buffer(self) -> list[str]:
        with self._lock:
            return list(self._input_audio)

    def commit_input_audio(self) -> list[str]:
        with self._lock:
            committed = list(self._input_audio)
            self._input_audio.clear()
            return committed

    def clear_input_audio(self) -> None:
        with self._lock:
            self._input_audio.clear()

    def append_output_audio(self, audio: str) -> None:
        with self._lock:
            self._output_audio.append(audio)

    def get_output_buffer(self) -> list[str]:
        with self._lock:
            return list(self._output_audio)

    def drain_output_audio(self) -> list[str]:
        with self._lock:
            drained = list(self._output_audio)
            self._output_audio.clear()
            return drained

    def clear_output_audio(self) -> None:
        with self._lock:
            self._output_audio.clear()

    def pending_input_audio_bytes(self) -> int:
        with self._lock:
            return sum(len(audio.encode("utf-8")) for audio in self._input_audio)

    def pending_output_audio_bytes(self) -> int:
        with self._lock:
            return sum(len(audio.encode("utf-8")) for audio in self._output_audio)

    def is_backpressure_applied(self, *, high_watermark_bytes: int) -> bool:
        return self.pending_input_audio_bytes() > high_watermark_bytes
