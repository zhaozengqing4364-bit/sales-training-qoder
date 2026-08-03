from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel

import task_runtime.worker as worker_module
from task_runtime.contracts import (
    ClaimedTask,
    TaskCompletion,
    TaskPolicy,
    TaskResultKind,
    TaskState,
)
from task_runtime.errors import TaskInfrastructureError
from task_runtime.registry import TaskDefinition, TaskRegistry
from task_runtime.worker import TaskWorker, WorkerStatus
from task_runtime.worker_main import WorkerSettings, resolve_worker_task_types
from task_runtime.worker_service import TaskWorkerService, WorkerProbeServer


class FakeWorker:
    def __init__(self) -> None:
        self.calls = 0
        self.stopped = False
        self.database_ready = True

    async def run_once(self):
        self.calls += 1
        await asyncio.sleep(0)
        return None

    def request_stop(self) -> None:
        self.stopped = True

    def status(self) -> WorkerStatus:
        return WorkerStatus(
            live=True,
            ready=not self.stopped and self.database_ready,
            accepting_new_tasks=not self.stopped,
            in_flight=0,
        )


class RecoveringWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__()
        self.failed = asyncio.Event()
        self.allow_recovery = asyncio.Event()

    async def run_once(self):
        self.calls += 1
        if self.calls == 1:
            self.database_ready = False
            self.failed.set()
            raise RuntimeError("database unavailable")
        await self.allow_recovery.wait()
        self.database_ready = True
        return None


class BlockingBacklogWorker(FakeWorker):
    def __init__(self) -> None:
        super().__init__()
        self.database_ready = False
        self.claim_committed = asyncio.Event()
        self.finish = asyncio.Event()

    async def run_once(self):
        self.calls += 1
        self.database_ready = True
        self.claim_committed.set()
        await self.finish.wait()
        return None


class CommitControlledSession:
    def __init__(self, controller: CommitController) -> None:
        self._controller = controller

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        if self._controller.fail_commit:
            raise RuntimeError("database commit failed")


class CommitController:
    def __init__(self) -> None:
        self.fail_commit = False

    def session(self) -> CommitControlledSession:
        return CommitControlledSession(self)


def _claim() -> ClaimedTask:
    now = datetime(2026, 7, 16, tzinfo=UTC)
    policy = TaskPolicy()
    return ClaimedTask(
        task_id="task-1",
        task_type="test.echo",
        schema_version=1,
        organization_id="org-1",
        actor_id="actor-1",
        resource_type="training",
        resource_id="training-1",
        input_payload={"value": "hello"},
        timeout_seconds=policy.timeout_seconds,
        lease_seconds=policy.lease_seconds,
        max_attempts=policy.max_attempts,
        deadline_at=None,
        retry_policy=policy,
        attempt_id="attempt-1",
        attempt_no=1,
        worker_id="worker-1",
        lease_token="lease-token",
        lease_expires_at=now + timedelta(seconds=policy.lease_seconds),
        fence_generation=1,
        correlation_id="correlation-1",
        trace_id=None,
    )


def _completion() -> TaskCompletion:
    return TaskCompletion(
        structured_payload={"value": "done"},
        result_kind=TaskResultKind.COMPLETE,
        resource_type="training_result",
        resource_id="result-1",
        location="/training-results/result-1",
    )


async def _probe(port: int, path: str) -> tuple[int, str]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = (await reader.read()).decode("utf-8")
    writer.close()
    await writer.wait_closed()
    status = int(response.split("\r\n", 1)[0].split()[1])
    return status, response.split("\r\n\r\n", 1)[1]


@pytest.mark.asyncio
async def test_worker_service_exposes_live_ready_and_drains_on_stop() -> None:
    worker = FakeWorker()
    service = TaskWorkerService(
        worker,
        poll_interval_seconds=0.01,
        max_parallelism=2,
    )
    probe = WorkerProbeServer(
        service.status,
        host="127.0.0.1",
        port=0,
    )
    await probe.start()
    running = asyncio.create_task(service.run())
    while not service.status().ready:
        await asyncio.sleep(0)

    live_status, live_body = await _probe(probe.bound_port, "/live")
    ready_status, ready_body = await _probe(probe.bound_port, "/ready")
    assert live_status == 200 and '"live":true' in live_body
    assert ready_status == 200 and '"ready":true' in ready_body

    service.request_stop()
    stopped_ready_status, _ = await _probe(probe.bound_port, "/ready")
    assert stopped_ready_status == 503
    await running
    assert worker.stopped
    assert not service.status().live
    await probe.close()


