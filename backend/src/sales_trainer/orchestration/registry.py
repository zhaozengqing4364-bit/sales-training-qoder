"""Non-dynamic registry for the remaining legacy activity capabilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.orchestration.activities.base import ActivityHandler
from sales_trainer.orchestration.errors import NewcomerOrchestrationError

SUPPORTED_ACTIVITY_TYPES = (
    "lesson",
    "quiz",
    "audio_assessment",
    "realtime_roleplay",
    "assignment",
)


class ActivityTypeRegistry:
    def __init__(self, handlers: Iterable[ActivityHandler]) -> None:
        by_type: dict[str, ActivityHandler] = {}
        for handler in handlers:
            type_key = handler.type_key
            if type_key not in SUPPORTED_ACTIVITY_TYPES:
                raise NewcomerOrchestrationError(
                    "[NEWCOMER_ACTIVITY_TYPE_UNSUPPORTED]", "不支持这种训练活动类型。"
                )
            if type_key in by_type:
                raise NewcomerOrchestrationError(
                    "[NEWCOMER_ACTIVITY_TYPE_DUPLICATE]", "训练活动处理器重复注册。"
                )
            by_type[type_key] = handler
        self._handlers = by_type

    @property
    def type_keys(self) -> tuple[str, ...]:
        return tuple(key for key in SUPPORTED_ACTIVITY_TYPES if key in self._handlers)

    def handler_for(self, type_key: str) -> ActivityHandler:
        handler = self._handlers.get(type_key)
        if handler is None:
            raise NewcomerOrchestrationError(
                "[NEWCOMER_ACTIVITY_TYPE_UNSUPPORTED]", "不支持这种训练活动类型。"
            )
        return cast(ActivityHandler, handler)


__all__ = ["ActivityTypeRegistry", "SUPPORTED_ACTIVITY_TYPES"]


def build_activity_registry(db: AsyncSession) -> ActivityTypeRegistry:
    from sales_trainer.orchestration.activities.assignment import (
        AssignmentActivityHandler,
    )
    from sales_trainer.orchestration.activities.audio_assessment import (
        AudioAssessmentActivityHandler,
    )
    from sales_trainer.orchestration.activities.lesson import LessonActivityHandler
    from sales_trainer.orchestration.activities.quiz import QuizActivityHandler
    from sales_trainer.orchestration.activities.realtime_roleplay import (
        RealtimeRoleplayActivityHandler,
    )

    return ActivityTypeRegistry(
        [
            LessonActivityHandler(db),
            QuizActivityHandler(db),
            AudioAssessmentActivityHandler(db),
            RealtimeRoleplayActivityHandler(db),
            AssignmentActivityHandler(db),
        ]
    )


__all__.append("build_activity_registry")
