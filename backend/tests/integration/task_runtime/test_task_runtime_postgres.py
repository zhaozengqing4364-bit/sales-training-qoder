from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tests.fakes.task_runtime import ControlledSleeper, FixedClock

from common.db.session import get_db
from task_runtime.api import (
    get_task_reader_actor,
    get_task_registry,
    require_task_runtime_operator,
    require_task_runtime_reader,
)
from task_runtime.api import (
    router as task_runtime_router,
)
from task_runtime.contracts import (
    ActorContext,
    TaskCommand,
    TaskPolicy,
    TaskResultItemRef,
    TaskResultKind,
    TaskState,
)
from task_runtime.errors import (
    IdempotencyKeyReusedError,
    OutboxEventConflictError,
    TaskAccessDeniedError,
    TaskExecutionError,
    TaskFailureKind,
    TaskLeaseLostError,
)
from task_runtime.models import (
    TASK_RUNTIME_TABLES,
    OutboxEvent,
    TaskLease,
    TaskOperatorScopeGrant,
)
from task_runtime.operator_service import (
    OperatorActor,
    TaskAccessAction,
    TaskOperatorService,
)
from task_runtime.outbox import (
    DomainEvent,
    IdempotentOutboxConsumer,
    OutboxDispatcher,
    SQLAlchemyOutboxWriter,
    append_domain_event,
)
from task_runtime.registry import TaskDefinition, TaskRegistry
from task_runtime.repository import SQLAlchemyTaskRuntime
from task_runtime.worker import TaskHandlerOutcome, TaskWorker
from task_runtime.worker_store import SQLAlchemyTaskWorkerStore

POSTGRES_URL = os.getenv("TASK_RUNTIME_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason="TASK_RUNTIME_TEST_DATABASE_URL is required for PostgreSQL semantics",
    ),
]


class EchoTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class EchoTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    echoed: str


class PartialSuccessHandler:
    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        await context.checkpoint()
        await context.report_progress(
            current=1,
            total=2,
            stage="saving",
            label="已保存第一部分",
        )
        return TaskHandlerOutcome(
            structured_payload={"echoed": payload.text},
            result_kind=TaskResultKind.PARTIAL_SUCCESS,
            resource_type="echo_result",
            resource_id="echo-1",
            location="/echo-results/echo-1",
            saved_items=[
                TaskResultItemRef(
                    resource_type="echo_part",
                    resource_id="part-1",
                )
            ],
            remaining_items=[
                TaskResultItemRef(
                    resource_type="echo_part",
                    resource_id="part-2",
                )
            ],
            retryable_items=[
                TaskResultItemRef(
                    resource_type="echo_part",
                    resource_id="part-2",
                )
            ],
        )


class RetryOnceHandler:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        self.calls += 1
        await context.checkpoint()
        if self.calls == 1:
            raise TaskExecutionError(
                code="provider_unavailable",
                message="temporary provider failure",
                kind=TaskFailureKind.PROVIDER_TEMPORARY,
            )
        return TaskHandlerOutcome(
            structured_payload={"echoed": payload.text},
            result_kind=TaskResultKind.COMPLETE,
            resource_type="echo_result",
            resource_id="echo-retry",
            location="/echo-results/echo-retry",
        )


class VersionedHandler:
    def __init__(self, version: int) -> None:
        self.version = version

    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        await context.checkpoint()
        return TaskHandlerOutcome(
            structured_payload={"echoed": f"v{self.version}:{payload.text}"},
            result_kind=TaskResultKind.COMPLETE,
            resource_type="echo_result",
            resource_id=f"echo-v{self.version}",
            location=f"/echo-results/v{self.version}",
        )


class CancellableHandler:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.continue_execution = asyncio.Event()

    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        self.started.set()
        await self.continue_execution.wait()
        await context.checkpoint()
        return TaskHandlerOutcome(
            structured_payload={"echoed": payload.text},
            result_kind=TaskResultKind.COMPLETE,
            resource_type="echo_result",
            resource_id="echo-cancel",
            location="/echo-results/echo-cancel",
        )


class BlockingHandler:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.finish = asyncio.Event()

    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        self.started.set()
        await self.finish.wait()
        await context.checkpoint()
        return TaskHandlerOutcome(
            structured_payload={"echoed": payload.text},
            result_kind=TaskResultKind.COMPLETE,
            resource_type="echo_result",
            resource_id="echo-heartbeat",
            location="/echo-results/echo-heartbeat",
        )


class DeadlineBlockingHandler:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.late_side_effect = False

    async def execute(self, context, payload: EchoTaskInput) -> TaskHandlerOutcome:
        del context
        self.started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        self.late_side_effect = True
        return TaskHandlerOutcome(
            structured_payload={"echoed": payload.text},
            result_kind=TaskResultKind.COMPLETE,
            resource_type="echo_result",
            resource_id="late-result",
            location="/echo-results/late-result",
        )


class FailFirstEventTransport:
    def __init__(self) -> None:
        self.attempted = []
        self.published = []
        self._failed = False

    async def publish(self, event) -> None:
        self.attempted.append(event)
        if not self._failed:
            self._failed = True
            raise RuntimeError("simulated transport outage")
        self.published.append(event)


class GrantSetTaskAccessPolicy:
    def __init__(self, grants: set[tuple[str, str, TaskAccessAction]]) -> None:
        self._grants = grants

    async def allows(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resource_type: str | None,
        resource_id: str | None,
        action: TaskAccessAction,
    ) -> bool:
        del resource_type, resource_id
        return (actor.actor_id, organization_id, action) in self._grants

    async def allowed_resource_keys(
        self,
        actor: OperatorActor,
        *,
        organization_id: str,
        resources: frozenset[tuple[str, str]],
        action: TaskAccessAction,
    ) -> frozenset[tuple[str, str]]:
        if (actor.actor_id, organization_id, action) not in self._grants:
            return frozenset()
        return resources


