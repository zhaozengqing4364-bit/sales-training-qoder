from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class TrainingTaskPortError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True, slots=True)
class TrainingTaskPracticeTemplate:
    template_id: str
    status: str
    curriculum_plan: dict[str, Any] | None


TrainingTaskPracticeTemplateResolver = Callable[
    [AsyncSession, str],
    Awaitable[TrainingTaskPracticeTemplate | None],
]

_practice_template_resolver: TrainingTaskPracticeTemplateResolver | None = None


def register_training_task_practice_template_resolver(
    resolver: TrainingTaskPracticeTemplateResolver,
) -> None:
    global _practice_template_resolver
    _practice_template_resolver = resolver


async def resolve_registered_training_task_practice_template(
    db: AsyncSession,
    template_id: str,
) -> TrainingTaskPracticeTemplate | None:
    if _practice_template_resolver is None:
        raise TrainingTaskPortError("[PRACTICE_TEMPLATE_RESOLVER_NOT_REGISTERED]")
    return await _practice_template_resolver(db, template_id)


def clear_training_task_ports() -> None:
    global _practice_template_resolver
    _practice_template_resolver = None
