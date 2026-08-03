"""Stable ports used by learning runtimes without importing foreign persistence."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ActivityOutcomePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    attempt_id: str = Field(min_length=1, max_length=160)
    lifecycle_result: Literal["completed", "failed", "invalidated", "cancelled"]
    assessment_result: Literal[
        "passed", "not_passed", "not_applicable", "needs_review"
    ] | None
    result_type: str
    result_id: str
    score: float | None
    max_score: float | None
    passed: bool | None
    competency_evidence_refs: tuple[dict[str, str], ...] = ()
    source_refs: tuple[dict[str, str], ...] = ()
    lineage: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_flags: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    next_action: dict[str, Any] | None = None
    idempotency_key: str
    trace_id: str | None = None


@runtime_checkable
class ActivityOutcomeWriterPort(Protocol):
    async def record(self, payload: ActivityOutcomePayload) -> str: ...


__all__ = ["ActivityOutcomePayload", "ActivityOutcomeWriterPort"]
