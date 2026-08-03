"""Ports keeping Coach domain code independent from foreign ORM models."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ai_coach.contracts import CoachContextSnapshot, CoachProfileSnapshot


@runtime_checkable
class CoachContextBuilderPort(Protocol):
    async def build(
        self,
        *,
        organization_id: str,
        learner_id: str,
        enrollment_id: str,
        path_revision_id: str,
        activity_id: str,
        profile_revision_id: str,
        profile: CoachProfileSnapshot,
    ) -> CoachContextSnapshot: ...


class CoachActivityOutcomePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    attempt_id: str = Field(min_length=1, max_length=160)
    lifecycle_result: Literal["completed", "cancelled"]
    assessment_result: Literal["passed", "not_applicable"]
    result_type: Literal["coach_outcome", "coach_session"]
    result_id: str = Field(min_length=1, max_length=160)
    score: float | None = Field(default=None, ge=0, le=100)
    max_score: float | None = Field(default=None, gt=0)
    passed: bool | None = None
    competency_evidence_refs: tuple[dict[str, str], ...] = ()
    source_refs: tuple[dict[str, str], ...] = ()
    lineage: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_flags: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    next_action: dict[str, Any] | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)
    trace_id: str | None = Field(default=None, max_length=160)


@runtime_checkable
class CoachActivityOutcomeWriterPort(Protocol):
    async def record(self, payload: CoachActivityOutcomePayload) -> str: ...


__all__ = [
    "CoachActivityOutcomePayload",
    "CoachActivityOutcomeWriterPort",
    "CoachContextBuilderPort",
]
