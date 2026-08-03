"""Deterministic task worker orchestration over the durable worker store."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from contextlib import suppress
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_runtime.contracts import (
    ClaimedTask,
    Clock,
    TaskCompletion,
    TaskProgressUpdate,
    TaskState,
)
from task_runtime.errors import (
    TaskCancellationRequested,
    TaskExecutionError,
    TaskFailureKind,
    TaskHandlerMissingError,
    TaskInfrastructureError,
    TaskLeaseLostError,
    TaskSchemaInvalidError,
    TaskTypeNotRegisteredError,
)
from task_runtime.registry import TaskRegistry
from task_runtime.repository import SystemClock
from task_runtime.worker_store import FencedTaskExecution, SQLAlchemyTaskWorkerStore

TaskHandlerOutcome = TaskCompletion


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class AsyncioSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class TaskRunResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    attempt_no: int
    state: TaskState


class WorkerStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    live: bool
    ready: bool
    accepting_new_tasks: bool
    in_flight: int


class TaskExecutionContext:
    """Handler context with explicit cancellation and fenced-UoW seams."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        claim: ClaimedTask,
        *,
        clock: Clock,
    ) -> None:
        self.claim = claim
        self._session_factory = session_factory
        self._clock = clock

    def fenced(self, session: AsyncSession) -> FencedTaskExecution:
        return SQLAlchemyTaskWorkerStore(session, clock=self._clock).execution(
            self.claim
        )

    async def checkpoint(self) -> None:
        async with self._session_factory() as session:
            state = await self.fenced(session).current_state()
            await session.rollback()
        if state is TaskState.CANCEL_REQUESTED:
            raise TaskCancellationRequested()

    async def report_progress(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        stage: str | None = None,
        label: str | None = None,
    ) -> int:
        update = TaskProgressUpdate(
            current=current,
            total=total,
            stage=stage,
            label=label,
        )
        async with self._session_factory() as session:
            sequence = await self.fenced(session).report_progress(update)
            await session.commit()
            return sequence


class TaskWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        registry: TaskRegistry,
        worker_id: str,
        clock: Clock | None = None,
        task_types: frozenset[str] | None = None,
        sleeper: Sleeper | None = None,
        heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry
        self._worker_id = worker_id
        self._clock = clock or SystemClock()
        self._task_types = task_types
        self._sleeper = sleeper or AsyncioSleeper()
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._stop_requested = False
        self._in_flight = 0
        self._database_ready = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def status(self) -> WorkerStatus:
        accepting = not self._stop_requested
        return WorkerStatus(
            live=True,
            ready=accepting and self._database_ready,
            accepting_new_tasks=accepting,
            in_flight=self._in_flight,
        )

    async def run_once(self) -> TaskRunResult | None:
        if self._stop_requested:
            return None
        try:
            async with self._session_factory() as session:
                store = SQLAlchemyTaskWorkerStore(session, clock=self._clock)
                await store.recover_expired(limit=100)
                await store.acknowledge_unleased_cancellations(limit=100)
                await store.reap_expired_queued(limit=100)
                await store.release_due_retries(limit=100)
                claim = await store.claim_next(
                    worker_id=self._worker_id,
                    task_types=self._task_types,
                )
                await session.commit()
            self._database_ready = True
        except Exception:
            self._database_ready = False
            raise
        if claim is None:
            return None

        context = TaskExecutionContext(
            self._session_factory,
            claim,
            clock=self._clock,
        )
        self._in_flight += 1
        deadline_limited = False
        try:
            definition = self._registry.resolve(
                claim.task_type,
                claim.schema_version,
            )
            if definition.handler is None:
                raise TaskHandlerMissingError(claim.task_type)
            payload = self._registry.parse_input(
                task_type=claim.task_type,
                schema_version=claim.schema_version,
                payload=claim.input_payload,
            )
            effective_timeout, deadline_limited = self._effective_timeout(claim)
            async with asyncio.timeout(effective_timeout):
                raw_outcome = await self._execute_with_heartbeat(
                    claim,
                    lease_seconds=claim.lease_seconds,
                    handler_awaitable=definition.handler.execute(context, payload),
                )
            if claim.deadline_at is not None and claim.deadline_at <= self._clock.now():
                raise TaskExecutionError(
                    code="deadline_expired",
                    message="任务截止时间已过。",
                    kind=TaskFailureKind.TIMEOUT,
                )
            outcome = TaskCompletion.model_validate(raw_outcome)
            structured = self._registry.validate_result(
                task_type=claim.task_type,
                schema_version=claim.schema_version,
                payload=outcome.structured_payload,
            )
            outcome = outcome.model_copy(update={"structured_payload": structured})
            state = await self._complete(claim, outcome)
        except TaskCancellationRequested:
            state = await self._acknowledge_cancel(claim)
        except TaskLeaseLostError:
            raise
        except TaskInfrastructureError:
            raise
        except TaskTypeNotRegisteredError:
            state = await self._fail(
                claim,
                code="task_type_not_registered",
                kind=TaskFailureKind.INVALID_INPUT,
            )
        except TaskExecutionError as exc:
            state = await self._fail(claim, code=exc.code, kind=exc.kind)
        except TimeoutError:
            state = await self._fail(
                claim,
                code=("deadline_expired" if deadline_limited else "task_timeout"),
                kind=TaskFailureKind.TIMEOUT,
            )
        except (TaskHandlerMissingError, TaskSchemaInvalidError, ValidationError):
            state = await self._fail(
                claim,
                code="task_contract_invalid",
                kind=TaskFailureKind.INVALID_INPUT,
            )
        except Exception:
            state = await self._fail(
                claim,
                code="task_system_error",
                kind=TaskFailureKind.SYSTEM_DEFECT,
            )
        finally:
            self._in_flight -= 1
        return TaskRunResult(
            task_id=claim.task_id,
            attempt_no=claim.attempt_no,
            state=state,
        )

    async def _execute_with_heartbeat(
        self,
        claim: ClaimedTask,
        *,
        lease_seconds: int,
        handler_awaitable: Awaitable[Any],
    ) -> Any:
        interval = (
            self._heartbeat_interval_seconds
            if self._heartbeat_interval_seconds is not None
            else max(1.0, lease_seconds / 3)
        )
        handler_task = asyncio.ensure_future(handler_awaitable)
        heartbeat_task: asyncio.Task[None] | None = None
        try:
            if interval >= lease_seconds / 2:
                raise ValueError(
                    "Task heartbeat interval must be shorter than half the lease."
                )
            heartbeat_task = asyncio.create_task(
                self._heartbeat(claim, interval_seconds=interval)
            )
            done, _ = await asyncio.wait(
                {handler_task, heartbeat_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat_task in done:
                error = heartbeat_task.exception()
                handler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await handler_task
                if error is not None:
                    raise error
                raise TaskLeaseLostError()
            return await handler_task
        finally:
            cleanup_tasks = [handler_task]
            if heartbeat_task is not None:
                cleanup_tasks.append(heartbeat_task)
            for task in cleanup_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    async def _heartbeat(self, claim: ClaimedTask, *, interval_seconds: float) -> None:
        current = claim
        try:
            while True:
                await self._sleeper.sleep(interval_seconds)
                async with self._session_factory() as session:
                    store = SQLAlchemyTaskWorkerStore(session, clock=self._clock)
                    current = await store.renew_lease(current)
                    await session.commit()
                self._database_ready = True
        except Exception:
            self._database_ready = False
            raise

    def _effective_timeout(self, claim: ClaimedTask) -> tuple[float, bool]:
        timeout = float(claim.timeout_seconds)
        if claim.deadline_at is None:
            return timeout, False
        remaining = (claim.deadline_at - self._clock.now()).total_seconds()
        if remaining <= 0:
            raise TaskExecutionError(
                code="deadline_expired",
                message="任务截止时间已过。",
                kind=TaskFailureKind.TIMEOUT,
            )
        return min(timeout, remaining), remaining <= timeout

    async def _complete(self, claim: ClaimedTask, outcome: TaskCompletion) -> TaskState:
        try:
            async with self._session_factory() as session:
                store = SQLAlchemyTaskWorkerStore(session, clock=self._clock)
                state = await store.complete(claim, outcome)
                await session.commit()
        except (
            TaskLeaseLostError,
            TaskExecutionError,
            TaskSchemaInvalidError,
            ValidationError,
        ):
            raise
        except Exception as exc:
            self._database_ready = False
            raise TaskInfrastructureError("complete") from exc
        self._database_ready = True
        return state

    async def _fail(
        self,
        claim: ClaimedTask,
        *,
        code: str,
        kind: TaskFailureKind,
    ) -> TaskState:
        try:
            async with self._session_factory() as session:
                store = SQLAlchemyTaskWorkerStore(session, clock=self._clock)
                state = await store.fail(claim, code=code, kind=kind)
                await session.commit()
        except TaskLeaseLostError:
            raise
        except Exception as exc:
            self._database_ready = False
            raise TaskInfrastructureError("fail") from exc
        self._database_ready = True
        return state

    async def _acknowledge_cancel(self, claim: ClaimedTask) -> TaskState:
        try:
            async with self._session_factory() as session:
                store = SQLAlchemyTaskWorkerStore(session, clock=self._clock)
                state = await store.acknowledge_cancel(claim)
                await session.commit()
        except TaskLeaseLostError:
            raise
        except Exception as exc:
            self._database_ready = False
            raise TaskInfrastructureError("acknowledge_cancel") from exc
        self._database_ready = True
        return state


__all__ = [
    "TaskExecutionContext",
    "AsyncioSleeper",
    "Sleeper",
    "TaskHandlerOutcome",
    "TaskRunResult",
    "TaskWorker",
    "WorkerStatus",
]
