"""Transactional Outbox delivery and effect-once consumer receipts."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_runtime.contracts import Clock
from task_runtime.errors import OutboxEventConflictError, OutboxLeaseLostError
from task_runtime.models import (
    DurableTask,
    OutboxConsumerReceipt,
    OutboxEvent,
)
from task_runtime.payload_guard import assert_safe_persisted_payload


class DomainEvent(BaseModel):
    """Stable business-event contract written inside the caller transaction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = Field(
        min_length=3,
        max_length=160,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]+$",
    )
    schema_version: int = Field(ge=1)
    occurred_at: datetime
    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str | None = Field(default=None, max_length=120)
    trace_id: str | None = Field(default=None, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    causation_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=240)
    aggregate_type: str = Field(min_length=1, max_length=120)
    aggregate_id: str = Field(min_length=1, max_length=160)
    aggregate_version: int = Field(ge=1)
    payload: dict[str, Any]


@runtime_checkable
class OutboxWriterPort(Protocol):
    async def append(self, event: DomainEvent) -> str: ...


class SQLAlchemyOutboxWriter:
    """UoW-bound adapter; business callers never receive persistence internals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: DomainEvent) -> str:
        return await append_domain_event(self._session, event)


class OutboxEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str
    event_type: str
    schema_version: int
    occurred_at: datetime
    organization_id: str
    actor_id: str | None
    trace_id: str | None
    correlation_id: str
    causation_id: str | None
    idempotency_key: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    payload: dict[str, Any]
    delivery_attempt: int


class DispatchReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claimed: int
    published: int
    failed: int
    dead_lettered: int


class EventTransport(Protocol):
    async def publish(self, event: OutboxEnvelope) -> None: ...


class OutboxEventHandler(Protocol):
    async def __call__(self, event: OutboxEnvelope, session: AsyncSession) -> None: ...


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


async def append_domain_event(session: AsyncSession, event: DomainEvent) -> str:
    """Append one generic domain event without owning the transaction boundary."""

    assert_safe_persisted_payload(
        event.payload,
        max_bytes=65_536,
        code_prefix="OUTBOX_PAYLOAD",
        subject_label="业务事件载荷",
    )
    event_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{event.organization_id}:{event.event_type}:{event.idempotency_key}",
        )
    )
    statement = (
        postgresql_insert(OutboxEvent)
        .values(
            event_id=event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            occurred_at=event.occurred_at,
            organization_id=event.organization_id,
            actor_id=event.actor_id,
            trace_id=event.trace_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            idempotency_key=event.idempotency_key,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            payload_json=event.payload,
            available_at=event.occurred_at,
            delivery_attempts=0,
        )
        .on_conflict_do_nothing(
            index_elements=["organization_id", "event_type", "idempotency_key"]
        )
        .returning(OutboxEvent.event_id)
    )
    inserted = (await session.execute(statement)).scalar_one_or_none()
    if inserted is not None:
        return event_id

    existing = (
        await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.organization_id == event.organization_id)
            .where(OutboxEvent.event_type == event.event_type)
            .where(OutboxEvent.idempotency_key == event.idempotency_key)
            .limit(1)
        )
    ).scalar_one()
    if any(
        (
            existing.schema_version != event.schema_version,
            existing.occurred_at != event.occurred_at,
            existing.actor_id != event.actor_id,
            existing.trace_id != event.trace_id,
            existing.correlation_id != event.correlation_id,
            existing.causation_id != event.causation_id,
            existing.aggregate_type != event.aggregate_type,
            existing.aggregate_id != event.aggregate_id,
            existing.aggregate_version != event.aggregate_version,
            existing.payload_json != event.payload,
        )
    ):
        raise OutboxEventConflictError()
    return existing.event_id


async def append_task_event(
    session: AsyncSession,
    task: DurableTask,
    *,
    event_type: str,
    occurred_at: datetime,
    actor_id: str | None,
    details: dict[str, Any] | None = None,
) -> str:
    """Append a safe task event in the caller's existing transaction."""

    idempotency_key = f"{task.task_id}:{event_type}:{task.version}"
    payload: dict[str, Any] = {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "state": task.state,
        "resource_type": task.resource_type,
        "resource_id": task.resource_id,
    }
    if details:
        overlap = payload.keys() & details.keys()
        if overlap:
            raise ValueError(
                "任务事件详情不能覆盖保留字段：" + ", ".join(sorted(overlap))
            )
        payload.update(details)
    return await append_domain_event(
        session,
        DomainEvent(
            event_type=event_type,
            schema_version=1,
            occurred_at=occurred_at,
            organization_id=task.organization_id,
            actor_id=actor_id,
            trace_id=task.trace_id,
            correlation_id=task.correlation_id,
            causation_id=task.causation_id,
            idempotency_key=idempotency_key,
            aggregate_type="DurableTask",
            aggregate_id=task.task_id,
            aggregate_version=task.version,
            payload=payload,
        ),
    )