@pytest_asyncio.fixture
async def task_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    assert POSTGRES_URL is not None
    schema = "slice1_task_runtime_test"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: TASK_RUNTIME_TABLES.drop_all(
                sync_connection, checkfirst=True
            )
        )
        await connection.run_sync(TASK_RUNTIME_TABLES.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    await engine.dispose()
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await admin_engine.dispose()


def build_registry() -> TaskRegistry:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=3),
        )
    )
    return registry


@pytest.mark.asyncio
async def test_enqueue_is_durable_and_rejects_idempotency_key_reuse(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    actor = ActorContext(
        organization_id="org-1",
        actor_id="learner-1",
        capabilities=frozenset(),
    )
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-1",
        idempotency_key="submit-1",
        input_payload={"text": "hello"},
        correlation_id="corr-1",
    )
    clock = FixedClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        first = await runtime.enqueue(command)
        repeated = await runtime.enqueue(command)
        assert repeated.task_id == first.task_id
        await session.commit()

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        projection = await runtime.get(first.task_id, actor)
        assert projection.task_id == first.task_id
        assert projection.state is TaskState.QUEUED
        assert projection.organization_id == "org-1"
        assert projection.resource_id == "attempt-1"

        with pytest.raises(IdempotencyKeyReusedError):
            await runtime.enqueue(
                command.model_copy(update={"input_payload": {"text": "changed"}})
            )


@pytest.mark.asyncio
async def test_actor_task_page_is_owner_scoped_and_bounded(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        for index, actor_id in enumerate(("learner-1", "learner-1", "learner-2")):
            await runtime.enqueue(
                TaskCommand(
                    task_type="test.echo",
                    schema_version=1,
                    organization_id="org-1",
                    actor_id=actor_id,
                    resource_type="activity_attempt",
                    resource_id=f"attempt-page-{index}",
                    idempotency_key=f"page-{index}",
                    input_payload={"text": str(index)},
                    correlation_id=f"corr-page-{index}",
                )
            )
            clock.advance(seconds=1)
        await session.commit()

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        first = await runtime.list_for_actor(
            ActorContext(organization_id="org-1", actor_id="learner-1"),
            page=1,
            page_size=1,
        )
        second = await runtime.list_for_actor(
            ActorContext(organization_id="org-1", actor_id="learner-1"),
            page=2,
            page_size=1,
        )

    assert first.total == 2
    assert first.has_more is True
    assert second.total == 2
    assert second.has_more is False
    assert {first.items[0].actor_id, second.items[0].actor_id} == {"learner-1"}
    assert first.items[0].task_id != second.items[0].task_id


@pytest.mark.asyncio
async def test_claim_uses_skip_locked_and_expired_lease_is_fenced_and_recovered(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(
                max_attempts=3,
                lease_seconds=5,
                initial_backoff_seconds=2,
                max_backoff_seconds=10,
            ),
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 12, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-claim",
        idempotency_key="claim-once",
        input_payload={"text": "hello"},
        correlation_id="corr-claim",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        await session.commit()

    async def claim(worker_id: str):
        async with task_session_factory() as session:
            store = SQLAlchemyTaskWorkerStore(session, clock=clock)
            claimed = await store.claim_next(worker_id=worker_id)
            await session.commit()
            return claimed

    claims = await asyncio.gather(claim("worker-a"), claim("worker-b"))
    claimed = next(item for item in claims if item is not None)
    assert sum(item is not None for item in claims) == 1
    assert claimed.attempt_no == 1
    assert claimed.input_payload == {"text": "hello"}
    assert claimed.timeout_seconds == 300
    assert claimed.lease_seconds == 5
    assert claimed.max_attempts == 3
    assert claimed.retry_policy.lease_seconds == 5

    clock.advance(seconds=2)
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        renewed = await store.renew_lease(claimed)
        await store.execution(renewed).assert_current()
        await session.commit()
    assert renewed.lease_expires_at > claimed.lease_expires_at

    stale_token = renewed.model_copy(update={"lease_token": "stale-token"})
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        with pytest.raises(TaskLeaseLostError):
            await store.execution(stale_token).assert_current()

    clock.advance(seconds=6)
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.recover_expired(limit=10) == 1
        await session.commit()

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        projection = await runtime.get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
        assert projection.state is TaskState.RETRY_WAIT
        assert projection.error is not None
        assert projection.error.message == "任务执行中断，将自动重试。"
        assert "Worker" not in projection.error.message

    clock.advance(seconds=3)
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.release_due_retries(limit=10) == 1
        recovered = await store.claim_next(worker_id="worker-c")
        await session.commit()
    assert recovered is not None
    assert recovered.task_id == task.task_id
    assert recovered.attempt_no == 2
    assert recovered.lease_token != renewed.lease_token

    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        with pytest.raises(TaskLeaseLostError):
            await store.execution(renewed).assert_current()
        with pytest.raises(TaskLeaseLostError):
            await store.complete(
                renewed,
                TaskHandlerOutcome(
                    structured_payload={"echoed": "stale"},
                    result_kind=TaskResultKind.COMPLETE,
                    resource_type="echo_result",
                    resource_id="stale-result",
                    location="/echo-results/stale-result",
                ),
            )


@pytest.mark.asyncio
async def test_worker_persists_typed_partial_result_and_stops_claiming_gracefully(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=3),
            handler=PartialSuccessHandler(),
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 13, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-partial",
        idempotency_key="partial-once",
        input_payload={"text": "partial"},
        correlation_id="corr-partial",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-partial",
        clock=clock,
    )
    run = await worker.run_once()
    assert run is not None
    assert run.state is TaskState.SUCCEEDED

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        projection = await runtime.get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
    assert projection.result_kind is TaskResultKind.PARTIAL_SUCCESS
    assert projection.result_location == "/echo-results/echo-1"
    assert projection.progress is not None
    assert projection.progress.current == 1
    assert projection.progress.total == 2
    assert projection.progress.label == "已保存第一部分"

    worker.request_stop()
    assert await worker.run_once() is None


@pytest.mark.asyncio
async def test_worker_resumes_queued_v1_and_v2_with_exact_version_handlers(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = TaskRegistry()
    for version in (1, 2):
        registry.register(
            TaskDefinition(
                task_type="test.versioned",
                schema_version=version,
                input_model=EchoTaskInput,
                result_model=EchoTaskResult,
                policy=TaskPolicy(max_attempts=2),
                handler=VersionedHandler(version),
            )
        )
    clock = FixedClock(datetime(2026, 7, 16, 13, 30, tzinfo=UTC))
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        references = []
        for version in (1, 2):
            references.append(
                await runtime.enqueue(
                    TaskCommand(
                        task_type="test.versioned",
                        schema_version=version,
                        organization_id="org-1",
                        actor_id="learner-1",
                        resource_type="activity_attempt",
                        resource_id=f"attempt-version-{version}",
                        idempotency_key=f"version-{version}",
                        input_payload={"text": "resume"},
                        correlation_id=f"corr-version-{version}",
                    )
                )
            )
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-versioned",
        clock=clock,
        task_types=frozenset({"test.versioned"}),
    )
    assert (await worker.run_once()).state is TaskState.SUCCEEDED  # type: ignore[union-attr]
    assert (await worker.run_once()).state is TaskState.SUCCEEDED  # type: ignore[union-attr]

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        projections = [
            await runtime.get(
                reference.task_id,
                ActorContext(organization_id="org-1", actor_id="learner-1"),
            )
            for reference in references
        ]
    assert {projection.result_location for projection in projections} == {
        "/echo-results/v1",
        "/echo-results/v2",
    }


@pytest.mark.asyncio
async def test_worker_retries_transient_failure_then_succeeds(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = RetryOnceHandler()
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(
                max_attempts=2,
                initial_backoff_seconds=1,
                max_backoff_seconds=2,
            ),
            handler=handler,
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 14, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-retry",
        idempotency_key="retry-once",
        input_payload={"text": "retry"},
        correlation_id="corr-retry",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-retry",
        clock=clock,
    )
    first_run = await worker.run_once()
    assert first_run is not None
    assert first_run.state is TaskState.RETRY_WAIT

    clock.advance(seconds=2)
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.release_due_retries(limit=10) == 1
        await session.commit()
    second_run = await worker.run_once()
    assert second_run is not None
    assert second_run.state is TaskState.SUCCEEDED
    assert handler.calls == 2

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        projection = await runtime.get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
    assert projection.attempt_count == 2


@pytest.mark.asyncio
async def test_worker_acknowledges_cancel_at_safe_checkpoint(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = CancellableHandler()
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=2),
            handler=handler,
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 15, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-cancel",
        idempotency_key="cancel-once",
        input_payload={"text": "cancel"},
        correlation_id="corr-cancel",
    )
    actor = ActorContext(organization_id="org-1", actor_id="learner-1")
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-cancel",
        clock=clock,
    )
    running = asyncio.create_task(worker.run_once())
    await handler.started.wait()
    assert worker.status().live
    assert worker.status().ready
    assert worker.status().in_flight == 1
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        requested = await runtime.request_cancel(task.task_id, actor)
        await session.commit()
    assert requested.state is TaskState.CANCEL_REQUESTED
    handler.continue_execution.set()
    result = await running
    assert result is not None
    assert result.state is TaskState.CANCELLED
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        cancelled = await runtime.get(task.task_id, actor)
    assert cancelled.error is None


