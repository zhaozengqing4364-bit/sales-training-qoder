"""Provider-neutral invocation contracts."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ai_platform.contracts import AIUsageSummary


class ProviderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    idempotency_key: str
    invocation_id: str
    attempt_no: int = Field(ge=1)
    prompt: str
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    output_schema_version: str
    trace_id: str


class ProviderResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    payload: dict[str, Any]
    provider_request_id: str
    usage: AIUsageSummary
    latency_ms: int = Field(ge=0)
    finish_reason: str
    partial: bool = False
    evidence_refs: tuple[str, ...] = ()


class ASRProviderRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    idempotency_key: str
    invocation_id: str
    attempt_no: int = Field(ge=1)
    audio_artifact_ref: str
    asr_profile_revision_id: str
    provider: str
    model: str
    timeout_seconds: int
    output_schema_version: str
    trace_id: str


class AIProvider(Protocol):
    async def invoke(
        self, request: ProviderRequest | ASRProviderRequest
    ) -> ProviderResponse:
        """Invoke with provider-side idempotency keyed by request.idempotency_key."""

    async def lookup(self, idempotency_key: str) -> ProviderResponse | None:
        """Return a prior provider result for crash-window reconciliation."""
