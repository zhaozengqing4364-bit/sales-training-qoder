"""StepFun reviewer-only thinking capture helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

MAX_THINKING_CHARS = 50_000
MAX_THINKING_LOG_ENTRIES = 50
TRUNCATED_SUFFIX = "…[truncated]"


@dataclass(frozen=True)
class ThinkingEntry:
    turn_index: int
    template_stage_key: str | None
    thinking_text: str
    captured_at: str
    response_id: str


@dataclass
class _ThinkingBuffer:
    response_id: str
    text: str = ""
    truncated: bool = False


class StepFunThinkingCapture:
    """Accumulates StepFun thinking chunks without exposing them to learners."""

    def __init__(
        self,
        *,
        turn_index: Callable[[], int] | None = None,
        template_stage_key: Callable[[], str | None] | None = None,
        clock: Callable[[], float] | None = None,
        max_chars: int = MAX_THINKING_CHARS,
    ) -> None:
        self._turn_index = turn_index or (lambda: 0)
        self._template_stage_key = template_stage_key or (lambda: None)
        self._clock = clock or (lambda: datetime.now(UTC).timestamp())
        self._max_chars = max(0, max_chars)
        self._buffers: dict[str, _ThinkingBuffer] = {}

    def on_delta(self, event: dict[str, object]) -> None:
        response_id = _response_id(event)
        delta = _thinking_delta(event)
        if not response_id or not delta:
            return
        buffer = self._buffers.setdefault(
            response_id,
            _ThinkingBuffer(response_id=response_id),
        )
        if buffer.truncated:
            return
        next_text = f"{buffer.text}{delta}"
        if self._max_chars and len(next_text) > self._max_chars:
            buffer.text = f"{next_text[: self._max_chars]}{TRUNCATED_SUFFIX}"
            buffer.truncated = True
            return
        buffer.text = next_text

    def on_done(self, event: dict[str, object]) -> ThinkingEntry | None:
        response_id = _response_id(event)
        if not response_id:
            return None
        buffer = self._buffers.pop(response_id, None)
        thinking_text = buffer.text if buffer is not None else ""
        if not thinking_text:
            thinking_text = _thinking_done_text(event)
        return self._build_entry(response_id, thinking_text)

    def flush_response(self, response_id: str) -> ThinkingEntry | None:
        response_id = str(response_id or "").strip()
        if not response_id:
            return None
        buffer = self._buffers.pop(response_id, None)
        if buffer is None:
            return None
        return self._build_entry(response_id, buffer.text)

    def clear(self) -> None:
        self._buffers.clear()

    def _build_entry(self, response_id: str, thinking_text: str) -> ThinkingEntry | None:
        thinking_text = str(thinking_text or "").strip()
        if not thinking_text:
            return None
        return ThinkingEntry(
            turn_index=max(0, int(self._turn_index() or 0)),
            template_stage_key=self._template_stage_key(),
            thinking_text=thinking_text,
            captured_at=_captured_at(self._clock),
            response_id=response_id,
        )


def apply_thinking_entry_to_runtime_state(
    runtime_state: dict[str, Any] | None,
    entry: ThinkingEntry,
    *,
    max_entries: int = MAX_THINKING_LOG_ENTRIES,
) -> dict[str, Any]:
    next_state = dict(runtime_state) if isinstance(runtime_state, dict) else {}
    existing_log = next_state.get("thinking_log")
    thinking_log = [dict(item) for item in existing_log or [] if isinstance(item, dict)]
    thinking_log.append(asdict(entry))
    if max_entries > 0 and len(thinking_log) > max_entries:
        thinking_log = thinking_log[-max_entries:]
    next_state["thinking_log"] = thinking_log
    return next_state


def _response_id(event: dict[str, object]) -> str:
    value = event.get("response_id")
    if value:
        return str(value).strip()
    response = event.get("response")
    if isinstance(response, dict):
        return str(response.get("id") or "").strip()
    return ""


def _thinking_delta(event: dict[str, object]) -> str:
    value = event.get("delta")
    if isinstance(value, str):
        return value
    return ""


def _thinking_done_text(event: dict[str, object]) -> str:
    value = event.get("thinking")
    if isinstance(value, str):
        return value.strip()
    response = event.get("response")
    if isinstance(response, dict):
        value = response.get("thinking")
        if isinstance(value, str):
            return value.strip()
    return ""


def _captured_at(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), UTC).isoformat().replace("+00:00", "Z")
