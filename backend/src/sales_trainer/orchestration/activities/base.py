"""Stable protocol shared by all activity execution adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sales_trainer.models import NewcomerTrainingActivityAttempt
from sales_trainer.orchestration.contracts import ActivityConfig
from sales_trainer.orchestration.graph import PathIssue


@dataclass(frozen=True, slots=True)
class ActivityExecutionContext:
    learner_id: str
    enrollment_id: str
    path_revision_id: str
    phase_id: str
    module_id: str
    activity: ActivityConfig


@dataclass(frozen=True, slots=True)
class ActivityProjection:
    activity_id: str
    activity_type: str
    status: str
    completed: bool
    score: float | None
    max_score: float | None
    passed: bool | None
    next_action: dict[str, object] | None
    message: str | None


class ActivityHandler(Protocol):
    type_key: str

    async def validate_config(
        self, activity: ActivityConfig
    ) -> tuple[PathIssue, ...]: ...

    async def check_access(self, context: ActivityExecutionContext) -> None: ...

    async def project(
        self, context: ActivityExecutionContext
    ) -> ActivityProjection: ...

    async def refresh_attempt(
        self,
        context: ActivityExecutionContext,
        attempt: NewcomerTrainingActivityAttempt,
    ) -> NewcomerTrainingActivityAttempt: ...


__all__ = ["ActivityExecutionContext", "ActivityHandler", "ActivityProjection"]
