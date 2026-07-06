"""Non-blocking StepFun realtime turn transcript capture seam."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from common.monitoring.logger import get_logger, get_trace_id
from sales_bot.websocket.components.stepfun_helpers import extract_response_text

logger = get_logger(__name__)


@dataclass(frozen=True)
class TurnTranscriptCaptureEvent:
    speaker: str
    transcript: str
    source_event_type: str
    session_id: str
    response_id: str | None
    turn_id: str | None
    turn_index: int
    template_stage_key: str | None
    instruction_contract_hash: str | None
    grounding_metadata: dict[str, Any] | None
    trace_id: str | None
    captured_at: str


class StepFunTurnTranscriptCapture:
    """Collect assistant/learner transcripts and dispatch them without blocking."""

    def __init__(
        self,
        *,
        session_id: Callable[[], str],
        template_stage_key: Callable[[], str | None],
        instruction_contract_hash: Callable[[], str | None],
        grounding_metadata: Callable[[], dict[str, Any] | None],
        trace_id: Callable[[], str | None] | None = None,
        sink: Callable[[dict[str, Any]], Any] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._session_id = session_id
        self._template_stage_key = template_stage_key
        self._instruction_contract_hash = instruction_contract_hash
        self._grounding_metadata = grounding_metadata
        self._trace_id = trace_id or get_trace_id
        self._sink = sink
        self._clock = clock or (lambda: datetime.now(UTC).timestamp())
        self._assistant_buffers: dict[str, str] = {}
        self._dispatched_response_ids: set[str] = set()

    def clear(self) -> None:
        self._assistant_buffers.clear()
        self._dispatched_response_ids.clear()

    def capture_learner_transcript(
        self,
        *,
        transcript: str,
        turn_id: str | None,
        turn_index: int,
        source_event_type: str,
    ) -> None:
        entry = self._build_event(
            speaker="learner",
            transcript=transcript,
            source_event_type=source_event_type,
            response_id=None,
            turn_id=turn_id,
            turn_index=turn_index,
        )
        if entry is not None:
            self._dispatch(entry)

    def capture_assistant_transcript(
        self,
        *,
        transcript: str,
        response_id: str | None,
        turn_id: str | None,
        turn_index: int,
        source_event_type: str,
    ) -> None:
        normalized_response_id = _normalize_text(response_id)
        if (
            normalized_response_id
            and normalized_response_id in self._dispatched_response_ids
        ):
            return
        entry = self._build_event(
            speaker="assistant",
            transcript=transcript,
            source_event_type=source_event_type,
            response_id=normalized_response_id,
            turn_id=turn_id,
            turn_index=turn_index,
        )
        if entry is None:
            return
        if normalized_response_id:
            self._assistant_buffers.pop(normalized_response_id, None)
            self._dispatched_response_ids.add(normalized_response_id)
        self._dispatch(entry)

    def on_upstream_event(
        self,
        event: dict[str, Any],
        *,
        active_response: Any | None,
        turn_id: str | None,
        turn_index: int,
    ) -> None:
        event_type = str(event.get("type") or "")
        fallback_response_id = _active_response_id(active_response)
        if event_type == "response.audio_transcript.delta":
            self._buffer_assistant_delta(
                event,
                fallback_response_id=fallback_response_id,
            )
            return
        if event_type == "response.audio_transcript.done":
            if _active_response_roleplay_suppressed(active_response):
                self._discard_response(
                    _response_id(event, fallback_response_id=fallback_response_id)
                )
                return
            response_id = _response_id(event, fallback_response_id=fallback_response_id)
            transcript = self._assistant_done_text(
                event,
                fallback_response_id=fallback_response_id,
            )
            self.capture_assistant_transcript(
                transcript=transcript,
                response_id=response_id,
                turn_id=turn_id,
                turn_index=turn_index,
                source_event_type=event_type,
            )
            return

    def _build_event(
        self,
        *,
        speaker: str,
        transcript: str,
        source_event_type: str,
        response_id: str | None,
        turn_id: str | None,
        turn_index: int,
    ) -> TurnTranscriptCaptureEvent | None:
        normalized_transcript = _normalize_text(transcript)
        session_id = _normalize_text(self._session_id())
        if not normalized_transcript or not session_id:
            return None
        template_stage_key = _normalize_text(self._template_stage_key())
        instruction_contract_hash = _normalize_text(self._instruction_contract_hash())
        grounding_metadata = self._grounding_metadata()
        if not isinstance(grounding_metadata, dict):
            grounding_metadata = None
        return TurnTranscriptCaptureEvent(
            speaker=speaker,
            transcript=normalized_transcript,
            source_event_type=source_event_type,
            session_id=session_id,
            response_id=response_id,
            turn_id=_normalize_text(turn_id) or None,
            turn_index=max(0, int(turn_index)),
            template_stage_key=template_stage_key or None,
            instruction_contract_hash=instruction_contract_hash or None,
            grounding_metadata=grounding_metadata,
            trace_id=_normalize_text(self._trace_id()) or None,
            captured_at=_captured_at(self._clock),
        )

    def _buffer_assistant_delta(
        self,
        event: dict[str, Any],
        *,
        fallback_response_id: str | None,
    ) -> None:
        response_id = _response_id(event, fallback_response_id=fallback_response_id)
        delta = _raw_string(event.get("delta"))
        if not response_id or not delta or response_id in self._dispatched_response_ids:
            return
        previous = self._assistant_buffers.get(response_id, "")
        self._assistant_buffers[response_id] = f"{previous}{delta}"

    def _assistant_done_text(
        self,
        event: dict[str, Any],
        *,
        fallback_response_id: str | None,
    ) -> str:
        response_id = _response_id(event, fallback_response_id=fallback_response_id)
        if response_id:
            buffered = _normalize_text(self._assistant_buffers.get(response_id))
            if buffered:
                return buffered
        direct_text = _extract_done_text(event)
        if direct_text:
            return direct_text
        if response_id:
            return _normalize_text(self._assistant_buffers.get(response_id))
        return ""

    def _discard_response(self, response_id: str | None) -> None:
        normalized_response_id = _normalize_text(response_id)
        if normalized_response_id:
            self._assistant_buffers.pop(normalized_response_id, None)

    def _dispatch(self, entry: TurnTranscriptCaptureEvent) -> None:
        if self._sink is None:
            return
        payload = asdict(entry)
        try:
            result = self._sink(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "stepfun_turn_transcript_capture_sink_failed",
                session_id=entry.session_id,
                speaker=entry.speaker,
                response_id=entry.response_id,
                error=str(exc),
            )
            return
        if not inspect.isawaitable(result):
            return
        try:
            task = asyncio.ensure_future(result)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "stepfun_turn_transcript_capture_sink_failed",
                session_id=entry.session_id,
                speaker=entry.speaker,
                response_id=entry.response_id,
                error=str(exc),
            )
            return
        task.add_done_callback(
            lambda pending: self._handle_async_sink_result(pending, entry)
        )

    def _handle_async_sink_result(
        self,
        task: asyncio.Task[Any],
        entry: TurnTranscriptCaptureEvent,
    ) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "stepfun_turn_transcript_capture_sink_failed",
                session_id=entry.session_id,
                speaker=entry.speaker,
                response_id=entry.response_id,
                error=str(exc),
            )


def _response_id(
    event: dict[str, Any],
    *,
    fallback_response_id: str | None = None,
) -> str | None:
    direct = _normalize_text(event.get("response_id"))
    if direct:
        return direct
    response = event.get("response")
    if isinstance(response, dict):
        nested = _normalize_text(response.get("id"))
        if nested:
            return nested
    return _normalize_text(fallback_response_id) or None


def _active_response_id(active_response: Any | None) -> str | None:
    if active_response is None:
        return None
    return _normalize_text(getattr(active_response, "response_id", None)) or None


def _active_response_roleplay_suppressed(active_response: Any | None) -> bool:
    if active_response is None:
        return False
    return bool(getattr(active_response, "roleplay_suppressed", False))


def _extract_done_text(event: dict[str, Any]) -> str:
    for key in ("transcript", "text", "delta"):
        value = _raw_string(event.get(key)).strip()
        if value:
            return value
    item = event.get("item")
    if isinstance(item, dict):
        for key in ("transcript", "text"):
            value = _raw_string(item.get(key)).strip()
            if value:
                return value
        content = item.get("content")
        content_text = _extract_content_text(content)
        if content_text:
            return content_text
    content_text = _extract_content_text(event.get("content"))
    if content_text:
        return content_text
    response = event.get("response")
    if isinstance(response, dict):
        response_text = extract_response_text({"response": response})
        if response_text:
            return response_text
    return ""


def _extract_content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        for key in ("transcript", "text"):
            value = _raw_string(part.get(key))
            if value.strip():
                text_parts.append(value)
                break
    return "".join(text_parts).strip()


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _raw_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def _captured_at(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), UTC).isoformat().replace("+00:00", "Z")