@pytest.mark.asyncio
async def test_outbox_is_transactional_retries_in_isolation_and_consumes_once(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=2),
            handler=PartialSuccessHandler(),
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 16, 0, tzinfo=UTC))
    base_command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-outbox",
        idempotency_key="outbox-once",
        input_payload={"text": "secret provider input"},
        correlation_id="corr-outbox",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        await runtime.enqueue(
            base_command.model_copy(
                update={
                    "resource_id": "attempt-rolled-back",
                    "idempotency_key": "rolled-back",
                }
            )
        )
        await session.rollback()

    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(base_command)
        repeated = await runtime.enqueue(base_command)
        assert repeated.task_id == task.task_id
        await session.commit()
    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-outbox",
        clock=clock,
    )
    assert await worker.run_once() is not None

    transport = FailFirstEventTransport()
    dispatcher = OutboxDispatcher(
        task_session_factory,
        transport=transport,
        dispatcher_id="dispatcher-1",
        clock=clock,
        retry_backoff_seconds=1,
    )
    first = await dispatcher.dispatch_once(limit=20)
    assert first.failed == 1
    assert first.published >= 2
    clock.advance(seconds=2)
    second = await dispatcher.dispatch_once(limit=20)
    assert second.failed == 0
    assert second.published == 1

    delivered_types = {event.event_type for event in transport.attempted}
    assert {
        "DurableTaskEnqueued",
        "TaskLeaseClaimed",
        "TaskSucceeded",
    } <= delivered_types
    assert (
        len(
            {
                event.event_id
                for event in transport.attempted
                if event.event_type == "DurableTaskEnqueued"
            }
        )
        == 1
    )
    assert all(event.aggregate_id == task.task_id for event in transport.attempted)
    assert "secret provider input" not in repr(transport.attempted)

    effects: list[str] = []

    async def handle_once(event, session) -> None:
        del session
        effects.append(event.event_id)

    event = transport.published[0]
    consumer = IdempotentOutboxConsumer(task_session_factory, clock=clock)
    assert await consumer.consume(
        event,
        consumer_name="test_projection",
        handler_version="v1",
        handler=handle_once,
    )
    assert not await consumer.consume(
        event,
        consumer_name="test_projection",
        handler_version="v1",
        handler=handle_once,
    )
    assert effects == [event.event_id]


