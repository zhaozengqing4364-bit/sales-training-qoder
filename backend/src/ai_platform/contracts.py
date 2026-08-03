"""Stable public contracts for governed AI invocation.

The request/result objects deliberately carry governance lineage.  Business callers
must not infer a prompt revision or model route from mutable configuration at run
time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class BudgetScope(StrEnum):
    ORGANIZATION = "organization"
    ACTOR = "actor"
    USE_CASE = "use_case"


class AIWorkloadKind(StrEnum):
    LLM = "llm"
    ASR = "asr"


class AIInvocationStatus(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class AIErrorClassification(StrEnum):
    PROMPT_REVISION_NOT_PUBLISHED = "prompt_revision_not_published"
    PROMPT_CONTRACT_MISMATCH = "prompt_contract_mismatch"
    MODEL_ROUTE_NOT_PUBLISHED = "model_route_not_published"
    INPUT_SCHEMA_INVALID = "input_schema_invalid"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    EMPTY_RESPONSE = "empty_response"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    BUDGET_EXCEEDED = "budget_exceeded"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    CANCELLED = "cancelled"
    POLICY_NOT_CALIBRATED = "policy_not_calibrated"
    DATA_CLASSIFICATION_NOT_ALLOWED = "data_classification_not_allowed"
    UNKNOWN = "unknown"


class AIUsageSummary(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_minor_units: int = Field(default=0, ge=0)
    currency: str = "CNY"

    @model_validator(mode="after")
    def validate_total(self) -> AIUsageSummary:
        expected = self.input_tokens + self.output_tokens
        if self.total_tokens != expected:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class AIInvocationFailure(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    code: str
    classification: AIErrorClassification
    retryable: bool
    message: str


class StructuredValidationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    input_valid: bool = False
    output_valid: bool = False
    output_validation_attempts: int = Field(default=0, ge=0)
    output_schema_version: str


class GovernedAIRequest(BaseModel):
    """A fully pinned invocation request.

    Both prompt and routing revision identifiers are mandatory.  There is no
    "latest active" fallback in this contract.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    business_purpose: str = Field(min_length=1)
    task_id: str | None = None
    workload_kind: AIWorkloadKind = AIWorkloadKind.LLM
    organization_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    prompt_template_id: str | None = None
    prompt_revision_id: str | None = None
    prompt_contract_hash: str | None = None
    asr_profile_revision_id: str | None = None
    input_artifact_ref: str | None = None
    model_routing_profile_id: str = Field(min_length=1)
    model_routing_revision_id: str = Field(min_length=1)
    input_schema_version: str = Field(min_length=1)
    output_schema_version: str = Field(min_length=1)
    input_payload: dict[str, Any]
    prompt_variables: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=255)
    data_classification: DataClassification
    trace_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    runtime_consumer: str = Field(min_length=1)
    timeout_policy_ref: str = Field(min_length=1)
    retry_policy_ref: str = Field(min_length=1)
    budget_scope: BudgetScope
    formal_scoring: bool = False
    allow_fallback: bool = True

    @model_validator(mode="after")
    def validate_workload_lineage(self) -> GovernedAIRequest:
        prompt_lineage = (
            self.prompt_template_id,
            self.prompt_revision_id,
            self.prompt_contract_hash,
        )
        if self.workload_kind is AIWorkloadKind.LLM:
            if not all(prompt_lineage):
                raise ValueError("LLM workload requires exact prompt lineage")
            if (
                self.asr_profile_revision_id is not None
                or self.input_artifact_ref is not None
            ):
                raise ValueError("LLM workload cannot carry ASR input lineage")
        else:
            if any(value is not None for value in prompt_lineage):
                raise ValueError("ASR workload cannot carry prompt lineage")
            if self.asr_profile_revision_id != self.model_routing_revision_id:
                raise ValueError("ASR profile revision must match routing revision")
            if (
                self.input_artifact_ref is None
                or not self.input_artifact_ref.startswith("artifact://")
            ):
                raise ValueError(
                    "ASR workload requires a controlled audio artifact ref"
                )
            if self.prompt_variables:
                raise ValueError("ASR workload cannot carry prompt variables")
            payload_artifact_ref = self.input_payload.get("audio_artifact_ref")
            if (
                payload_artifact_ref is not None
                and payload_artifact_ref != self.input_artifact_ref
            ):
                raise ValueError(
                    "ASR input payload artifact must match governed artifact lineage"
                )
        return self


class AIInvocationResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    invocation_id: str
    workload_kind: AIWorkloadKind = AIWorkloadKind.LLM
    status: AIInvocationStatus
    validated_output: dict[str, Any] | None = None
    failure: AIInvocationFailure | None = None
    prompt_template_id: str | None = None
    prompt_revision_id: str | None = None
    prompt_contract_hash: str | None = None
    asr_profile_revision_id: str | None = None
    model_routing_profile_id: str
    model_routing_revision_id: str
    provider: str | None = None
    model: str | None = None
    usage: AIUsageSummary = Field(default_factory=AIUsageSummary)
    provider_request_id: str | None = None
    finish_reason: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    evidence_refs: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    validation: StructuredValidationSummary | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> AIInvocationResult:
        if self.status in {AIInvocationStatus.SUCCEEDED, AIInvocationStatus.PARTIAL}:
            if self.validated_output is None:
                raise ValueError("successful/partial result requires validated_output")
        if self.status == AIInvocationStatus.FAILED and self.failure is None:
            raise ValueError("failed result requires failure")
        return self


@runtime_checkable
class AIInvocationPort(Protocol):
    async def invoke(self, request: GovernedAIRequest) -> AIInvocationResult:
        """Execute or replay one governed logical invocation."""
