"""Small runtime state containers for StepFun realtime sessions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RealtimeResponseState:
    """Tracks one active model response stream."""

    request_id: int
    stream_id: str
    response_id: str | None = None
    text_parts: list[str] = field(default_factory=list)
    chunk_index: int = 0
    total_duration_ms: int = 0
    first_chunk_sent: bool = False
    question_limit_enforced: bool = False



@dataclass
class FunctionCallState:
    """Tracks arguments streaming for one tool call."""

    call_id: str
    name: str
    delta_arguments: str = ""
    done_arguments: str = ""

