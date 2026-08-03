"""Independent transactional Outbox dispatcher process entrypoint."""

from __future__ import annotations

import asyncio
import os
import signal
import socket
from dataclasses import dataclass

from common.db.session import AsyncSessionLocal, verify_database_schema
from common.monitoring.logger import get_logger
from task_runtime.composition import get_application_event_transport
from task_runtime.outbox import EventTransport, OutboxDispatcher, OutboxEnvelope
from task_runtime.outbox_service import OutboxDispatcherService
from task_runtime.worker_service import WorkerProbeServer

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


class DeterministicDevelopmentTransport:
    """Explicit local-only transport; never selected implicitly or in production."""

    async def publish(self, event: OutboxEnvelope) -> None:
        logger.info(
            "outbox_development_event_published",
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            delivery_attempt=event.delivery_attempt,
        )


def resolve_outbox_transport() -> EventTransport:
    configured = get_application_event_transport()
    if configured is not None:
        return configured
    if os.getenv("OUTBOX_DISPATCHER_ALLOW_DEV_FAKE", "0") != "1":
        raise ValueError("Outbox Dispatcher 未配置生产 EventTransport，拒绝启动。")
    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    if environment not in {"development", "local", "test"}:
        raise ValueError(
            "Deterministic Outbox transport 仅允许显式用于本地或测试环境。"
        )
    return DeterministicDevelopmentTransport()


@dataclass(frozen=True, slots=True)
class OutboxDispatcherSettings:
    dispatcher_id: str
    batch_size: int
    poll_interval_seconds: float
    lease_seconds: int
    retry_backoff_seconds: int
    max_attempts: int
    publish_timeout_seconds: float
    probe_host: str
    probe_port: int

    @classmethod
    def from_env(cls) -> OutboxDispatcherSettings:
        probe_port = int(os.getenv("OUTBOX_DISPATCHER_PROBE_PORT", "3447"))
        if not 1 <= probe_port <= 65_535:
            raise ValueError("OUTBOX_DISPATCHER_PROBE_PORT 必须是有效端口。")
        dispatcher_id = os.getenv("OUTBOX_DISPATCHER_ID", "").strip() or (
            f"{socket.gethostname()}-{os.getpid()}"
        )
        return cls(
            dispatcher_id=dispatcher_id,
            batch_size=_positive_int("OUTBOX_DISPATCHER_BATCH_SIZE", "100"),
            poll_interval_seconds=_positive_float(
                "OUTBOX_DISPATCHER_POLL_SECONDS", "1"
            ),
            lease_seconds=_positive_int("OUTBOX_DISPATCHER_LEASE_SECONDS", "30"),
            retry_backoff_seconds=_positive_int("OUTBOX_DISPATCHER_RETRY_SECONDS", "5"),
            max_attempts=_positive_int("OUTBOX_DISPATCHER_MAX_ATTEMPTS", "10"),
            publish_timeout_seconds=_positive_float(
                "OUTBOX_DISPATCHER_PUBLISH_TIMEOUT_SECONDS", "10"
            ),
            probe_host=os.getenv("OUTBOX_DISPATCHER_PROBE_HOST", "127.0.0.1").strip(),
            probe_port=probe_port,
        )


async def run_outbox_dispatcher(settings: OutboxDispatcherSettings) -> None:
    transport = resolve_outbox_transport()
    await verify_database_schema()
    dispatcher = OutboxDispatcher(
        AsyncSessionLocal,
        transport=transport,
        dispatcher_id=settings.dispatcher_id,
        lease_seconds=settings.lease_seconds,
        retry_backoff_seconds=settings.retry_backoff_seconds,
        max_attempts=settings.max_attempts,
        publish_timeout_seconds=settings.publish_timeout_seconds,
    )
    service = OutboxDispatcherService(
        dispatcher,
        poll_interval_seconds=settings.poll_interval_seconds,
        batch_size=settings.batch_size,
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
        "outbox_dispatcher_started",
        dispatcher_id=settings.dispatcher_id,
        probe_port=probe.bound_port,
        batch_size=settings.batch_size,
    )
    try:
        await service.run()
    finally:
        await probe.close()
        logger.info(
            "outbox_dispatcher_stopped",
            dispatcher_id=settings.dispatcher_id,
        )


def main() -> None:
    asyncio.run(run_outbox_dispatcher(OutboxDispatcherSettings.from_env()))


if __name__ == "__main__":
    main()


__all__ = [
    "DeterministicDevelopmentTransport",
    "OutboxDispatcherSettings",
    "main",
    "resolve_outbox_transport",
    "run_outbox_dispatcher",
]
