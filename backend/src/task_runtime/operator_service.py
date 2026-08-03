"""Scoped System Admin application service for durable task operations."""

from __future__ import annotations

import hashlib
import json
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as BinasciiError
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from task_runtime.contracts import (
    ActorContext,
    Clock,
    TaskCommand,
    TaskErrorProjection,
    TaskProgressProjection,
    TaskReference,
    TaskResultKind,
    TaskState,
)
from task_runtime.errors import (
    IdempotencyKeyReusedError,
    TaskAccessDeniedError,
    TaskNotFoundError,
    TaskQueryInvalidError,
    TaskTransitionError,
)
from task_runtime.models import (
    DurableTask,
    OutboxEvent,
    TaskAttempt,
    TaskLease,
    TaskOperatorScopeGrant,
    TaskPayloadArtifact,
    TaskTypeControl,
    TaskTypeControlCommand,
)
from task_runtime.outbox import append_task_event
from task_runtime.registry import TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime, SystemClock


class TaskAccessAction(StrEnum):
    READ = "read"
    OPERATE = "operate"


class OperatorActor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)


class TaskAccessPolicyPort(Protocol):
    async def allows(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resource_type: str | None,
        resource_id: str | None,
        action: TaskAccessAction,
    ) -> bool: ...

    async def allowed_resource_keys(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resources: frozenset[tuple[str, str]],
        action: TaskAccessAction,
    ) -> frozenset[tuple[str, str]]: ...


class DenyAllTaskAccessPolicy:
    """Production-safe fallback until authoritative org/object grants are wired."""

    async def allows(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resource_type: str | None,
        resource_id: str | None,
        action: TaskAccessAction,
    ) -> bool:
        del actor, organization_id, resource_type, resource_id, action
        return False

    async def allowed_resource_keys(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resources: frozenset[tuple[str, str]],
        action: TaskAccessAction,
    ) -> frozenset[tuple[str, str]]:
        del actor, organization_id, resources, action
        return frozenset()


