"""Provider contract tests through the public governed invocation seam."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ai_platform import (
    AIErrorClassification,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    BudgetScope,
    DataClassification,
    DeterministicAIProvider,
    GovernedAIInvocationService,
    GovernedAIRequest,
    InMemoryAIInvocationStore,
    ModelRoute,
    OutputSchemaRegistry,
    ProviderScenario,
    PublishedModelRoutingProfileSnapshot,
    PublishedPromptRevisionSnapshot,
    StaticPublishedModelRoutingProfileResolver,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)
from ai_platform.errors import AIPlatformError
from ai_platform.providers import AIProvider, ProviderRequest, ProviderResponse


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class _Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    answer: str


class _MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


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


def _routing(**overrides: object) -> PublishedModelRoutingProfileSnapshot:
    values: dict[str, object] = {
        "profile_id": "test.default",
        "business_purpose": "test.generate",
        "revision_id": "route-rev-1",
        "revision_no": 1,
        "status": "published",
        "provider": "primary",
        "model": "model-a",
        "temperature": 0.0,
        "max_output_tokens": 128,
        "timeout_seconds": 5,
        "timeout_policy_ref": "timeout.v1",
        "max_provider_retries": 0,
        "max_schema_retries": 1,
        "retry_policy_ref": "retry.v1",
        "requests_per_minute": 60,
        "rate_limit_scopes": (
            BudgetScope.ORGANIZATION,
            BudgetScope.ACTOR,
            BudgetScope.USE_CASE,
        ),
        "budget_scope": BudgetScope.ORGANIZATION,
        "budget_limit_minor_units": 100,
        "budget_reservation_minor_units": 10,
        "budget_window_seconds": 3600,
        "currency": "CNY",
        "circuit_failure_threshold": 2,
        "circuit_recovery_seconds": 30,
        "fallback_allowed": False,
        "fallback_error_allowlist": (
            AIErrorClassification.TIMEOUT,
            AIErrorClassification.PROVIDER_UNAVAILABLE,
            AIErrorClassification.OUTPUT_SCHEMA_INVALID,
            AIErrorClassification.EMPTY_RESPONSE,
            AIErrorClassification.CIRCUIT_OPEN,
        ),
        "calibrated_for_formal_scoring": True,
        "allowed_data_classifications": (
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
        ),
    }
    values.update(overrides)
    return PublishedModelRoutingProfileSnapshot.model_validate(values)


def _request(
    *,
    prompt: PublishedPromptRevisionSnapshot,
    routing: PublishedModelRoutingProfileSnapshot,
    compiler: StrictPromptCompiler,
    idempotency_key: str = "request-1",
    formal_scoring: bool = False,
    allow_fallback: bool = True,
) -> GovernedAIRequest:
    compiled = compiler.compile(
        revision=prompt,
        variables={"text": "hello"},
        runtime_consumer="provider-contract-test",
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
        idempotency_key=idempotency_key,
        data_classification=DataClassification.INTERNAL,
        trace_id="trace-1",
        correlation_id="correlation-1",
        causation_id="cause-1",
        runtime_consumer="provider-contract-test",
        timeout_policy_ref=routing.timeout_policy_ref,
        retry_policy_ref=routing.retry_policy_ref,
        budget_scope=routing.budget_scope,
        formal_scoring=formal_scoring,
        allow_fallback=allow_fallback,
    )


def _service(
    *,
    routing: PublishedModelRoutingProfileSnapshot,
    providers: dict[str, AIProvider],
    store: InMemoryAIInvocationStore | None = None,
) -> tuple[GovernedAIInvocationService, GovernedAIRequest, InMemoryAIInvocationStore]:
    prompt = _prompt()
    compiler = StrictPromptCompiler()
    schemas = OutputSchemaRegistry()
    schemas.register_input(prompt.input_schema_version, _Input)
    schemas.register_output(prompt.output_schema_version, _Output)
    invocation_store = store or InMemoryAIInvocationStore()
    service = GovernedAIInvocationService(
        prompt_resolver=StaticPublishedPromptRevisionResolver([prompt]),
        routing_resolver=StaticPublishedModelRoutingProfileResolver([routing]),
        compiler=compiler,
        schemas=schemas,
        providers=providers,
        store=invocation_store,
    )
    return (
        service,
        _request(prompt=prompt, routing=routing, compiler=compiler),
        invocation_store,
    )


class _NeverReturningProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        del idempotency_key
        return None

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        del request
        self.calls += 1
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class _UnexpectedFailureProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        del idempotency_key
        return None

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        del request
        self.calls += 1
        raise ValueError("raw provider secret must not escape")


class _CurrencyMismatchProvider:
    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        del idempotency_key
        return None

    async def invoke(self, request: ProviderRequest) -> ProviderResponse:
        del request
        return ProviderResponse(
            payload={"answer": "must-not-be-accounted"},
            provider_request_id="currency-mismatch-1",
            usage=AIUsageSummary(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                cost_minor_units=9,
                currency="USD",
            ),
            latency_ms=1,
            finish_reason="stop",
        )


@pytest.mark.parametrize(
    ("scenario", "classification"),
    [
        (ProviderScenario.timeout(), AIErrorClassification.TIMEOUT),
        (ProviderScenario.rate_limited(), AIErrorClassification.RATE_LIMITED),
        (
            ProviderScenario.unavailable(status_code=503),
            AIErrorClassification.PROVIDER_UNAVAILABLE,
        ),
        (ProviderScenario.cancelled(), AIErrorClassification.CANCELLED),
    ],
)
async def test_provider_failures_are_classified_and_persisted(
    scenario: ProviderScenario,
    classification: AIErrorClassification,
) -> None:
    provider = DeterministicAIProvider(scenarios=[scenario])
    service, request, store = _service(
        routing=_routing(), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is classification
    assert store.terminal_result(request) == result
    assert store.attempt_count(request) == 1


@pytest.mark.parametrize(
    "bad_scenario",
    [
        ProviderScenario.invalid_schema(payload={"wrong": "shape"}),
        ProviderScenario.empty(),
    ],
)
async def test_structured_output_failure_retries_once_then_succeeds(
    bad_scenario: ProviderScenario,
) -> None:
    provider = DeterministicAIProvider(
        scenarios=[bad_scenario, ProviderScenario.success(payload={"answer": "ok"})]
    )
    service, request, store = _service(
        routing=_routing(max_schema_retries=1), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "succeeded"
    assert result.validated_output == {"answer": "ok"}
    assert provider.call_count == 2
    assert store.attempt_count(request) == 2
    assert store.usage_entry_count(request) == 2


async def test_invalid_output_fails_closed_after_bounded_retry() -> None:
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.invalid_schema(payload={"wrong": "one"}),
            ProviderScenario.invalid_schema(payload={"wrong": "two"}),
        ]
    )
    service, request, store = _service(
        routing=_routing(max_schema_retries=1), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is AIErrorClassification.OUTPUT_SCHEMA_INVALID
    assert provider.call_count == 2
    assert store.attempt_count(request) == 2


async def test_failed_invocation_reports_usage_from_all_completed_attempts() -> None:
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(
                payload={"wrong": "one"},
                input_tokens=2,
                output_tokens=3,
                cost_minor_units=2,
            ),
            ProviderScenario.success(
                payload={"wrong": "two"},
                input_tokens=5,
                output_tokens=7,
                cost_minor_units=3,
            ),
        ]
    )
    service, request, _ = _service(
        routing=_routing(max_schema_retries=1), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.usage.input_tokens == 7
    assert result.usage.output_tokens == 10
    assert result.usage.total_tokens == 17
    assert result.usage.cost_minor_units == 5


async def test_partial_response_is_explicit_and_keeps_the_output_contract() -> None:
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(payload={"answer": "partial"}, partial=True)
        ]
    )
    service, request, _ = _service(routing=_routing(), providers={"primary": provider})

    result = await service.invoke(request)

    assert result.status == "partial"
    assert result.validated_output == {"answer": "partial"}


async def test_duplicate_delivery_replays_without_provider_or_budget_duplication() -> (
    None
):
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(payload={"answer": "once"}, cost_minor_units=3)
        ]
    )
    service, request, store = _service(
        routing=_routing(), providers={"primary": provider}
    )

    first = await service.invoke(request)
    replay = await service.invoke(request)

    assert replay == first
    assert provider.call_count == 1
    assert store.reservation_count(request) == 1
    assert store.usage_entry_count(request) == 1
    assert store.released_budget(request) == 7


async def test_budget_reservation_is_transferred_so_later_work_can_use_the_remainder() -> (
    None
):
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(payload={"answer": "first"}, cost_minor_units=3),
            ProviderScenario.success(payload={"answer": "second"}, cost_minor_units=3),
        ]
    )
    route = _routing(
        budget_limit_minor_units=10,
        budget_reservation_minor_units=7,
    )
    service, first_request, _ = _service(routing=route, providers={"primary": provider})

    first = await service.invoke(first_request)
    second = await service.invoke(
        first_request.model_copy(
            update={"object_id": "object-2", "idempotency_key": "request-2"}
        )
    )

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert provider.call_count == 2


async def test_actual_cost_above_reservation_is_fully_consumed() -> None:
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(payload={"answer": "costly"}, cost_minor_units=8)
        ]
    )
    route = _routing(
        budget_limit_minor_units=10,
        budget_reservation_minor_units=6,
    )
    service, first_request, store = _service(
        routing=route, providers={"primary": provider}
    )
    first = await service.invoke(first_request)
    second_request = first_request.model_copy(
        update={"object_id": "cost-2", "idempotency_key": "cost-2"}
    )
    second = await service.invoke(second_request)

    assert first.status == "succeeded"
    assert first.usage.cost_minor_units == 8
    assert store.released_budget(first_request) == 0
    assert second.status == "failed"
    assert second.failure is not None
    assert second.failure.classification is AIErrorClassification.BUDGET_EXCEEDED
    assert provider.call_count == 1


async def test_budget_and_rate_limit_are_typed_persisted_failures() -> None:
    budget_provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(payload={"answer": "first"}, cost_minor_units=3)
        ]
    )
    budget_service, budget_request, budget_store = _service(
        routing=_routing(
            budget_limit_minor_units=10,
            budget_reservation_minor_units=8,
        ),
        providers={"primary": budget_provider},
    )

    assert (await budget_service.invoke(budget_request)).status == "succeeded"
    second_budget_request = budget_request.model_copy(
        update={"object_id": "budget-2", "idempotency_key": "budget-2"}
    )
    budget_result = await budget_service.invoke(second_budget_request)

    assert budget_result.status == "failed"
    assert budget_result.failure is not None
    assert budget_result.failure.classification is AIErrorClassification.BUDGET_EXCEEDED
    assert budget_store.terminal_result(second_budget_request) == budget_result
    assert budget_provider.call_count == 1

    rate_provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "first"})]
    )
    rate_service, rate_request, rate_store = _service(
        routing=_routing(requests_per_minute=1),
        providers={"primary": rate_provider},
    )
    assert (await rate_service.invoke(rate_request)).status == "succeeded"
    second_rate_request = rate_request.model_copy(
        update={"object_id": "object-rate-2", "idempotency_key": "rate-2"}
    )

    rate_result = await rate_service.invoke(second_rate_request)

    assert rate_result.status == "failed"
    assert rate_result.failure is not None
    assert rate_result.failure.code == "AI_RATE_LIMIT_EXCEEDED"
    assert rate_store.terminal_result(second_rate_request) == rate_result
    assert rate_provider.call_count == 1


async def test_provider_retry_is_bounded_by_the_published_profile() -> None:
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.timeout(),
            ProviderScenario.success(payload={"answer": "recovered"}),
        ]
    )
    service, request, store = _service(
        routing=_routing(max_provider_retries=1), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "succeeded"
    assert provider.call_count == 2
    assert store.attempt_count(request) == 2


async def test_platform_enforces_real_timeout_and_persists_typed_failure() -> None:
    provider = _NeverReturningProvider()
    service, request, store = _service(
        routing=_routing(timeout_seconds=1), providers={"primary": provider}
    )

    result = await asyncio.wait_for(service.invoke(request), timeout=2)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is AIErrorClassification.TIMEOUT
    assert store.terminal_result(request) == result
    assert provider.calls == 1


async def test_unknown_provider_exception_is_safely_classified_and_persisted() -> None:
    provider = _UnexpectedFailureProvider()
    service, request, store = _service(
        routing=_routing(), providers={"primary": provider}
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.code == "AI_PROVIDER_UNEXPECTED_FAILURE"
    assert result.failure.classification is AIErrorClassification.PROVIDER_UNAVAILABLE
    assert "secret" not in result.failure.message
    assert store.terminal_result(request) == result


async def test_route_purpose_and_data_classification_are_admission_controls() -> None:
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    service, request, store = _service(
        routing=_routing(
            allowed_data_classifications=(DataClassification.INTERNAL,),
        ),
        providers={"primary": provider},
    )
    restricted = request.model_copy(
        update={
            "idempotency_key": "restricted-1",
            "data_classification": DataClassification.RESTRICTED,
        }
    )

    classification_result = await service.invoke(restricted)

    assert classification_result.status == "failed"
    assert classification_result.failure is not None
    assert (
        classification_result.failure.classification
        is AIErrorClassification.DATA_CLASSIFICATION_NOT_ALLOWED
    )
    assert store.terminal_result(restricted) == classification_result
    assert store.reservation_count(restricted) == 0
    assert provider.call_count == 0

    wrong_purpose_route = _routing(business_purpose="different.purpose")
    wrong_service, wrong_request, _ = _service(
        routing=wrong_purpose_route,
        providers={"primary": provider},
    )
    purpose_result = await wrong_service.invoke(wrong_request)
    assert purpose_result.status == "failed"
    assert purpose_result.failure is not None
    assert (
        purpose_result.failure.classification
        is AIErrorClassification.PROMPT_CONTRACT_MISMATCH
    )
    assert provider.call_count == 0


def test_fallback_profile_rejects_unsafe_failure_classes() -> None:
    with pytest.raises(ValidationError, match="unsafe failure classes"):
        _routing(
            fallback_error_allowlist=(AIErrorClassification.CANCELLED,),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"rate_limit_scopes": ()},
        {
            "rate_limit_scopes": (
                BudgetScope.ORGANIZATION,
                BudgetScope.ORGANIZATION,
            )
        },
        {
            "budget_limit_minor_units": 5,
            "budget_reservation_minor_units": 6,
        },
        {
            "budget_limit_minor_units": 0,
            "budget_reservation_minor_units": 0,
        },
    ],
)
def test_routing_profile_rejects_bypassable_quota_policy(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _routing(**overrides)


async def test_open_circuit_is_a_persisted_failure_without_an_external_call() -> None:
    provider = DeterministicAIProvider(scenarios=[ProviderScenario.unavailable(503)])
    service, first_request, store = _service(
        routing=_routing(circuit_failure_threshold=1),
        providers={"primary": provider},
    )
    assert (await service.invoke(first_request)).status == "failed"
    second_request = first_request.model_copy(
        update={"object_id": "object-circuit-2", "idempotency_key": "circuit-2"}
    )

    result = await service.invoke(second_request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is AIErrorClassification.CIRCUIT_OPEN
    assert store.terminal_result(second_request) == result
    assert provider.call_count == 1


@pytest.mark.parametrize(
    ("request_update", "expected_classification"),
    [
        (
            {"input_schema_version": "unpublished.input.v2"},
            AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
        ),
        (
            {"business_purpose": "different.purpose"},
            AIErrorClassification.PROMPT_CONTRACT_MISMATCH,
        ),
        (
            {"input_payload": {"unexpected": "value"}},
            AIErrorClassification.INPUT_SCHEMA_INVALID,
        ),
        (
            {"prompt_variables": {"text": "hello", "extra": "value"}},
            AIErrorClassification.INPUT_SCHEMA_INVALID,
        ),
    ],
)
async def test_preflight_contract_failures_are_persisted(
    request_update: dict[str, object],
    expected_classification: AIErrorClassification,
) -> None:
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    service, request, store = _service(
        routing=_routing(), providers={"primary": provider}
    )
    changed = request.model_copy(update=request_update)

    result = await service.invoke(changed)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is expected_classification
    assert store.terminal_result(changed) == result
    assert store.reservation_count(changed) == 0
    assert provider.call_count == 0


async def test_local_admission_failure_does_not_consume_rate_or_budget() -> None:
    provider = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "valid"})]
    )
    service, request, store = _service(
        routing=_routing(
            requests_per_minute=1,
            budget_limit_minor_units=10,
            budget_reservation_minor_units=10,
        ),
        providers={"primary": provider},
    )
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
    assert store.terminal_result(invalid) == invalid_result
    assert store.reservation_count(invalid) == 0
    assert valid_result.status == "succeeded"
    assert store.reservation_count(request) == 1
    assert provider.call_count == 1


async def test_fallback_is_policy_owned_and_formal_scoring_requires_calibration() -> (
    None
):
    primary = DeterministicAIProvider(scenarios=[ProviderScenario.unavailable(503)])
    fallback = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "fallback"})]
    )
    route = _routing(
        fallback_allowed=True,
        fallback=ModelRoute(
            provider="fallback",
            model="model-b",
            calibrated_for_formal_scoring=False,
        ),
    )
    service, request, store = _service(
        routing=route,
        providers={"primary": primary, "fallback": fallback},
    )

    draft_result = await service.invoke(request)

    assert draft_result.status == "succeeded"
    assert draft_result.provider == "fallback"
    assert draft_result.degradations == ("fallback_route",)

    formal_request = request.model_copy(
        update={"idempotency_key": "formal-1", "formal_scoring": True}
    )
    formal_result = await service.invoke(formal_request)
    assert formal_result.status == "failed"
    assert formal_result.failure is not None
    assert formal_result.failure.code == "AI_FALLBACK_NOT_CALIBRATED"
    assert store.reservation_count(formal_request) == 0
    assert primary.call_count == 1
    assert fallback.call_count == 1


async def test_caller_cannot_enable_fallback_for_a_policy_that_forbids_it() -> None:
    primary = DeterministicAIProvider(scenarios=[ProviderScenario.unavailable(503)])
    fallback = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    route = _routing(
        fallback_allowed=False,
        fallback=ModelRoute(
            provider="fallback",
            model="model-b",
            calibrated_for_formal_scoring=True,
        ),
    )
    service, request, _ = _service(
        routing=route,
        providers={"primary": primary, "fallback": fallback},
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert fallback.call_count == 0


async def test_fallback_only_runs_for_profile_allowlisted_failure_classes() -> None:
    primary = DeterministicAIProvider(scenarios=[ProviderScenario.cancelled()])
    fallback = DeterministicAIProvider(
        scenarios=[ProviderScenario.success(payload={"answer": "must-not-run"})]
    )
    route = _routing(
        fallback_allowed=True,
        fallback_error_allowlist=(AIErrorClassification.PROVIDER_UNAVAILABLE,),
        fallback=ModelRoute(
            provider="fallback",
            model="model-b",
            calibrated_for_formal_scoring=True,
        ),
    )
    service, request, _ = _service(
        routing=route,
        providers={"primary": primary, "fallback": fallback},
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is AIErrorClassification.CANCELLED
    assert fallback.call_count == 0


async def test_provider_usage_currency_must_match_routing_budget_currency() -> None:
    service, request, store = _service(
        routing=_routing(currency="CNY"),
        providers={"primary": _CurrencyMismatchProvider()},
    )

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.code == "AI_PROVIDER_USAGE_CURRENCY_MISMATCH"
    assert result.usage.cost_minor_units == 0
    assert store.usage_entry_count(request) == 0


async def test_in_memory_limits_are_isolated_by_routing_revision() -> None:
    store = InMemoryAIInvocationStore()
    first_route = _routing(
        requests_per_minute=1,
        budget_limit_minor_units=10,
        budget_reservation_minor_units=10,
    )
    second_route = _routing(
        revision_id="route-rev-2",
        revision_no=2,
        requests_per_minute=1,
        budget_limit_minor_units=10,
        budget_reservation_minor_units=10,
    )
    first_service, first_request, _ = _service(
        routing=first_route,
        providers={
            "primary": DeterministicAIProvider(
                scenarios=[ProviderScenario.success(payload={"answer": "first"})]
            )
        },
        store=store,
    )
    second_service, second_request, _ = _service(
        routing=second_route,
        providers={
            "primary": DeterministicAIProvider(
                scenarios=[ProviderScenario.success(payload={"answer": "second"})]
            )
        },
        store=store,
    )
    second_request = second_request.model_copy(update={"idempotency_key": "request-2"})

    first_result = await first_service.invoke(first_request)
    second_result = await second_service.invoke(second_request)

    assert first_result.status == "succeeded"
    assert second_result.status == "succeeded"


async def test_in_memory_attempt_replay_rejects_route_contract_drift() -> None:
    store = InMemoryAIInvocationStore()
    prompt = _prompt()
    routing = _routing()
    request = _request(
        prompt=prompt,
        routing=routing,
        compiler=StrictPromptCompiler(),
    )
    preparation = await store.prepare(
        request=request,
        request_fingerprint="fingerprint-1",
        routing=routing,
    )
    await store.begin_attempt(
        preparation=preparation,
        attempt_no=1,
        provider="primary",
        model="model-a",
        route_kind="primary",
    )

    with pytest.raises(AIPlatformError, match="AI Provider attempt") as exc_info:
        await store.begin_attempt(
            preparation=preparation,
            attempt_no=1,
            provider="other",
            model="model-b",
            route_kind="fallback",
        )

    assert exc_info.value.code == "AI_ATTEMPT_CONTRACT_CONFLICT"


async def test_in_memory_rejects_response_from_expired_owner_token() -> None:
    clock = _MutableClock(datetime(2026, 7, 17, tzinfo=UTC))
    store = InMemoryAIInvocationStore(clock=clock, ownership_ttl_seconds=1)
    prompt = _prompt()
    routing = _routing()
    request = _request(
        prompt=prompt,
        routing=routing,
        compiler=StrictPromptCompiler(),
    )
    preparation = await store.prepare(
        request=request,
        request_fingerprint="fingerprint-1",
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

    with pytest.raises(AIPlatformError) as exc_info:
        await store.record_attempt_response(
            preparation=preparation,
            attempt=late_attempt,
            response=ProviderResponse(
                payload={"answer": "late"},
                provider_request_id="late-response",
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

    assert exc_info.value.code == "AI_INVOCATION_OWNERSHIP_LOST"
    assert store.usage_entry_count(request) == 1


async def test_in_memory_complete_requires_unexpired_owner_lease() -> None:
    clock = _MutableClock(datetime(2026, 7, 17, tzinfo=UTC))
    store = InMemoryAIInvocationStore(clock=clock, ownership_ttl_seconds=1)
    prompt = _prompt()
    routing = _routing()
    request = _request(
        prompt=prompt,
        routing=routing,
        compiler=StrictPromptCompiler(),
    )

    live_preparation = await store.prepare(
        request=request,
        request_fingerprint="live-fingerprint",
        routing=routing,
    )
    live_result = AIInvocationResult(
        invocation_id=live_preparation.invocation_id,
        workload_kind=request.workload_kind,
        status=AIInvocationStatus.SUCCEEDED,
        validated_output={"answer": "on-time"},
        prompt_template_id=request.prompt_template_id,
        prompt_revision_id=request.prompt_revision_id,
        prompt_contract_hash=request.prompt_contract_hash,
        model_routing_profile_id=request.model_routing_profile_id,
        model_routing_revision_id=request.model_routing_revision_id,
        created_at=live_preparation.created_at,
    )
    await store.complete(
        request=request,
        preparation=live_preparation,
        result=live_result,
    )
    replay = await store.prepare(
        request=request,
        request_fingerprint="live-fingerprint",
        routing=routing,
    )
    assert replay.replay_result == live_result

    expired_request = request.model_copy(
        update={"idempotency_key": "expired-completion"}
    )
    expired_preparation = await store.prepare(
        request=expired_request,
        request_fingerprint="expired-fingerprint",
        routing=routing,
    )
    expired_result = live_result.model_copy(
        update={
            "invocation_id": expired_preparation.invocation_id,
            "validated_output": {"answer": "late"},
            "created_at": expired_preparation.created_at,
        }
    )
    clock.advance(seconds=11)

    with pytest.raises(AIPlatformError) as exc_info:
        await store.complete(
            request=expired_request,
            preparation=expired_preparation,
            result=expired_result,
        )

    assert exc_info.value.code == "AI_INVOCATION_OWNERSHIP_LOST"


def test_schema_registration_is_idempotent_but_version_drift_fails_closed() -> None:
    registry = OutputSchemaRegistry()

    registry.register_input("input.v1", _Input)
    registry.register_input("input.v1", _Input)
    registry.register_output("output.v1", _Output)
    registry.register_output("output.v1", _Output)

    with pytest.raises(ValueError, match="input.v1"):
        registry.register_input("input.v1", _Output)
    with pytest.raises(ValueError, match="output.v1"):
        registry.register_output("output.v1", _Input)