@pytest.mark.asyncio
async def test_generic_domain_outbox_is_transactional_and_conflict_safe(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    occurred_at = datetime(2026, 7, 16, 16, 30, tzinfo=UTC)
    event = DomainEvent(
        event_type="LearningAttemptCompleted",
        schema_version=2,
        occurred_at=occurred_at,
        organization_id="org-1",
        actor_id="learner-1",
        trace_id="trace-domain",
        correlation_id="corr-domain",
        causation_id="command-domain",
        idempotency_key="attempt-1:v2",
        aggregate_type="LearningAttempt",
        aggregate_id="attempt-1",
        aggregate_version=2,
        payload={"attempt_id": "attempt-1", "result_ref": "result-1"},
    )
    async with task_session_factory() as session:
        rolled_back_id = await append_domain_event(session, event)
        await session.rollback()
    async with task_session_factory() as session:
        assert await session.get(OutboxEvent, rolled_back_id) is None

    async with task_session_factory() as session:
        writer = SQLAlchemyOutboxWriter(session)
        event_id = await writer.append(event)
        assert await writer.append(event) == event_id
        await session.commit()
    async with task_session_factory() as session:
        with pytest.raises(OutboxEventConflictError):
            await append_domain_event(
                session,
                event.model_copy(update={"payload": {"attempt_id": "different"}}),
            )
        await session.rollback()

    class RecordingTransport:
        def __init__(self) -> None:
            self.published = []

        async def publish(self, envelope) -> None:
            self.published.append(envelope)

    transport = RecordingTransport()
    dispatcher = OutboxDispatcher(
        task_session_factory,
        transport=transport,
        dispatcher_id="generic-domain-dispatcher",
    )
    report = await dispatcher.dispatch_once(limit=10)
    assert report.published == 1
    consumed: list[str] = []

    async def consume_once(envelope, session) -> None:
        del session
        consumed.append(envelope.event_id)

    consumer = IdempotentOutboxConsumer(task_session_factory)
    assert await consumer.consume(
        transport.published[0],
        consumer_name="generic-domain-projection",
        handler_version="v1",
        handler=consume_once,
    )
    assert not await consumer.consume(
        transport.published[0],
        consumer_name="generic-domain-projection",
        handler_version="v1",
        handler=consume_once,
    )
    assert consumed == [event_id]

    with pytest.raises(Exception, match="OUTBOX_PAYLOAD_SENSITIVE_CONTENT"):
        async with task_session_factory() as session:
            await append_domain_event(
                session,
                event.model_copy(update={"payload": {"raw_ai_response": "secret"}}),
            )


@pytest.mark.asyncio
async def test_operator_requires_server_scope_and_redrive_creates_a_new_task(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=1),
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 17, 0, tzinfo=UTC))
    actor = OperatorActor(
        actor_id="system-admin-1",
        capabilities=frozenset({"task_runtime.read", "task_runtime.operate"}),
    )
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-operator",
        idempotency_key="operator-source",
        input_payload={"text": "operator"},
        correlation_id="corr-operator",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        await session.commit()

    no_scope = GrantSetTaskAccessPolicy(set())
    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=no_scope,
            clock=clock,
        )
        with pytest.raises(TaskAccessDeniedError):
            await service.get_task(task.task_id, actor=actor)

    scope_without_capability = GrantSetTaskAccessPolicy(
        {("scoped-without-cap", "org-1", TaskAccessAction.READ)}
    )
    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=scope_without_capability,
            clock=clock,
        )
        with pytest.raises(TaskAccessDeniedError):
            await service.get_task(
                task.task_id,
                actor=OperatorActor(actor_id="scoped-without-cap"),
            )

    cross_org_only = GrantSetTaskAccessPolicy(
        {("system-admin-1", "org-2", TaskAccessAction.READ)}
    )
    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=cross_org_only,
            clock=clock,
        )
        with pytest.raises(TaskAccessDeniedError):
            await service.get_task(task.task_id, actor=actor)

    read_only_actor = OperatorActor(
        actor_id="read-only-admin",
        capabilities=frozenset({"task_runtime.read"}),
    )
    read_and_operate_scope = GrantSetTaskAccessPolicy(
        {
            ("read-only-admin", "org-1", TaskAccessAction.READ),
            ("read-only-admin", "org-1", TaskAccessAction.OPERATE),
        }
    )
    async with task_session_factory() as session:
        read_only = await TaskOperatorService(
            session,
            registry=registry,
            access_policy=read_and_operate_scope,
            clock=clock,
        ).get_task(task.task_id, actor=read_only_actor)
    assert not read_only.can_cancel
    assert not read_only.can_redrive

    capability_without_operate_scope = OperatorActor(
        actor_id="capability-no-scope",
        capabilities=frozenset({"task_runtime.read", "task_runtime.operate"}),
    )
    read_scope_only = GrantSetTaskAccessPolicy(
        {("capability-no-scope", "org-1", TaskAccessAction.READ)}
    )
    async with task_session_factory() as session:
        no_operate_scope = await TaskOperatorService(
            session,
            registry=registry,
            access_policy=read_scope_only,
            clock=clock,
        ).get_task(task.task_id, actor=capability_without_operate_scope)
    assert not no_operate_scope.can_cancel
    assert not no_operate_scope.can_redrive

    policy = GrantSetTaskAccessPolicy(
        {
            ("system-admin-1", "org-1", TaskAccessAction.READ),
            ("system-admin-1", "org-1", TaskAccessAction.OPERATE),
        }
    )
    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=policy,
            clock=clock,
        )
        detail = await service.get_task(task.task_id, actor=actor)
        assert detail.task_id == task.task_id
        assert detail.status_label == "等待处理"
        assert detail.can_cancel
        await service.pause_task_type(
            organization_id="org-1",
            task_type="test.echo",
            actor=actor,
            idempotency_key="pause-1",
            reason="maintenance",
        )
        await session.commit()

    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.claim_next(worker_id="paused-worker") is None

    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=policy,
            clock=clock,
        )
        await service.resume_task_type(
            organization_id="org-1",
            task_type="test.echo",
            actor=actor,
            idempotency_key="resume-1",
            reason="maintenance complete",
        )
        await session.commit()

    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        claimed = await store.claim_next(worker_id="operator-worker")
        assert claimed is not None
        state = await store.fail(
            claimed,
            code="invalid_input",
            kind=TaskFailureKind.INVALID_INPUT,
        )
        assert state is TaskState.DEAD_LETTER
        await session.commit()

    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=policy,
            clock=clock,
        )
        redriven = await service.redrive_dead_letter(
            task_id=task.task_id,
            actor=actor,
            idempotency_key="redrive-1",
            reason="人工确认输入已修复，只重试当前业务对象",
        )
        clock.advance(minutes=3)
        repeated = await service.redrive_dead_letter(
            task_id=task.task_id,
            actor=actor,
            idempotency_key="redrive-1",
            reason="人工确认输入已修复，只重试当前业务对象",
        )
        assert repeated.task_id == redriven.task_id
        assert redriven.task_id != task.task_id
        assert redriven.state is TaskState.QUEUED
        redrive_event_count = (
            await session.execute(
                select(func.count(OutboxEvent.event_id))
                .where(OutboxEvent.aggregate_id == redriven.task_id)
                .where(OutboxEvent.event_type == "TaskDeadLetterRedriven")
            )
        ).scalar_one()
        assert redrive_event_count == 1
        redrive_event_payload = (
            await session.execute(
                select(OutboxEvent.payload_json)
                .where(OutboxEvent.aggregate_id == redriven.task_id)
                .where(OutboxEvent.event_type == "TaskDeadLetterRedriven")
            )
        ).scalar_one()
        assert redrive_event_payload["reason"] == (
            "人工确认输入已修复，只重试当前业务对象"
        )
        original = await service.get_task(task.task_id, actor=actor)
        assert original.state is TaskState.DEAD_LETTER
        assert original.can_redrive
        health = await service.health(organization_id="org-1", actor=actor)
        assert health.dead_letter_count == 1
        await session.commit()