class SQLAlchemyTaskAccessPolicy:
    """Persisted scope adapter; absence of an active grant denies access."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allows(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resource_type: str | None,
        resource_id: str | None,
        action: TaskAccessAction,
    ) -> bool:
        permission_column = (
            TaskOperatorScopeGrant.can_read
            if action is TaskAccessAction.READ
            else TaskOperatorScopeGrant.can_operate
        )
        scope_filter = and_(
            TaskOperatorScopeGrant.resource_type == "",
            TaskOperatorScopeGrant.resource_id == "",
        )
        if resource_type is not None and resource_id is not None:
            scope_filter = or_(
                scope_filter,
                and_(
                    TaskOperatorScopeGrant.resource_type == resource_type,
                    TaskOperatorScopeGrant.resource_id == resource_id,
                ),
            )
        result = await self._session.execute(
            select(TaskOperatorScopeGrant.grant_id)
            .where(TaskOperatorScopeGrant.actor_id == actor.actor_id)
            .where(TaskOperatorScopeGrant.organization_id == organization_id)
            .where(TaskOperatorScopeGrant.is_active.is_(True))
            .where(TaskOperatorScopeGrant.expires_at > func.now())
            .where(TaskOperatorScopeGrant.revoked_at.is_(None))
            .where(permission_column.is_(True))
            .where(scope_filter)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def allowed_resource_keys(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resources: frozenset[tuple[str, str]],
        action: TaskAccessAction,
    ) -> frozenset[tuple[str, str]]:
        if not resources:
            return frozenset()
        permission_column = (
            TaskOperatorScopeGrant.can_read
            if action is TaskAccessAction.READ
            else TaskOperatorScopeGrant.can_operate
        )
        result = await self._session.execute(
            select(
                TaskOperatorScopeGrant.resource_type,
                TaskOperatorScopeGrant.resource_id,
            )
            .where(TaskOperatorScopeGrant.actor_id == actor.actor_id)
            .where(TaskOperatorScopeGrant.organization_id == organization_id)
            .where(TaskOperatorScopeGrant.is_active.is_(True))
            .where(TaskOperatorScopeGrant.expires_at > func.now())
            .where(TaskOperatorScopeGrant.revoked_at.is_(None))
            .where(permission_column.is_(True))
            .where(
                or_(
                    and_(
                        TaskOperatorScopeGrant.resource_type == "",
                        TaskOperatorScopeGrant.resource_id == "",
                    ),
                    tuple_(
                        TaskOperatorScopeGrant.resource_type,
                        TaskOperatorScopeGrant.resource_id,
                    ).in_(sorted(resources)),
                )
            )
        )
        granted = {(str(row[0]), str(row[1])) for row in result}
        if ("", "") in granted:
            return resources
        return frozenset(granted & resources)


class TaskViewModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_type: str
    organization_id: str
    resource_type: str
    resource_id: str
    state: TaskState
    status_label: str
    current_step: str
    progress: TaskProgressProjection | None
    can_cancel: bool
    can_redrive: bool
    result_kind: TaskResultKind | None
    result_location: str | None
    partial_success_message: str | None
    error: TaskErrorProjection | None
    attempt_count: int
    max_attempts: int
    updated_at: datetime
    stale: bool


class TaskTypeControlView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    task_type: str
    is_paused: bool
    version: int
    reason: str | None
    max_concurrency: int | None
    rate_limit_per_minute: int | None


class TaskRuntimeHealth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    queue_depth: int
    running_count: int
    retry_wait_count: int
    dead_letter_count: int
    expired_lease_count: int
    outbox_lag_seconds: float
    metrics_window_minutes: int
    retry_rate: float
    average_processing_latency_ms: float


class TaskListItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_type: str
    organization_id: str
    resource_type: str
    resource_id: str
    state: TaskState
    status_label: str
    attempt_count: int
    max_attempts: int
    can_cancel: bool
    can_redrive: bool
    updated_at: datetime


class TaskListPage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[TaskListItem]
    limit: int
    next_cursor: str | None
    has_more: bool


_STATUS_LABELS = {
    TaskState.QUEUED: "等待处理",
    TaskState.RUNNING: "正在处理",
    TaskState.RETRY_WAIT: "等待自动重试",
    TaskState.CANCEL_REQUESTED: "正在安全取消",
    TaskState.CANCELLED: "已取消",
    TaskState.SUCCEEDED: "已完成",
    TaskState.DEAD_LETTER: "需要人工处理",
}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class TaskOperatorService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: TaskRegistry,
        access_policy: TaskAccessPolicyPort,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._registry = registry
        self._access_policy = access_policy
        self._clock = clock or SystemClock()

    async def get_task(self, task_id: str, *, actor: OperatorActor) -> TaskViewModel:
        task = await self._load_task(task_id)
        await self._authorize_task(task, actor=actor, action=TaskAccessAction.READ)
        projection = await SQLAlchemyTaskRuntime(
            self._session,
            registry=self._registry,
            clock=self._clock,
        ).get(
            task_id,
            ActorContext(
                organization_id=task.organization_id,
                actor_id=actor.actor_id,
                capabilities=actor.capabilities,
            ),
        )
        state = projection.state
        may_operate = await self._can_access_task(
            task,
            actor=actor,
            action=TaskAccessAction.OPERATE,
        )
        partial_message = None
        if projection.result_kind is TaskResultKind.PARTIAL_SUCCESS:
            partial_message = "部分结果已保存，可从结果位置继续处理未完成项。"
        return TaskViewModel(
            task_id=projection.task_id,
            task_type=projection.task_type,
            organization_id=projection.organization_id,
            resource_type=projection.resource_type,
            resource_id=projection.resource_id,
            state=state,
            status_label=_STATUS_LABELS[state],
            current_step=(
                projection.progress.label
                if projection.progress and projection.progress.label
                else _STATUS_LABELS[state]
            ),
            progress=projection.progress,
            can_cancel=may_operate
            and state in {TaskState.QUEUED, TaskState.RUNNING, TaskState.RETRY_WAIT},
            can_redrive=may_operate and state is TaskState.DEAD_LETTER,
            result_kind=projection.result_kind,
            result_location=projection.result_location,
            partial_success_message=partial_message,
            error=projection.error,
            attempt_count=projection.attempt_count,
            max_attempts=projection.max_attempts,
            updated_at=projection.updated_at,
            stale=self._clock.now() - projection.updated_at > timedelta(minutes=5),
        )

    async def list_tasks(
        self,
        *,
        organization_id: str,
        actor: OperatorActor,
        states: frozenset[TaskState] | None = None,
        task_type: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> TaskListPage:
        await self._authorize_scope(
            organization_id=organization_id,
            actor=actor,
            action=TaskAccessAction.READ,
        )
        filters = [DurableTask.organization_id == organization_id]
        if states:
            filters.append(DurableTask.state.in_([state.value for state in states]))
        if task_type:
            filters.append(DurableTask.task_type == task_type)
        if cursor:
            cursor_updated_at, cursor_task_id = self._decode_cursor(cursor)
            filters.append(
                or_(
                    DurableTask.updated_at < cursor_updated_at,
                    and_(
                        DurableTask.updated_at == cursor_updated_at,
                        DurableTask.task_id < cursor_task_id,
                    ),
                )
            )
        tasks_result = await self._session.execute(
            select(DurableTask)
            .where(*filters)
            .order_by(DurableTask.updated_at.desc(), DurableTask.task_id.desc())
            .limit(limit + 1)
        )
        rows = list(tasks_result.scalars())
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        page_resource_keys = frozenset(
            (task.resource_type, task.resource_id) for task in page_rows
        )
        operable_resource_keys = (
            await self._access_policy.allowed_resource_keys(
                actor,
                organization_id=organization_id,
                resources=page_resource_keys,
                action=TaskAccessAction.OPERATE,
            )
            if "task_runtime.operate" in actor.capabilities
            else frozenset()
        )
        items: list[TaskListItem] = []
        for task in page_rows:
            state = TaskState(task.state)
            may_operate = (
                task.resource_type,
                task.resource_id,
            ) in operable_resource_keys
            items.append(
                TaskListItem(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    organization_id=task.organization_id,
                    resource_type=task.resource_type,
                    resource_id=task.resource_id,
                    state=state,
                    status_label=_STATUS_LABELS[state],
                    attempt_count=task.attempt_count,
                    max_attempts=task.max_attempts,
                    can_cancel=may_operate
                    and state
                    in {TaskState.QUEUED, TaskState.RUNNING, TaskState.RETRY_WAIT},
                    can_redrive=may_operate and state is TaskState.DEAD_LETTER,
                    updated_at=task.updated_at,
                )
            )
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_cursor(last.updated_at, last.task_id)
        return TaskListPage(
            items=items,
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def pause_task_type(
        self,
        *,
        organization_id: str,
        task_type: str,
        actor: OperatorActor,
        idempotency_key: str,
        reason: str,
    ) -> TaskTypeControlView:
        return await self._set_task_type_control(
            organization_id=organization_id,
            task_type=task_type,
            actor=actor,
            idempotency_key=idempotency_key,
            reason=reason,
            is_paused=True,
        )

    async def resume_task_type(
        self,
        *,
        organization_id: str,
        task_type: str,
        actor: OperatorActor,
        idempotency_key: str,
        reason: str,
    ) -> TaskTypeControlView:
        return await self._set_task_type_control(
            organization_id=organization_id,
            task_type=task_type,
            actor=actor,
            idempotency_key=idempotency_key,
            reason=reason,
            is_paused=False,
        )

    async def configure_task_type_limits(
        self,
        *,
        organization_id: str,
        task_type: str,
        actor: OperatorActor,
        idempotency_key: str,
        max_concurrency: int | None,
        rate_limit_per_minute: int | None,
        reason: str,
    ) -> TaskTypeControlView:
        if max_concurrency is not None and max_concurrency < 1:
            raise TaskQueryInvalidError("最大并发数必须为正数。")
        if rate_limit_per_minute is not None and rate_limit_per_minute < 1:
            raise TaskQueryInvalidError("每分钟速率上限必须为正数。")
        self._registry.definitions_for_type(task_type)
        await self._authorize_scope(
            organization_id=organization_id,
            actor=actor,
            action=TaskAccessAction.OPERATE,
        )
        now = self._clock.now()
        await self._session.execute(
            postgresql_insert(TaskTypeControl)
            .values(
                control_id=str(uuid.uuid4()),
                organization_id=organization_id,
                task_type=task_type,
                is_paused=False,
                max_concurrency=max_concurrency,
                rate_limit_per_minute=rate_limit_per_minute,
                version=1,
                reason=reason,
                updated_by=actor.actor_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["organization_id", "task_type"])
        )
        control = await self._load_control(
            organization_id=organization_id,
            task_type=task_type,
            for_update=True,
        )
        if control is None:
            raise RuntimeError("Task type control upsert did not create a row.")
        key_hash = _hash_text(idempotency_key)
        fingerprint = _hash_json(
            {
                "organization_id": organization_id,
                "task_type": task_type,
                "action": "configure_limits",
                "actor_id": actor.actor_id,
                "max_concurrency": max_concurrency,
                "rate_limit_per_minute": rate_limit_per_minute,
                "reason": reason,
            }
        )
        command_result = await self._session.execute(
            select(TaskTypeControlCommand)
            .where(TaskTypeControlCommand.organization_id == organization_id)
            .where(TaskTypeControlCommand.task_type == task_type)
            .where(TaskTypeControlCommand.action == "configure_limits")
            .where(TaskTypeControlCommand.idempotency_key_hash == key_hash)
            .limit(1)
        )
        existing = command_result.scalar_one_or_none()
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyKeyReusedError()
            return self._control_view(control)
        if (
            control.max_concurrency != max_concurrency
            or control.rate_limit_per_minute != rate_limit_per_minute
            or control.reason != reason
        ):
            control.max_concurrency = max_concurrency
            control.rate_limit_per_minute = rate_limit_per_minute
            control.reason = reason
            control.updated_by = actor.actor_id
            control.updated_at = now
            control.version += 1
        self._session.add(
            TaskTypeControlCommand(
                command_id=str(uuid.uuid4()),
                organization_id=organization_id,
                task_type=task_type,
                action="configure_limits",
                actor_id=actor.actor_id,
                idempotency_key_hash=key_hash,
                request_fingerprint=fingerprint,
                result_version=control.version,
                created_at=now,
            )
        )
        await self._session.flush()
        return self._control_view(control)

    async def redrive_dead_letter(
        self,
        *,
        task_id: str,
        actor: OperatorActor,
        idempotency_key: str,
        reason: str | None = None,
    ) -> TaskReference:
        source = await self._load_task(task_id, for_update=True)
        await self._authorize_task(source, actor=actor, action=TaskAccessAction.OPERATE)
        if TaskState(source.state) is not TaskState.DEAD_LETTER:
            raise TaskTransitionError(source.state, "redrive")
        artifact_result = await self._session.execute(
            select(TaskPayloadArtifact)
            .where(TaskPayloadArtifact.artifact_id == source.input_artifact_id)
            .limit(1)
        )
        artifact = artifact_result.scalar_one()
        redrive_key = "redrive:" + _hash_text(f"{task_id}:{idempotency_key}")
        runtime = SQLAlchemyTaskRuntime(
            self._session,
            registry=self._registry,
            clock=self._clock,
        )
        reference = await runtime.enqueue(
            TaskCommand(
                task_type=source.task_type,
                schema_version=source.schema_version,
                organization_id=source.organization_id,
                actor_id=source.actor_id,
                resource_type=source.resource_type,
                resource_id=source.resource_id,
                idempotency_key=redrive_key,
                input_payload=artifact.payload_json,
                priority=source.priority,
                correlation_id=source.correlation_id,
                causation_id=source.task_id,
                trace_id=source.trace_id,
                data_classification=artifact.data_classification,
            )
        )
        redriven = await self._load_task(reference.task_id)
        await append_task_event(
            self._session,
            redriven,
            event_type="TaskDeadLetterRedriven",
            occurred_at=redriven.created_at,
            actor_id=actor.actor_id,
            details={
                "source_task_id": source.task_id,
                **({"reason": reason.strip()} if reason and reason.strip() else {}),
            },
        )
        return reference

    async def request_cancel(
        self,
        *,
        task_id: str,
        actor: OperatorActor,
        idempotency_key: str,
        reason: str | None = None,
    ) -> TaskViewModel:
        task = await self._load_task(task_id)
        await self._authorize_task(
            task,
            actor=actor,
            action=TaskAccessAction.OPERATE,
        )
        before_state = task.state
        await SQLAlchemyTaskRuntime(
            self._session,
            registry=self._registry,
            clock=self._clock,
        ).request_cancel(
            task_id,
            ActorContext(
                organization_id=task.organization_id,
                actor_id=actor.actor_id,
                capabilities=actor.capabilities,
            ),
            idempotency_key=idempotency_key,
        )
        result = await self.get_task(task_id, actor=actor)
        if before_state != result.state.value and reason and reason.strip():
            refreshed = await self._load_task(task_id)
            await append_task_event(
                self._session,
                refreshed,
                event_type="TaskCancellationReasonRecorded",
                occurred_at=self._clock.now(),
                actor_id=actor.actor_id,
                details={"reason": reason.strip()},
            )
        return result

    async def health(
        self, *, organization_id: str, actor: OperatorActor
    ) -> TaskRuntimeHealth:
        await self._authorize_scope(
            organization_id=organization_id,
            actor=actor,
            action=TaskAccessAction.READ,
        )
        counts_result = await self._session.execute(
            select(
                func.count().filter(DurableTask.state == TaskState.QUEUED.value),
                func.count().filter(DurableTask.state == TaskState.RUNNING.value),
                func.count().filter(DurableTask.state == TaskState.RETRY_WAIT.value),
                func.count().filter(DurableTask.state == TaskState.DEAD_LETTER.value),
            ).where(DurableTask.organization_id == organization_id)
        )
        queue, running, retry_wait, dead_letter = counts_result.one()
        expired_result = await self._session.execute(
            select(func.count(TaskLease.lease_id))
            .join(DurableTask, DurableTask.task_id == TaskLease.task_id)
            .where(DurableTask.organization_id == organization_id)
            .where(TaskLease.expires_at <= self._clock.now())
        )
        oldest_result = await self._session.execute(
            select(func.min(OutboxEvent.occurred_at))
            .where(OutboxEvent.organization_id == organization_id)
            .where(OutboxEvent.published_at.is_(None))
            .where(OutboxEvent.dead_lettered_at.is_(None))
        )
        oldest = oldest_result.scalar_one_or_none()
        lag = max((self._clock.now() - oldest).total_seconds(), 0.0) if oldest else 0.0
        metrics_window_minutes = 15
        metrics_cutoff = self._clock.now() - timedelta(minutes=metrics_window_minutes)
        attempt_metrics_result = await self._session.execute(
            select(
                func.count(TaskAttempt.attempt_id),
                func.count(TaskAttempt.attempt_id).filter(
                    TaskAttempt.outcome.in_(["retry_wait", "lease_expired"])
                ),
                func.avg(
                    func.extract(
                        "epoch", TaskAttempt.finished_at - TaskAttempt.started_at
                    )
                    * 1000
                ),
            )
            .join(DurableTask, DurableTask.task_id == TaskAttempt.task_id)
            .where(DurableTask.organization_id == organization_id)
            .where(TaskAttempt.started_at >= metrics_cutoff)
            .where(TaskAttempt.finished_at.is_not(None))
        )
        attempt_count, retry_count, average_latency = attempt_metrics_result.one()
        retry_rate = (
            float(retry_count or 0) / float(attempt_count) if attempt_count else 0.0
        )
        return TaskRuntimeHealth(
            organization_id=organization_id,
            queue_depth=int(queue or 0),
            running_count=int(running or 0),
            retry_wait_count=int(retry_wait or 0),
            dead_letter_count=int(dead_letter or 0),
            expired_lease_count=int(expired_result.scalar_one() or 0),
            outbox_lag_seconds=lag,
            metrics_window_minutes=metrics_window_minutes,
            retry_rate=retry_rate,
            average_processing_latency_ms=float(average_latency or 0.0),
        )

    async def _set_task_type_control(
        self,
        *,
        organization_id: str,
        task_type: str,
        actor: OperatorActor,
        idempotency_key: str,
        reason: str,
        is_paused: bool,
    ) -> TaskTypeControlView:
        self._registry.definitions_for_type(task_type)
        await self._authorize_scope(
            organization_id=organization_id,
            actor=actor,
            action=TaskAccessAction.OPERATE,
        )
        action = "pause" if is_paused else "resume"
        key_hash = _hash_text(idempotency_key)
        fingerprint = _hash_json(
            {
                "organization_id": organization_id,
                "task_type": task_type,
                "action": action,
                "actor_id": actor.actor_id,
                "reason": reason,
            }
        )
        now = self._clock.now()
        await self._session.execute(
            postgresql_insert(TaskTypeControl)
            .values(
                control_id=str(uuid.uuid4()),
                organization_id=organization_id,
                task_type=task_type,
                is_paused=is_paused,
                max_concurrency=None,
                rate_limit_per_minute=None,
                version=1,
                reason=reason,
                updated_by=actor.actor_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["organization_id", "task_type"])
        )
        control = await self._load_control(
            organization_id=organization_id,
            task_type=task_type,
            for_update=True,
        )
        if control is None:
            raise RuntimeError("Task type control upsert did not create a row.")
        command_result = await self._session.execute(
            select(TaskTypeControlCommand)
            .where(TaskTypeControlCommand.organization_id == organization_id)
            .where(TaskTypeControlCommand.task_type == task_type)
            .where(TaskTypeControlCommand.action == action)
            .where(TaskTypeControlCommand.idempotency_key_hash == key_hash)
            .limit(1)
        )
        existing_command = command_result.scalar_one_or_none()
        if existing_command is not None:
            if existing_command.request_fingerprint != fingerprint:
                raise IdempotencyKeyReusedError()
            return self._control_view(control)
        if control.is_paused != is_paused or control.reason != reason:
            control.is_paused = is_paused
            control.reason = reason
            control.updated_by = actor.actor_id
            control.updated_at = now
            control.version += 1
        self._session.add(
            TaskTypeControlCommand(
                command_id=str(uuid.uuid4()),
                organization_id=organization_id,
                task_type=task_type,
                action=action,
                actor_id=actor.actor_id,
                idempotency_key_hash=key_hash,
                request_fingerprint=fingerprint,
                result_version=control.version,
                created_at=now,
            )
        )
        await self._session.flush()
        return self._control_view(control)

    async def _load_task(
        self, task_id: str, *, for_update: bool = False
    ) -> DurableTask:
        query = select(DurableTask).where(DurableTask.task_id == task_id).limit(1)
        if for_update:
            query = query.with_for_update()
        result = await self._session.execute(query)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError()
        return task

    async def _load_control(
        self,
        *,
        organization_id: str,
        task_type: str,
        for_update: bool,
    ) -> TaskTypeControl | None:
        query = (
            select(TaskTypeControl)
            .where(TaskTypeControl.organization_id == organization_id)
            .where(TaskTypeControl.task_type == task_type)
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return (await self._session.execute(query)).scalar_one_or_none()

    async def _authorize_task(
        self,
        task: DurableTask,
        *,
        actor: OperatorActor,
        action: TaskAccessAction,
    ) -> None:
        self._require_capability(actor, action)
        if not await self._access_policy.allows(
            actor,
            organization_id=task.organization_id,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            action=action,
        ):
            raise TaskAccessDeniedError()

    async def _can_access_task(
        self,
        task: DurableTask,
        *,
        actor: OperatorActor,
        action: TaskAccessAction,
    ) -> bool:
        required = (
            "task_runtime.read"
            if action is TaskAccessAction.READ
            else "task_runtime.operate"
        )
        if required not in actor.capabilities:
            return False
        return await self._access_policy.allows(
            actor,
            organization_id=task.organization_id,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            action=action,
        )

    async def _authorize_scope(
        self,
        *,
        organization_id: str,
        actor: OperatorActor,
        action: TaskAccessAction,
    ) -> None:
        self._require_capability(actor, action)
        if not await self._access_policy.allows(
            actor,
            organization_id=organization_id,
            resource_type=None,
            resource_id=None,
            action=action,
        ):
            raise TaskAccessDeniedError()

    @staticmethod
    def _require_capability(actor: OperatorActor, action: TaskAccessAction) -> None:
        required = (
            "task_runtime.read"
            if action is TaskAccessAction.READ
            else "task_runtime.operate"
        )
        if required not in actor.capabilities:
            raise TaskAccessDeniedError()

    @staticmethod
    def _control_view(control: TaskTypeControl) -> TaskTypeControlView:
        return TaskTypeControlView(
            organization_id=control.organization_id,
            task_type=control.task_type,
            is_paused=control.is_paused,
            version=control.version,
            reason=control.reason,
            max_concurrency=control.max_concurrency,
            rate_limit_per_minute=control.rate_limit_per_minute,
        )

    @staticmethod
    def _encode_cursor(updated_at: datetime, task_id: str) -> str:
        raw = json.dumps(
            {"updated_at": updated_at.isoformat(), "task_id": task_id},
            separators=(",", ":"),
        ).encode("utf-8")
        return urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            padding = "=" * (-len(cursor) % 4)
            payload = json.loads(urlsafe_b64decode(cursor + padding))
            updated_at = datetime.fromisoformat(payload["updated_at"])
            task_id = str(payload["task_id"])
            if updated_at.tzinfo is None or not task_id:
                raise ValueError
            return updated_at, task_id
        except (
            BinasciiError,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            raise TaskQueryInvalidError() from exc


__all__ = [
    "DenyAllTaskAccessPolicy",
    "OperatorActor",
    "SQLAlchemyTaskAccessPolicy",
    "TaskAccessAction",
    "TaskAccessPolicyPort",
    "TaskListPage",
    "TaskListItem",
    "TaskOperatorService",
    "TaskRuntimeHealth",
    "TaskTypeControlView",
    "TaskViewModel",
]
