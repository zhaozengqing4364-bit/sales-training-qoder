"""Explicit API/Worker registration for foundation-domain durable tasks."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_coach.task_definitions import register_coach_task_definitions
from ai_platform import AIInvocationPort
from audio_assessment.storage import build_audio_object_storage
from audio_assessment.task_definitions import register_audio_task_definition
from common.db.session import AsyncSessionLocal
from foundation_ai_composition import (
    build_foundation_ai_invocation_factory,
    build_foundation_prompt_compilation_service,
)
from learning.task_definitions import register_learning_task_definitions
from newcomer_foundation_composition import (
    SQLAlchemyActivityOutcomeWriter,
    SQLAlchemyAudioOutcomeWriter,
)
from task_runtime.composition import get_application_task_registry

AIInvocationFactory = Callable[[], AIInvocationPort]

_application_ai_factory: AIInvocationFactory | None = None


def configure_foundation_ai_invocation_factory(
    factory: AIInvocationFactory | None,
) -> None:
    """Configure one explicit governed-AI composition; never select a fake implicitly."""

    global _application_ai_factory
    _application_ai_factory = factory


def register_foundation_api_tasks() -> None:
    """Register schemas/policies so API enqueue validates before persistence."""

    register_learning_task_definitions(get_application_task_registry())
    register_audio_task_definition(get_application_task_registry())
    register_coach_task_definitions(get_application_task_registry())


def register_foundation_worker_tasks(
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ai_factory: AIInvocationFactory | None = None,
) -> None:
    """Register executable handlers; fail closed without a real AI composition."""

    effective_ai_factory = (
        ai_factory
        or _application_ai_factory
        or build_foundation_ai_invocation_factory(
            session_factory=session_factory,
        )
    )
    register_learning_task_definitions(
        get_application_task_registry(),
        session_factory=session_factory,
        ai_factory=effective_ai_factory,
        outcome_writer_factory=SQLAlchemyActivityOutcomeWriter,
    )
    register_audio_task_definition(
        get_application_task_registry(),
        session_factory=session_factory,
        ai_factory=effective_ai_factory,
        outcome_writer_factory=SQLAlchemyAudioOutcomeWriter,
        prompt_compiler=build_foundation_prompt_compilation_service(
            session_factory=session_factory,
        ),
        storage=build_audio_object_storage(),
    )
    register_coach_task_definitions(
        get_application_task_registry(),
        session_factory=session_factory,
        ai_factory=effective_ai_factory,
        prompt_compiler=build_foundation_prompt_compilation_service(
            session_factory=session_factory,
        ),
    )


__all__ = [
    "configure_foundation_ai_invocation_factory",
    "register_foundation_api_tasks",
    "register_foundation_worker_tasks",
]