@pytest.mark.asyncio
async def test_operator_http_is_capability_and_scope_protected_without_enqueue_route(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 16, 18, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-http",
        idempotency_key="http-task",
        input_payload={"text": "http"},
        correlation_id="corr-http",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        second_task = await runtime.enqueue(
            command.model_copy(
                update={
                    "resource_id": "attempt-http-2",
                    "idempotency_key": "http-task-2",
                }
            )
        )
        await session.commit()

    app = FastAPI()
    app.include_router(task_runtime_router, prefix="/api/v1/admin")

    async def override_db():
        async with task_session_factory() as session:
            yield session

    admin_user = SimpleNamespace(user_id="system-admin-1", role="admin")

    async def override_reader():
        return admin_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_task_runtime_reader] = override_reader
    app.dependency_overrides[require_task_runtime_operator] = override_reader
    app.dependency_overrides[get_task_reader_actor] = lambda: OperatorActor(
        actor_id="system-admin-1",
        capabilities=frozenset({"task_runtime.read", "task_runtime.operate"}),
    )
    app.dependency_overrides[get_task_registry] = lambda: registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with task_session_factory() as session:
            session.add(
                TaskOperatorScopeGrant(
                    actor_id="system-admin-1",
                    organization_id="org-1",
                    resource_type="activity_attempt",
                    resource_id="attempt-http",
                    can_read=True,
                    can_operate=False,
                    expires_at=clock.now() + timedelta(hours=1),
                    granted_by="security-admin-1",
                    reason="已过期的故障调查授权",
                    created_at=clock.now(),
                    updated_at=clock.now(),
                )
            )
            await session.commit()
        denied = await client.get(f"/api/v1/admin/task-runtime/tasks/{task.task_id}")
        assert denied.status_code == 403

        async with task_session_factory() as session:
            session.add(
                TaskOperatorScopeGrant(
                    actor_id="system-admin-1",
                    organization_id="org-1",
                    resource_type="activity_attempt",
                    resource_id="attempt-http",
                    can_read=True,
                    can_operate=False,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    granted_by="security-admin-1",
                    reason="重新授权调查指定任务故障",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            await session.commit()
        async with task_session_factory() as session:
            grant_count = (
                await session.execute(
                    select(func.count(TaskOperatorScopeGrant.grant_id)).where(
                        TaskOperatorScopeGrant.actor_id == "system-admin-1",
                        TaskOperatorScopeGrant.resource_id == "attempt-http",
                    )
                )
            ).scalar_one()
        assert grant_count == 2
        detail = await client.get(f"/api/v1/admin/task-runtime/tasks/{task.task_id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["task_id"] == task.task_id
        denied_page = await client.get(
            "/api/v1/admin/task-runtime/tasks",
            params={"organization_id": "org-1"},
        )
        assert denied_page.status_code == 403

        async with task_session_factory() as session:
            session.add(
                TaskOperatorScopeGrant(
                    actor_id="system-admin-1",
                    organization_id="org-1",
                    resource_type="",
                    resource_id="",
                    can_read=True,
                    can_operate=True,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                    granted_by="security-admin-1",
                    reason="限时处理任务运行平台故障",
                    created_at=clock.now(),
                    updated_at=clock.now(),
                )
            )
            await session.commit()
        page = await client.get(
            "/api/v1/admin/task-runtime/tasks",
            params={
                "organization_id": "org-1",
                "state": "queued",
                "limit": 1,
            },
        )
        assert page.status_code == 200
        assert len(page.json()["data"]["items"]) == 1
        assert page.json()["data"]["has_more"]
        cursor = page.json()["data"]["next_cursor"]
        next_page = await client.get(
            "/api/v1/admin/task-runtime/tasks",
            params={
                "organization_id": "org-1",
                "state": "queued",
                "limit": 1,
                "cursor": cursor,
            },
        )
        assert next_page.status_code == 200
        assert len(next_page.json()["data"]["items"]) == 1
        first_id = page.json()["data"]["items"][0]["task_id"]
        second_id = next_page.json()["data"]["items"][0]["task_id"]
        assert {first_id, second_id} == {task.task_id, second_task.task_id}

        cancelled = await client.post(
            f"/api/v1/admin/task-runtime/tasks/{task.task_id}/cancel",
            headers={"Idempotency-Key": "cancel-http"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["state"] == "cancel_requested"
        repeated_cancel = await client.post(
            f"/api/v1/admin/task-runtime/tasks/{task.task_id}/cancel",
            headers={"Idempotency-Key": "cancel-http"},
        )
        assert repeated_cancel.status_code == 200
        assert repeated_cancel.json()["data"]["state"] == "cancel_requested"

        conflict = await client.post(
            f"/api/v1/admin/task-runtime/tasks/{task.task_id}/redrive",
            headers={"Idempotency-Key": "redrive-http"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"] == "[TASK_STATE_TRANSITION_INVALID]"
        unregistered = await client.post(
            "/api/v1/admin/task-runtime/task-types/unknown.type/pause",
            headers={"Idempotency-Key": "pause-http"},
            json={"organization_id": "org-1", "reason": "maintenance"},
        )
        assert unregistered.status_code == 422
        assert unregistered.json()["error"] == "[TASK_TYPE_NOT_REGISTERED]"

    route_methods = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("/api/v1/admin/task-runtime/tasks", "POST") not in route_methods


@pytest.mark.asyncio
async def test_concurrent_pause_command_is_idempotent(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 16, 19, 0, tzinfo=UTC))
    actor = OperatorActor(
        actor_id="system-admin-1",
        capabilities=frozenset({"task_runtime.operate"}),
    )
    policy = GrantSetTaskAccessPolicy(
        {("system-admin-1", "org-1", TaskAccessAction.OPERATE)}
    )

    async def pause():
        async with task_session_factory() as session:
            view = await TaskOperatorService(
                session,
                registry=registry,
                access_policy=policy,
                clock=clock,
            ).pause_task_type(
                organization_id="org-1",
                task_type="test.echo",
                actor=actor,
                idempotency_key="concurrent-pause",
                reason="maintenance",
            )
            await session.commit()
            return view

    first, second = await asyncio.gather(pause(), pause())
    assert first.is_paused and second.is_paused
    assert first.version == second.version == 1


@pytest.mark.asyncio
async def test_worker_renews_in_flight_lease_during_graceful_stop(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = BlockingHandler()
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(lease_seconds=5, timeout_seconds=30),
            handler=handler,
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 20, 0, tzinfo=UTC))
    sleeper = ControlledSleeper(clock)
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-heartbeat",
        idempotency_key="heartbeat-task",
        input_payload={"text": "heartbeat"},
        correlation_id="corr-heartbeat",
    )
    async with task_session_factory() as session:
        task = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).enqueue(command)
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-heartbeat",
        clock=clock,
        sleeper=sleeper,
        heartbeat_interval_seconds=2,
    )
    running = asyncio.create_task(worker.run_once())
    await handler.started.wait()
    for heartbeat_no in range(1, 4):
        await sleeper.tick_after_call(heartbeat_no)
        while sleeper.calls < heartbeat_no + 1:
            await asyncio.sleep(0)

    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.recover_expired(limit=10) == 0

    worker.request_stop()
    assert not worker.status().ready
    handler.finish.set()
    result = await running
    assert result is not None
    assert result.state is TaskState.SUCCEEDED
    assert await worker.run_once() is None

    async with task_session_factory() as session:
        projection = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
    assert projection.state is TaskState.SUCCEEDED


@pytest.mark.asyncio
async def test_deadline_timeout_cancels_handler_and_rejects_late_result(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = DeadlineBlockingHandler()
    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.deadline",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(timeout_seconds=30, max_attempts=3),
            handler=handler,
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 20, 30, tzinfo=UTC))
    async with task_session_factory() as session:
        task = await SQLAlchemyTaskRuntime(
            session,
            registry=registry,
            clock=clock,
        ).enqueue(
            TaskCommand(
                task_type="test.deadline",
                schema_version=1,
                organization_id="org-1",
                actor_id="learner-1",
                resource_type="activity_attempt",
                resource_id="attempt-deadline-running",
                idempotency_key="deadline-running",
                input_payload={"text": "must-not-arrive-late"},
                deadline_at=clock.now() + timedelta(milliseconds=50),
                correlation_id="corr-deadline-running",
            )
        )
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-deadline",
        clock=clock,
    )
    result = await worker.run_once()

    assert result is not None
    assert result.state is TaskState.DEAD_LETTER
    assert handler.started.is_set()
    assert handler.cancelled.is_set()
    assert not handler.late_side_effect
    async with task_session_factory() as session:
        projection = await SQLAlchemyTaskRuntime(
            session,
            registry=registry,
            clock=clock,
        ).get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
    assert projection.result_location is None
    assert projection.error is not None
    assert projection.error.code == "deadline_expired"
    assert "截止时间" in projection.error.message
    assert "晚到结果" in projection.error.message


