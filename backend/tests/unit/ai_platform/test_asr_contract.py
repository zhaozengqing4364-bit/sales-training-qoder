"""ASR workloads use the same governed invocation, quota, and audit path."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ai_platform import (
    AIErrorClassification,
    AIWorkloadKind,
    ASRScenario,
    BudgetScope,
    DataClassification,
    DeterministicASRProvider,
    GovernedAIInvocationService,
    GovernedAIRequest,
    InMemoryAIInvocationStore,
    OutputSchemaRegistry,
    PublishedModelRoutingProfileSnapshot,
    StaticPublishedModelRoutingProfileResolver,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
)


class _ASRInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    audio_artifact_ref: str
    language: str


class _ASROutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    transcript: str
    confidence: float


def _route(**overrides: object) -> PublishedModelRoutingProfileSnapshot:
    values: dict[str, object] = {
        "profile_id": "asr.default",
        "business_purpose": "audio.transcribe",
        "revision_id": "asr-route-rev-2",
        "revision_no": 2,
        "status": "published",
        "provider": "deterministic_asr",
        "model": "asr-model-v2",
        "temperature": 0.0,
        "max_output_tokens": 1,
        "timeout_seconds": 5,
        "timeout_policy_ref": "asr-timeout.v1",
        "max_provider_retries": 0,
        "max_schema_retries": 1,
        "retry_policy_ref": "asr-retry.v1",
        "requests_per_minute": 30,
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
        "fallback_error_allowlist": (),
        "calibrated_for_formal_scoring": False,
        "allowed_data_classifications": (DataClassification.CONFIDENTIAL,),
    }
    values.update(overrides)
    return PublishedModelRoutingProfileSnapshot.model_validate(values)


def _request(route: PublishedModelRoutingProfileSnapshot) -> GovernedAIRequest:
    artifact_ref = "artifact://audio/org-1/session-1/recording-1"
    return GovernedAIRequest(
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


def _service(
    provider: DeterministicASRProvider,
) -> tuple[GovernedAIInvocationService, GovernedAIRequest, InMemoryAIInvocationStore]:
    route = _route()
    schemas = OutputSchemaRegistry()
    schemas.register_input("asr.input.v1", _ASRInput)
    schemas.register_output("asr.output.v1", _ASROutput)
    store = InMemoryAIInvocationStore()
    return (
        GovernedAIInvocationService(
            prompt_resolver=StaticPublishedPromptRevisionResolver([]),
            routing_resolver=StaticPublishedModelRoutingProfileResolver([route]),
            compiler=StrictPromptCompiler(),
            schemas=schemas,
            providers={"deterministic_asr": provider},
            store=store,
        ),
        _request(route),
        store,
    )


async def test_asr_uses_artifact_lineage_and_effect_once_governance() -> None:
    provider = DeterministicASRProvider(
        scenarios=[
            ASRScenario.success(
                transcript="客户希望下周再沟通。",
                confidence=0.91,
                cost_minor_units=4,
            )
        ]
    )
    service, request, store = _service(provider)

    result = await service.invoke(request)
    replay = await service.invoke(request)

    assert result.status == "succeeded"
    assert result.workload_kind is AIWorkloadKind.ASR
    assert result.prompt_revision_id is None
    assert result.asr_profile_revision_id == "asr-route-rev-2"
    assert result.validated_output == {
        "transcript": "客户希望下周再沟通。",
        "confidence": 0.91,
    }
    assert result.usage.cost_minor_units == 4
    assert replay == result
    assert provider.call_count == 1
    assert provider.requests[0].audio_artifact_ref == request.input_artifact_ref
    assert store.reservation_count(request) == 1
    assert store.usage_entry_count(request) == 1


async def test_low_confidence_asr_is_explicit_partial_result() -> None:
    provider = DeterministicASRProvider(
        scenarios=[ASRScenario.low_confidence(transcript="不确定的转写")]
    )
    service, request, _ = _service(provider)

    result = await service.invoke(request)

    assert result.status == "partial"
    assert result.validated_output == {
        "transcript": "不确定的转写",
        "confidence": 0.2,
    }


async def test_asr_invalid_schema_retries_with_a_new_durable_attempt() -> None:
    provider = DeterministicASRProvider(
        scenarios=[
            ASRScenario.invalid_schema(),
            ASRScenario.success(transcript="重试成功"),
        ]
    )
    service, request, store = _service(provider)

    result = await service.invoke(request)

    assert result.status == "succeeded"
    assert provider.call_count == 2
    assert store.attempt_count(request) == 2


@pytest.mark.parametrize(
    ("scenario", "classification"),
    [
        (ASRScenario.timeout(), AIErrorClassification.TIMEOUT),
        (ASRScenario.rate_limited(), AIErrorClassification.RATE_LIMITED),
        (ASRScenario.unavailable(), AIErrorClassification.PROVIDER_UNAVAILABLE),
        (ASRScenario.cancelled(), AIErrorClassification.CANCELLED),
    ],
)
async def test_asr_fake_failures_keep_the_shared_error_taxonomy(
    scenario: ASRScenario,
    classification: AIErrorClassification,
) -> None:
    provider = DeterministicASRProvider(scenarios=[scenario])
    service, request, store = _service(provider)

    result = await service.invoke(request)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.classification is classification
    assert store.terminal_result(request) == result


def test_asr_rejects_split_brain_audio_artifact_lineage() -> None:
    route = _route()
    valid = _request(route)

    with pytest.raises(ValidationError, match="must match governed artifact"):
        GovernedAIRequest.model_validate(
            {
                **valid.model_dump(),
                "input_payload": {
                    "audio_artifact_ref": "artifact://audio/different",
                    "language": "zh-CN",
                },
            }
        )
