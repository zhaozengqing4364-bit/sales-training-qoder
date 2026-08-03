"""Governed AI invocation application service."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass

from ai_platform.contracts import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationPort,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    GovernedAIRequest,
    StructuredValidationSummary,
)
from ai_platform.errors import (
    AIPlatformError,
    DataClassificationNotAllowedError,
    EmptyProviderResponseError,
    FallbackNotCalibratedError,
    PrimaryRouteNotCalibratedError,
    PromptContractMismatchError,
    ProviderTimeoutError,
    ProviderUsageCurrencyMismatchError,
)
from ai_platform.prompting import (
    PublishedPromptRevisionResolver,
    PublishedPromptRevisionSnapshot,
    StrictPromptCompiler,
)
from ai_platform.providers import (
    AIProvider,
    ASRProviderRequest,
    ProviderRequest,
    ProviderResponse,
)
from ai_platform.routing import (
    ModelRoute,
    PublishedModelRoutingProfileResolver,
    PublishedModelRoutingProfileSnapshot,
)
from ai_platform.schemas import OutputSchemaRegistry
from ai_platform.store import (
    AIInvocationStore,
    InvocationPreparation,
    PreparationDisposition,
    ProviderAttemptHandle,
)


@dataclass(frozen=True, slots=True)
class _Route:
    provider: str
    model: str
    kind: str
    calibrated_for_formal_scoring: bool


class GovernedAIInvocationService(AIInvocationPort):
    def __init__(
        self,
        *,
        prompt_resolver: PublishedPromptRevisionResolver,
        routing_resolver: PublishedModelRoutingProfileResolver,
        compiler: StrictPromptCompiler,
        schemas: OutputSchemaRegistry,
        providers: dict[str, AIProvider],
        store: AIInvocationStore,
    ) -> None:
        self._prompt_resolver = prompt_resolver
        self._routing_resolver = routing_resolver
        self._compiler = compiler
        self._schemas = schemas
        self._providers = providers
        self._store = store

    async def invoke(self, request: GovernedAIRequest) -> AIInvocationResult:
        fingerprint = self._fingerprint(request)
        try:
            prompt_revision: PublishedPromptRevisionSnapshot | None = None
            if request.workload_kind is AIWorkloadKind.LLM:
                assert request.prompt_template_id is not None
                assert request.prompt_revision_id is not None
                prompt_revision = await self._prompt_resolver.resolve_published(
                    template_id=request.prompt_template_id,
                    revision_id=request.prompt_revision_id,
                )
            routing = await self._routing_resolver.resolve_published(
                profile_id=request.model_routing_profile_id,
                revision_id=request.model_routing_revision_id,
            )
        except AIPlatformError as error:
            return await self._store.reject_before_admission(
                request=request,
                request_fingerprint=fingerprint,
                failure=self._failure(error),
            )

        rendered_prompt: str | None = None
        try:
            self._validate_frozen_contract(request, prompt_revision, routing)
            self._schemas.validate_input(
                request.input_schema_version, request.input_payload
            )
            if request.workload_kind is AIWorkloadKind.LLM:
                assert prompt_revision is not None
                compiled = self._compiler.compile(
                    revision=prompt_revision,
                    variables=request.prompt_variables,
                    runtime_consumer=request.runtime_consumer,
                    model_routing_revision_id=routing.revision_id,
                )
                if compiled.contract_hash != request.prompt_contract_hash:
                    raise PromptContractMismatchError()
                rendered_prompt = compiled.rendered_prompt
            if request.formal_scoring and not routing.calibrated_for_formal_scoring:
                raise PrimaryRouteNotCalibratedError()
            if (
                request.formal_scoring
                and routing.fallback_allowed
                and request.allow_fallback
                and routing.fallback is not None
                and not routing.fallback.calibrated_for_formal_scoring
            ):
                raise FallbackNotCalibratedError()
        except AIPlatformError as error:
            return await self._store.reject_before_admission(
                request=request,
                request_fingerprint=fingerprint,
                failure=self._failure(error),
            )

        preparation = await self._store.prepare(
            request=request,
            request_fingerprint=fingerprint,
            routing=routing,
        )
        if preparation.disposition is PreparationDisposition.REPLAY:
            assert preparation.replay_result is not None
            return preparation.replay_result
        if preparation.disposition is PreparationDisposition.IN_FLIGHT:
            return self._in_flight_result(request, preparation)
        if preparation.rejection is not None:
            usage = await self._store.usage_summary(
                invocation_id=preparation.invocation_id,
                currency=routing.currency,
            )
            result = self._failed_result(
                request=request,
                preparation=preparation,
                failure=preparation.rejection,
                output_attempts=0,
                usage=usage,
            )
            await self._store.complete(
                request=request, preparation=preparation, result=result
            )
            return result

        routes = self._routes(request=request, routing=routing)
        attempt_no = 0
        output_attempts = 0
        last_error: AIPlatformError | None = None
        for route in routes:
            if (
                request.formal_scoring
                and route.kind == "fallback"
                and not route.calibrated_for_formal_scoring
            ):
                last_error = FallbackNotCalibratedError()
                break
            provider_retries = 0
            schema_retries = 0
            while True:
                attempt_no += 1
                attempt: ProviderAttemptHandle | None = None
                try:
                    await self._store.before_provider_attempt(
                        routing_revision_id=routing.revision_id,
                        provider=route.provider,
                        model=route.model,
                        failure_threshold=routing.circuit_failure_threshold,
                        recovery_seconds=routing.circuit_recovery_seconds,
                    )
                    attempt = await self._store.begin_attempt(
                        preparation=preparation,
                        attempt_no=attempt_no,
                        provider=route.provider,
                        model=route.model,
                        route_kind=route.kind,
                    )
                    await self._store.renew_owner(
                        preparation=preparation,
                        lease_seconds=routing.timeout_seconds + 5,
                    )
                    response = await self._invoke_or_reconcile(
                        request=request,
                        routing=routing,
                        route=route,
                        preparation=preparation,
                        attempt=attempt,
                        prompt=rendered_prompt,
                    )
                    if response.usage.currency != routing.currency:
                        raise ProviderUsageCurrencyMismatchError()
                    await self._store.record_attempt_response(
                        preparation=preparation,
                        attempt=attempt,
                        response=response,
                    )
                    await self._store.record_provider_health(
                        routing_revision_id=routing.revision_id,
                        provider=route.provider,
                        model=route.model,
                        success=True,
                        failure_threshold=routing.circuit_failure_threshold,
                        recovery_seconds=routing.circuit_recovery_seconds,
                    )
                    output_attempts += 1
                    if not response.payload:
                        raise EmptyProviderResponseError()
                    validated = self._schemas.validate_output(
                        request.output_schema_version, response.payload
                    )
                    usage = await self._store.usage_summary(
                        invocation_id=preparation.invocation_id,
                        currency=routing.currency,
                    )
                    status = (
                        AIInvocationStatus.PARTIAL
                        if response.partial
                        else AIInvocationStatus.SUCCEEDED
                    )
                    result = AIInvocationResult(
                        invocation_id=preparation.invocation_id,
                        workload_kind=request.workload_kind,
                        status=status,
                        validated_output=validated,
                        prompt_template_id=request.prompt_template_id,
                        prompt_revision_id=request.prompt_revision_id,
                        prompt_contract_hash=request.prompt_contract_hash,
                        asr_profile_revision_id=request.asr_profile_revision_id,
                        model_routing_profile_id=request.model_routing_profile_id,
                        model_routing_revision_id=request.model_routing_revision_id,
                        provider=route.provider,
                        model=route.model,
                        usage=usage,
                        provider_request_id=response.provider_request_id,
                        finish_reason=response.finish_reason,
                        latency_ms=response.latency_ms,
                        evidence_refs=response.evidence_refs,
                        degradations=("fallback_route",)
                        if route.kind == "fallback"
                        else (),
                        validation=StructuredValidationSummary(
                            input_valid=True,
                            output_valid=True,
                            output_validation_attempts=output_attempts,
                            output_schema_version=request.output_schema_version,
                        ),
                        created_at=preparation.created_at,
                    )
                    await self._store.complete(
                        request=request, preparation=preparation, result=result
                    )
                    return result
                except AIPlatformError as error:
                    last_error = error
                    failure = self._failure(error)
                    if attempt is not None:
                        await self._store.record_attempt_failure(
                            preparation=preparation,
                            attempt=attempt,
                            failure=failure,
                        )
                    if error.classification in {
                        AIErrorClassification.TIMEOUT,
                        AIErrorClassification.RATE_LIMITED,
                        AIErrorClassification.PROVIDER_UNAVAILABLE,
                    }:
                        await self._store.record_provider_health(
                            routing_revision_id=routing.revision_id,
                            provider=route.provider,
                            model=route.model,
                            success=False,
                            failure_threshold=routing.circuit_failure_threshold,
                            recovery_seconds=routing.circuit_recovery_seconds,
                        )
                        if provider_retries < routing.max_provider_retries:
                            provider_retries += 1
                            continue
                    elif error.classification in {
                        AIErrorClassification.OUTPUT_SCHEMA_INVALID,
                        AIErrorClassification.EMPTY_RESPONSE,
                    }:
                        if schema_retries < routing.max_schema_retries:
                            schema_retries += 1
                            continue
                    break
            if (
                route.kind == "primary"
                and len(routes) > 1
                and last_error.classification in routing.fallback_error_allowlist
            ):
                continue
            break

        assert last_error is not None
        return await self._persist_failure(
            request=request,
            preparation=preparation,
            error=last_error,
            output_attempts=output_attempts,
            currency=routing.currency,
        )

    async def _invoke_or_reconcile(
        self,
        *,
        request: GovernedAIRequest,
        routing: PublishedModelRoutingProfileSnapshot,
        route: _Route,
        preparation: InvocationPreparation,
        attempt: ProviderAttemptHandle,
        prompt: str | None,
    ) -> ProviderResponse:
        provider = self._providers.get(route.provider)
        if provider is None:
            raise AIPlatformError(
                code="AI_PROVIDER_NOT_REGISTERED",
                classification=AIErrorClassification.PROVIDER_UNAVAILABLE,
                message="模型服务适配器未注册。",
                retryable=False,
            )
        try:
            async with asyncio.timeout(routing.timeout_seconds):
                response = await provider.lookup(attempt.provider_idempotency_key)
                if response is not None:
                    return response
                provider_request: ProviderRequest | ASRProviderRequest
                if request.workload_kind is AIWorkloadKind.ASR:
                    assert request.input_artifact_ref is not None
                    assert request.asr_profile_revision_id is not None
                    provider_request = ASRProviderRequest(
                        idempotency_key=attempt.provider_idempotency_key,
                        invocation_id=preparation.invocation_id,
                        attempt_no=attempt.attempt_no,
                        audio_artifact_ref=request.input_artifact_ref,
                        asr_profile_revision_id=request.asr_profile_revision_id,
                        provider=route.provider,
                        model=route.model,
                        timeout_seconds=routing.timeout_seconds,
                        output_schema_version=request.output_schema_version,
                        trace_id=request.trace_id,
                    )
                else:
                    assert prompt is not None
                    provider_request = ProviderRequest(
                        idempotency_key=attempt.provider_idempotency_key,
                        invocation_id=preparation.invocation_id,
                        attempt_no=attempt.attempt_no,
                        prompt=prompt,
                        provider=route.provider,
                        model=route.model,
                        temperature=routing.temperature,
                        max_output_tokens=routing.max_output_tokens,
                        timeout_seconds=routing.timeout_seconds,
                        output_schema_version=request.output_schema_version,
                        trace_id=request.trace_id,
                    )
                return await provider.invoke(provider_request)
        except TimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except AIPlatformError:
            raise
        except Exception as exc:
            raise AIPlatformError(
                code="AI_PROVIDER_UNEXPECTED_FAILURE",
                classification=AIErrorClassification.PROVIDER_UNAVAILABLE,
                message="模型服务发生未分类故障。",
                retryable=True,
            ) from exc

    @staticmethod
    def _validate_frozen_contract(
        request: GovernedAIRequest,
        prompt_revision: PublishedPromptRevisionSnapshot | None,
        routing: PublishedModelRoutingProfileSnapshot,
    ) -> None:
        if request.workload_kind is AIWorkloadKind.LLM:
            if (
                prompt_revision is None
                or prompt_revision.business_purpose != request.business_purpose
            ):
                raise PromptContractMismatchError()
            if (
                prompt_revision.input_schema_version != request.input_schema_version
                or prompt_revision.output_schema_version
                != request.output_schema_version
            ):
                raise PromptContractMismatchError()
        elif request.asr_profile_revision_id != routing.revision_id:
            raise PromptContractMismatchError()
        if routing.business_purpose != request.business_purpose:
            raise PromptContractMismatchError()
        if request.timeout_policy_ref != routing.timeout_policy_ref:
            raise PromptContractMismatchError()
        if request.retry_policy_ref != routing.retry_policy_ref:
            raise PromptContractMismatchError()
        if request.budget_scope is not routing.budget_scope:
            raise PromptContractMismatchError()
        if request.data_classification not in routing.allowed_data_classifications:
            raise DataClassificationNotAllowedError()

    @staticmethod
    def _routes(
        *, request: GovernedAIRequest, routing: PublishedModelRoutingProfileSnapshot
    ) -> list[_Route]:
        routes = [
            _Route(
                provider=routing.provider,
                model=routing.model,
                kind="primary",
                calibrated_for_formal_scoring=routing.calibrated_for_formal_scoring,
            )
        ]
        fallback: ModelRoute | None = routing.fallback
        if routing.fallback_allowed and request.allow_fallback and fallback is not None:
            routes.append(
                _Route(
                    provider=fallback.provider,
                    model=fallback.model,
                    kind="fallback",
                    calibrated_for_formal_scoring=(
                        fallback.calibrated_for_formal_scoring
                    ),
                )
            )
        return routes

    async def _persist_failure(
        self,
        *,
        request: GovernedAIRequest,
        preparation: InvocationPreparation,
        error: AIPlatformError,
        output_attempts: int,
        currency: str,
    ) -> AIInvocationResult:
        usage = await self._store.usage_summary(
            invocation_id=preparation.invocation_id,
            currency=currency,
        )
        result = self._failed_result(
            request=request,
            preparation=preparation,
            failure=self._failure(error),
            output_attempts=output_attempts,
            usage=usage,
        )
        await self._store.complete(
            request=request, preparation=preparation, result=result
        )
        return result

    @staticmethod
    def _failure(error: AIPlatformError) -> AIInvocationFailure:
        return AIInvocationFailure(
            code=error.code,
            classification=error.classification,
            retryable=error.retryable,
            message=error.safe_message,
        )

    @staticmethod
    def _failed_result(
        *,
        request: GovernedAIRequest,
        preparation: InvocationPreparation,
        failure: AIInvocationFailure,
        output_attempts: int,
        usage: AIUsageSummary,
    ) -> AIInvocationResult:
        return AIInvocationResult(
            invocation_id=preparation.invocation_id,
            workload_kind=request.workload_kind,
            status=AIInvocationStatus.FAILED,
            failure=failure,
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            asr_profile_revision_id=request.asr_profile_revision_id,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            usage=usage,
            validation=StructuredValidationSummary(
                input_valid=(
                    failure.classification
                    is not AIErrorClassification.INPUT_SCHEMA_INVALID
                ),
                output_valid=False,
                output_validation_attempts=output_attempts,
                output_schema_version=request.output_schema_version,
            ),
            created_at=preparation.created_at,
        )

    @staticmethod
    def _in_flight_result(
        request: GovernedAIRequest, preparation: InvocationPreparation
    ) -> AIInvocationResult:
        return AIInvocationResult(
            invocation_id=preparation.invocation_id,
            workload_kind=request.workload_kind,
            status=AIInvocationStatus.RUNNING,
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            asr_profile_revision_id=request.asr_profile_revision_id,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            created_at=preparation.created_at,
        )

    @staticmethod
    def _fingerprint(request: GovernedAIRequest) -> str:
        payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        digest = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return f"sha256:{digest}"
