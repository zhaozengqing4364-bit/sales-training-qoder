from __future__ import annotations

from sales_bot.websocket.components.stepfun_thinking_capture import (
    StepFunThinkingCapture,
    ThinkingEntry,
    apply_thinking_entry_to_runtime_state,
)


def test_should_assemble_delta_chunks_until_done_event() -> None:
    capture = StepFunThinkingCapture(turn_index=lambda: 3, clock=lambda: 10.0)

    capture.on_delta({"response_id": "resp_001", "delta": "先判断"})
    capture.on_delta({"response_id": "resp_001", "delta": "客户异议"})
    entry = capture.on_done({"response_id": "resp_001"})

    assert entry == ThinkingEntry(
        turn_index=3,
        template_stage_key=None,
        thinking_text="先判断客户异议",
        captured_at="1970-01-01T00:00:10Z",
        response_id="resp_001",
    )


def test_should_group_thinking_by_response_id_and_stage_key() -> None:
    capture = StepFunThinkingCapture(
        turn_index=lambda: 4,
        template_stage_key=lambda: "standard_roleplay",
        clock=lambda: 20.0,
    )

    capture.on_delta({"response_id": "resp_stage", "delta": "阶段证据"})
    entry = capture.on_done({"response_id": "resp_stage"})

    assert entry is not None
    assert entry.turn_index == 4
    assert entry.template_stage_key == "standard_roleplay"
    assert entry.response_id == "resp_stage"


def test_should_ignore_empty_delta_without_crashing() -> None:
    capture = StepFunThinkingCapture(turn_index=lambda: 1)

    capture.on_delta({"response_id": "resp_empty", "delta": ""})
    capture.on_delta({"response_id": "resp_empty", "delta": "   "})

    assert capture.on_done({"response_id": "resp_empty"}) is None


def test_should_preserve_delta_chunk_whitespace_until_final_entry() -> None:
    capture = StepFunThinkingCapture(turn_index=lambda: 1, clock=lambda: 50.0)

    capture.on_delta({"response_id": "resp_space", "delta": "  first\n"})
    capture.on_delta({"response_id": "resp_space", "delta": "  second  "})
    entry = capture.on_done({"response_id": "resp_space"})

    assert entry is not None
    assert entry.thinking_text == "first\n  second"


def test_should_flush_bounded_per_turn_thinking_entry() -> None:
    capture = StepFunThinkingCapture(
        turn_index=lambda: 2,
        template_stage_key=lambda: "stage_a",
        clock=lambda: 30.0,
        max_chars=8,
    )
    capture.on_delta({"response_id": "resp_bound", "delta": "123456"})
    capture.on_delta({"response_id": "resp_bound", "delta": "7890"})

    entry = capture.flush_response("resp_bound")

    assert entry is not None
    assert entry.thinking_text == "12345678…[truncated]"

    runtime_state = apply_thinking_entry_to_runtime_state(
        {"thinking_log": [{"response_id": "old"}, {"response_id": "older"}]},
        entry,
        max_entries=2,
    )
    assert [item["response_id"] for item in runtime_state["thinking_log"]] == [
        "older",
        "resp_bound",
    ]


def test_should_not_mix_chunks_from_parallel_response_ids() -> None:
    capture = StepFunThinkingCapture(turn_index=lambda: 5, clock=lambda: 40.0)

    capture.on_delta({"response_id": "resp_a", "delta": "A1"})
    capture.on_delta({"response_id": "resp_b", "delta": "B1"})
    capture.on_delta({"response_id": "resp_a", "delta": "A2"})

    entry_b = capture.on_done({"response_id": "resp_b"})
    entry_a = capture.on_done({"response_id": "resp_a"})

    assert entry_b is not None
    assert entry_a is not None
    assert entry_b.thinking_text == "B1"
    assert entry_a.thinking_text == "A1A2"
