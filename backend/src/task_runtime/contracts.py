"""Stable task-runtime contracts consumed by business application modules."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from task_runtime.errors import TaskRuntimeError
from task_runtime.payload_guard import assert_safe_persisted_payload

_MAX_RESULT_ITEMS_PER_GROUP = 100
_MAX_RESULT_ITEMS_BYTES = 16_384


class TaskState(StrEnum):
    """Canonical lifecycle from the accepted Slice 0 state-machine contract."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"


class TaskResultKind(StrEnum):
    """Typed result semantics that intentionally do not add task states."""

    COMPLETE = "complete"
    PARTIAL_SUCCESS = "partial_success"
    WAITING_INPUT = "waiting_input"


class ActorContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)


class TaskPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timeout_seconds: int = Field(default=300, ge=1, le=86_400)
    max_attempts: int = Field(default=3, ge=1, le=100)
    initial_backoff_seconds: int = Field(default=30, ge=1, le=86_400)
    max_backoff_seconds: int = Field(default=900, ge=1, le=604_800)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    lease_seconds: int = Field(default=60, ge=5, le=3_600)
    retryable_error_codes: frozenset[str] = Field(default_factory=frozenset)
    terminal_error_codes: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("max_backoff_seconds")
    @classmethod
    def validate_max_backoff(cls, value: int, info: Any) -> int:
        initial = info.data.get("initial_backoff_seconds")
        if isinstance(initial, int) and value < initial:
            raise ValueError("max_backoff_seconds must be >= initial_backoff_seconds")
        return value


class TaskCommand(BaseModel):
    """Internal application command; it is never accepted as an HTTP payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    schema_version: int = Field(ge=1)
    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=200)
    input_payload: dict[str, Any]
    priority: int = Field(default=50, ge=0, le=100)
    deadline_at: datetime | None = None
    next_run_at: datetime | None = None
    correlation_id: str = Field(min_length=1, max_length=160)
    causation_id: str | None = Field(default=None, max_length=160)
    trace_id: str | None = Field(default=None, max_length=160)
    data_classification: str = Field(default="internal", max_length=40)

    @model_validator(mode="after")
    def validate_schedule_before_deadline(self) -> TaskCommand:
        if (
            self.next_run_at is not None
            and self.deadline_at is not None
            and self.next_run_at >= self.deadline_at
        ):
            raise ValueError("next_run_at must be earlier than deadline_at")
        return self


class TaskReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    state: TaskState
    organization_id: str
    resource_type: str
    resource_id: str
    created_at: datetime


class ClaimedTask(BaseModel):
    """A fenced execution grant. The raw lease token must never be persisted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_type: str
    schema_version: int
    organization_id: str
    actor_id: str
    resource_type: str
    resource_id: str
    input_payload: dict[str, Any]
    timeout_seconds: int = Field(ge=1, le=86_400)
    lease_seconds: int = Field(ge=5, le=3_600)
    max_attempts: int = Field(ge=1, le=100)
    deadline_at: datetime | None
    retry_policy: TaskPolicy
    attempt_id: str
    attempt_no: int
    worker_id: str
    lease_token: str
    lease_expires_at: datetime
    fence_generation: int
    correlation_id: str
    trace_id: str | None

    @model_validator(mode="after")
    def validate_frozen_policy_snapshot(self) -> ClaimedTask:
        if self.timeout_seconds != self.retry_policy.timeout_seconds:
            raise ValueError("Claim timeout must match the frozen retry policy.")
        if self.lease_seconds != self.retry_policy.lease_seconds:
            raise ValueError("Claim lease must match the frozen retry policy.")
        if self.max_attempts != self.retry_policy.max_attempts:
            raise ValueError("Claim attempts must match the frozen retry policy.")
        return self


class TaskProgressProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    current: int | None = None
    total: int | None = None
    stage: str | None = None
    label: str | None = None


class TaskProgressUpdate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=1)
    stage: str | None = Field(default=None, min_length=1, max_length=120)
    label: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_progress_bounds(self) -> TaskProgressUpdate:
        if (
            self.current is not None
            and self.total is not None
            and self.current > self.total
        ):
            raise ValueError("current must be <= total")
        if all(
            value is None
            for value in (self.current, self.total, self.stage, self.label)
        ):
            raise ValueError("at least one progress field is required")
        return self


class TaskErrorProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    retryable: bool
    message: str


class TaskResultItemRef(BaseModel):
    """Opaque business-object reference; shared task tables never store content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    resource_type: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_.-]+$",
    )
    resource_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )


class TaskCompletion(BaseModel):
    """Validated handler result plus a reference to the formal business object."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    structured_payload: dict[str, Any]
    result_kind: TaskResultKind
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=500)
    saved_items: list[TaskResultItemRef] = Field(
        default_factory=list,
        max_length=_MAX_RESULT_ITEMS_PER_GROUP,
    )
    remaining_items: list[TaskResultItemRef] = Field(
        default_factory=list,
        max_length=_MAX_RESULT_ITEMS_PER_GROUP,
    )
    retryable_items: list[TaskResultItemRef] = Field(
        default_factory=list,
        max_length=_MAX_RESULT_ITEMS_PER_GROUP,
    )

    @model_validator(mode="after")
    def validate_result_item_references(self) -> TaskCompletion:
        self.result_items_payload()
        return self

    def result_items_payload(self) -> dict[str, list[dict[str, str]]]:
        payload: dict[str, list[dict[str, str]]] = {}
        for field_name in (
            "saved_items",
            "remaining_items",
            "retryable_items",
        ):
            items = getattr(self, field_name)
            if len(items) > _MAX_RESULT_ITEMS_PER_GROUP:
                raise ValueError(
                    f"{field_name} 最多包含 {_MAX_RESULT_ITEMS_PER_GROUP} 个结果引用。"
                )
            payload[field_name] = [
                TaskResultItemRef.model_validate(item).model_dump(mode="json")
                for item in items
            ]
        try:
            assert_safe_persisted_payload(
                payload,
                max_bytes=_MAX_RESULT_ITEMS_BYTES,
                code_prefix="TASK_RESULT_REFS",
                subject_label="任务结果项引用",
            )
        except TaskRuntimeError as exc:
            raise ValueError(exc.message) from exc
        return payload


class TaskProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_type: str
    schema_version: int
    organization_id: str
    actor_id: str
    resource_type: str
    resource_id: str
    state: TaskState
    priority: int
    attempt_count: int
    max_attempts: int
    next_run_at: datetime | None
    deadline_at: datetime | None
    progress: TaskProgressProjection | None
    result_kind: TaskResultKind | None
    result_location: str | None
    error: TaskErrorProjection | None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskPage(BaseModel):
    """Stable, owner-scoped task page for resumable user task centers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[TaskProjection, ...]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool


@runtime_checkable
class TaskRuntimePort(Protocol):
    async def enqueue(self, command: TaskCommand) -> TaskReference: ...

    async def get(self, task_id: str, viewer: ActorContext) -> TaskProjection: ...

    async def request_cancel(
        self,
        task_id: str,
        actor: ActorContext,
        *,
        idempotency_key: str | None = None,
    ) -> TaskProjection: ...


@runtime_checkable
class TaskRuntimeInboxPort(Protocol):
    async def list_for_actor(
        self,
        viewer: ActorContext,
        *,
        page: int = 1,
        page_size: int = 20,
        state: TaskState | None = None,
    ) -> TaskPage: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
