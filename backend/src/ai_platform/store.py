"""Persistence boundary and deterministic in-memory contract adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from ai_platform.contracts import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    BudgetScope,
    GovernedAIRequest,
    StructuredValidationSummary,
)
from ai_platform.errors import AIPlatformError, CircuitOpenError
from ai_platform.providers import ProviderResponse
from ai_platform.routing import PublishedModelRoutingProfileSnapshot


class PreparationDisposition(StrEnum):
    EXECUTE = "execute"
    REPLAY = "replay"
    IN_FLIGHT = "in_flight"


@dataclass(frozen=True, slots=True)
class InvocationPreparation:
    invocation_id: str
    disposition: PreparationDisposition
    created_at: datetime
    owner_token: str | None = None
    replay_result: AIInvocationResult | None = None
    rejection: AIInvocationFailure | None = None


@dataclass(frozen=True, slots=True)
class ProviderAttemptHandle:
    invocation_id: str
    attempt_no: int
    provider_idempotency_key: str
    provider: str
    model: str
    route_kind: str
    state: str
    prior_failure: AIInvocationFailure | None = None


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class AIInvocationStore(Protocol):
    async def reject_before_admission(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        failure: AIInvocationFailure,
    ) -> AIInvocationResult: ...

    async def prepare(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        routing: PublishedModelRoutingProfileSnapshot,
    ) -> InvocationPreparation: ...

    async def begin_attempt(
        self,
        *,
        preparation: InvocationPreparation,
        attempt_no: int,
        provider: str,
        model: str,
        route_kind: str,
    ) -> ProviderAttemptHandle: ...

    async def renew_owner(
        self,
        *,
        preparation: InvocationPreparation,
        lease_seconds: int,
    ) -> None: ...

    async def record_attempt_response(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        response: ProviderResponse,
    ) -> None: ...

    async def record_attempt_failure(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        failure: AIInvocationFailure,
    ) -> None: ...

    async def complete(
        self,
        *,
        request: GovernedAIRequest,
        preparation: InvocationPreparation,
        result: AIInvocationResult,
    ) -> None: ...

    async def usage_summary(
        self, *, invocation_id: str, currency: str
    ) -> AIUsageSummary: ...

    async def before_provider_attempt(
        self,
        *,
        routing_revision_id: str,
        provider: str,
        model: str,
        failure_threshold: int,
        recovery_seconds: int,
    ) -> None: ...

    async def record_provider_health(
        self,
        *,
        routing_revision_id: str,
        provider: str,
        model: str,
        success: bool,
        failure_threshold: int,
        recovery_seconds: int,
    ) -> None: ...


@dataclass(slots=True)
class _MemoryAttempt:
    handle: ProviderAttemptHandle
    response: ProviderResponse | None = None
    failure: AIInvocationFailure | None = None


@dataclass(slots=True)
class _MemoryInvocation:
    fingerprint: str
    invocation_id: str
    owner_token: str
    owner_expires_at: datetime
    created_at: datetime
    result: AIInvocationResult | None = None
    rejection: AIInvocationFailure | None = None
    reserved_minor_units: int = 0
    released_minor_units: int = 0
    reservation_created: bool = False
    budget_key: tuple[str, str, str, str, int] | None = None
    budget_finalized: bool = False
    attempts: dict[int, _MemoryAttempt] = field(default_factory=dict)
    ledger_effects: set[str] = field(default_factory=set)


@dataclass(slots=True)
class _Circuit:
    failures: int = 0
    opened_until: datetime | None = None


class InMemoryAIInvocationStore:
    """Concurrency-safe fake mirroring the durable adapter's effect-once rules."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        ownership_ttl_seconds: int = 30,
    ) -> None:
        self._lock = asyncio.Lock()
        self._clock = clock or SystemClock()
        self._ownership_ttl_seconds = ownership_ttl_seconds
        self._records: dict[tuple[str, str, str, str, str], _MemoryInvocation] = {}
        self._budget_reserved: dict[tuple[str, str, str, str, int], int] = {}
        self._budget_consumed: dict[tuple[str, str, str, str, int], int] = {}
        self._rate_counts: dict[tuple[str, str, str, str, int], int] = {}
        self._circuits: dict[tuple[str, str, str], _Circuit] = {}

    @staticmethod
    def _logical_key(request: GovernedAIRequest) -> tuple[str, str, str, str, str]:
        return (
            request.organization_id,
            request.business_purpose,
            request.object_type,
            request.object_id,
            request.idempotency_key,
        )

    @staticmethod
    def _scope_key(request: GovernedAIRequest, scope: BudgetScope) -> str:
        if scope is BudgetScope.ORGANIZATION:
            return request.organization_id
        if scope is BudgetScope.ACTOR:
            return request.actor_id
        return request.business_purpose

    def _rate_key(
        self,
        request: GovernedAIRequest,
        routing: PublishedModelRoutingProfileSnapshot,
        scope: BudgetScope,
    ) -> tuple[str, str, str, str, int]:
        minute = int(self._clock.now().timestamp()) // 60
        return (
            routing.revision_id,
            scope.value,
            self._scope_key(request, scope),
            request.business_purpose,
            minute,
        )

    def _budget_key(
        self,
        request: GovernedAIRequest,
        routing: PublishedModelRoutingProfileSnapshot,
    ) -> tuple[str, str, str, str, int]:
        window = int(self._clock.now().timestamp()) // routing.budget_window_seconds
        return (
            routing.revision_id,
            request.budget_scope.value,
            self._scope_key(request, request.budget_scope),
            request.business_purpose,
            window,
        )

    async def reject_before_admission(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        failure: AIInvocationFailure,
    ) -> AIInvocationResult:
        key = self._logical_key(request)
        async with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                if existing.fingerprint != request_fingerprint:
                    raise AIPlatformError(
                        code="AI_IDEMPOTENCY_CONFLICT",
                        classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                        message="相同幂等键对应了不同的 AI 请求。",
                    )
                if existing.result is not None:
                    return existing.result
                return self._running_result(request, existing.invocation_id)
            invocation_id = str(uuid4())
            result = self._rejection_result(
                request=request,
                invocation_id=invocation_id,
                failure=failure,
            )
            self._records[key] = _MemoryInvocation(
                fingerprint=request_fingerprint,
                invocation_id=invocation_id,
                owner_token="",
                owner_expires_at=self._clock.now(),
                created_at=self._clock.now(),
                result=result,
            )
            return result

    async def prepare(
        self,
        *,
        request: GovernedAIRequest,
        request_fingerprint: str,
        routing: PublishedModelRoutingProfileSnapshot,
    ) -> InvocationPreparation:
        key = self._logical_key(request)
        now = self._clock.now()
        lease_seconds = max(
            self._ownership_ttl_seconds,
            routing.timeout_seconds + 5,
        )
        async with self._lock:
            existing = self._records.get(key)
            if existing is not None:
                if existing.fingerprint != request_fingerprint:
                    raise AIPlatformError(
                        code="AI_IDEMPOTENCY_CONFLICT",
                        classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                        message="相同幂等键对应了不同的 AI 请求。",
                    )
                if existing.result is not None:
                    return InvocationPreparation(
                        invocation_id=existing.invocation_id,
                        disposition=PreparationDisposition.REPLAY,
                        created_at=existing.created_at,
                        replay_result=existing.result,
                    )
                if existing.owner_expires_at > now:
                    return InvocationPreparation(
                        invocation_id=existing.invocation_id,
                        disposition=PreparationDisposition.IN_FLIGHT,
                        created_at=existing.created_at,
                    )
                existing.owner_token = str(uuid4())
                existing.owner_expires_at = now + timedelta(seconds=lease_seconds)
                return InvocationPreparation(
                    invocation_id=existing.invocation_id,
                    disposition=PreparationDisposition.EXECUTE,
                    created_at=existing.created_at,
                    owner_token=existing.owner_token,
                    rejection=existing.rejection,
                )

            invocation_id = str(uuid4())
            owner_token = str(uuid4())
            record = _MemoryInvocation(
                fingerprint=request_fingerprint,
                invocation_id=invocation_id,
                owner_token=owner_token,
                owner_expires_at=now + timedelta(seconds=lease_seconds),
                created_at=now,
            )
            self._records[key] = record

            rate_keys = [
                self._rate_key(request, routing, scope)
                for scope in routing.rate_limit_scopes
            ]
            if any(
                self._rate_counts.get(rate_key, 0) >= routing.requests_per_minute
                for rate_key in rate_keys
            ):
                record.rejection = AIInvocationFailure(
                    code="AI_RATE_LIMIT_EXCEEDED",
                    classification=AIErrorClassification.RATE_LIMITED,
                    retryable=True,
                    message="当前 AI 请求频率已达到策略上限。",
                )
            else:
                for rate_key in rate_keys:
                    self._rate_counts[rate_key] = self._rate_counts.get(rate_key, 0) + 1

            if record.rejection is None:
                budget_key = self._budget_key(request, routing)
                reserved = self._budget_reserved.get(budget_key, 0)
                consumed = self._budget_consumed.get(budget_key, 0)
                requested = routing.budget_reservation_minor_units
                if (
                    routing.budget_limit_minor_units == 0
                    or reserved + consumed + requested
                    > routing.budget_limit_minor_units
                ):
                    record.rejection = AIInvocationFailure(
                        code="AI_BUDGET_EXCEEDED",
                        classification=AIErrorClassification.BUDGET_EXCEEDED,
                        retryable=True,
                        message="当前 AI 预算不足。",
                    )
                else:
                    self._budget_reserved[budget_key] = reserved + requested
                    record.reserved_minor_units = requested
                    record.reservation_created = True
                    record.budget_key = budget_key

            return InvocationPreparation(
                invocation_id=invocation_id,
                disposition=PreparationDisposition.EXECUTE,
                created_at=now,
                owner_token=owner_token,
                rejection=record.rejection,
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
        async with self._lock:
            record = self._record_by_id(preparation.invocation_id)
            self._require_owner(record, preparation)
            existing = record.attempts.get(attempt_no)
            if existing is not None:
                if (
                    existing.handle.provider != provider
                    or existing.handle.model != model
                    or existing.handle.route_kind != route_kind
                ):
                    raise AIPlatformError(
                        code="AI_ATTEMPT_CONTRACT_CONFLICT",
                        classification=AIErrorClassification.IDEMPOTENCY_CONFLICT,
                        message="AI Provider attempt 与已持久化契约不一致。",
                    )
                return existing.handle
            handle = ProviderAttemptHandle(
                invocation_id=preparation.invocation_id,
                attempt_no=attempt_no,
                provider_idempotency_key=(
                    f"ai:{preparation.invocation_id}:attempt:{attempt_no}"
                ),
                provider=provider,
                model=model,
                route_kind=route_kind,
                state="invoking",
            )
            record.attempts[attempt_no] = _MemoryAttempt(handle=handle)
            return handle

    async def record_attempt_response(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        response: ProviderResponse,
    ) -> None:
        async with self._lock:
            record = self._record_by_id(preparation.invocation_id)
            self._require_owner(record, preparation)
            stored = record.attempts[attempt.attempt_no]
            stored.response = response
            stored.failure = None
            stored.handle = (
                ProviderAttemptHandle(
                    **{
                        **attempt.__dict__,
                        "state": "responded",
                    }
                )
                if hasattr(attempt, "__dict__")
                else ProviderAttemptHandle(
                    invocation_id=attempt.invocation_id,
                    attempt_no=attempt.attempt_no,
                    provider_idempotency_key=attempt.provider_idempotency_key,
                    provider=attempt.provider,
                    model=attempt.model,
                    route_kind=attempt.route_kind,
                    state="responded",
                )
            )
            effect_key = attempt.provider_idempotency_key
            record.ledger_effects.add(effect_key)

    async def renew_owner(
        self,
        *,
        preparation: InvocationPreparation,
        lease_seconds: int,
    ) -> None:
        async with self._lock:
            record = self._record_by_id(preparation.invocation_id)
            self._require_owner(record, preparation)
            record.owner_expires_at = self._clock.now() + timedelta(
                seconds=max(lease_seconds, self._ownership_ttl_seconds)
            )

    async def record_attempt_failure(
        self,
        *,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        failure: AIInvocationFailure,
    ) -> None:
        async with self._lock:
            record = self._record_by_id(preparation.invocation_id)
            self._require_owner(record, preparation)
            stored = record.attempts[attempt.attempt_no]
            stored.failure = failure
            stored.handle = ProviderAttemptHandle(
                invocation_id=attempt.invocation_id,
                attempt_no=attempt.attempt_no,
                provider_idempotency_key=attempt.provider_idempotency_key,
                provider=attempt.provider,
                model=attempt.model,
                route_kind=attempt.route_kind,
                state="failed",
                prior_failure=failure,
            )

    async def complete(
        self,
        *,
        request: GovernedAIRequest,
        preparation: InvocationPreparation,
        result: AIInvocationResult,
    ) -> None:
        async with self._lock:
            record = self._records[self._logical_key(request)]
            if record.result is not None:
                return
            self._require_owner(record, preparation)
            actual = sum(
                attempt.response.usage.cost_minor_units
                for attempt in record.attempts.values()
                if attempt.response is not None
            )
            record.released_minor_units = max(record.reserved_minor_units - actual, 0)
            if (
                record.reservation_created
                and not record.budget_finalized
                and record.budget_key is not None
            ):
                budget_key = record.budget_key
                self._budget_reserved[budget_key] = max(
                    self._budget_reserved.get(budget_key, 0)
                    - record.reserved_minor_units,
                    0,
                )
                self._budget_consumed[budget_key] = (
                    self._budget_consumed.get(budget_key, 0) + actual
                )
                record.budget_finalized = True
            record.result = result

    async def usage_summary(
        self, *, invocation_id: str, currency: str
    ) -> AIUsageSummary:
        async with self._lock:
            record = self._record_by_id(invocation_id)
            responses = [
                attempt.response
                for attempt in record.attempts.values()
                if attempt.response is not None
            ]
            input_tokens = sum(response.usage.input_tokens for response in responses)
            output_tokens = sum(response.usage.output_tokens for response in responses)
            return AIUsageSummary(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_minor_units=sum(
                    response.usage.cost_minor_units for response in responses
                ),
                currency=currency,
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
        async with self._lock:
            circuit = self._circuits.get((routing_revision_id, provider, model))
            if circuit is None or circuit.opened_until is None:
                return
            if circuit.opened_until > self._clock.now():
                raise CircuitOpenError()
            circuit.failures = 0
            circuit.opened_until = None

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
        key = (routing_revision_id, provider, model)
        async with self._lock:
            circuit = self._circuits.setdefault(key, _Circuit())
            if success:
                circuit.failures = 0
                circuit.opened_until = None
                return
            circuit.failures += 1
            if circuit.failures >= failure_threshold:
                circuit.opened_until = self._clock.now() + timedelta(
                    seconds=recovery_seconds
                )

    def terminal_result(self, request: GovernedAIRequest) -> AIInvocationResult | None:
        return self._records[self._logical_key(request)].result

    def attempt_count(self, request: GovernedAIRequest) -> int:
        return len(self._records[self._logical_key(request)].attempts)

    def usage_entry_count(self, request: GovernedAIRequest) -> int:
        return len(self._records[self._logical_key(request)].ledger_effects)

    def reservation_count(self, request: GovernedAIRequest) -> int:
        return int(self._records[self._logical_key(request)].reservation_created)

    def released_budget(self, request: GovernedAIRequest) -> int:
        return self._records[self._logical_key(request)].released_minor_units

    def _record_by_id(self, invocation_id: str) -> _MemoryInvocation:
        return next(
            record
            for record in self._records.values()
            if record.invocation_id == invocation_id
        )

    @staticmethod
    def _rejection_result(
        *,
        request: GovernedAIRequest,
        invocation_id: str,
        failure: AIInvocationFailure,
    ) -> AIInvocationResult:
        return AIInvocationResult(
            invocation_id=invocation_id,
            workload_kind=request.workload_kind,
            status=AIInvocationStatus.FAILED,
            failure=failure,
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            asr_profile_revision_id=request.asr_profile_revision_id,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            validation=StructuredValidationSummary(
                input_valid=(
                    failure.classification
                    is not AIErrorClassification.INPUT_SCHEMA_INVALID
                ),
                output_valid=False,
                output_validation_attempts=0,
                output_schema_version=request.output_schema_version,
            ),
        )

    @staticmethod
    def _running_result(
        request: GovernedAIRequest, invocation_id: str
    ) -> AIInvocationResult:
        return AIInvocationResult(
            invocation_id=invocation_id,
            workload_kind=request.workload_kind,
            status=AIInvocationStatus.RUNNING,
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            asr_profile_revision_id=request.asr_profile_revision_id,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
        )

    def _require_owner(
        self,
        record: _MemoryInvocation,
        preparation: InvocationPreparation,
    ) -> None:
        if (
            preparation.owner_token is None
            or record.owner_token != preparation.owner_token
            or record.owner_expires_at <= self._clock.now()
        ):
            raise AIPlatformError(
                code="AI_INVOCATION_OWNERSHIP_LOST",
                classification=AIErrorClassification.UNKNOWN,
                message="AI 调用执行权已失效。",
                retryable=True,
            )
