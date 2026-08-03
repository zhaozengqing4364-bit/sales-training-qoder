"""Versioned governed-AI schemas owned by audio_assessment."""

from __future__ import annotations

from ai_platform.schemas import OutputSchemaRegistry
from audio_assessment.contracts import (
    AudioScoringAIInput,
    AudioScoringAIOutput,
    AudioTranscriptAIInput,
    AudioTranscriptAIOutput,
)

AUDIO_TRANSCRIPT_INPUT_SCHEMA = "audio-transcript-input-v1"
AUDIO_TRANSCRIPT_OUTPUT_SCHEMA = "audio-transcript-output-v1"
AUDIO_SCORING_INPUT_SCHEMA = "audio-scoring-input-v1"
AUDIO_SCORING_OUTPUT_SCHEMA = "audio-scoring-output-v1"


def register_audio_ai_schemas(registry: OutputSchemaRegistry) -> None:
    registry.register_input(AUDIO_TRANSCRIPT_INPUT_SCHEMA, AudioTranscriptAIInput)
    registry.register_output(AUDIO_TRANSCRIPT_OUTPUT_SCHEMA, AudioTranscriptAIOutput)
    registry.register_input(AUDIO_SCORING_INPUT_SCHEMA, AudioScoringAIInput)
    registry.register_output(AUDIO_SCORING_OUTPUT_SCHEMA, AudioScoringAIOutput)


__all__ = [
    "AUDIO_SCORING_INPUT_SCHEMA",
    "AUDIO_SCORING_OUTPUT_SCHEMA",
    "AUDIO_TRANSCRIPT_INPUT_SCHEMA",
    "AUDIO_TRANSCRIPT_OUTPUT_SCHEMA",
    "register_audio_ai_schemas",
]
