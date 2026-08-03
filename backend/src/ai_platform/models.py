"""Durable SQLAlchemy records owned by the governed AI platform.

Raw provider payloads, rendered prompts, prompt variables, and business inputs are
intentionally absent from invocation/attempt rows.  Only validated output may be
stored in the separately classified artifact table.
"""

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
from task_runtime.models import DurableTask  # noqa: F401 - registers FK target metadata


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AIPromptRevisionRecord(Base):
    __tablename__ = "ai_prompt_revisions"

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    business_purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    input_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('published','archived')",
            name="ck_ai_prompt_revisions_status",
        ),
        UniqueConstraint(
            "template_id", "revision_id", name="uq_ai_prompt_revisions_exact"
        ),
        UniqueConstraint(
            "template_id", "revision_no", name="uq_ai_prompt_revisions_number"
        ),
    )


class AIModelRoutingProfileRecord(Base):
    __tablename__ = "ai_model_routing_profiles"

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('published','archived')",
            name="ck_ai_model_routing_profiles_status",
        ),
        UniqueConstraint(
            "profile_id", "revision_id", name="uq_ai_model_routing_profiles_exact"
        ),
        UniqueConstraint(
            "profile_id",
            "revision_no",
            name="uq_ai_model_routing_profiles_number",
        ),
    )


class AIInvocationRecord(Base):
    __tablename__ = "ai_invocations"

    invocation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "durable_tasks.task_id",
            ondelete="SET NULL",
            name="fk_ai_invocations_task",
        ),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    business_purpose: Mapped[str] = mapped_column(
        String(160), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(80), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    workload_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    owner_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    prompt_template_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_revision_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_contract_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    asr_profile_revision_id: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    input_artifact_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_routing_profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    input_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    timeout_policy_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    retry_policy_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    budget_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_consumer: Mapped[str] = mapped_column(String(160), nullable=False)

    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_minor_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    output_validation_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    result_artifact_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "ai_invocation_artifacts.artifact_id",
            name="fk_ai_invocations_result_artifact",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )
    evidence_refs_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    degradations_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )

    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    causation_id: Mapped[str] = mapped_column(String(160), nullable=False)
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
            "state IN ('prepared','running','succeeded','partial','failed')",
            name="ck_ai_invocations_state",
        ),
        CheckConstraint(
            "workload_kind IN ('llm','asr')",
            name="ck_ai_invocations_workload_kind",
        ),
        CheckConstraint(
            "(workload_kind = 'llm' AND prompt_template_id IS NOT NULL "
            "AND prompt_revision_id IS NOT NULL AND prompt_contract_hash IS NOT NULL "
            "AND asr_profile_revision_id IS NULL AND input_artifact_ref IS NULL) OR "
            "(workload_kind = 'asr' AND prompt_template_id IS NULL "
            "AND prompt_revision_id IS NULL AND prompt_contract_hash IS NULL "
            "AND asr_profile_revision_id IS NOT NULL AND input_artifact_ref IS NOT NULL)",
            name="ck_ai_invocations_workload_lineage",
        ),
        UniqueConstraint(
            "organization_id",
            "business_purpose",
            "object_type",
            "object_id",
            "idempotency_key_hash",
            name="uq_ai_invocations_logical_request",
        ),
        Index(
            "ix_ai_invocations_business_object",
            "organization_id",
            "object_type",
            "object_id",
        ),
    )


class AIInvocationArtifactRecord(Base):
    __tablename__ = "ai_invocation_artifacts"

    artifact_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    invocation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_invocations.invocation_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    artifact_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validated_payload_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIBudgetWindowRecord(Base):
    __tablename__ = "ai_budget_windows"

    window_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
    business_purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    limit_minor_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_minor_units: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    consumed_minor_units: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "model_routing_revision_id",
            "scope_type",
            "scope_key",
            "business_purpose",
            "window_start",
            name="uq_ai_budget_windows_scope",
        ),
    )


class AIBudgetReservationRecord(Base):
    __tablename__ = "ai_budget_reservations"

    reservation_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    invocation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_invocations.invocation_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    window_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_budget_windows.window_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reserved_minor_units: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_minor_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    released_minor_units: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('reserved','finalized','released')",
            name="ck_ai_budget_reservations_state",
        ),
    )


class AIProviderAttemptRecord(Base):
    __tablename__ = "ai_provider_attempts"

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    invocation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_invocations.invocation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_idempotency_key: Mapped[str] = mapped_column(
        String(240), nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    route_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('invoking','responded','failed')",
            name="ck_ai_provider_attempts_state",
        ),
        CheckConstraint(
            "route_kind IN ('primary','fallback')",
            name="ck_ai_provider_attempts_route_kind",
        ),
        UniqueConstraint(
            "invocation_id", "attempt_no", name="uq_ai_provider_attempts_number"
        ),
    )


class AIUsageLedgerRecord(Base):
    __tablename__ = "ai_usage_ledger"

    ledger_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    invocation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_invocations.invocation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_provider_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
    )
    effect_key: Mapped[str] = mapped_column(String(240), nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    business_purpose: Mapped[str] = mapped_column(
        String(160), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_minor_units: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_ai_usage_ledger_attempt"),
        UniqueConstraint("effect_key", name="uq_ai_usage_ledger_effect"),
    )


class AIRateLimitWindowRecord(Base):
    __tablename__ = "ai_rate_limit_windows"

    window_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
    business_purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_limit: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "model_routing_revision_id",
            "scope_type",
            "scope_key",
            "business_purpose",
            "window_start",
            name="uq_ai_rate_limit_windows_scope",
        ),
    )


class AICircuitStateRecord(Base):
    __tablename__ = "ai_circuit_states"

    circuit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    opened_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "model_routing_revision_id",
            "provider",
            "model",
            name="uq_ai_circuit_states_route",
        ),
    )


class _AIPlatformTableSet:
    """Narrow metadata facade for isolated PostgreSQL contract tests."""

    def __init__(self, metadata: MetaData) -> None:
        self._metadata = metadata

    @property
    def tables(self) -> tuple[Any, ...]:
        names = {
            AIPromptRevisionRecord.__tablename__,
            AIModelRoutingProfileRecord.__tablename__,
            AIInvocationRecord.__tablename__,
            AIInvocationArtifactRecord.__tablename__,
            AIBudgetWindowRecord.__tablename__,
            AIBudgetReservationRecord.__tablename__,
            AIProviderAttemptRecord.__tablename__,
            AIUsageLedgerRecord.__tablename__,
            AIRateLimitWindowRecord.__tablename__,
            AICircuitStateRecord.__tablename__,
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


AI_PLATFORM_TABLES = _AIPlatformTableSet(Base.metadata)


__all__ = [
    "AI_PLATFORM_TABLES",
    "AIBudgetReservationRecord",
    "AIBudgetWindowRecord",
    "AICircuitStateRecord",
    "AIInvocationArtifactRecord",
    "AIInvocationRecord",
    "AIModelRoutingProfileRecord",
    "AIProviderAttemptRecord",
    "AIPromptRevisionRecord",
    "AIRateLimitWindowRecord",
    "AIUsageLedgerRecord",
]
