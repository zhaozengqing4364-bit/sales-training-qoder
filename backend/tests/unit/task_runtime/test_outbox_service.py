from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

import task_runtime.outbox as outbox_module
from task_runtime.composition import configure_application_event_transport
from task_runtime.outbox import (
    DispatchReport,
    OutboxDispatcher,
    OutboxEnvelope,
)
from task_runtime.outbox_main import (
    DeterministicDevelopmentTransport,
    resolve_outbox_transport,
)
from task_runtime.outbox_service import OutboxDispatcherService
from task_runtime.worker_service import WorkerProbeServer


class BlockingDispatcher:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.finish = asyncio.Event()

    async def dispatch_once(self, *, limit: int = 100) -> DispatchReport:
        assert limit == 25
        self.entered.set()
        await self.finish.wait()
        return DispatchReport(claimed=1, published=1, failed=0, dead_lettered=0)


class RecoveringDispatcher:
    def __init__(self) -> None:
        self.calls = 0
        self.failed = asyncio.Event()
        self.recovered = asyncio.Event()
        self.allow_recovery = asyncio.Event()

    async def dispatch_once(self, *, limit: int = 100) -> DispatchReport:
        del limit
        self.calls += 1
        if self.calls == 1:
            self.failed.set()
            raise RuntimeError("database unavailable")
        await self.allow_recovery.wait()
        self.recovered.set()
        return DispatchReport(claimed=0, published=0, failed=0, dead_lettered=0)


class DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        return None


def _envelope(event_id: str) -> OutboxEnvelope:
    return OutboxEnvelope(
        event_id=event_id,
        event_type="TestEvent",
        schema_version=1,
        occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
        organization_id="org-1",
        actor_id=None,
        trace_id=None,
        correlation_id="corr-1",
        causation_id=None,
        idempotency_key=event_id,
        aggregate_type="TestAggregate",
        aggregate_id=event_id,
        aggregate_version=1,
        payload={"value": event_id},
        delivery_attempt=1,
    )


async def _probe(port: int, path: str) -> int:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = (await reader.read()).decode("utf-8")
    writer.close()
    await writer.wait_closed()
    return int(response.split("\r\n", 1)[0].split()[1])


@pytest.mark.asyncio
async def test_outbox_service_exposes_probes_and_drains_in_flight_batch() -> None:
    dispatcher = BlockingDispatcher()
    service = OutboxDispatcherService(
        dispatcher,
        poll_interval_seconds=0.01,
        batch_size=25,
    )
    probe = WorkerProbeServer(service.status, host="127.0.0.1", port=0)
    await probe.start()
    running = asyncio.create_task(service.run())
    await dispatcher.entered.wait()

    assert await _probe(probe.bound_port, "/live") == 200
    assert await _probe(probe.bound_port, "/ready") == 503
    service.request_stop()
    dispatcher.finish.set()
    await running

    assert not service.status().live
    assert service.status().last_report is not None
    assert service.status().last_report.published == 1
    await probe.close()


@pytest.mark.asyncio
async def test_outbox_readiness_fails_then_recovers_after_successful_iteration() -> (
    None
):
    dispatcher = RecoveringDispatcher()
    service = OutboxDispatcherService(
        dispatcher,
        poll_interval_seconds=0.01,
        batch_size=10,
    )
    running = asyncio.create_task(service.run())
    await dispatcher.failed.wait()
    assert not service.status().ready
    assert service.status().last_error_code == "RuntimeError"

    dispatcher.allow_recovery.set()
    await dispatcher.recovered.wait()
    while not service.status().ready:
        await asyncio.sleep(0)
    assert service.status().last_error_code is None

    service.request_stop()
    await running


def test_outbox_transport_resolution_fails_closed_and_dev_fake_is_explicit(
    monkeypatch,
) -> None:
    configure_application_event_transport(None)
    monkeypatch.delenv("OUTBOX_DISPATCHER_ALLOW_DEV_FAKE", raising=False)
    with pytest.raises(ValueError, match="未配置生产 EventTransport"):
        resolve_outbox_transport()

    monkeypatch.setenv("OUTBOX_DISPATCHER_ALLOW_DEV_FAKE", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="仅允许"):
        resolve_outbox_transport()

    monkeypatch.setenv("ENVIRONMENT", "development")
    assert isinstance(resolve_outbox_transport(), DeterministicDevelopmentTransport)
    configure_application_event_transport(None)


@pytest.mark.asyncio
async def test_dispatch_once_waits_for_every_delivery_before_raising(
    monkeypatch,
) -> None:
    envelopes = [_envelope("event-fails"), _envelope("event-slow")]

    class FakeStore:
        def __init__(self, session, *, clock) -> None:
            del session, clock

        async def claim_batch(self, **kwargs):
            del kwargs
            return envelopes

    monkeypatch.setattr(outbox_module, "SQLAlchemyOutboxStore", FakeStore)

    class UnusedTransport:
        async def publish(self, event) -> None:
            raise AssertionError(event)

    dispatcher = OutboxDispatcher(
        lambda: DummySession(),  # type: ignore[arg-type]
        transport=UnusedTransport(),
        dispatcher_id="dispatcher-test",
    )
    slow_started = asyncio.Event()
    slow_finished = asyncio.Event()

    async def deliver(event: OutboxEnvelope) -> tuple[int, int, int]:
        if event.event_id == "event-fails":
            await slow_started.wait()
            raise RuntimeError("mark_published failed")
        slow_started.set()
        await asyncio.sleep(0.02)
        slow_finished.set()
        return 1, 0, 0

    monkeypatch.setattr(dispatcher, "_deliver", deliver)
    with pytest.raises(RuntimeError, match="mark_published failed"):
        await dispatcher.dispatch_once(limit=2)
    assert slow_finished.is_set()
