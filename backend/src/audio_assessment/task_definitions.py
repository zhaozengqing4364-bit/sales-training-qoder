"""Explicit durable-task registration for the full-file audio pipeline."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform import AIInvocationPort, PromptCompilationService
from audio_assessment.contracts import AudioPipelineTaskInput, AudioPipelineTaskResult
from audio_assessment.media import FFmpegAudioMediaTool
from audio_assessment.pipeline import AudioPipelineTaskHandler
from audio_assessment.ports import (
    AudioMediaToolPort,
    AudioObjectStoragePort,
    AudioOutcomeWriterPort,
)
from audio_assessment.runtime import AUDIO_PIPELINE_TASK_TYPE
from task_runtime import TaskDefinition, TaskRegistry
from task_runtime.contracts import TaskPolicy

AIInvocationFactory = Callable[[], AIInvocationPort]
AudioOutcomeWriterFactory = Callable[[AsyncSession], AudioOutcomeWriterPort]


def register_audio_task_definition(
    registry: TaskRegistry,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    ai_factory: AIInvocationFactory | None = None,
    outcome_writer_factory: AudioOutcomeWriterFactory | None = None,
    prompt_compiler: PromptCompilationService | None = None,
    storage: AudioObjectStoragePort | None = None,
    media: AudioMediaToolPort | None = None,
) -> None:
    dependencies = (
        session_factory,
        ai_factory,
        outcome_writer_factory,
        prompt_compiler,
        storage,
    )
    if any(item is not None for item in dependencies) and not all(
        item is not None for item in dependencies
    ):
        raise ValueError(
            "Audio Worker 注册必须同时提供 session、AI、Outcome 和存储依赖。"
        )
    handler = None
    if session_factory is not None:
        assert ai_factory is not None
        assert outcome_writer_factory is not None
        assert prompt_compiler is not None
        assert storage is not None
        handler = AudioPipelineTaskHandler(
            session_factory,
            ai_factory=ai_factory,
            outcome_writer_factory=outcome_writer_factory,
            prompt_compiler=prompt_compiler,
            storage=storage,
            media=media or FFmpegAudioMediaTool(),
        )
    registry.register(
        TaskDefinition(
            task_type=AUDIO_PIPELINE_TASK_TYPE,
            schema_version=1,
            input_model=AudioPipelineTaskInput,
            result_model=AudioPipelineTaskResult,
            policy=TaskPolicy(
                timeout_seconds=1_800,
                max_attempts=5,
                initial_backoff_seconds=20,
                max_backoff_seconds=600,
                lease_seconds=90,
                retryable_error_codes=frozenset(
                    {
                        "audio_storage_head_failed",
                        "audio_storage_download_failed",
                        "audio_storage_write_failed",
                        "audio_transcription_ai_failed",
                        "audio_scoring_ai_failed",
                    }
                ),
            ),
            handler=handler,
            metric_tags=(
                ("domain", "audio_assessment"),
                ("workload", "full_file_pipeline"),
            ),
            allowed_data_classifications=frozenset({"confidential"}),
            max_payload_bytes=2_048,
        )
    )


__all__ = ["register_audio_task_definition"]
