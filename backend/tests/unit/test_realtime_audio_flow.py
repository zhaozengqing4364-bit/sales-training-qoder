from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sales_bot.websocket.realtime_audio_flow import RealtimeAudioFlowModule


def test_append_input_audio_tracks_buffered_audio() -> None:
    flow = RealtimeAudioFlowModule()

    flow.append_input_audio("base64-audio")

    assert flow.get_input_buffer() == ["base64-audio"]


def test_commit_input_audio_returns_buffer_and_clears_it() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_input_audio("chunk-1")
    flow.append_input_audio("chunk-2")

    committed = flow.commit_input_audio()

    assert committed == ["chunk-1", "chunk-2"]
    assert flow.get_input_buffer() == []


def test_clear_input_audio_empties_buffer() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_input_audio("chunk-1")

    flow.clear_input_audio()

    assert flow.get_input_buffer() == []


def test_append_output_audio_tracks_buffered_audio() -> None:
    flow = RealtimeAudioFlowModule()

    flow.append_output_audio("output-1")

    assert flow.get_output_buffer() == ["output-1"]


def test_drain_output_audio_returns_buffer_and_clears_it() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_output_audio("output-1")
    flow.append_output_audio("output-2")

    drained = flow.drain_output_audio()

    assert drained == ["output-1", "output-2"]
    assert flow.get_output_buffer() == []


def test_clear_output_audio_empties_buffer() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_output_audio("output-1")

    flow.clear_output_audio()

    assert flow.get_output_buffer() == []


def test_pending_output_audio_bytes_returns_correct_count() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_output_audio("12345")
    flow.append_output_audio("你好")

    assert flow.pending_output_audio_bytes() == len("12345你好".encode())


def test_backpressure_applies_when_input_buffer_exceeds_threshold() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_input_audio("12345")
    flow.append_input_audio("67890")

    assert flow.is_backpressure_applied(high_watermark_bytes=9) is True


def test_backpressure_does_not_apply_at_or_below_threshold() -> None:
    flow = RealtimeAudioFlowModule()
    flow.append_input_audio("12345")
    flow.append_input_audio("67890")

    assert flow.is_backpressure_applied(high_watermark_bytes=10) is False
    assert flow.is_backpressure_applied(high_watermark_bytes=11) is False


def test_concurrent_input_appends_are_safe_without_sleep() -> None:
    flow = RealtimeAudioFlowModule()
    chunks = [f"chunk-{index}" for index in range(64)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(flow.append_input_audio, chunks))

    assert sorted(flow.get_input_buffer()) == sorted(chunks)
