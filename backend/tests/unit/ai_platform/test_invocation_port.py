"""Public contract tests for the governed AI invocation port."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ai_platform import (
    BudgetScope,
    DataClassification,
    DeterministicAIProvider,
    GovernedAIInvocationService,
    GovernedAIRequest,
    InMemoryAIInvocationStore,
    OutputSchemaRegistry,
    PromptCompilationService,
    PromptPreviewRequest,
    ProviderScenario,
    PublishedModelRoutingProfileSnapshot,
    PublishedPromptRevisionSnapshot,
    StaticPublishedModelRoutingProfileResolver,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)


class _CoachInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: str


class _CoachOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    answer: str


async def test_invoke_resolves_exact_published_lineage_and_returns_validated_output() -> (
    None
):
    prompt_revision = PublishedPromptRevisionSnapshot(
        template_id="coach.reply",
        business_purpose="coach.reply",
        revision_id="prompt-rev-7",
        revision_no=7,
        status="published",
        template="Question: {{ question }}",
        variables=("question",),
        input_schema_version="coach.input.v1",
        output_schema_version="coach.output.v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="coach.reply",
            business_purpose="coach.reply",
            revision_id="prompt-rev-7",
            revision_no=7,
            template="Question: {{ question }}",
            variables=("question",),
            input_schema_version="coach.input.v1",
            output_schema_version="coach.output.v1",
        ),
    )
    routing_profile = PublishedModelRoutingProfileSnapshot(
        profile_id="coach.default",
        business_purpose="coach.reply",
        revision_id="route-rev-3",
        revision_no=3,
        status="published",
        provider="deterministic",
        model="coach-model-v2",
        temperature=0,
        max_output_tokens=256,
        timeout_seconds=5,
        timeout_policy_ref="timeout.v1",
        max_provider_retries=0,
        max_schema_retries=1,
        retry_policy_ref="retry.v1",
        requests_per_minute=60,
        rate_limit_scopes=(BudgetScope.ORGANIZATION,),
        budget_scope=BudgetScope.ORGANIZATION,
        budget_limit_minor_units=100,
        budget_reservation_minor_units=10,
        budget_window_seconds=3600,
        currency="CNY",
        circuit_failure_threshold=3,
        circuit_recovery_seconds=30,
        allowed_data_classifications=(DataClassification.INTERNAL,),
    )
    compiler = StrictPromptCompiler()
    prompt_resolver = StaticPublishedPromptRevisionResolver([prompt_revision])
    compiled = await PromptCompilationService(
        resolver=prompt_resolver,
        compiler=compiler,
    ).preview(
        PromptPreviewRequest(
            template_id=prompt_revision.template_id,
            revision_id=prompt_revision.revision_id,
            business_purpose=prompt_revision.business_purpose,
            input_schema_version=prompt_revision.input_schema_version,
            output_schema_version=prompt_revision.output_schema_version,
            variables={"question": "如何处理客户的价格异议？"},
            runtime_consumer="unit-test",
            model_routing_revision_id=routing_profile.revision_id,
        )
    )
    schemas = OutputSchemaRegistry()
    schemas.register_input("coach.input.v1", _CoachInput)
    schemas.register_output("coach.output.v1", _CoachOutput)
    provider = DeterministicAIProvider(
        scenarios=[
            ProviderScenario.success(
                payload={"answer": "先确认异议背后的预算约束，再讨论价值。"},
                input_tokens=17,
                output_tokens=12,
                cost_minor_units=3,
            )
        ]
    )
    service = GovernedAIInvocationService(
        prompt_resolver=prompt_resolver,
        routing_resolver=StaticPublishedModelRoutingProfileResolver([routing_profile]),
        compiler=compiler,
        schemas=schemas,
        providers={"deterministic": provider},
        store=InMemoryAIInvocationStore(),
    )

    result = await service.invoke(
        GovernedAIRequest(
            business_purpose="coach.reply",
            organization_id="org-1",
            actor_id="user-9",
            object_type="training_session",
            object_id="session-11",
            prompt_template_id=prompt_revision.template_id,
            prompt_revision_id=prompt_revision.revision_id,
            prompt_contract_hash=compiled.contract_hash,
            model_routing_profile_id=routing_profile.profile_id,
            model_routing_revision_id=routing_profile.revision_id,
            input_schema_version=prompt_revision.input_schema_version,
            output_schema_version=prompt_revision.output_schema_version,
            input_payload={"question": "如何处理客户的价格异议？"},
            prompt_variables={"question": "如何处理客户的价格异议？"},
            idempotency_key="coach-reply-session-11-turn-2",
            data_classification=DataClassification.INTERNAL,
            trace_id="trace-1",
            correlation_id="corr-1",
            causation_id="turn-2",
            runtime_consumer="unit-test",
            timeout_policy_ref=routing_profile.timeout_policy_ref,
            retry_policy_ref=routing_profile.retry_policy_ref,
            budget_scope=BudgetScope.ORGANIZATION,
        )
    )

    assert result.status == "succeeded"
    assert result.validated_output == {
        "answer": "先确认异议背后的预算约束，再讨论价值。"
    }
    assert result.prompt_revision_id == "prompt-rev-7"
    assert result.model_routing_revision_id == "route-rev-3"
    assert result.provider == "deterministic"
    assert result.model == "coach-model-v2"
    assert result.usage.total_tokens == 29
    assert result.usage.cost_minor_units == 3
    assert provider.call_count == 1


def test_compiler_rejects_variables_outside_the_published_contract() -> None:
    revision = PublishedPromptRevisionSnapshot(
        template_id="coach.reply",
        business_purpose="coach.reply",
        revision_id="prompt-rev-1",
        revision_no=1,
        status="published",
        template="Question: {{ question }}",
        variables=("question",),
        input_schema_version="coach.input.v1",
        output_schema_version="coach.output.v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="coach.reply",
            business_purpose="coach.reply",
            revision_id="prompt-rev-1",
            revision_no=1,
            template="Question: {{ question }}",
            variables=("question",),
            input_schema_version="coach.input.v1",
            output_schema_version="coach.output.v1",
        ),
    )

    try:
        StrictPromptCompiler().compile(
            revision=revision,
            variables={"question": "Q", "unpublished_context": "secret"},
            runtime_consumer="unit-test",
            model_routing_revision_id="route-rev-1",
        )
    except Exception as exc:  # public error shape is asserted without internals
        assert getattr(exc, "code", None) == "AI_PROMPT_VARIABLES_INVALID"
    else:
        raise AssertionError("extra variables must fail closed")


def test_prompt_revision_integrity_rejects_declared_variable_or_content_tampering() -> (
    None
):
    with pytest.raises(ValidationError, match="declared prompt variables"):
        PublishedPromptRevisionSnapshot(
            template_id="coach.reply",
            business_purpose="coach.reply",
            revision_id="prompt-rev-bad-vars",
            revision_no=2,
            status="published",
            template="Question: {{ question }}",
            variables=("different",),
            input_schema_version="coach.input.v1",
            output_schema_version="coach.output.v1",
            content_hash=compute_prompt_revision_content_hash(
                template_id="coach.reply",
                business_purpose="coach.reply",
                revision_id="prompt-rev-bad-vars",
                revision_no=2,
                template="Question: {{ question }}",
                variables=("different",),
                input_schema_version="coach.input.v1",
                output_schema_version="coach.output.v1",
            ),
        )

    valid = PublishedPromptRevisionSnapshot(
        template_id="coach.reply",
        business_purpose="coach.reply",
        revision_id="prompt-rev-valid",
        revision_no=3,
        status="published",
        template="Question: {{ question }}",
        variables=("question",),
        input_schema_version="coach.input.v1",
        output_schema_version="coach.output.v1",
        content_hash=compute_prompt_revision_content_hash(
            template_id="coach.reply",
            business_purpose="coach.reply",
            revision_id="prompt-rev-valid",
            revision_no=3,
            template="Question: {{ question }}",
            variables=("question",),
            input_schema_version="coach.input.v1",
            output_schema_version="coach.output.v1",
        ),
    )
    tampered = PublishedPromptRevisionSnapshot.model_construct(
        **{**valid.model_dump(), "template": "Changed: {{ question }}"}
    )
    with pytest.raises(Exception) as exc_info:
        StrictPromptCompiler().compile(
            revision=tampered,
            variables={"question": "Q"},
            runtime_consumer="unit-test",
            model_routing_revision_id="route-rev-1",
        )
    assert (
        getattr(exc_info.value, "code", None) == "AI_PROMPT_REVISION_INTEGRITY_FAILED"
    )