@pytest.mark.asyncio
async def test_worker_uses_enqueued_policy_snapshot_after_registry_policy_drift(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    enqueue_registry = TaskRegistry()
    enqueue_registry.register(
        TaskDefinition(
            task_type="test.policy-snapshot",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(
                timeout_seconds=30,
                lease_seconds=5,
                max_attempts=3,
            ),
        )
    )
    handler = BlockingHandler()
    deployed_registry = TaskRegistry()
    deployed_registry.register(
        TaskDefinition(
            task_type="test.policy-snapshot",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(
                timeout_seconds=1,
                lease_seconds=30,
                max_attempts=9,
            ),
            handler=handler,
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 20, 45, tzinfo=UTC))
    sleeper = ControlledSleeper(clock)
    async with task_session_factory() as session:
        await SQLAlchemyTaskRuntime(
            session,
            registry=enqueue_registry,
            clock=clock,
        ).enqueue(
            TaskCommand(
                task_type="test.policy-snapshot",
                schema_version=1,
                organization_id="org-1",
                actor_id="learner-1",
                resource_type="activity_attempt",
                resource_id="attempt-policy-snapshot",
                idempotency_key="policy-snapshot",
                input_payload={"text": "snapshot"},
                correlation_id="corr-policy-snapshot",
            )
        )
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=deployed_registry,
        worker_id="worker-policy-snapshot",
        clock=clock,
        sleeper=sleeper,
        heartbeat_interval_seconds=2,
    )
    running = asyncio.create_task(worker.run_once())
    await handler.started.wait()
    await sleeper.tick_after_call(1)
    while sleeper.calls < 2:
        await asyncio.sleep(0)
    async with task_session_factory() as session:
        lease_expires_at = (
            await session.execute(select(TaskLease.expires_at))
        ).scalar_one()
    assert lease_expires_at == clock.now() + timedelta(seconds=5)

    await asyncio.sleep(1.05)
    handler.finish.set()
    result = await running
    assert result is not None
    assert result.state is TaskState.SUCCEEDED


