"""Independent durable-task Worker process entrypoint."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
from dataclasses import dataclass

from common.ai.config_manager import initialize_config_manager
from common.db.session import AsyncSessionLocal, verify_database_schema
from common.monitoring.logger import get_logger
from foundation_task_bootstrap import register_foundation_worker_tasks
from task_runtime.composition import get_application_task_registry
from task_runtime.registry import TaskRegistry
from task_runtime.worker import TaskWorker
from task_runtime.worker_service import TaskWorkerService, WorkerProbeServer

logger = get_logger(__name__)


def _positive_float(name: str, default: str) -> float:
    value = float(os.getenv(name, default))
    if value <= 0:
        raise ValueError(f"{name} 必须大于 0。")
    return value


def _positive_int(name: str, default: str) -> int:
    value = int(os.getenv(name, default))
    if value < 1:
        raise ValueError(f"{name} 必须至少为 1。")
    return value


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    worker_id: str
    task_types: frozenset[str] | None
    max_parallelism: int
    poll_interval_seconds: float
    heartbeat_interval_seconds: float | None
    probe_host: str
    probe_port: int

    @classmethod
    def from_env(cls) -> WorkerSettings:
        raw_task_types = os.getenv("TASK_WORKER_TASK_TYPES", "").strip()
        task_types = (
            frozenset(
                item.strip() for item in raw_task_types.split(",") if item.strip()
            )
            if raw_task_types
            else None
        )
        raw_heartbeat = os.getenv("TASK_WORKER_HEARTBEAT_SECONDS", "").strip()
        heartbeat = float(raw_heartbeat) if raw_heartbeat else None
        if heartbeat is not None and heartbeat <= 0:
            raise ValueError("TASK_WORKER_HEARTBEAT_SECONDS 必须大于 0。")
        probe_port = int(os.getenv("TASK_WORKER_PROBE_PORT", "3446"))
        if not 1 <= probe_port <= 65_535:
            raise ValueError("TASK_WORKER_PROBE_PORT 必须是有效端口。")
        worker_id = os.getenv("TASK_WORKER_ID", "").strip() or (
            f"{socket.gethostname()}-{os.getpid()}"
        )
        return cls(
            worker_id=worker_id,
            task_types=task_types,
            max_parallelism=_positive_int("TASK_WORKER_MAX_PARALLELISM", "4"),
            poll_interval_seconds=_positive_float("TASK_WORKER_POLL_SECONDS", "1"),
            heartbeat_interval_seconds=heartbeat,
            probe_host=os.getenv("TASK_WORKER_PROBE_HOST", "127.0.0.1").strip(),
            probe_port=probe_port,
        )


def resolve_worker_task_types(
    registry: TaskRegistry,
    requested: frozenset[str] | None,
) -> frozenset[str]:
    candidates = requested or frozenset(registry.registered_types())
    if not candidates:
        raise ValueError("Worker 没有配置任何可执行任务类型。")
    executable: set[str] = set()
    for task_type in candidates:
        definitions = registry.definitions_for_type(task_type)
        if any(definition.handler is None for definition in definitions):
            raise ValueError(f"任务类型未配置 Worker handler：{task_type}")
        executable.add(task_type)
    if not executable:
        raise ValueError("Worker 没有配置任何可执行任务类型。")
    return frozenset(executable)


async def run_worker(settings: WorkerSettings) -> None:
    await verify_database_schema()
    await initialize_config_manager()
    register_foundation_worker_tasks()
    registry = get_application_task_registry()
    task_types = resolve_worker_task_types(registry, settings.task_types)
    worker = TaskWorker(
        AsyncSessionLocal,
        registry=registry,
        worker_id=settings.worker_id,
        task_types=task_types,
        heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
    )
    service = TaskWorkerService(
        worker,
        poll_interval_seconds=settings.poll_interval_seconds,
        max_parallelism=settings.max_parallelism,
        supported_task_types=tuple(task_types),
    )
    probe = WorkerProbeServer(
        service.status,
        host=settings.probe_host,
        port=settings.probe_port,
    )
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, service.request_stop)
        except NotImplementedError:  # pragma: no cover - Windows event loops
            pass
    await probe.start()
    logger.info(
        "task_worker_started",
        worker_id=settings.worker_id,
        probe_port=probe.bound_port,
        max_parallelism=settings.max_parallelism,
        task_type_count=len(task_types),
    )
    try:
        await service.run()
    finally:
        await probe.close()
        logger.info("task_worker_stopped", worker_id=settings.worker_id)


def main() -> None:
    asyncio.run(run_worker(WorkerSettings.from_env()))


if __name__ == "__main__":
    main()


__all__ = [
    "WorkerSettings",
    "main",
    "resolve_worker_task_types",
    "run_worker",
]
