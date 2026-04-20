"""StepFun realtime websocket event payload helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_stage_update_event(
    *,
    stage_data: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    return {
        "type": "stage_update",
        "timestamp": _utc_now_iso(),
        "trace_id": trace_id,
        "data": stage_data,
    }


def build_asr_transcript_event(
    *,
    text: str,
    is_final: bool,
    confidence: float = 0.95,
) -> dict[str, Any]:
    return {
        "type": "asr_transcript",
        "timestamp": _utc_now_iso(),
        "data": {
            "text": text,
            "is_final": is_final,
            "confidence": confidence,
        },
    }


def build_status_event(
    *,
    session_status: str,
    ai_state: str,
    turn_count: int,
    trace_id: str,
) -> dict[str, Any]:
    return {
        "type": "status",
        "timestamp": _utc_now_iso(),
        "trace_id": trace_id,
        "data": {
            "session_status": session_status,
            "ai_state": ai_state,
            "turn_count": turn_count,
        },
    }


def build_heartbeat_event() -> dict[str, Any]:
    return {
        "type": "heartbeat",
        "timestamp": _utc_now_iso(),
        "data": {},
    }


def build_error_event(
    *,
    code: str,
    message: str,
    session_status: str,
    ai_state: str,
    turn_count: int,
    trace_id: str,
    user_action: str = "请稍后重试",
) -> dict[str, Any]:
    return {
        "type": "error",
        "timestamp": _utc_now_iso(),
        "trace_id": trace_id,
        "data": {
            "code": code,
            "message": message,
            "user_action": user_action,
            "session_status": session_status,
            "ai_state": ai_state,
            "turn_count": turn_count,
        },
    }


def build_interrupted_event(
    *,
    reason: str,
    session_status: str,
    ai_state: str,
    turn_count: int,
    trace_id: str,
    stream_id: str | None,
) -> dict[str, Any]:
    return {
        "type": "interrupted",
        "timestamp": _utc_now_iso(),
        "trace_id": trace_id,
        "stream_id": stream_id,
        "data": {
            "reason": reason,
            "session_status": session_status,
            "ai_state": ai_state,
            "turn_count": turn_count,
        },
    }
