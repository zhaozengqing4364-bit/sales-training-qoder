"""Long-running worker loop and dependency-free liveness/readiness probes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from common.monitoring.logger import get_logger
from task_runtime.worker import TaskRunResult, WorkerStatus

logger = get_logger(__name__)


class WorkerLoopPort(Protocol):
    async def run_once(self) -> TaskRunResult | None: ...

    def request_stop(self) -> None: ...

    def status(self) -> WorkerStatus: ...


class WorkerServiceStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    live: bool
    ready: bool
    accepting_new_tasks: bool
    in_flight: int
    loop_failure_count: int
    last_error_code: str | None
    supported_task_types: tuple[str, ...]


class TaskWorkerService:
    def __init__(
        self,
        worker: WorkerLoopPort,
        *,
        poll_interval_seconds: float,
        max_parallelism: int,
        supported_task_types: tuple[str, ...] = (),
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("Worker 轮询间隔必须大于 0。")
        if max_parallelism < 1:
            raise ValueError("Worker 并行数必须至少为 1。")
        self._worker = worker
        self._poll_interval_seconds = poll_interval_seconds
        self._max_parallelism = max_parallelism
        self._supported_task_types = tuple(sorted(supported_task_types))
        self._stop_requested = asyncio.Event()
        self._live = False
        self._loop_failure_count = 0
        self._last_error_code: str | None = None

    def request_stop(self) -> None:
        self._stop_requested.set()
        self._worker.request_stop()

    def status(self) -> WorkerServiceStatus:
        worker_status = self._worker.status()
        last_error_code = None if worker_status.ready else self._last_error_code
        accepting = (
            self._live
            and not self._stop_requested.is_set()
            and worker_status.accepting_new_tasks
        )
        return WorkerServiceStatus(
            live=self._live,
            ready=(accepting and worker_status.ready and last_error_code is None),
            accepting_new_tasks=accepting,
            in_flight=worker_status.in_flight,
            loop_failure_count=self._loop_failure_count,
            last_error_code=last_error_code,
            supported_task_types=self._supported_task_types,
        )

    async def run(self) -> None:
        self._live = True
        in_progress: set[asyncio.Task[TaskRunResult | None]] = set()
        try:
            while not self._stop_requested.is_set():
                while (
                    len(in_progress) < self._max_parallelism
                    and not self._stop_requested.is_set()
                ):
                    in_progress.add(asyncio.create_task(self._worker.run_once()))
                if not in_progress:
                    await self._wait_for_poll_or_stop()
                    continue
                done, _ = await asyncio.wait(
                    in_progress,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                in_progress.difference_update(done)
                all_idle = True
                for completed in done:
                    try:
                        result = completed.result()
                    except Exception as exc:
                        self._loop_failure_count += 1
                        self._last_error_code = type(exc).__name__
                        logger.error(
                            "task_worker_iteration_failed",
                            error_code=self._last_error_code,
                            failure_count=self._loop_failure_count,
                        )
                    else:
                        self._last_error_code = None
                        all_idle = all_idle and result is None
                if all_idle or not self._worker.status().ready:
                    await self._wait_for_poll_or_stop()
        finally:
            self._worker.request_stop()
            if in_progress:
                results = await asyncio.gather(*in_progress, return_exceptions=True)
                for drain_result in results:
                    if isinstance(drain_result, Exception):
                        logger.error(
                            "task_worker_drain_failed",
                            error_code=type(drain_result).__name__,
                        )
            self._live = False

    async def _wait_for_poll_or_stop(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_requested.wait(),
                timeout=self._poll_interval_seconds,
            )
        except TimeoutError:
            pass


class WorkerProbeServer:
    def __init__(
        self,
        status_provider: Callable[[], Any],
        *,
        host: str,
        port: int,
    ) -> None:
        self._status_provider = status_provider
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("Worker probe 尚未启动。")
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle,
            host=self._host,
            port=self._port,
        )

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=2,
            )
            request_line = request.split(b"\r\n", 1)[0].decode(
                "ascii", errors="replace"
            )
            method, path, _ = request_line.split(" ", 2)
            status = self._status_provider()
            if method != "GET":
                status_code = 405
                payload = {"error": "method_not_allowed"}
            elif path == "/live":
                status_code = 200 if status.live else 503
                payload = status.model_dump(mode="json")
            elif path == "/ready":
                status_code = 200 if status.ready else 503
                payload = status.model_dump(mode="json")
            elif path == "/status":
                status_code = 200
                payload = status.model_dump(mode="json")
            else:
                status_code = 404
                payload = {"error": "not_found"}
        except (asyncio.IncompleteReadError, TimeoutError, ValueError):
            status_code = 400
            payload = {"error": "bad_request"}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        reason = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
            503: "Service Unavailable",
        }[status_code]
        writer.write(
            (
                f"HTTP/1.1 {status_code} {reason}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii")
            + body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()


__all__ = [
    "TaskWorkerService",
    "WorkerLoopPort",
    "WorkerProbeServer",
    "WorkerServiceStatus",
]
