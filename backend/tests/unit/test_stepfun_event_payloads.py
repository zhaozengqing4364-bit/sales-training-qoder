"""Unit tests for StepFun websocket event payload helpers."""

from __future__ import annotations

from datetime import datetime

from sales_bot.websocket.components.stepfun_event_payloads import (
    build_asr_transcript_event,
    build_error_event,
    build_heartbeat_event,
    build_stage_update_event,
    build_status_event,
)


def _assert_iso_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None


def test_build_stage_update_event_shape():
    payload = build_stage_update_event(
        stage_data={"current_stage": "discovery", "stage_changed": True},
        trace_id="trace-stage",
    )

    assert payload["type"] == "stage_update"
    assert payload["trace_id"] == "trace-stage"
    assert payload["data"]["current_stage"] == "discovery"
    _assert_iso_timestamp(payload["timestamp"])


def test_build_asr_transcript_event_shape():
    payload = build_asr_transcript_event(text="你好", is_final=True)

    assert payload["type"] == "asr_transcript"
    assert payload["data"] == {
        "text": "你好",
        "is_final": True,
        "confidence": 0.95,
    }
    _assert_iso_timestamp(payload["timestamp"])


def test_build_status_event_shape():
    payload = build_status_event(
        session_status="in_progress",
        ai_state="listening",
        turn_count=3,
        trace_id="trace-status",
    )

    assert payload["type"] == "status"
    assert payload["trace_id"] == "trace-status"
    assert payload["data"] == {
        "session_status": "in_progress",
        "ai_state": "listening",
        "turn_count": 3,
    }
    _assert_iso_timestamp(payload["timestamp"])


def test_build_heartbeat_event_shape():
    payload = build_heartbeat_event()

    assert payload["type"] == "heartbeat"
    assert payload["data"] == {}
    _assert_iso_timestamp(payload["timestamp"])


def test_build_error_event_shape():
    payload = build_error_event(
        code="[ERR]",
        message="failed",
        session_status="in_progress",
        ai_state="idle",
        turn_count=5,
        trace_id="trace-error",
    )

    assert payload["type"] == "error"
    assert payload["trace_id"] == "trace-error"
    assert payload["data"] == {
        "code": "[ERR]",
        "message": "failed",
        "user_action": "请稍后重试",
        "session_status": "in_progress",
        "ai_state": "idle",
        "turn_count": 5,
    }
    _assert_iso_timestamp(payload["timestamp"])
