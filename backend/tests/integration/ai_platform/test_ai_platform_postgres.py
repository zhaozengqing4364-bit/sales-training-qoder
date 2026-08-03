"""PostgreSQL semantics for durable governed AI invocation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ai_platform import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationMetricsFilter,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    ASRScenario,
    BudgetScope,
    DataClassification,
    DeterministicAIProvider,
    DeterministicASRProvider,
    GovernedAIInvocationService,
    GovernedAIRequest,
    OutputSchemaRegistry,
    ProviderScenario,
    PublishedModelRoutingProfileSnapshot,
    PublishedPromptRevisionSnapshot,
    SQLAlchemyAIInvocationMetricsReader,
    StrictPromptCompiler,
    compute_model_routing_profile_content_hash,
    compute_prompt_revision_content_hash,
)
from ai_platform.errors import AIPlatformError
from ai_platform.models import (
    AI_PLATFORM_TABLES,
    AIBudgetReservationRecord,
    AIInvocationRecord,
    AIModelRoutingProfileRecord,
    AIPromptRevisionRecord,
    AIProviderAttemptRecord,
    AIRateLimitWindowRecord,
    AIUsageLedgerRecord,
)
from ai_platform.providers import ProviderRequest, ProviderResponse
from ai_platform.sqlalchemy_adapters import (
    SQLAlchemyAIInvocationStore,
    SQLAlchemyPublishedModelRoutingProfileResolver,
    SQLAlchemyPublishedPromptRevisionResolver,
)
from task_runtime.models import TASK_RUNTIME_TABLES

POSTGRES_URL = os.getenv("AI_PLATFORM_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason="AI_PLATFORM_TEST_DATABASE_URL is required for PostgreSQL semantics",
    ),
]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    answer: str


class _ASRInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    audio_artifact_ref: str
    language: str


class _ASROutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    transcript: str
    confidence: float


class _MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class _BlockingProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self._results: dict[str, ProviderResponse] = {}

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        return self._results.get(idempotency_key)

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        response = ProviderResponse(
            payload={"answer": "durable"},
            provider_request_id="provider-request-1",
            usage=AIUsageSummary(
                input_tokens=2,
                output_tokens=3,
                total_tokens=5,
                cost_minor_units=3,
                currency="CNY",
            ),
            latency_ms=7,
            finish_reason="stop",
        )
        self._results[request.idempotency_key] = response
        return response


class _FailFirstCompletionStore(SQLAlchemyAIInvocationStore):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._fail_once = True

    async def complete(self, **kwargs: object) -> None:
        if self._fail_once:
            self._fail_once = False
            raise RuntimeError("simulated process crash before invocation finalization")
        await super().complete(**kwargs)


@pytest_asyncio.fixture
async def ai_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    assert POSTGRES_URL is not None
    schema = "slice1_ai_platform_test"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(TASK_RUNTIME_TABLES.create_all)
        await connection.run_sync(AI_PLATFORM_TABLES.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory

    await engine.dispose()
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    await admin_engine.dispose()


def _prompt() -> PublishedPromptRevisionSnapshot:
    return PublishedPromptRevisionSnapshot(
        template_id="test.generate",
        business_purpose="test.generate",
        revision_id="prompt-rev-1",
        revision_no=1,
        status="published",
        template="Input: {{ text }}",
        variables=("text",),
        input_schema_version="test.input.v1",
        output_schema_version="test.output.v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="test.generate",
            business_purpose="test.generate",
            revision_id="prompt-rev-1",
            revision_no=1,
            template="Input: {{ text }}",
            variables=("text",),
            input_schema_version="test.input.v1",
            output_schema_version="test.output.v1",
        ),
    )


def _routing() -> PublishedModelRoutingProfileSnapshot:
    return PublishedModelRoutingProfileSnapshot(
        profile_id="test.default",
        business_purpose="test.generate",
        revision_id="route-rev-1",
        revision_no=1,
        status="published",
        provider="primary",
        model="model-a",
        temperature=0.0,
        max_output_tokens=128,
        timeout_seconds=5,
        timeout_policy_ref="timeout.v1",
        max_provider_retries=0,
        max_schema_retries=0,
        retry_policy_ref="retry.v1",
        requests_per_minute=60,
        rate_limit_scopes=(
            BudgetScope.ORGANIZATION,
            BudgetScope.ACTOR,
            BudgetScope.USE_CASE,
        ),
        budget_scope=BudgetScope.ORGANIZATION,
        budget_limit_minor_units=100,
        budget_reservation_minor_units=10,
        budget_window_seconds=3600,
        currency="CNY",
        circuit_failure_threshold=3,
        circuit_recovery_seconds=30,
        fallback_allowed=False,
        fallback_error_allowlist=(AIErrorClassification.PROVIDER_UNAVAILABLE,),
        calibrated_for_formal_scoring=True,
        allowed_data_classifications=(
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
        ),
    )


async def _seed_published_catalog(
    factory: async_sessionmaker[AsyncSession],
    prompt: PublishedPromptRevisionSnapshot,
    routing: PublishedModelRoutingProfileSnapshot,
) -> None:
    async with factory() as session, session.begin():
        session.add(
            AIPromptRevisionRecord(
                template_id=prompt.template_id,
                revision_id=prompt.revision_id,
                revision_no=prompt.revision_no,
                status=prompt.status,
                business_purpose=prompt.business_purpose,
                template_text=prompt.template,
                variables_json=list(prompt.variables),
                input_schema_version=prompt.input_schema_version,
                output_schema_version=prompt.output_schema_version,
                content_hash=prompt.content_hash,
            )
        )
        session.add(
            AIModelRoutingProfileRecord(
                profile_id=routing.profile_id,
                revision_id=routing.revision_id,
                revision_no=routing.revision_no,
                status=routing.status,
                snapshot_json=routing.model_dump(mode="json"),
                content_hash=compute_model_routing_profile_content_hash(routing),
            )
        )


def _request(
    prompt: PublishedPromptRevisionSnapshot,
    routing: PublishedModelRoutingProfileSnapshot,
) -> GovernedAIRequest:
    compiler = StrictPromptCompiler()
    compiled = compiler.compile(
        revision=prompt,
        variables={"text": "hello"},
        runtime_consumer="postgres-contract-test",
        model_routing_revision_id=routing.revision_id,
    )
    return GovernedAIRequest(
        business_purpose=prompt.business_purpose,
        organization_id="org-1",
        actor_id="actor-1",
        object_type="test_object",
        object_id="object-1",
        prompt_template_id=prompt.template_id,
        prompt_revision_id=prompt.revision_id,
        prompt_contract_hash=compiled.contract_hash,
        model_routing_profile_id=routing.profile_id,
        model_routing_revision_id=routing.revision_id,
        input_schema_version=prompt.input_schema_version,
        output_schema_version=prompt.output_schema_version,
        input_payload={"text": "hello"},
        prompt_variables={"text": "hello"},
        idempotency_key="request-1",
        data_classification=DataClassification.CONFIDENTIAL,
        trace_id="trace-1",
        correlation_id="correlation-1",
        causation_id="cause-1",
        runtime_consumer="postgres-contract-test",
        timeout_policy_ref=routing.timeout_policy_ref,
        retry_policy_ref=routing.retry_policy_ref,
        budget_scope=routing.budget_scope,
    )


def _service(
    *,
    factory: async_sessionmaker[AsyncSession],
    provider: object,
    store: SQLAlchemyAIInvocationStore,
) -> GovernedAIInvocationService:
    schemas = OutputSchemaRegistry()
    schemas.register_input("test.input.v1", _Input)
    schemas.register_output("test.output.v1", _Output)
    return GovernedAIInvocationService(
        prompt_resolver=SQLAlchemyPublishedPromptRevisionResolver(factory),
        routing_resolver=SQLAlchemyPublishedModelRoutingProfileResolver(factory),
        compiler=StrictPromptCompiler(),
        schemas=schemas,
        providers={"primary": provider},
        store=store,
    )


async def test_owner_token_cannot_write_after_lease_expiry(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    request = _request(prompt, routing)
    clock = _MutableClock(datetime(2026, 7, 17, tzinfo=UTC))
    store = SQLAlchemyAIInvocationStore(
        ai_session_factory,
        clock=clock,
        ownership_ttl_seconds=1,
    )
    preparation = await store.prepare(
        request=request,
        request_fingerprint="ownership-fingerprint",
        routing=routing,
    )
    on_time_attempt = await store.begin_attempt(
        preparation=preparation,
        attempt_no=1,
        provider="primary",
        model="model-a",
        route_kind="primary",
    )
    await store.record_attempt_response(
        preparation=preparation,
        attempt=on_time_attempt,
        response=ProviderResponse(
            payload={"answer": "on-time"},
            provider_request_id="on-time-response",
            usage=AIUsageSummary(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                cost_minor_units=1,
                currency="CNY",
            ),
            latency_ms=1,
            finish_reason="stop",
        ),
    )
    late_attempt = await store.begin_attempt(
        preparation=preparation,
        attempt_no=2,
        provider="primary",
        model="model-a",
        route_kind="primary",
    )
    clock.advance(seconds=11)

    with pytest.raises(AIPlatformError) as response_error:
        await store.record_attempt_response(
            preparation=preparation,
            attempt=late_attempt,
            response=ProviderResponse(
                payload={"answer": "late"},
                provider_request_id="late-response",
                usage=AIUsageSummary(
                    input_tokens=2,
                    output_tokens=2,
                    total_tokens=4,
                    cost_minor_units=2,
                    currency="CNY",
                ),
                latency_ms=2,
                finish_reason="stop",
            ),
        )
    assert response_error.value.code == "AI_INVOCATION_OWNERSHIP_LOST"

    late_result = AIInvocationResult(
        invocation_id=preparation.invocation_id,
        workload_kind=request.workload_kind,
        status=AIInvocationStatus.SUCCEEDED,
        validated_output={"answer": "late"},
        prompt_template_id=request.prompt_template_id,
        prompt_revision_id=request.prompt_revision_id,
        prompt_contract_hash=request.prompt_contract_hash,
        model_routing_profile_id=request.model_routing_profile_id,
        model_routing_revision_id=request.model_routing_revision_id,
        created_at=preparation.created_at,
    )
    with pytest.raises(AIPlatformError) as completion_error:
        await store.complete(
            request=request,
            preparation=preparation,
            result=late_result,
        )
    assert completion_error.value.code == "AI_INVOCATION_OWNERSHIP_LOST"

    async with ai_session_factory() as session:
        invocation = await session.get(AIInvocationRecord, preparation.invocation_id)
        assert invocation is not None
        assert invocation.state == AIInvocationStatus.RUNNING.value
        attempts = (
            (
                await session.execute(
                    select(AIProviderAttemptRecord).order_by(
                        AIProviderAttemptRecord.attempt_no
                    )
                )
            )
            .scalars()
            .all()
        )
        assert [attempt.state for attempt in attempts] == ["responded", "invoking"]
        assert (
            await session.scalar(select(func.count()).select_from(AIUsageLedgerRecord))
            == 1
        )


async def test_concurrent_replay_has_one_owner_reservation_attempt_and_ledger_effect(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    request = _request(prompt, routing)
    provider = _BlockingProvider()
    clock = _MutableClock(datetime(2026, 7, 17, tzinfo=UTC))
    service_a = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(
            ai_session_factory, clock=clock, ownership_ttl_seconds=1
        ),
    )
    service_b = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(
            ai_session_factory, clock=clock, ownership_ttl_seconds=1
        ),
    )

    owner_call = asyncio.create_task(service_a.invoke(request))
    await asyncio.wait_for(provider.started.wait(), timeout=5)
    clock.advance(seconds=2)
    concurrent_result = await asyncio.wait_for(service_b.invoke(request), timeout=5)

    assert concurrent_result.status == "running"
    assert provider.calls == 1

    provider.release.set()
    owner_result = await asyncio.wait_for(owner_call, timeout=5)
    replay_result = await asyncio.wait_for(service_b.invoke(request), timeout=5)

    assert owner_result.status == "succeeded"
    assert replay_result.validated_output == {"answer": "durable"}
    assert replay_result.invocation_id == owner_result.invocation_id
    assert provider.calls == 1

    async with ai_session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(AIInvocationRecord))
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(AIProviderAttemptRecord)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(AIBudgetReservationRecord)
            )
            == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(AIUsageLedgerRecord))
            == 1
        )
        reservation = (
            await session.execute(select(AIBudgetReservationRecord))
        ).scalar_one()
        assert reservation.state == "finalized"
        assert reservation.actual_minor_units == 3
        assert reservation.released_minor_units == 7


async def test_crash_window_reconciles_provider_result_without_duplicate_cost(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    request = _request(prompt, routing)
    clock = _MutableClock(datetime(2026, 7, 17, tzinfo=UTC))
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(
                payload={"answer": "reconciled"},
                input_tokens=4,
                output_tokens=6,
                cost_minor_units=4,
            )
        ]
    )
    crashing_store = _FailFirstCompletionStore(
        ai_session_factory,
        clock=clock,
        ownership_ttl_seconds=5,
    )
    crashing_service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=crashing_store,
    )

    with pytest.raises(RuntimeError, match="simulated process crash"):
        await crashing_service.invoke(request)

    clock.advance(seconds=11)
    recovery_service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(
            ai_session_factory,
            clock=clock,
            ownership_ttl_seconds=5,
        ),
    )
    result = await recovery_service.invoke(request)

    assert result.status == "succeeded"
    assert result.validated_output == {"answer": "reconciled"}
    assert provider.call_count == 1
    async with ai_session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(AIUsageLedgerRecord))
            == 1
        )
        attempt = (await session.execute(select(AIProviderAttemptRecord))).scalar_one()
        assert attempt.provider_request_id == "deterministic-1"


async def test_reconciled_success_clears_stale_attempt_failure_audit_fields(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    request = _request(prompt, routing)
    store = SQLAlchemyAIInvocationStore(ai_session_factory)
    preparation = await store.prepare(
        request=request,
        request_fingerprint="reconcile-after-failure",
        routing=routing,
    )
    attempt = await store.begin_attempt(
        preparation=preparation,
        attempt_no=1,
        provider=routing.provider,
        model=routing.model,
        route_kind="primary",
    )
    await store.record_attempt_failure(
        preparation=preparation,
        attempt=attempt,
        failure=AIInvocationFailure(
            code="AI_PROVIDER_HTTP_503",
            classification=AIErrorClassification.PROVIDER_UNAVAILABLE,
            retryable=True,
            message="模型服务暂时不可用。",
        ),
    )

    await store.record_attempt_response(
        preparation=preparation,
        attempt=attempt,
        response=ProviderResponse(
            payload={"answer": "reconciled"},
            provider_request_id="provider-reconciled-1",
            usage=AIUsageSummary(
                input_tokens=2,
                output_tokens=3,
                total_tokens=5,
                cost_minor_units=3,
                currency=routing.currency,
            ),
            latency_ms=7,
            finish_reason="stop",
        ),
    )

    async with ai_session_factory() as session:
        stored = (await session.execute(select(AIProviderAttemptRecord))).scalar_one()
        assert stored.state == "responded"
        assert stored.error_code is None
        assert stored.error_classification is None
        assert stored.error_retryable is None
        assert stored.safe_error_message is None


async def test_missing_published_revisions_are_failed_audit_rows_without_quota_use(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )
    request = _request(prompt, routing)
    missing_prompt = request.model_copy(
        update={
            "prompt_revision_id": "missing-prompt-revision",
            "object_id": "missing-prompt",
            "idempotency_key": "missing-prompt",
        }
    )
    missing_profile = request.model_copy(
        update={
            "model_routing_revision_id": "missing-routing-revision",
            "object_id": "missing-profile",
            "idempotency_key": "missing-profile",
        }
    )

    prompt_result = await asyncio.wait_for(service.invoke(missing_prompt), timeout=5)
    profile_result = await asyncio.wait_for(service.invoke(missing_profile), timeout=5)

    assert prompt_result.status == "failed"
    assert prompt_result.failure is not None
    assert prompt_result.failure.code == "AI_PROMPT_REVISION_NOT_PUBLISHED"
    assert profile_result.status == "failed"
    assert profile_result.failure is not None
    assert profile_result.failure.code == "AI_MODEL_ROUTE_NOT_PUBLISHED"
    assert provider.call_count == 0
    async with ai_session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(AIInvocationRecord))
            == 2
        )
        assert (
            await session.scalar(
                select(func.count()).select_from(AIBudgetReservationRecord)
            )
            == 0
        )


async def test_local_admission_failure_is_audited_without_quota_use(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing().model_copy(
        update={
            "requests_per_minute": 1,
            "budget_limit_minor_units": 10,
            "budget_reservation_minor_units": 10,
        }
    )
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "valid"})]
    )
    service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )
    request = _request(prompt, routing)
    invalid = request.model_copy(
        update={
            "object_id": "invalid-input",
            "idempotency_key": "invalid-input",
            "input_payload": {"unexpected": "value"},
        }
    )

    invalid_result, invalid_replay = await asyncio.gather(
        service.invoke(invalid), service.invoke(invalid)
    )
    valid_result = await service.invoke(request)

    assert invalid_result.status == "failed"
    assert invalid_result.failure is not None
    assert (
        invalid_result.failure.classification
        is AIErrorClassification.INPUT_SCHEMA_INVALID
    )
    assert invalid_replay == invalid_result
    assert valid_result.status == "succeeded"
    assert provider.call_count == 1
    async with ai_session_factory() as session:
        reservations = (
            (await session.execute(select(AIBudgetReservationRecord))).scalars().all()
        )
        rate_windows = (
            (await session.execute(select(AIRateLimitWindowRecord))).scalars().all()
        )
        assert len(reservations) == 1
        assert reservations[0].invocation_id == valid_result.invocation_id
        assert len(rate_windows) == len(routing.rate_limit_scopes)
        assert all(window.request_count == 1 for window in rate_windows)


async def test_tampered_published_prompt_is_typed_and_audited(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    async with ai_session_factory() as session, session.begin():
        record = (await session.execute(select(AIPromptRevisionRecord))).scalar_one()
        record.template_text = "Tampered: {{ text }}"
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )

    result = await asyncio.wait_for(
        service.invoke(_request(prompt, routing)), timeout=5
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.code == "AI_PROMPT_REVISION_INTEGRITY_FAILED"
    assert provider.call_count == 0
    async with ai_session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(AIInvocationRecord))
            == 1
        )


async def test_tampered_published_profile_is_typed_and_audited(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    async with ai_session_factory() as session, session.begin():
        record = (
            await session.execute(select(AIModelRoutingProfileRecord))
        ).scalar_one()
        snapshot = dict(record.snapshot_json)
        snapshot["provider"] = "legally-shaped-but-tampered-provider"
        record.snapshot_json = snapshot
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )

    result = await asyncio.wait_for(
        service.invoke(_request(prompt, routing)), timeout=5
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.code == "AI_MODEL_ROUTE_INTEGRITY_FAILED"
    assert provider.call_count == 0
    async with ai_session_factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(AIInvocationRecord))
            == 1
        )


def test_durable_audit_rows_do_not_have_raw_sensitive_io_columns() -> None:
    invocation_columns = set(AIInvocationRecord.__table__.columns.keys())
    attempt_columns = set(AIProviderAttemptRecord.__table__.columns.keys())

    forbidden = {
        "raw_input",
        "input_payload",
        "prompt_variables",
        "rendered_prompt",
        "raw_output",
        "provider_payload",
    }
    assert invocation_columns.isdisjoint(forbidden)
    assert attempt_columns.isdisjoint(forbidden)


async def test_metrics_reader_aggregates_by_tenant_use_case_route_and_result(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    prompt = _prompt()
    routing = _routing()
    await _seed_published_catalog(ai_session_factory, prompt, routing)
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(
                payload={"answer": "metric"},
                input_tokens=4,
                output_tokens=6,
                cost_minor_units=3,
            )
        ]
    )
    service = _service(
        factory=ai_session_factory,
        provider=provider,
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )
    assert (await service.invoke(_request(prompt, routing))).status == "succeeded"

    rows = await SQLAlchemyAIInvocationMetricsReader(ai_session_factory).query(
        AIInvocationMetricsFilter(organization_id="org-1")
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == "org-1"
    assert row.business_purpose == "test.generate"
    assert row.provider == "primary"
    assert row.model == "model-a"
    assert row.result_classification == "succeeded"
    assert row.currency == "CNY"
    assert row.invocation_count == 1
    assert row.failed_count == 0
    assert row.degraded_count == 0
    assert row.input_tokens == 4
    assert row.output_tokens == 6
    assert row.cost_minor_units == 3


async def test_asr_uses_the_same_durable_lineage_budget_rate_and_audit_path(
    ai_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    route = _routing().model_copy(
        update={
            "profile_id": "asr.default",
            "business_purpose": "audio.transcribe",
            "revision_id": "asr-route-rev-1",
            "provider": "deterministic_asr",
            "model": "asr-model-v1",
        }
    )
    async with ai_session_factory() as session, session.begin():
        session.add(
            AIModelRoutingProfileRecord(
                profile_id=route.profile_id,
                revision_id=route.revision_id,
                revision_no=route.revision_no,
                status=route.status,
                snapshot_json=route.model_dump(mode="json"),
                content_hash=compute_model_routing_profile_content_hash(route),
            )
        )
    schemas = OutputSchemaRegistry()
    schemas.register_input("asr.input.v1", _ASRInput)
    schemas.register_output("asr.output.v1", _ASROutput)
    provider = DeterministicASRProvider(
        scenarios=[
            ASRScenario.success(
                transcript="客户希望下周沟通。",
                confidence=0.93,
                cost_minor_units=5,
            )
        ]
    )
    service = GovernedAIInvocationService(
        prompt_resolver=SQLAlchemyPublishedPromptRevisionResolver(ai_session_factory),
        routing_resolver=SQLAlchemyPublishedModelRoutingProfileResolver(
            ai_session_factory
        ),
        compiler=StrictPromptCompiler(),
        schemas=schemas,
        providers={"deterministic_asr": provider},
        store=SQLAlchemyAIInvocationStore(ai_session_factory),
    )
    artifact_ref = "artifact://audio/org-1/recording-1"
    request = GovernedAIRequest(
        workload_kind=AIWorkloadKind.ASR,
        business_purpose="audio.transcribe",
        organization_id="org-1",
        actor_id="learner-1",
        object_type="audio_recording",
        object_id="recording-1",
        asr_profile_revision_id=route.revision_id,
        input_artifact_ref=artifact_ref,
        model_routing_profile_id=route.profile_id,
        model_routing_revision_id=route.revision_id,
        input_schema_version="asr.input.v1",
        output_schema_version="asr.output.v1",
        input_payload={"audio_artifact_ref": artifact_ref, "language": "zh-CN"},
        idempotency_key="asr-recording-1",
        data_classification=DataClassification.CONFIDENTIAL,
        trace_id="trace-asr-1",
        correlation_id="corr-asr-1",
        causation_id="upload-1",
        runtime_consumer="audio-transcription",
        timeout_policy_ref=route.timeout_policy_ref,
        retry_policy_ref=route.retry_policy_ref,
        budget_scope=route.budget_scope,
    )

    result = await asyncio.wait_for(service.invoke(request), timeout=5)
    replay = await asyncio.wait_for(service.invoke(request), timeout=5)

    assert result.status == "succeeded"
    assert result.workload_kind is AIWorkloadKind.ASR
    assert result.validated_output == {
        "transcript": "客户希望下周沟通。",
        "confidence": 0.93,
    }
    assert replay == result
    assert provider.call_count == 1
    async with ai_session_factory() as session:
        invocation = (await session.execute(select(AIInvocationRecord))).scalar_one()
        assert invocation.workload_kind == "asr"
        assert invocation.asr_profile_revision_id == route.revision_id
        assert invocation.input_artifact_ref == artifact_ref
        assert invocation.prompt_revision_id is None
        assert (
            await session.scalar(
                select(func.count()).select_from(AIBudgetReservationRecord)
            )
            == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(AIUsageLedgerRecord))
            == 1
        )