@pytest.mark.asyncio
async def test_worker_readiness_fails_on_iteration_error_then_recovers() -> None:
    worker = RecoveringWorker()
    service = TaskWorkerService(
        worker,
        poll_interval_seconds=0.01,
        max_parallelism=1,
    )
    probe = WorkerProbeServer(service.status, host="127.0.0.1", port=0)
    await probe.start()
    running = asyncio.create_task(service.run())
    await worker.failed.wait()

    failed_status, failed_body = await _probe(probe.bound_port, "/ready")
    assert failed_status == 503
    assert '"last_error_code":"RuntimeError"' in failed_body

    worker.allow_recovery.set()
    while not service.status().ready:
        await asyncio.sleep(0)
    recovered_status, recovered_body = await _probe(probe.bound_port, "/ready")
    assert recovered_status == 200
    assert '"last_error_code":null' in recovered_body

    service.request_stop()
    await running
    await probe.close()


@pytest.mark.asyncio
async def test_worker_is_ready_after_claim_commit_while_handler_is_still_running() -> (
    None
):
    worker = BlockingBacklogWorker()
    service = TaskWorkerService(
        worker,
        poll_interval_seconds=0.01,
        max_parallelism=1,
    )
    probe = WorkerProbeServer(service.status, host="127.0.0.1", port=0)
    await probe.start()
    running = asyncio.create_task(service.run())
    await worker.claim_committed.wait()

    ready_status, ready_body = await _probe(probe.bound_port, "/ready")
    assert ready_status == 200
    assert '"ready":true' in ready_body

    service.request_stop()
    worker.finish.set()
    await running
    await probe.close()


@pytest.mark.asyncio
async def test_completion_commit_failure_lowers_readiness_then_success_recovers(
    monkeypatch,
) -> None:
    class CompletionStore:
        def __init__(self, session, *, clock) -> None:
            del session, clock

        async def complete(self, claim, outcome) -> TaskState:
            del claim, outcome
            return TaskState.SUCCEEDED

    monkeypatch.setattr(
        worker_module,
        "SQLAlchemyTaskWorkerStore",
        CompletionStore,
    )
    controller = CommitController()
    worker = TaskWorker(
        controller.session,  # type: ignore[arg-type]
        registry=TaskRegistry(),
        worker_id="worker-1",
    )

    assert (
        await worker._complete(_claim(), _completion())  # noqa: SLF001
        is TaskState.SUCCEEDED
    )
    assert worker.status().ready

    controller.fail_commit = True
    with pytest.raises(TaskInfrastructureError, match="complete"):
        await worker._complete(_claim(), _completion())  # noqa: SLF001
    assert not worker.status().ready

    controller.fail_commit = False
    assert (
        await worker._complete(_claim(), _completion())  # noqa: SLF001
        is TaskState.SUCCEEDED
    )
    assert worker.status().ready


def test_worker_settings_validate_operational_limits(monkeypatch) -> None:
    monkeypatch.setenv("TASK_WORKER_ID", "worker-test")
    monkeypatch.setenv("TASK_WORKER_TASK_TYPES", "test.echo,test.other")
    monkeypatch.setenv("TASK_WORKER_MAX_PARALLELISM", "3")
    monkeypatch.setenv("TASK_WORKER_POLL_SECONDS", "0.25")
    monkeypatch.setenv("TASK_WORKER_PROBE_PORT", "4555")

    settings = WorkerSettings.from_env()

    assert settings.worker_id == "worker-test"
    assert settings.task_types == frozenset({"test.echo", "test.other"})
    assert settings.max_parallelism == 3
    assert settings.poll_interval_seconds == 0.25
    assert settings.probe_port == 4555


def test_worker_task_type_configuration_fails_closed_without_handler() -> None:
    class Input(BaseModel):
        value: str

    registry = TaskRegistry()
    registry.register(
        TaskDefinition(
            task_type="test.no-handler",
            schema_version=1,
            input_model=Input,
            result_model=Input,
            policy=TaskPolicy(),
        )
    )

    with pytest.raises(ValueError, match="未配置 Worker handler"):
        resolve_worker_task_types(registry, frozenset({"test.no-handler"}))

    with pytest.raises(ValueError, match="没有配置任何可执行任务类型"):
        resolve_worker_task_types(TaskRegistry(), None)