class SQLAlchemyOutboxStore:
    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._clock = clock or _SystemClock()

    async def claim_batch(
        self,
        *,
        dispatcher_id: str,
        limit: int,
        lease_seconds: int,
    ) -> list[OutboxEnvelope]:
        now = self._clock.now()
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .where(OutboxEvent.dead_lettered_at.is_(None))
            .where(OutboxEvent.available_at <= now)
            .where(
                or_(
                    OutboxEvent.lease_owner.is_(None),
                    OutboxEvent.lease_expires_at <= now,
                )
            )
            .order_by(OutboxEvent.occurred_at.asc(), OutboxEvent.event_id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        events = list(result.scalars())
        for event in events:
            event.lease_owner = dispatcher_id
            event.lease_expires_at = now + timedelta(seconds=lease_seconds)
            event.delivery_attempts += 1
        await self._session.flush(events)
        return [self._envelope(event) for event in events]

    async def mark_published(self, *, event_id: str, dispatcher_id: str) -> None:
        event = await self._load_current(event_id, dispatcher_id=dispatcher_id)
        event.published_at = self._clock.now()
        event.lease_owner = None
        event.lease_expires_at = None
        event.last_error_code = None
        await self._session.flush([event])

    async def mark_failed(
        self,
        *,
        event_id: str,
        dispatcher_id: str,
        error_code: str,
        retry_backoff_seconds: int,
        max_attempts: int,
    ) -> bool:
        event = await self._load_current(event_id, dispatcher_id=dispatcher_id)
        now = self._clock.now()
        event.last_error_code = error_code
        event.lease_owner = None
        event.lease_expires_at = None
        dead_lettered = event.delivery_attempts >= max_attempts
        if dead_lettered:
            event.dead_lettered_at = now
        else:
            event.available_at = now + timedelta(seconds=retry_backoff_seconds)
        await self._session.flush([event])
        return dead_lettered

    async def _load_current(self, event_id: str, *, dispatcher_id: str) -> OutboxEvent:
        now = self._clock.now()
        result = await self._session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.event_id == event_id)
            .where(OutboxEvent.lease_owner == dispatcher_id)
            .where(OutboxEvent.lease_expires_at > now)
            .where(OutboxEvent.published_at.is_(None))
            .where(OutboxEvent.dead_lettered_at.is_(None))
            .with_for_update()
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise OutboxLeaseLostError()
        return event

    @staticmethod
    def _envelope(event: OutboxEvent) -> OutboxEnvelope:
        return OutboxEnvelope(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            occurred_at=event.occurred_at,
            organization_id=event.organization_id,
            actor_id=event.actor_id,
            trace_id=event.trace_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            idempotency_key=event.idempotency_key,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            payload=event.payload_json,
            delivery_attempt=event.delivery_attempts,
        )


class OutboxDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        transport: EventTransport,
        dispatcher_id: str,
        clock: Clock | None = None,
        lease_seconds: int = 30,
        retry_backoff_seconds: int = 5,
        max_attempts: int = 10,
        publish_timeout_seconds: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._transport = transport
        self._dispatcher_id = dispatcher_id
        self._clock = clock or _SystemClock()
        self._lease_seconds = lease_seconds
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_attempts = max_attempts
        self._publish_timeout_seconds = (
            publish_timeout_seconds
            if publish_timeout_seconds is not None
            else max(1.0, lease_seconds / 2)
        )
        if self._publish_timeout_seconds >= lease_seconds:
            raise ValueError("Outbox publish timeout must be shorter than its lease.")

    async def dispatch_once(self, *, limit: int = 100) -> DispatchReport:
        async with self._session_factory() as session:
            store = SQLAlchemyOutboxStore(session, clock=self._clock)
            events = await store.claim_batch(
                dispatcher_id=self._dispatcher_id,
                limit=limit,
                lease_seconds=self._lease_seconds,
            )
            await session.commit()
        results = await asyncio.gather(
            *(self._deliver(event) for event in events),
            return_exceptions=True,
        )
        delivery_results: list[tuple[int, int, int]] = []
        for result in results:
            if isinstance(result, BaseException):
                raise result
            delivery_results.append(result)
        published = sum(result[0] for result in delivery_results)
        failed = sum(result[1] for result in delivery_results)
        dead_lettered = sum(result[2] for result in delivery_results)
        return DispatchReport(
            claimed=len(events),
            published=published,
            failed=failed,
            dead_lettered=dead_lettered,
        )

    async def _deliver(self, event: OutboxEnvelope) -> tuple[int, int, int]:
        try:
            async with asyncio.timeout(self._publish_timeout_seconds):
                await self._transport.publish(event)
        except Exception:
            async with self._session_factory() as session:
                store = SQLAlchemyOutboxStore(session, clock=self._clock)
                is_dead = await store.mark_failed(
                    event_id=event.event_id,
                    dispatcher_id=self._dispatcher_id,
                    error_code="transport_publish_failed",
                    retry_backoff_seconds=self._retry_backoff_seconds,
                    max_attempts=self._max_attempts,
                )
                await session.commit()
            return 0, 1, int(is_dead)
        async with self._session_factory() as session:
            store = SQLAlchemyOutboxStore(session, clock=self._clock)
            await store.mark_published(
                event_id=event.event_id,
                dispatcher_id=self._dispatcher_id,
            )
            await session.commit()
        return 1, 0, 0


class IdempotentOutboxConsumer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or _SystemClock()

    async def consume(
        self,
        event: OutboxEnvelope,
        *,
        consumer_name: str,
        handler_version: str,
        handler: OutboxEventHandler,
    ) -> bool:
        receipt_id = str(uuid.uuid4())
        async with self._session_factory() as session:
            statement = (
                postgresql_insert(OutboxConsumerReceipt)
                .values(
                    receipt_id=receipt_id,
                    event_id=event.event_id,
                    consumer_name=consumer_name,
                    handler_version=handler_version,
                    processed_at=self._clock.now(),
                )
                .on_conflict_do_nothing(index_elements=["consumer_name", "event_id"])
                .returning(OutboxConsumerReceipt.receipt_id)
            )
            inserted = (await session.execute(statement)).scalar_one_or_none()
            if inserted is None:
                await session.rollback()
                return False
            await handler(event, session)
            await session.commit()
            return True


__all__ = [
    "DomainEvent",
    "DispatchReport",
    "EventTransport",
    "IdempotentOutboxConsumer",
    "OutboxDispatcher",
    "OutboxEnvelope",
    "OutboxWriterPort",
    "SQLAlchemyOutboxWriter",
    "SQLAlchemyOutboxStore",
    "append_domain_event",
    "append_task_event",
]
