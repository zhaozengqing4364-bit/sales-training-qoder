"""Short-transaction PostgreSQL adapters for governed AI persistence.

Every method commits before returning.  The application service performs provider
I/O only between these methods, so no database transaction is held across an
external call.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_platform.contracts import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    BudgetScope,
    GovernedAIRequest,
    StructuredValidationSummary,
)
from ai_platform.errors import (
    AIPlatformError,
    CircuitOpenError,
    ModelRouteIntegrityError,
    ModelRouteNotPublishedError,
    PromptRevisionIntegrityError,
    PromptRevisionNotPublishedError,
)
from ai_platform.models import (
    AIBudgetReservationRecord,
    AIBudgetWindowRecord,
    AICircuitStateRecord,
    AIInvocationArtifactRecord,
    AIInvocationRecord,
    AIModelRoutingProfileRecord,
    AIPromptRevisionRecord,
    AIProviderAttemptRecord,
    AIRateLimitWindowRecord,
    AIUsageLedgerRecord,
)
from ai_platform.prompting import (
    PublishedPromptRevisionResolver,
    PublishedPromptRevisionSnapshot,
)
from ai_platform.providers import ProviderResponse
from ai_platform.routing import (
    PublishedModelRoutingProfileResolver,
    PublishedModelRoutingProfileSnapshot,
    compute_model_routing_profile_content_hash,
)
from ai_platform.store import (
    Clock,
    InvocationPreparation,
    PreparationDisposition,
    ProviderAttemptHandle,
    SystemClock,
)

_TERMINAL_STATES = {
    AIInvocationStatus.SUCCEEDED.value,
    AIInvocationStatus.PARTIAL.value,
    AIInvocationStatus.FAILED.value,
}


def _uuid() -> str:
    return str(uuid.uuid4())


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SQLAlchemyPublishedPromptRevisionResolver(PublishedPromptRevisionResolver):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_published(
        self, *, template_id: str, revision_id: str
    ) -> PublishedPromptRevisionSnapshot:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AIPromptRevisionRecord)
                .where(AIPromptRevisionRecord.template_id == template_id)
                .where(AIPromptRevisionRecord.revision_id == revision_id)
                .where(AIPromptRevisionRecord.status == "published")
                .limit(1)
            )
            record = result.scalar_one_or_none()
            if record is None:
                raise PromptRevisionNotPublishedError()
            try:
                return PublishedPromptRevisionSnapshot(
                    template_id=record.template_id,
                    business_purpose=record.business_purpose,
                    revision_id=record.revision_id,
                    revision_no=record.revision_no,
                    status="published",
                    template=record.template_text,
                    variables=tuple(record.variables_json),
                    input_schema_version=record.input_schema_version,
                    output_schema_version=record.output_schema_version,
                    content_hash=record.content_hash,
                )
            except ValidationError as exc:
                raise PromptRevisionIntegrityError() from exc


class SQLAlchemyPublishedModelRoutingProfileResolver(
    PublishedModelRoutingProfileResolver
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_published(
        self, *, profile_id: str, revision_id: str
    ) -> PublishedModelRoutingProfileSnapshot:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AIModelRoutingProfileRecord)
                .where(AIModelRoutingProfileRecord.profile_id == profile_id)
                .where(AIModelRoutingProfileRecord.revision_id == revision_id)
                .where(AIModelRoutingProfileRecord.status == "published")
                .limit(1)
            )
            record = result.scalar_one_or_none()
            if record is None:
                raise ModelRouteNotPublishedError()
            if record.content_hash != compute_model_routing_profile_content_hash(
                record.snapshot_json
            ):
                raise ModelRouteIntegrityError()
            try:
                snapshot = PublishedModelRoutingProfileSnapshot.model_validate(
                    record.snapshot_json,
                    strict=False,
                )
            except ValidationError as exc:
                raise ModelRouteIntegrityError() from exc
            if (
                snapshot.profile_id != record.profile_id
                or snapshot.revision_id != record.revision_id
                or snapshot.revision_no != record.revision_no
                or snapshot.status != "published"
            ):
                raise ModelRouteIntegrityError()
            return snapshot


class SQLAlchemyAIInvocationStore:
    """Durable idempotency, ownership, budget, rate, ledger, and circuit adapter."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
        ownership_ttl_seconds: int = 30,
        result_retention_seconds: int = 30 * 24 * 60 * 60,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or SystemClock()
        self._ownership_ttl_seconds = ownership_ttl_seconds
        self._result_retention_seconds = result_retention_seconds

    async def reject_before_admission(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        failure: AIInvocationFailure,
    ) -> AIInvocationResult:
        now = self._clock.now()
        invocation_id = _uuid()
        values = self._invocation_values(
            invocation_id=invocation_id,
            request=request,
            request_fingerprint=request_fingerprint,
            owner_token=_uuid(),
            owner_expires_at=now,
            now=now,
        )
        values.update(
            {
                "state": AIInvocationStatus.FAILED.value,
                "owner_token_hash": None,
                "owner_expires_at": None,
                "error_code": failure.code,
                "error_classification": failure.classification.value,
                "error_retryable": failure.retryable,
                "safe_error_message": failure.message,
                "completed_at": now,
            }
        )
        async with self._session_factory() as session, session.begin():
            inserted = await session.scalar(
                pg_insert(AIInvocationRecord)
                .values(**values)
                .on_conflict_do_nothing(constraint="uq_ai_invocations_logical_request")
                .returning(AIInvocationRecord.invocation_id)
            )
            invocation = await self._find_logical_invocation(
                session, request=request, for_update=True
            )
            assert invocation is not None
            if invocation.request_fingerprint != request_fingerprint:
                raise AIPlatformError(
                    code="AI_IDEMPOTENCY_CONFLICT",
                    classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                    message="相同幂等键对应了不同的 AI 请求。",
                )
            if inserted is None and invocation.state not in _TERMINAL_STATES:
                return AIInvocationResult(
                    invocation_id=invocation.invocation_id,
                    workload_kind=request.workload_kind,
                    status=AIInvocationStatus.RUNNING,
                    prompt_template_id=request.prompt_template_id,
                    prompt_revision_id=request.prompt_revision_id,
                    prompt_contract_hash=request.prompt_contract_hash,
                    asr_profile_revision_id=request.asr_profile_revision_id,
                    model_routing_profile_id=request.model_routing_profile_id,
                    model_routing_revision_id=request.model_routing_revision_id,
                )
            return await self._result_from_record(session, invocation)

    async def prepare(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        routing: PublishedModelRoutingProfileSnapshot,
    ) -> InvocationPreparation:
        now = self._clock.now()
        lease_seconds = max(
            self._ownership_ttl_seconds,
            routing.timeout_seconds + 5,
        )
        owner_token = _uuid()
        invocation_id = _uuid()
        values = self._invocation_values(
            invocation_id=invocation_id,
            request=request,
            request_fingerprint=request_fingerprint,
            owner_token=owner_token,
            owner_expires_at=now + timedelta(seconds=lease_seconds),
            now=now,
        )
        async with self._session_factory() as session, session.begin():
            inserted = await session.scalar(
                pg_insert(AIInvocationRecord)
                .values(**values)
                .on_conflict_do_nothing(constraint="uq_ai_invocations_logical_request")
                .returning(AIInvocationRecord.invocation_id)
            )
            if inserted is None:
                existing = await self._find_logical_invocation(
                    session, request=request, for_update=True
                )
                assert existing is not None
                if existing.request_fingerprint != request_fingerprint:
                    raise AIPlatformError(
                        code="AI_IDEMPOTENCY_CONFLICT",
                        classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                        message="相同幂等键对应了不同的 AI 请求。",
                    )
                if existing.state in _TERMINAL_STATES:
                    replay = await self._result_from_record(session, existing)
                    return InvocationPreparation(
                        invocation_id=existing.invocation_id,
                        disposition=PreparationDisposition.REPLAY,
                        created_at=existing.created_at,
                        replay_result=replay,
                    )
                if (
                    existing.owner_expires_at is not None
                    and existing.owner_expires_at > now
                ):
                    return InvocationPreparation(
                        invocation_id=existing.invocation_id,
                        disposition=PreparationDisposition.IN_FLIGHT,
                        created_at=existing.created_at,
                    )
                existing.owner_token_hash = _secret_hash(owner_token)
                existing.owner_expires_at = now + timedelta(seconds=lease_seconds)
                existing.state = AIInvocationStatus.RUNNING.value
                existing.updated_at = now
                return InvocationPreparation(
                    invocation_id=existing.invocation_id,
                    disposition=PreparationDisposition.EXECUTE,
                    created_at=existing.created_at,
                    owner_token=owner_token,
                    rejection=self._stored_rejection(existing),
                )

            invocation = await session.get(AIInvocationRecord, invocation_id)
            assert invocation is not None
            rejection = await self._consume_rate_limit(
                session,
                request=request,
                routing=routing,
                now=now,
            )
            if rejection is None:
                rejection = await self._reserve_budget(
                    session,
                    invocation_id=invocation_id,
                    request=request,
                    routing=routing,
                    now=now,
                )
            invocation.state = AIInvocationStatus.RUNNING.value
            invocation.updated_at = now
            if rejection is not None:
                invocation.error_code = rejection.code
                invocation.error_classification = rejection.classification.value
                invocation.error_retryable = rejection.retryable
                invocation.safe_error_message = rejection.message
            return InvocationPreparation(
                invocation_id=invocation_id,
                disposition=PreparationDisposition.EXECUTE,
                created_at=now,
                owner_token=owner_token,
                rejection=rejection,
            )

    async def begin_attempt(
        self,
        *,
        preparation: InvocationPreparation,
        attempt_no: int,
        provider: str,
        model: str,
        route_kind: str,
    ) -> ProviderAttemptHandle:
        async with self._session_factory() as session, session.begin():
            invocation = await self._owned_invocation(session, preparation)
            result = await session.execute(
                select(AIProviderAttemptRecord)
                .where(
                    AIProviderAttemptRecord.invocation_id == preparation.invocation_id
                )
                .where(AIProviderAttemptRecord.attempt_no == attempt_no)
                .with_for_update()
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                if (
                    existing.provider != provider
                    or existing.model != model
                    or existing.route_kind != route_kind
                ):
                    raise AIPlatformError(
                        code="AI_ATTEMPT_CONTRACT_CONFLICT",
                        classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                        message="AI Provider attempt 与已持久化契约不一致。",
                    )
                return self._attempt_handle(existing)

            attempt = AIProviderAttemptRecord(
                attempt_id=_uuid(),
                invocation_id=preparation.invocation_id,
                attempt_no=attempt_no,
                provider_idempotency_key=(
                    f"ai:{preparation.invocation_id}:attempt:{attempt_no}"
                ),
                provider=provider,
                model=model,
                route_kind=route_kind,
                state="invoking",
                started_at=self._clock.now(),
            )
            session.add(attempt)
            invocation.updated_at = self._clock.now()
            await session.flush([attempt])
            return self._attempt_handle(attempt)

    async def record_attempt_response(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        response: ProviderResponse,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invocation = await self._owned_invocation(session, preparation)
            stored = await self._attempt_record(
                session,
                invocation_id=preparation.invocation_id,
                attempt_no=attempt.attempt_no,
            )
            stored.state = "responded"
            stored.provider_request_id = response.provider_request_id
            stored.finish_reason = response.finish_reason
            stored.latency_ms = response.latency_ms
            stored.partial = response.partial
            stored.error_code = None
            stored.error_classification = None
            stored.error_retryable = None
            stored.safe_error_message = None
            stored.finished_at = self._clock.now()
            await session.execute(
                pg_insert(AIUsageLedgerRecord)
                .values(
                    ledger_id=_uuid(),
                    invocation_id=preparation.invocation_id,
                    attempt_id=stored.attempt_id,
                    effect_key=attempt.provider_idempotency_key,
                    organization_id=invocation.organization_id,
                    actor_id=invocation.actor_id,
                    business_purpose=invocation.business_purpose,
                    provider=attempt.provider,
                    model=attempt.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.total_tokens,
                    cost_minor_units=response.usage.cost_minor_units,
                    currency=response.usage.currency,
                    created_at=self._clock.now(),
                )
                .on_conflict_do_nothing(constraint="uq_ai_usage_ledger_attempt")
            )

    async def renew_owner(
        self,
        *,
        preparation: InvocationPreparation,
        lease_seconds: int,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invocation = await self._owned_invocation(session, preparation)
            invocation.owner_expires_at = self._clock.now() + timedelta(
                seconds=max(lease_seconds, self._ownership_ttl_seconds)
            )
            invocation.updated_at = self._clock.now()

    async def record_attempt_failure(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        failure: AIInvocationFailure,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await self._owned_invocation(session, preparation)
            stored = await self._attempt_record(
                session,
                invocation_id=preparation.invocation_id,
                attempt_no=attempt.attempt_no,
            )
            stored.state = "failed"
            stored.error_code = failure.code
            stored.error_classification = failure.classification.value
            stored.error_retryable = failure.retryable
            stored.safe_error_message = failure.message
            stored.finished_at = self._clock.now()

    async def complete(
        self,
        *,
        request: GovernedAIRequest,
        preparation: InvocationPreparation,
        result: AIInvocationResult,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            invocation = await session.scalar(
                select(AIInvocationRecord)
                .where(AIInvocationRecord.invocation_id == preparation.invocation_id)
                .with_for_update()
            )
            if invocation is None:
                raise AIPlatformError(
                    code="AI_INVOCATION_NOT_FOUND",
                    classification=AIErrorClassification.UNKNOWN,
                    message="AI 调用记录不存在。",
                )
            if invocation.state in _TERMINAL_STATES:
                return
            self._require_owner(invocation, preparation)

            usage = await self._usage_summary_in_session(
                session,
                invocation_id=preparation.invocation_id,
                currency=result.usage.currency,
            )
            artifact_id: str | None = None
            if result.validated_output is not None:
                artifact = await session.scalar(
                    select(AIInvocationArtifactRecord)
                    .where(
                        AIInvocationArtifactRecord.invocation_id
                        == preparation.invocation_id
                    )
                    .limit(1)
                )
                if artifact is None:
                    artifact_id = _uuid()
                    artifact = AIInvocationArtifactRecord(
                        artifact_id=artifact_id,
                        invocation_id=preparation.invocation_id,
                        organization_id=request.organization_id,
                        artifact_kind="validated_output",
                        data_classification=request.data_classification.value,
                        content_hash=_canonical_hash(result.validated_output),
                        validated_payload_json=result.validated_output,
                        created_at=self._clock.now(),
                        retention_expires_at=self._clock.now()
                        + timedelta(seconds=self._result_retention_seconds),
                    )
                    session.add(artifact)
                else:
                    artifact_id = artifact.artifact_id

            invocation.state = result.status.value
            invocation.provider = result.provider
            invocation.model = result.model
            invocation.provider_request_id = result.provider_request_id
            invocation.finish_reason = result.finish_reason
            invocation.latency_ms = result.latency_ms
            invocation.input_tokens = usage.input_tokens
            invocation.output_tokens = usage.output_tokens
            invocation.cost_minor_units = usage.cost_minor_units
            invocation.currency = usage.currency
            invocation.result_artifact_id = artifact_id
            invocation.evidence_refs_json = list(result.evidence_refs)
            invocation.degradations_json = list(result.degradations)
            invocation.output_validation_attempts = (
                result.validation.output_validation_attempts
                if result.validation is not None
                else 0
            )
            if result.failure is not None:
                invocation.error_code = result.failure.code
                invocation.error_classification = result.failure.classification.value
                invocation.error_retryable = result.failure.retryable
                invocation.safe_error_message = result.failure.message
            else:
                invocation.error_code = None
                invocation.error_classification = None
                invocation.error_retryable = None
                invocation.safe_error_message = None
            invocation.owner_token_hash = None
            invocation.owner_expires_at = None
            invocation.updated_at = self._clock.now()
            invocation.completed_at = self._clock.now()
            await self._finalize_budget(
                session,
                invocation_id=preparation.invocation_id,
                actual_minor_units=usage.cost_minor_units,
                now=self._clock.now(),
            )

    async def usage_summary(
        self, *, invocation_id: str, currency: str
    ) -> AIUsageSummary:
        async with self._session_factory() as session:
            return await self._usage_summary_in_session(
                session, invocation_id=invocation_id, currency=currency
            )

    async def before_provider_attempt(
        self,
        *,
        routing_revision_id: str,
        provider: str,
        model: str,
        failure_threshold: int,
        recovery_seconds: int,
    ) -> None:
        del failure_threshold, recovery_seconds
        async with self._session_factory() as session, session.begin():
            circuit = await session.scalar(
                select(AICircuitStateRecord)
                .where(
                    AICircuitStateRecord.model_routing_revision_id
                    == routing_revision_id
                )
                .where(AICircuitStateRecord.provider == provider)
                .where(AICircuitStateRecord.model == model)
                .with_for_update()
                .limit(1)
            )
            if circuit is None or circuit.opened_until is None:
                return
            if circuit.opened_until > self._clock.now():
                raise CircuitOpenError()
            circuit.consecutive_failures = 0
            circuit.opened_until = None
            circuit.updated_at = self._clock.now()

    async def record_provider_health(
        self,
        *,
        routing_revision_id: str,
        provider: str,
        model: str,
        success: bool,
        failure_threshold: int,
        recovery_seconds: int,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                pg_insert(AICircuitStateRecord)
                .values(
                    circuit_id=_uuid(),
                    model_routing_revision_id=routing_revision_id,
                    provider=provider,
                    model=model,
                    consecutive_failures=0,
                    updated_at=self._clock.now(),
                )
                .on_conflict_do_nothing(constraint="uq_ai_circuit_states_route")
            )
            circuit = await session.scalar(
                select(AICircuitStateRecord)
                .where(
                    AICircuitStateRecord.model_routing_revision_id
                    == routing_revision_id
                )
                .where(AICircuitStateRecord.provider == provider)
                .where(AICircuitStateRecord.model == model)
                .with_for_update()
            )
            assert circuit is not None
            if success:
                circuit.consecutive_failures = 0
                circuit.opened_until = None
            else:
                circuit.consecutive_failures += 1
                if circuit.consecutive_failures >= failure_threshold:
                    circuit.opened_until = self._clock.now() + timedelta(
                        seconds=recovery_seconds
                    )
            circuit.updated_at = self._clock.now()

    async def _consume_rate_limit(
        self,
        session: AsyncSession,
        *,
        request: GovernedAIRequest,
        routing: PublishedModelRoutingProfileSnapshot,
        now: datetime,
    ) -> AIInvocationFailure | None:
        window_start = datetime.fromtimestamp(
            (int(now.timestamp()) // 60) * 60,
            tz=UTC,
        )
        windows: list[AIRateLimitWindowRecord] = []
        for scope in sorted(routing.rate_limit_scopes, key=lambda item: item.value):
            scope_key = self._scope_key(request, scope)
            await session.execute(
                pg_insert(AIRateLimitWindowRecord)
                .values(
                    window_id=_uuid(),
                    model_routing_revision_id=routing.revision_id,
                    scope_type=scope.value,
                    scope_key=scope_key,
                    business_purpose=request.business_purpose,
                    window_start=window_start,
                    request_count=0,
                    request_limit=routing.requests_per_minute,
                )
                .on_conflict_do_nothing(constraint="uq_ai_rate_limit_windows_scope")
            )
            window = await session.scalar(
                select(AIRateLimitWindowRecord)
                .where(
                    AIRateLimitWindowRecord.model_routing_revision_id
                    == routing.revision_id
                )
                .where(AIRateLimitWindowRecord.scope_type == scope.value)
                .where(AIRateLimitWindowRecord.scope_key == scope_key)
                .where(
                    AIRateLimitWindowRecord.business_purpose == request.business_purpose
                )
                .where(AIRateLimitWindowRecord.window_start == window_start)
                .with_for_update()
            )
            assert window is not None
            windows.append(window)
        if any(window.request_count >= window.request_limit for window in windows):
            return AIInvocationFailure(
                code="AI_RATE_LIMIT_EXCEEDED",
                classification=AIErrorClassification.RATE_LIMITED,
                retryable=True,
                message="当前 AI 请求频率已达到策略上限。",
            )
        for window in windows:
            window.request_count += 1
        return None

    async def _reserve_budget(
        self,
        session: AsyncSession,
        *,
        invocation_id: str,
        request: GovernedAIRequest,
        routing: PublishedModelRoutingProfileSnapshot,
        now: datetime,
    ) -> AIInvocationFailure | None:
        window_index = int(now.timestamp()) // routing.budget_window_seconds
        window_start = datetime.fromtimestamp(
            window_index * routing.budget_window_seconds,
            tz=UTC,
        )
        window_end = window_start + timedelta(seconds=routing.budget_window_seconds)
        scope = routing.budget_scope
        scope_key = self._scope_key(request, scope)
        await session.execute(
            pg_insert(AIBudgetWindowRecord)
            .values(
                window_id=_uuid(),
                model_routing_revision_id=routing.revision_id,
                scope_type=scope.value,
                scope_key=scope_key,
                business_purpose=request.business_purpose,
                window_start=window_start,
                window_end=window_end,
                limit_minor_units=routing.budget_limit_minor_units,
                reserved_minor_units=0,
                consumed_minor_units=0,
                currency=routing.currency,
            )
            .on_conflict_do_nothing(constraint="uq_ai_budget_windows_scope")
        )
        window = await session.scalar(
            select(AIBudgetWindowRecord)
            .where(
                AIBudgetWindowRecord.model_routing_revision_id == routing.revision_id
            )
            .where(AIBudgetWindowRecord.scope_type == scope.value)
            .where(AIBudgetWindowRecord.scope_key == scope_key)
            .where(AIBudgetWindowRecord.business_purpose == request.business_purpose)
            .where(AIBudgetWindowRecord.window_start == window_start)
            .with_for_update()
        )
        assert window is not None
        requested = routing.budget_reservation_minor_units
        if window.limit_minor_units == 0 or (
            window.reserved_minor_units + window.consumed_minor_units + requested
            > window.limit_minor_units
        ):
            return AIInvocationFailure(
                code="AI_BUDGET_EXCEEDED",
                classification=AIErrorClassification.BUDGET_EXCEEDED,
                retryable=True,
                message="当前 AI 预算不足。",
            )
        window.reserved_minor_units += requested
        session.add(
            AIBudgetReservationRecord(
                reservation_id=_uuid(),
                invocation_id=invocation_id,
                window_id=window.window_id,
                reserved_minor_units=requested,
                actual_minor_units=0,
                released_minor_units=0,
                currency=routing.currency,
                state="reserved",
                created_at=now,
            )
        )
        return None

    async def _finalize_budget(
        self,
        session: AsyncSession,
        *,
        invocation_id: str,
        actual_minor_units: int,
        now: datetime,
    ) -> None:
        reservation = await session.scalar(
            select(AIBudgetReservationRecord)
            .where(AIBudgetReservationRecord.invocation_id == invocation_id)
            .with_for_update()
            .limit(1)
        )
        if reservation is None or reservation.state != "reserved":
            return
        window = await session.scalar(
            select(AIBudgetWindowRecord)
            .where(AIBudgetWindowRecord.window_id == reservation.window_id)
            .with_for_update()
        )
        assert window is not None
        window.reserved_minor_units = max(
            window.reserved_minor_units - reservation.reserved_minor_units,
            0,
        )
        window.consumed_minor_units += actual_minor_units
        reservation.actual_minor_units = actual_minor_units
        reservation.released_minor_units = max(
            reservation.reserved_minor_units - actual_minor_units,
            0,
        )
        reservation.state = "finalized"
        reservation.finalized_at = now

    async def _usage_summary_in_session(
        self,
        session: AsyncSession,
        *,
        invocation_id: str,
        currency: str,
    ) -> AIUsageSummary:
        row = (
            await session.execute(
                select(
                    func.coalesce(func.sum(AIUsageLedgerRecord.input_tokens), 0),
                    func.coalesce(func.sum(AIUsageLedgerRecord.output_tokens), 0),
                    func.coalesce(func.sum(AIUsageLedgerRecord.cost_minor_units), 0),
                ).where(AIUsageLedgerRecord.invocation_id == invocation_id)
            )
        ).one()
        input_tokens = int(row[0])
        output_tokens = int(row[1])
        return AIUsageSummary(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_minor_units=int(row[2]),
            currency=currency,
        )

    async def _result_from_record(
        self,
        session: AsyncSession,
        invocation: AIInvocationRecord,
    ) -> AIInvocationResult:
        validated_output: dict[str, Any] | None = None
        if invocation.result_artifact_id is not None:
            artifact = await session.get(
                AIInvocationArtifactRecord, invocation.result_artifact_id
            )
            if artifact is not None:
                validated_output = artifact.validated_payload_json
        failure: AIInvocationFailure | None = None
        if invocation.error_code is not None:
            failure = AIInvocationFailure(
                code=invocation.error_code,
                classification=AIErrorClassification(
                    invocation.error_classification
                    or AIErrorClassification.UNKNOWN.value
                ),
                retryable=bool(invocation.error_retryable),
                message=invocation.safe_error_message or "AI 调用失败。",
            )
        status = AIInvocationStatus(invocation.state)
        return AIInvocationResult(
            invocation_id=invocation.invocation_id,
            workload_kind=AIWorkloadKind(invocation.workload_kind),
            status=status,
            validated_output=validated_output,
            failure=failure,
            prompt_template_id=invocation.prompt_template_id,
            prompt_revision_id=invocation.prompt_revision_id,
            prompt_contract_hash=invocation.prompt_contract_hash,
            asr_profile_revision_id=invocation.asr_profile_revision_id,
            model_routing_profile_id=invocation.model_routing_profile_id,
            model_routing_revision_id=invocation.model_routing_revision_id,
            provider=invocation.provider,
            model=invocation.model,
            usage=AIUsageSummary(
                input_tokens=invocation.input_tokens,
                output_tokens=invocation.output_tokens,
                total_tokens=invocation.input_tokens + invocation.output_tokens,
                cost_minor_units=invocation.cost_minor_units,
                currency=invocation.currency,
            ),
            provider_request_id=invocation.provider_request_id,
            finish_reason=invocation.finish_reason,
            latency_ms=invocation.latency_ms,
            evidence_refs=tuple(invocation.evidence_refs_json),
            degradations=tuple(invocation.degradations_json),
            validation=StructuredValidationSummary(
                input_valid=(
                    failure is None
                    or failure.classification
                    is not AIErrorClassification.INPUT_SCHEMA_INVALID
                ),
                output_valid=status
                in {AIInvocationStatus.SUCCEEDED, AIInvocationStatus.PARTIAL},
                output_validation_attempts=invocation.output_validation_attempts,
                output_schema_version=invocation.output_schema_version,
            ),
            created_at=invocation.created_at,
        )

    async def _find_logical_invocation(
        self,
        session: AsyncSession,
        *,
        request: GovernedAIRequest,
        for_update: bool,
    ) -> AIInvocationRecord | None:
        query = (
            select(AIInvocationRecord)
            .where(AIInvocationRecord.organization_id == request.organization_id)
            .where(AIInvocationRecord.business_purpose == request.business_purpose)
            .where(AIInvocationRecord.object_type == request.object_type)
            .where(AIInvocationRecord.object_id == request.object_id)
            .where(
                AIInvocationRecord.idempotency_key_hash
                == _secret_hash(request.idempotency_key)
            )
            .limit(1)
        )
        if for_update:
            query = query.with_for_update()
        return cast(AIInvocationRecord | None, await session.scalar(query))

    async def _owned_invocation(
        self,
        session: AsyncSession,
        preparation: InvocationPreparation,
    ) -> AIInvocationRecord:
        invocation = await session.scalar(
            select(AIInvocationRecord)
            .where(AIInvocationRecord.invocation_id == preparation.invocation_id)
            .with_for_update()
        )
        if invocation is None:
            raise AIPlatformError(
                code="AI_INVOCATION_NOT_FOUND",
                classification=AIErrorClassification.UNKNOWN,
                message="AI 调用记录不存在。",
            )
        self._require_owner(invocation, preparation)
        return invocation

    def _require_owner(
        self,
        invocation: AIInvocationRecord,
        preparation: InvocationPreparation,
    ) -> None:
        if (
            preparation.owner_token is None
            or invocation.owner_token_hash != _secret_hash(preparation.owner_token)
            or invocation.owner_expires_at is None
            or invocation.owner_expires_at <= self._clock.now()
        ):
            raise AIPlatformError(
                code="AI_INVOCATION_OWNERSHIP_LOST",
                classification=AIErrorClassification.UNKNOWN,
                message="AI 调用执行权已失效。",
                retryable=True,
            )

    async def _attempt_record(
        self,
        session: AsyncSession,
        *,
        invocation_id: str,
        attempt_no: int,
    ) -> AIProviderAttemptRecord:
        attempt = await session.scalar(
            select(AIProviderAttemptRecord)
            .where(AIProviderAttemptRecord.invocation_id == invocation_id)
            .where(AIProviderAttemptRecord.attempt_no == attempt_no)
            .with_for_update()
        )
        if attempt is None:
            raise AIPlatformError(
                code="AI_PROVIDER_ATTEMPT_NOT_FOUND",
                classification=AIErrorClassification.UNKNOWN,
                message="AI Provider attempt 不存在。",
            )
        return attempt

    @staticmethod
    def _attempt_handle(record: AIProviderAttemptRecord) -> ProviderAttemptHandle:
        failure: AIInvocationFailure | None = None
        if record.error_code is not None:
            failure = AIInvocationFailure(
                code=record.error_code,
                classification=AIErrorClassification(
                    record.error_classification or AIErrorClassification.UNKNOWN.value
                ),
                retryable=bool(record.error_retryable),
                message=record.safe_error_message or "AI Provider attempt 失败。",
            )
        return ProviderAttemptHandle(
            invocation_id=record.invocation_id,
            attempt_no=record.attempt_no,
            provider_idempotency_key=record.provider_idempotency_key,
            provider=record.provider,
            model=record.model,
            route_kind=record.route_kind,
            state=record.state,
            prior_failure=failure,
        )

    @staticmethod
    def _stored_rejection(
        invocation: AIInvocationRecord,
    ) -> AIInvocationFailure | None:
        if invocation.error_code not in {
            "AI_RATE_LIMIT_EXCEEDED",
            "AI_BUDGET_EXCEEDED",
        }:
            return None
        return AIInvocationFailure(
            code=invocation.error_code,
            classification=AIErrorClassification(
                invocation.error_classification or AIErrorClassification.UNKNOWN.value
            ),
            retryable=bool(invocation.error_retryable),
            message=invocation.safe_error_message or "AI 调用被治理策略拒绝。",
        )

    @staticmethod
    def _scope_key(request: GovernedAIRequest, scope: BudgetScope) -> str:
        if scope is BudgetScope.ORGANIZATION:
            return request.organization_id
        if scope is BudgetScope.ACTOR:
            return request.actor_id
        return request.business_purpose

    @staticmethod
    def _invocation_values(
        *,
        invocation_id: str,
        request: GovernedAIRequest,
        request_fingerprint: str,
        owner_token: str,
        owner_expires_at: datetime,
        now: datetime,
    ) -> dict[str, Any]:
        return {
            "invocation_id": invocation_id,
            "task_id": request.task_id,
            "organization_id": request.organization_id,
            "actor_id": request.actor_id,
            "business_purpose": request.business_purpose,
            "object_type": request.object_type,
            "object_id": request.object_id,
            "idempotency_key_hash": _secret_hash(request.idempotency_key),
            "request_fingerprint": request_fingerprint,
            "data_classification": request.data_classification.value,
            "workload_kind": request.workload_kind.value,
            "state": AIInvocationStatus.PREPARED.value,
            "owner_token_hash": _secret_hash(owner_token),
            "owner_expires_at": owner_expires_at,
            "prompt_template_id": request.prompt_template_id,
            "prompt_revision_id": request.prompt_revision_id,
            "prompt_contract_hash": request.prompt_contract_hash,
            "asr_profile_revision_id": request.asr_profile_revision_id,
            "input_artifact_ref": request.input_artifact_ref,
            "model_routing_profile_id": request.model_routing_profile_id,
            "model_routing_revision_id": request.model_routing_revision_id,
            "input_schema_version": request.input_schema_version,
            "output_schema_version": request.output_schema_version,
            "timeout_policy_ref": request.timeout_policy_ref,
            "retry_policy_ref": request.retry_policy_ref,
            "budget_scope": request.budget_scope.value,
            "runtime_consumer": request.runtime_consumer,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_minor_units": 0,
            "currency": "CNY",
            "output_validation_attempts": 0,
            "evidence_refs_json": [],
            "degradations_json": [],
            "trace_id": request.trace_id,
            "correlation_id": request.correlation_id,
            "causation_id": request.causation_id,
            "created_at": now,
            "updated_at": now,
        }
