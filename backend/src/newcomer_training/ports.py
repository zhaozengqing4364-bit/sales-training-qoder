"""Narrow ports owned by newcomer training and implemented at composition seams."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


@runtime_checkable
class PublishedActivityResourcePort(Protocol):
    async def require_published(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> None: ...


@runtime_checkable
class PublishedCompetencyMappingPort(Protocol):
    async def require_valid(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
    ) -> None: ...

    async def record_published(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: tuple[str, ...],
        actor_id: str,
    ) -> None: ...


class ReleaseDependency(BaseModel):
    """One exact revision inspected through an application-root adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=160)
    revision_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=240)
    status: str = Field(min_length=1, max_length=40)
    content_hash: str = Field(min_length=1, max_length=160)
    publish_required: bool = False
    expected_resource_version: int | None = Field(default=None, ge=1)
    dependencies: tuple[dict[str, str], ...] = ()
    issues: tuple[dict[str, str], ...] = ()


@runtime_checkable
class ReleaseDependencyPort(Protocol):
    async def inspect(
        self,
        *,
        organization_id: str,
        activity_type: str,
        revision_id: str,
    ) -> ReleaseDependency: ...

    async def inspect_resource(
        self,
        *,
        organization_id: str,
        resource_type: str,
        revision_id: str,
    ) -> ReleaseDependency: ...

    async def publish(
        self,
        *,
        organization_id: str,
        actor_id: str,
        capability_set: frozenset[str],
        dependency: ReleaseDependency,
        idempotency_key: str,
        reason: str,
        trace_id: str | None,
    ) -> ReleaseDependency: ...

class ActivityRuntimeStart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    enrollment_id: str = Field(min_length=1, max_length=160)
    path_revision_id: str = Field(min_length=1, max_length=160)
    activity_id: str = Field(min_length=1, max_length=160)
    activity_type: str = Field(min_length=1, max_length=40)
    attempt_id: str = Field(min_length=1, max_length=160)
    config: dict[str, Any]
    competency_keys: tuple[str, ...] = ()
    idempotency_key: str = Field(min_length=1, max_length=200)
    trace_id: str | None = Field(default=None, max_length=160)
    relearn_of_detail_id: str | None = Field(default=None, max_length=160)


class ActivityRuntimeCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    attempt_id: str = Field(min_length=1, max_length=160)
    activity_id: str = Field(min_length=1, max_length=160)
    activity_type: str = Field(min_length=1, max_length=40)
    command_type: str = Field(min_length=1, max_length=80)
    expected_detail_version: int = Field(ge=1)
    payload: dict[str, Any]
    config: dict[str, Any]
    competency_keys: tuple[str, ...] = ()
    idempotency_key: str = Field(min_length=1, max_length=200)
    trace_id: str | None = Field(default=None, max_length=160)


class ActivityRuntimeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail_id: str
    detail_status: str
    detail_version: int
    task_id: str | None = None
    runner: dict[str, Any]
    available_commands: tuple[str, ...]


@runtime_checkable
class ActivityRuntimePort(Protocol):
    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        activity_id: str,
        activity_type: str,
        config: dict[str, Any],
        attempt_id: str | None,
    ) -> ActivityRuntimeResult | None: ...

    async def start(self, command: ActivityRuntimeStart) -> ActivityRuntimeResult: ...

    async def execute(
        self, command: ActivityRuntimeCommand
    ) -> ActivityRuntimeResult: ...


__all__ = [
    "ActivityRuntimeCommand",
    "ActivityRuntimePort",
    "ActivityRuntimeResult",
    "ActivityRuntimeStart",
    "PublishedActivityResourcePort",
    "PublishedCompetencyMappingPort",
    "ReleaseDependency",
    "ReleaseDependencyPort",
]
