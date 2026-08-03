"""SQLAlchemy persistence owned by the durable task runtime."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry.base import Base, jsonb_compatible_type


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TaskPayloadArtifact(Base):
    __tablename__ = "task_payload_artifacts"

    artifact_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class DurableTask(Base):
    __tablename__ = "durable_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_artifact_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_payload_artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="queued", index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_policy_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    deadline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    correlation_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    causation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fence_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','running','retry_wait','cancel_requested',"
            "'cancelled','succeeded','dead_letter')",
            name="ck_durable_tasks_state",
        ),
        CheckConstraint("priority BETWEEN 0 AND 100", name="ck_durable_tasks_priority"),
        UniqueConstraint(
            "organization_id",
            "task_type",
            "resource_type",
            "resource_id",
            "idempotency_key_hash",
            name="uq_durable_tasks_business_object_idempotency",
        ),
        Index(
            "ix_durable_tasks_resource",
            "organization_id",
            "resource_type",
            "resource_id",
        ),
    )


Index(
    "ix_durable_tasks_claim",
    DurableTask.state,
    DurableTask.priority.desc(),
    DurableTask.next_run_at,
    DurableTask.created_at,
    DurableTask.task_id,
)
Index(
    "ix_durable_tasks_type_claim",
    DurableTask.task_type,
    DurableTask.state,
    DurableTask.priority.desc(),
    DurableTask.next_run_at,
    DurableTask.created_at,
    DurableTask.task_id,
)
Index(
    "ix_durable_tasks_aged_claim",
    DurableTask.state,
    DurableTask.created_at,
    DurableTask.next_run_at,
    DurableTask.task_id,
)
Index(
    "ix_durable_tasks_type_aged_claim",
    DurableTask.task_type,
    DurableTask.state,
    DurableTask.created_at,
    DurableTask.next_run_at,
    DurableTask.task_id,
)
Index(
    "ix_durable_tasks_org_updated_keyset",
    DurableTask.organization_id,
    DurableTask.updated_at.desc(),
    DurableTask.task_id.desc(),
)


class TaskAttempt(Base):
    __tablename__ = "task_attempts"

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="CASCADE"), index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(160), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("task_id", "attempt_no", name="uq_task_attempts_task_no"),
        Index("ix_task_attempts_started_task", "started_at", "task_id"),
    )


class TaskLease(Base):
    __tablename__ = "task_leases"

    lease_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("durable_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    lease_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    fence_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    renewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class TaskProgress(Base):
    __tablename__ = "task_progress"

    progress_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(120), nullable=True)
    label: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_progress_sequence"),
        CheckConstraint(
            "current IS NULL OR current >= 0",
            name="ck_task_progress_current_non_negative",
        ),
        CheckConstraint(
            "total IS NULL OR total > 0",
            name="ck_task_progress_total_positive",
        ),
        CheckConstraint(
            "current IS NULL OR total IS NULL OR current <= total",
            name="ck_task_progress_bounds",
        ),
    )


class TaskResultRef(Base):
    __tablename__ = "task_result_refs"

    result_ref_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("durable_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    result_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    saved_items_json: Mapped[list[Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    remaining_items_json: Mapped[list[Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    retryable_items_json: Mapped[list[Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "result_kind IN ('complete','partial_success','waiting_input')",
            name="ck_task_result_refs_kind",
        ),
    )


class TaskCommandRecord(Base):
    """Immutable command receipt used for idempotency and operator audit."""

    __tablename__ = "task_command_records"

    command_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("durable_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    command_type: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_state: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "command_type",
            "idempotency_key_hash",
            name="uq_task_command_records_idempotency",
        ),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    causation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(120), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(
        String(160), nullable=True, index=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "event_type",
            "idempotency_key",
            name="uq_outbox_events_logical_event",
        ),
        Index(
            "ix_outbox_events_dispatch",
            "published_at",
            "dead_lettered_at",
            "available_at",
            "occurred_at",
        ),
    )


class OutboxConsumerReceipt(Base):
    __tablename__ = "outbox_consumer_receipts"

    receipt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("outbox_events.event_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consumer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    handler_version: Mapped[str] = mapped_column(String(80), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_outbox_consumer_receipts_effect_once",
        ),
    )


class TaskTypeControl(Base):
    __tablename__ = "task_type_controls"

    control_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "max_concurrency IS NULL OR max_concurrency > 0",
            name="ck_task_type_controls_max_concurrency_positive",
        ),
        CheckConstraint(
            "rate_limit_per_minute IS NULL OR rate_limit_per_minute > 0",
            name="ck_task_type_controls_rate_limit_positive",
        ),
        UniqueConstraint(
            "organization_id",
            "task_type",
            name="uq_task_type_controls_org_type",
        ),
    )


class TaskTypeControlCommand(Base):
    __tablename__ = "task_type_control_commands"

    command_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "task_type",
            "action",
            "idempotency_key_hash",
            name="uq_task_type_control_commands_idempotency",
        ),
    )


class TaskOperatorScopeGrant(Base):
    """Authoritative server-side organization/object scope for task operators."""

    __tablename__ = "task_operator_scope_grants"

    grant_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_operate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    granted_by: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "(resource_type = '' AND resource_id = '') OR "
            "(resource_type <> '' AND resource_id <> '')",
            name="ck_task_operator_scope_grants_shape",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_task_operator_scope_grants_future_expiry",
        ),
        CheckConstraint(
            "granted_by <> '' AND reason <> ''",
            name="ck_task_operator_scope_grants_audit_required",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL AND "
            "revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND "
            "revocation_reason IS NOT NULL)",
            name="ck_task_operator_scope_grants_revocation_audit",
        ),
        Index(
            "ix_task_operator_scope_grants_lookup",
            "actor_id",
            "organization_id",
            "resource_type",
            "resource_id",
            "expires_at",
        ),
    )


class _TaskRuntimeTableSet:
    """Narrow metadata facade used by isolated PostgreSQL integration fixtures."""

    def __init__(self, metadata: MetaData) -> None:
        self._metadata = metadata

    @property
    def tables(self) -> tuple[Any, ...]:
        names = {
            TaskPayloadArtifact.__tablename__,
            DurableTask.__tablename__,
            TaskAttempt.__tablename__,
            TaskLease.__tablename__,
            TaskProgress.__tablename__,
            TaskResultRef.__tablename__,
            TaskCommandRecord.__tablename__,
            OutboxEvent.__tablename__,
            OutboxConsumerReceipt.__tablename__,
            TaskTypeControl.__tablename__,
            TaskTypeControlCommand.__tablename__,
            TaskOperatorScopeGrant.__tablename__,
        }
        return tuple(
            table for table in self._metadata.sorted_tables if table.name in names
        )

    def create_all(self, bind: Any) -> None:
        self._metadata.create_all(bind, tables=list(self.tables), checkfirst=True)

    def drop_all(self, bind: Any, *, checkfirst: bool = True) -> None:
        self._metadata.drop_all(
            bind, tables=list(reversed(self.tables)), checkfirst=checkfirst
        )


TASK_RUNTIME_TABLES = _TaskRuntimeTableSet(Base.metadata)


__all__ = [
    "DurableTask",
    "OutboxConsumerReceipt",
    "OutboxEvent",
    "TASK_RUNTIME_TABLES",
    "TaskAttempt",
    "TaskCommandRecord",
    "TaskLease",
    "TaskPayloadArtifact",
    "TaskProgress",
    "TaskOperatorScopeGrant",
    "TaskResultRef",
    "TaskTypeControl",
    "TaskTypeControlCommand",
]
