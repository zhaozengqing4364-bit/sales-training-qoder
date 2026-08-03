"""Transactional SQLAlchemy adapter for the public TaskRuntimePort."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from task_runtime.contracts import (
    ActorContext,
    Clock,
    TaskCommand,
    TaskErrorProjection,
    TaskPage,
    TaskProgressProjection,
    TaskProjection,
    TaskReference,
    TaskResultKind,
    TaskState,
)
from task_runtime.errors import (
    IdempotencyKeyReusedError,
    TaskAccessDeniedError,
    TaskNotFoundError,
)
from task_runtime.models import (
    DurableTask,
    TaskCommandRecord,
    TaskPayloadArtifact,
    TaskProgress,
    TaskResultRef,
)
from task_runtime.outbox import append_task_event
from task_runtime.registry import TaskRegistry
from task_runtime.state_machine import TERMINAL_TASK_STATES, require_task_transition


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _canonical_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SQLAlchemyTaskRuntime:
    """Task application adapter; callers own commit/rollback boundaries."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: TaskRegistry,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._registry = registry
        self._clock = clock or SystemClock()

    async def enqueue(self, command: TaskCommand) -> TaskReference:
        validated_payload = self._registry.validate_input(
            task_type=command.task_type,
            schema_version=command.schema_version,
            payload=command.input_payload,
            data_classification=command.data_classification,
        )
        definition = self._registry.resolve(
            command.task_type,
            command.schema_version,
        )
        fingerprint = _canonical_hash(
            {
                "task_type": command.task_type,
                "schema_version": command.schema_version,
                "organization_id": command.organization_id,
                "actor_id": command.actor_id,
                "resource_type": command.resource_type,
                "resource_id": command.resource_id,
                "payload": validated_payload,
                "priority": command.priority,
                "deadline_at": (
                    command.deadline_at.isoformat() if command.deadline_at else None
                ),
                "next_run_at": (
                    command.next_run_at.isoformat() if command.next_run_at else None
                ),
                "data_classification": command.data_classification,
            }
        )
        existing = await self._find_by_idempotency(command)
        if existing is not None:
            self._assert_same_idempotency(existing, fingerprint)
            return self._reference(existing)

        now = self._clock.now()
        artifact_id = str(uuid.uuid4())
        artifact = TaskPayloadArtifact(
            artifact_id=artifact_id,
            organization_id=command.organization_id,
            data_classification=command.data_classification,
            content_hash=_canonical_hash(validated_payload),
            payload_json=validated_payload,
            created_at=now,
        )
        task = DurableTask(
            task_type=command.task_type,
            schema_version=command.schema_version,
            organization_id=command.organization_id,
            actor_id=command.actor_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            idempotency_key_hash=_secret_hash(command.idempotency_key),
            idempotency_fingerprint=fingerprint,
            input_artifact_id=artifact_id,
            state=TaskState.QUEUED.value,
            priority=command.priority,
            attempt_count=0,
            max_attempts=definition.policy.max_attempts,
            timeout_seconds=definition.policy.timeout_seconds,
            retry_policy_json=definition.policy.model_dump(mode="json"),
            next_run_at=command.next_run_at or now,
            deadline_at=command.deadline_at,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            trace_id=command.trace_id,
            fence_generation=0,
            version=1,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(artifact)
                await self._session.flush([artifact])
                self._session.add(task)
                await self._session.flush([task])
                await append_task_event(
                    self._session,
                    task,
                    event_type="DurableTaskEnqueued",
                    occurred_at=now,
                    actor_id=command.actor_id,
                )
        except IntegrityError:
            existing = await self._find_by_idempotency(command)
            if existing is None:
                raise
            self._assert_same_idempotency(existing, fingerprint)
            return self._reference(existing)
        return self._reference(task)

    async def get(self, task_id: str, viewer: ActorContext) -> TaskProjection:
        task = await self._load_task(task_id)
        self._require_view_access(task, viewer)
        return await self._projection(task)

    async def list_for_actor(
        self,
        viewer: ActorContext,
        *,
        page: int = 1,
        page_size: int = 20,
        state: TaskState | None = None,
    ) -> TaskPage:
        resolved_page = max(1, page)
        resolved_page_size = max(1, min(page_size, 100))
        filters = [DurableTask.organization_id == viewer.organization_id]
        if not ({"task_runtime.read", "task_runtime.operate"} & viewer.capabilities):
            filters.append(DurableTask.actor_id == viewer.actor_id)
        if state is not None:
            filters.append(DurableTask.state == state.value)

        total = int(
            await self._session.scalar(
                select(func.count(DurableTask.task_id)).where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.execute(
                    select(DurableTask)
                    .where(*filters)
                    .order_by(
                        DurableTask.updated_at.desc(),
                        DurableTask.task_id.desc(),
                    )
                    .offset((resolved_page - 1) * resolved_page_size)
                    .limit(resolved_page_size)
                )
            ).scalars()
        )
        return TaskPage(
            items=tuple(await self._projections(rows)),
            total=total,
            page=resolved_page,
            page_size=resolved_page_size,
            has_more=resolved_page * resolved_page_size < total,
        )

    async def request_cancel(
        self,
        task_id: str,
        actor: ActorContext,
        *,
        idempotency_key: str | None = None,
    ) -> TaskProjection:
        task = await self._load_task(task_id, for_update=True)
        self._require_cancel_access(task, actor)
        command_type = "request_cancel"
        key_hash = _secret_hash(
            idempotency_key
            or f"request_cancel:{task_id}:{actor.organization_id}:{actor.actor_id}"
        )
        fingerprint = _canonical_hash(
            {
                "task_id": task_id,
                "organization_id": actor.organization_id,
                "actor_id": actor.actor_id,
                "command_type": command_type,
                "idempotency_key": idempotency_key,
            }
        )
        existing_command = await self._find_command_record(
            task_id=task_id,
            command_type=command_type,
            idempotency_key_hash=key_hash,
        )
        if existing_command is not None:
            self._assert_same_command(existing_command, fingerprint)
            return await self._projection(task)

        state = TaskState(task.state)
        if (
            state not in TERMINAL_TASK_STATES
            and state is not TaskState.CANCEL_REQUESTED
        ):
            require_task_transition(state, TaskState.CANCEL_REQUESTED)
            task.state = TaskState.CANCEL_REQUESTED.value
            task.version += 1
            task.updated_at = self._clock.now()
            await append_task_event(
                self._session,
                task,
                event_type="TaskCancelRequested",
                occurred_at=self._clock.now(),
                actor_id=actor.actor_id,
            )
        self._session.add(
            TaskCommandRecord(
                task_id=task.task_id,
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                command_type=command_type,
                idempotency_key_hash=key_hash,
                request_fingerprint=fingerprint,
                result_state=task.state,
                created_at=self._clock.now(),
            )
        )
        await self._session.flush()
        return await self._projection(task)

    async def _find_by_idempotency(self, command: TaskCommand) -> DurableTask | None:
        result = await self._session.execute(
            select(DurableTask)
            .where(DurableTask.organization_id == command.organization_id)
            .where(DurableTask.task_type == command.task_type)
            .where(DurableTask.resource_type == command.resource_type)
            .where(DurableTask.resource_id == command.resource_id)
            .where(
                DurableTask.idempotency_key_hash
                == _secret_hash(command.idempotency_key)
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_command_record(
        self,
        *,
        task_id: str,
        command_type: str,
        idempotency_key_hash: str,
    ) -> TaskCommandRecord | None:
        result = await self._session.execute(
            select(TaskCommandRecord)
            .where(TaskCommandRecord.task_id == task_id)
            .where(TaskCommandRecord.command_type == command_type)
            .where(TaskCommandRecord.idempotency_key_hash == idempotency_key_hash)
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    @staticmethod
    def _assert_same_idempotency(task: DurableTask, fingerprint: str) -> None:
        if task.idempotency_fingerprint != fingerprint:
            raise IdempotencyKeyReusedError()

    @staticmethod
    def _assert_same_command(command: TaskCommandRecord, fingerprint: str) -> None:
        if command.request_fingerprint != fingerprint:
            raise IdempotencyKeyReusedError()

    @staticmethod
    def _require_view_access(task: DurableTask, viewer: ActorContext) -> None:
        if task.organization_id != viewer.organization_id:
            raise TaskAccessDeniedError()
        if task.actor_id == viewer.actor_id:
            return
        if {"task_runtime.read", "task_runtime.operate"} & viewer.capabilities:
            return
        raise TaskAccessDeniedError()

    @staticmethod
    def _require_cancel_access(task: DurableTask, actor: ActorContext) -> None:
        if task.organization_id != actor.organization_id:
            raise TaskAccessDeniedError()
        if task.actor_id == actor.actor_id:
            return
        if "task_runtime.operate" in actor.capabilities:
            return
        raise TaskAccessDeniedError()

    @staticmethod
    def _reference(task: DurableTask) -> TaskReference:
        return TaskReference(
            task_id=task.task_id,
            state=TaskState(task.state),
            organization_id=task.organization_id,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            created_at=task.created_at,
        )

    async def _projection(self, task: DurableTask) -> TaskProjection:
        projections = await self._projections([task])
        return projections[0]

    async def _projections(
        self, tasks: list[DurableTask]
    ) -> list[TaskProjection]:
        if not tasks:
            return []
        task_ids = tuple(task.task_id for task in tasks)
        progress_rows = list(
            (
                await self._session.execute(
                    select(TaskProgress)
                    .where(TaskProgress.task_id.in_(task_ids))
                    .order_by(TaskProgress.task_id, desc(TaskProgress.sequence))
                )
            ).scalars()
        )
        latest_progress: dict[str, TaskProgress] = {}
        for row in progress_rows:
            latest_progress.setdefault(row.task_id, row)
        result_refs = list(
            (
                await self._session.execute(
                    select(TaskResultRef).where(TaskResultRef.task_id.in_(task_ids))
                )
            ).scalars()
        )
        result_by_task = {row.task_id: row for row in result_refs}
        return [
            self._projection_from_rows(
                task,
                progress_row=latest_progress.get(task.task_id),
                result_ref=result_by_task.get(task.task_id),
            )
            for task in tasks
        ]

    @staticmethod
    def _projection_from_rows(
        task: DurableTask,
        *,
        progress_row: TaskProgress | None,
        result_ref: TaskResultRef | None,
    ) -> TaskProjection:
        progress = None
        if progress_row is not None:
            progress = TaskProgressProjection(
                current=progress_row.current,
                total=progress_row.total,
                stage=progress_row.stage,
                label=progress_row.label,
            )
        error = None
        if task.last_error_code:
            error = TaskErrorProjection(
                code=task.last_error_code,
                retryable=TaskState(task.state) is TaskState.RETRY_WAIT,
                message=task.last_error_message or "任务处理失败，请稍后重试。",
            )
        return TaskProjection(
            task_id=task.task_id,
            task_type=task.task_type,
            schema_version=task.schema_version,
            organization_id=task.organization_id,
            actor_id=task.actor_id,
            resource_type=task.resource_type,
            resource_id=task.resource_id,
            state=TaskState(task.state),
            priority=task.priority,
            attempt_count=task.attempt_count,
            max_attempts=task.max_attempts,
            next_run_at=task.next_run_at,
            deadline_at=task.deadline_at,
            progress=progress,
            result_kind=(
                TaskResultKind(result_ref.result_kind)
                if result_ref is not None
                else None
            ),
            result_location=result_ref.location if result_ref is not None else None,
            error=error,
            version=task.version,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
