"""StepFun realtime emotion-signal extraction from local speech events."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

MAX_EMOTION_LOG_ENTRIES = 50


@dataclass(frozen=True)
class EmotionSignal:
    turn_id: str
    signal_type: Literal[
        "response_done_to_user_start_ms",
        "speaking_rate",
        "hesitation_count",
    ]
    value: float
    source_event_ids: tuple[str, ...]
    captured_at: str


class StepFunEmotionAnalyzer:
    """Extracts bounded speech signals from existing StepFun event payloads."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC).timestamp())
        self._last_ai_stop_ms: float | None = None
        self._last_ai_stop_event_id = ""

    def on_speech_started(self, event: dict[str, object]) -> list[EmotionSignal]:
        event_ms = _event_timestamp_ms(event, self._clock)
        turn_id = _turn_id(event)
        if self._last_ai_stop_ms is None or not turn_id:
            return []
        latency_ms = max(0.0, event_ms - self._last_ai_stop_ms)
        return [
            EmotionSignal(
                turn_id=turn_id,
                signal_type="response_done_to_user_start_ms",
                value=round(latency_ms, 3),
                source_event_ids=(self._last_ai_stop_event_id, _event_id(event)),
                captured_at=_captured_at(self._clock),
            )
        ]

    def on_speech_stopped(self, event: dict[str, object]) -> list[EmotionSignal]:
        self._last_ai_stop_ms = _event_timestamp_ms(event, self._clock)
        self._last_ai_stop_event_id = _event_id(event)
        return []

    def on_audio_transcript_done(self, event: dict[str, object]) -> list[EmotionSignal]:
        transcript = _transcript_text(event)
        if not transcript:
            return []
        duration_ms = _duration_ms(event)
        if duration_ms <= 0:
            return []
        token_count = len(_speech_tokens(transcript))
        if token_count <= 0:
            return []
        return [
            EmotionSignal(
                turn_id=_turn_id(event),
                signal_type="speaking_rate",
                value=round(token_count / (duration_ms / 1000.0), 3),
                source_event_ids=(_event_id(event),),
                captured_at=_captured_at(self._clock),
            ),
            EmotionSignal(
                turn_id=_turn_id(event),
                signal_type="hesitation_count",
                value=float(_hesitation_count(transcript)),
                source_event_ids=(_event_id(event),),
                captured_at=_captured_at(self._clock),
            ),
        ]

    def flush_turn(self, turn_id: str) -> list[EmotionSignal]:
        return []


def _event_timestamp_ms(
    event: dict[str, object],
    clock: Callable[[], float],
) -> float:
    value = event.get("timestamp_ms")
    if isinstance(value, int | float):
        return float(value)
    value = event.get("created_at_ms")
    if isinstance(value, int | float):
        return float(value)
    return clock() * 1000.0


def _event_id(event: dict[str, object]) -> str:
    value = event.get("event_id") or event.get("id")
    return str(value or "")


def _turn_id(event: dict[str, object]) -> str:
    value = event.get("turn_id") or event.get("item_id") or event.get("response_id")
    return str(value or "")


def _captured_at(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), UTC).isoformat().replace("+00:00", "Z")


def _transcript_text(event: dict[str, object]) -> str:
    for key in ("transcript", "text", "audio_transcript", "delta", "stash"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    item = event.get("item")
    if isinstance(item, dict):
        return _transcript_text(item)
    return ""


def _duration_ms(event: dict[str, object]) -> float:
    for key in ("duration_ms", "audio_duration_ms"):
        value = event.get(key)
        if isinstance(value, int | float):
            return max(0.0, float(value))
    start_ms = event.get("speech_started_at_ms")
    stop_ms = event.get("speech_stopped_at_ms")
    if isinstance(start_ms, int | float) and isinstance(stop_ms, int | float):
        return max(0.0, float(stop_ms) - float(start_ms))
    return 0.0


def _speech_tokens(transcript: str) -> list[str]:
    spaced_tokens = [token for token in re.split(r"\s+", transcript.strip()) if token]
    if len(spaced_tokens) > 1:
        return spaced_tokens
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", transcript)
    if chinese_chars:
        return chinese_chars
    return re.findall(r"[A-Za-z0-9]+", transcript)


def _hesitation_count(transcript: str) -> int:
    return sum(transcript.count(marker) for marker in ("嗯", "呃", "那个", "这个"))


def apply_emotion_signals_to_runtime_state(
    runtime_state: dict[str, Any] | None,
    signals: list[EmotionSignal],
    *,
    template_stage_key: str | None = None,
    max_entries: int = MAX_EMOTION_LOG_ENTRIES,
) -> dict[str, Any]:
    next_state = dict(runtime_state) if isinstance(runtime_state, dict) else {}
    existing_log = next_state.get("emotion_log")
    emotion_log = [dict(item) for item in existing_log or [] if isinstance(item, dict)]
    entry_by_turn_id = {
        str(item.get("turn_id") or ""): item
        for item in emotion_log
        if str(item.get("turn_id") or "")
    }

    grouped: dict[str, dict[str, Any]] = {}
    for signal in signals:
        entry = grouped.setdefault(signal.turn_id, entry_by_turn_id.get(signal.turn_id, {}))
        entry.setdefault("turn_id", signal.turn_id)
        entry.setdefault("source_event_ids", [])
        if template_stage_key:
            entry["template_stage_key"] = template_stage_key
        entry[signal.signal_type] = signal.value
        source_event_ids = entry["source_event_ids"]
        if isinstance(source_event_ids, list):
            for event_id in signal.source_event_ids:
                if event_id and event_id not in source_event_ids:
                    source_event_ids.append(event_id)
        entry["captured_at"] = signal.captured_at

    for turn_id, entry in grouped.items():
        if turn_id not in entry_by_turn_id:
            emotion_log.append(entry)
            entry_by_turn_id[turn_id] = entry
    if max_entries > 0 and len(emotion_log) > max_entries:
        emotion_log = emotion_log[-max_entries:]
    next_state["emotion_log"] = emotion_log
    return next_state
