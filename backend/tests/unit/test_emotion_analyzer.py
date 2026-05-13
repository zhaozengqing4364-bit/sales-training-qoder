from __future__ import annotations

from sales_bot.websocket.components.stepfun_emotion_analyzer import (
    StepFunEmotionAnalyzer,
)


def test_should_measure_response_latency_between_ai_stop_and_user_start() -> None:
    analyzer = StepFunEmotionAnalyzer(clock=lambda: 10.0)

    analyzer.on_speech_stopped(
        {"type": "response.done", "event_id": "ai-stop", "turn_id": "turn-1"}
    )
    signals = analyzer.on_speech_started(
        {
            "type": "input_audio_buffer.speech_started",
            "event_id": "user-start",
            "turn_id": "turn-1",
            "timestamp_ms": 10820,
        }
    )

    assert [signal.signal_type for signal in signals] == ["response_latency_ms"]
    assert signals[0].turn_id == "turn-1"
    assert signals[0].value == 820
    assert signals[0].source_event_ids == ("ai-stop", "user-start")


def test_should_measure_speaking_rate_from_transcript_words_and_duration() -> None:
    analyzer = StepFunEmotionAnalyzer(clock=lambda: 20.0)

    signals = analyzer.on_audio_transcript_done(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "transcript-done",
            "turn_id": "turn-2",
            "transcript": "我们 帮助 你们 提升 转化",
            "duration_ms": 2500,
        }
    )

    assert len(signals) == 2
    speaking_rate = next(
        signal for signal in signals if signal.signal_type == "speaking_rate"
    )
    assert speaking_rate.turn_id == "turn-2"
    assert speaking_rate.value == 2.0
    assert speaking_rate.source_event_ids == ("transcript-done",)


def test_should_count_chinese_hesitation_markers() -> None:
    analyzer = StepFunEmotionAnalyzer(clock=lambda: 30.0)

    signals = analyzer.on_audio_transcript_done(
        {
            "type": "input_audio_buffer.transcription.completed",
            "event_id": "hesitation-transcript",
            "turn_id": "turn-3",
            "transcript": "嗯，这个呃，我们可能先那个看一下。",
            "duration_ms": 3000,
        }
    )

    hesitation_count = next(
        signal for signal in signals if signal.signal_type == "hesitation_count"
    )
    assert hesitation_count.value == 4


def test_should_ignore_incomplete_event_sequences_without_crashing() -> None:
    analyzer = StepFunEmotionAnalyzer(clock=lambda: 40.0)

    assert analyzer.on_speech_started({"type": "input_audio_buffer.speech_started"}) == []
    assert analyzer.on_audio_transcript_done(
        {"type": "input_audio_buffer.transcription.completed", "transcript": "你好"}
    ) == []


def test_should_emit_empty_signal_for_empty_transcript() -> None:
    analyzer = StepFunEmotionAnalyzer(clock=lambda: 50.0)

    assert analyzer.on_audio_transcript_done(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "event_id": "empty-transcript",
            "turn_id": "turn-empty",
            "transcript": "   ",
            "duration_ms": 1800,
        }
    ) == []