@pytest.mark.asyncio
async def test_worker_dead_letters_claimed_task_missing_from_deployed_registry(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    enqueue_registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 16, 21, 0, tzinfo=UTC))
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-missing-registry",
        idempotency_key="missing-registry",
        input_payload={"text": "missing"},
        correlation_id="corr-missing-registry",
    )
    async with task_session_factory() as session:
        task = await SQLAlchemyTaskRuntime(
            session, registry=enqueue_registry, clock=clock
        ).enqueue(command)
        await session.commit()

    deployed_registry = TaskRegistry()
    deployed_registry.register(
        TaskDefinition(
            task_type="test.echo",
            schema_version=2,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(),
            handler=VersionedHandler(2),
        )
    )
    worker = TaskWorker(
        task_session_factory,
        registry=deployed_registry,
        worker_id="worker-missing-registry",
        clock=clock,
    )
    result = await worker.run_once()
    assert result is not None
    assert result.state is TaskState.DEAD_LETTER

    async with task_session_factory() as session:
        projection = await SQLAlchemyTaskRuntime(
            session, registry=enqueue_registry, clock=clock
        ).get(
            task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
    assert projection.error is not None
    assert projection.error.code == "task_type_not_registered"


@pytest.mark.asyncio
async def test_queued_cancel_is_requested_then_acknowledged_by_worker_maintenance(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 16, 22, 0, tzinfo=UTC))
    actor = ActorContext(organization_id="org-1", actor_id="learner-1")
    command = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-queued-cancel",
        idempotency_key="queued-cancel",
        input_payload={"text": "cancel before start"},
        correlation_id="corr-queued-cancel",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        task = await runtime.enqueue(command)
        requested = await runtime.request_cancel(task.task_id, actor)
        assert requested.state is TaskState.CANCEL_REQUESTED
        await session.commit()

    worker = TaskWorker(
        task_session_factory,
        registry=registry,
        worker_id="worker-cancel-maintenance",
        clock=clock,
    )
    assert await worker.run_once() is None
    async with task_session_factory() as session:
        cancelled = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).get(task.task_id, actor)
    assert cancelled.state is TaskState.CANCELLED
    assert cancelled.attempt_count == 0
    assert cancelled.error is None

    retry_command = command.model_copy(
        update={
            "resource_id": "attempt-retry-cancel",
            "idempotency_key": "retry-cancel",
        }
    )
    async with task_session_factory() as session:
        retry_task = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).enqueue(retry_command)
        await session.commit()
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        claimed = await store.claim_next(worker_id="retry-cancel-worker")
        assert claimed is not None
        assert (
            await store.fail(
                claimed,
                code="provider_unavailable",
                kind=TaskFailureKind.PROVIDER_TEMPORARY,
            )
            is TaskState.RETRY_WAIT
        )
        await session.commit()
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        retry_requested = await runtime.request_cancel(retry_task.task_id, actor)
        assert retry_requested.state is TaskState.CANCEL_REQUESTED
        await session.commit()
    assert await worker.run_once() is None
    async with task_session_factory() as session:
        retry_cancelled = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).get(retry_task.task_id, actor)
    assert retry_cancelled.state is TaskState.CANCELLED
    assert retry_cancelled.attempt_count == 1


@pytest.mark.asyncio
async def test_task_type_claim_limits_and_queued_deadline_reaping(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    registry.register(
        TaskDefinition(
            task_type="test.other",
            schema_version=1,
            input_model=EchoTaskInput,
            result_model=EchoTaskResult,
            policy=TaskPolicy(max_attempts=3),
        )
    )
    clock = FixedClock(datetime(2026, 7, 16, 23, 0, tzinfo=UTC))
    actor = OperatorActor(
        actor_id="system-admin-1",
        capabilities=frozenset({"task_runtime.read", "task_runtime.operate"}),
    )
    policy = GrantSetTaskAccessPolicy(
        {
            ("system-admin-1", "org-1", TaskAccessAction.READ),
            ("system-admin-1", "org-1", TaskAccessAction.OPERATE),
        }
    )
    async with task_session_factory() as session:
        service = TaskOperatorService(
            session,
            registry=registry,
            access_policy=policy,
            clock=clock,
        )
        control = await service.configure_task_type_limits(
            organization_id="org-1",
            task_type="test.echo",
            actor=actor,
            idempotency_key="limits-1",
            max_concurrency=1,
            rate_limit_per_minute=1,
            reason="protect provider",
        )
        assert control.max_concurrency == 1
        assert control.rate_limit_per_minute == 1
        await session.commit()

    base = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="attempt-limited-1",
        idempotency_key="limited-1",
        input_payload={"text": "limited"},
        correlation_id="corr-limited",
    )
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        await runtime.enqueue(base)
        await runtime.enqueue(
            base.model_copy(
                update={
                    "resource_id": "attempt-limited-2",
                    "idempotency_key": "limited-2",
                }
            )
        )
        await session.commit()

    async def claim_limited(worker_id: str):
        async with task_session_factory() as session:
            claim = await SQLAlchemyTaskWorkerStore(session, clock=clock).claim_next(
                worker_id=worker_id
            )
            await session.commit()
            return claim

    first_claims = await asyncio.gather(
        claim_limited("limited-a"), claim_limited("limited-b")
    )
    claim = next(item for item in first_claims if item is not None)
    assert sum(item is not None for item in first_claims) == 1
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert (
            await store.fail(
                claim,
                code="provider_unavailable",
                kind=TaskFailureKind.PROVIDER_TEMPORARY,
            )
            is TaskState.RETRY_WAIT
        )
        await session.commit()
    assert await claim_limited("limited-c") is None
    async with task_session_factory() as session:
        await SQLAlchemyTaskRuntime(session, registry=registry, clock=clock).enqueue(
            base.model_copy(
                update={
                    "task_type": "test.other",
                    "resource_id": "attempt-unblocked-low-priority",
                    "idempotency_key": "unblocked-low-priority",
                    "priority": 0,
                }
            )
        )
        await session.commit()
    unblocked = await claim_limited("limited-other")
    assert unblocked is not None
    assert unblocked.task_type == "test.other"
    clock.advance(seconds=61)
    assert await claim_limited("limited-d") is not None

    deadline_command = base.model_copy(
        update={
            "resource_id": "attempt-deadline",
            "idempotency_key": "deadline-task",
            "deadline_at": clock.now() + timedelta(seconds=5),
        }
    )
    async with task_session_factory() as session:
        deadline_task = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).enqueue(deadline_command)
        await session.commit()
    clock.advance(seconds=6)
    async with task_session_factory() as session:
        store = SQLAlchemyTaskWorkerStore(session, clock=clock)
        assert await store.reap_expired_queued(limit=10) == 1
        await session.commit()
    async with task_session_factory() as session:
        deadline_projection = await SQLAlchemyTaskRuntime(
            session, registry=registry, clock=clock
        ).get(
            deadline_task.task_id,
            ActorContext(organization_id="org-1", actor_id="learner-1"),
        )
        health = await TaskOperatorService(
            session,
            registry=registry,
            access_policy=policy,
            clock=clock,
        ).health(organization_id="org-1", actor=actor)
    assert deadline_projection.state is TaskState.DEAD_LETTER
    assert deadline_projection.error is not None
    assert deadline_projection.error.code == "deadline_expired"
    assert health.retry_rate > 0
    assert health.average_processing_latency_ms >= 0
    assert health.metrics_window_minutes == 15


