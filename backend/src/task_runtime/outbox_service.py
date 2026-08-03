"""Long-running Outbox dispatcher loop with graceful drain and probe state."""

from __future__ import annotations

import asyncio
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from common.monitoring.logger import get_logger
from task_runtime.outbox import DispatchReport

logger = get_logger(__name__)


class OutboxDispatchLoopPort(Protocol):
    async def dispatch_once(self, *, limit: int = 100) -> DispatchReport: ...


class OutboxDispatcherStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    live: bool
    ready: bool
    accepting_new_batches: bool
    in_flight_batches: int
    loop_failure_count: int
    last_error_code: str | None
    last_report: DispatchReport | None


class OutboxDispatcherService:
    def __init__(
        self,
        dispatcher: OutboxDispatchLoopPort,
        *,
        poll_interval_seconds: float,
        batch_size: int,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("Outbox 轮询间隔必须大于 0。")
        if batch_size < 1:
            raise ValueError("Outbox 批次大小必须至少为 1。")
        self._dispatcher = dispatcher
        self._poll_interval_seconds = poll_interval_seconds
        self._batch_size = batch_size
        self._stop_requested = asyncio.Event()
        self._live = False
        self._ready = False
        self._in_flight_batches = 0
        self._loop_failure_count = 0
        self._last_error_code: str | None = None
        self._last_report: DispatchReport | None = None

    def request_stop(self) -> None:
        self._stop_requested.set()

    def status(self) -> OutboxDispatcherStatus:
        accepting = self._live and not self._stop_requested.is_set()
        return OutboxDispatcherStatus(
            live=self._live,
            ready=accepting and self._ready,
            accepting_new_batches=accepting,
            in_flight_batches=self._in_flight_batches,
            loop_failure_count=self._loop_failure_count,
            last_error_code=self._last_error_code,
            last_report=self._last_report,
        )

    async def run(self) -> None:
        self._live = True
        try:
            while not self._stop_requested.is_set():
                self._in_flight_batches = 1
                try:
                    report = await self._dispatcher.dispatch_once(
                        limit=self._batch_size
                    )
                except Exception as exc:
                    self._ready = False
                    self._loop_failure_count += 1
                    self._last_error_code = type(exc).__name__
                    logger.error(
                        "outbox_dispatch_iteration_failed",
                        error_code=self._last_error_code,
                        failure_count=self._loop_failure_count,
                    )
                    await self._wait_for_poll_or_stop()
                else:
                    self._ready = True
                    self._last_error_code = None
                    self._last_report = report
                    if report.claimed == 0:
                        await self._wait_for_poll_or_stop()
                finally:
                    self._in_flight_batches = 0
        finally:
            self._ready = False
            self._live = False

    async def _wait_for_poll_or_stop(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_requested.wait(),
                timeout=self._poll_interval_seconds,
            )
        except TimeoutError:
            pass


__all__ = [
    "OutboxDispatchLoopPort",
    "OutboxDispatcherService",
    "OutboxDispatcherStatus",
]