@pytest.mark.asyncio
async def test_aged_low_priority_lane_prevents_continuous_high_priority_starvation(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = build_registry()
    clock = FixedClock(datetime(2026, 7, 17, 0, 0, tzinfo=UTC))
    base = TaskCommand(
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="learner-1",
        resource_type="activity_attempt",
        resource_id="aged-low-priority",
        idempotency_key="aged-low-priority",
        input_payload={"text": "aged"},
        priority=0,
        correlation_id="corr-aged",
    )
    async with task_session_factory() as session:
        low = await SQLAlchemyTaskRuntime(
            session,
            registry=registry,
            clock=clock,
        ).enqueue(base)
        await session.commit()

    clock.advance(minutes=6)
    async with task_session_factory() as session:
        runtime = SQLAlchemyTaskRuntime(session, registry=registry, clock=clock)
        for index in range(20):
            await runtime.enqueue(
                base.model_copy(
                    update={
                        "resource_id": f"fresh-high-{index}",
                        "idempotency_key": f"fresh-high-{index}",
                        "priority": 100,
                        "correlation_id": f"corr-high-{index}",
                    }
                )
            )
        await session.commit()

    async with task_session_factory() as session:
        claim = await SQLAlchemyTaskWorkerStore(
            session,
            clock=clock,
        ).claim_next(
            worker_id="aged-lane-worker",
            task_types=frozenset({"test.echo"}),
        )
        await session.commit()
    assert claim is not None
    assert claim.task_id == low.task_id


@pytest.mark.asyncio
async def test_runtime_hot_queries_have_matching_postgres_index_plans(
    task_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with task_session_factory() as session:
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        claim_plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON, COSTS OFF)
                    SELECT task_id
                    FROM durable_tasks
                    WHERE state = 'queued' AND next_run_at <= CURRENT_TIMESTAMP
                    ORDER BY priority DESC, next_run_at ASC, created_at ASC, task_id ASC
                    LIMIT 1
                    """
                )
            )
        ).scalar_one()
        type_claim_plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON, COSTS OFF)
                    SELECT task_id
                    FROM durable_tasks
                    WHERE task_type = 'test.echo'
                      AND state = 'queued'
                      AND next_run_at <= CURRENT_TIMESTAMP
                    ORDER BY priority DESC, next_run_at ASC, created_at ASC, task_id ASC
                    LIMIT 1
                    """
                )
            )
        ).scalar_one()
        aged_claim_plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON, COSTS OFF)
                    SELECT task_id
                    FROM durable_tasks
                    WHERE task_type = 'test.echo'
                      AND state = 'queued'
                      AND created_at <= CURRENT_TIMESTAMP - INTERVAL '5 minutes'
                      AND next_run_at <= CURRENT_TIMESTAMP
                    ORDER BY created_at ASC, next_run_at ASC, task_id ASC
                    LIMIT 1
                    """
                )
            )
        ).scalar_one()
        keyset_plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON, COSTS OFF)
                    SELECT task_id
                    FROM durable_tasks
                    WHERE organization_id = 'org-1'
                    ORDER BY updated_at DESC, task_id DESC
                    LIMIT 50
                    """
                )
            )
        ).scalar_one()
        metrics_plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON, COSTS OFF)
                    SELECT task_id
                    FROM task_attempts
                    WHERE started_at >= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                    ORDER BY started_at ASC, task_id ASC
                    """
                )
            )
        ).scalar_one()
        durable_task_indexes = set(
            (
                await session.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema() "
                        "AND tablename = 'durable_tasks'"
                    )
                )
            ).scalars()
        )

    assert "ix_durable_tasks_claim" in json.dumps(claim_plan)
    assert any(
        index_name in json.dumps(type_claim_plan)
        for index_name in (
            "ix_durable_tasks_claim",
            "ix_durable_tasks_type_claim",
        )
    )
    assert "ix_durable_tasks_type_claim" in durable_task_indexes
    assert any(
        index_name in json.dumps(aged_claim_plan)
        for index_name in (
            "ix_durable_tasks_aged_claim",
            "ix_durable_tasks_type_aged_claim",
        )
    )
    assert "ix_durable_tasks_aged_claim" in durable_task_indexes
    assert "ix_durable_tasks_type_aged_claim" in durable_task_indexes
    assert "ix_durable_tasks_org_updated_keyset" in json.dumps(keyset_plan)
    assert "ix_task_attempts_started_task" in json.dumps(metrics_plan)
